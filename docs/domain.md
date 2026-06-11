# Domain Model — Lead Triage Demo

> Prepared 2026-06-11 per `docs/standards/DOMAIN-FIRST.md` to retrofit the
> domain-first standard onto this prototype. Every term and rule below is
> derived from the shipped code (`service/src/`, `workflow/lead-triage.json`,
> `docs/spec.md`) and the CEO's stated goals. Nothing is invented.

---

## Ubiquitous Language

| Term | Definition (as used in code, tests, and conversation) |
|---|---|
| **Lead** | An inbound contact submission: `{ email, name?, company?, message, source? }`. The unit of work the system processes. |
| **Idempotency Key** | The identity of one Lead submission. Computed as the `Idempotency-Key` HTTP header if supplied; otherwise `sha256(email + "\n" + message)`. Two requests with the same key are the same lead. |
| **Classification** | The LLM's qualification verdict for a Lead: one of `hot`, `warm`, or `cold`. Determines which Slack channel the structured message is routed to. |
| **Processed Lead** | A Lead that was successfully classified and routed. Persisted in `processed_leads` keyed by its Idempotency Key; acts as the idempotency ledger. |
| **Dead-Letter** | A record of a Lead that could not be processed — either invalid input (`reason="validation"`) or an unexpected failure (`reason="error"`). Persisted in `dead_letter`. Never silently dropped. |
| **Run** | One append-only audit entry recording the outcome of a single processing attempt: `status ∈ {success, duplicate, error}`. Persisted in `runs`. |
| **Tier** | Synonym for Classification in the routing context (used in Slack messages and the LLM prompt). |
| **Sidecar** | The Node/TypeScript/Hono microservice that owns the SQLite store and exposes the idempotency, dead-letter, and run-log API. It is the only novel handwritten code in this system. |

---

## Entities and Value Objects

### Entity: Processed Lead
- **Identity:** `key` (TEXT PRIMARY KEY — the Idempotency Key).
- **Fields:** `key`, `created_at`, `slack_ts` (nullable), `classification`.
- **Lifecycle:** written once by `/idempotency/commit`; `INSERT OR REPLACE` enforces the single-row invariant. Never deleted (intentional — it is a durable idempotency ledger).

### Entity: Dead-Letter Entry
- **Identity:** `id` (AUTOINCREMENT — append-only, no natural key required).
- **Fields:** `id`, `key` (nullable — bad leads may lack a computable key), `reason` (`"validation"` | `"error"`), `payload` (serialised original data or error context), `created_at`.
- **Lifecycle:** append-only. Written by `/deadletter`. Never updated or deleted.

### Entity: Run
- **Identity:** `id` (AUTOINCREMENT).
- **Fields:** `id`, `key` (nullable), `status` (`"success"` | `"duplicate"` | `"error"`), `detail` (nullable, free-text), `created_at`.
- **Lifecycle:** append-only. One row per processing attempt. Written by `/runs`.

### Value Object: Idempotency Key
- A plain string. No object wrapping needed — plain CRUD, no complex invariant on the key itself.
- Computed externally (in the n8n workflow node). The sidecar treats it as an opaque string.

### Value Object: Classification (Tier)
- One of three string values: `"hot"`, `"warm"`, `"cold"`.
- The LLM produces this; the sidecar stores it; the workflow routes on it.
- The sidecar does NOT validate the value — it is accepted as-is (validation belongs to the workflow).

---

## Invariants and Rules

These map 1-to-1 to tests in `service/src/sidecar.test.ts`.

| # | Invariant | Where enforced | Test |
|---|---|---|---|
| I1 | **One Processed Lead per Idempotency Key.** `INSERT OR REPLACE` ensures a second commit for the same key replaces rather than appends. No two rows in `processed_leads` can share a key. | `service/src/app.ts` `/idempotency/commit`; SQLite PRIMARY KEY constraint | "committing the same key twice leaves exactly one row" |
| I2 | **No inbound lead is ever silently dropped.** Every lead ends in exactly one of: a Slack post + ProcessedLead row (`success`), a duplicate acknowledgment (`duplicate`), a Dead-Letter + alert + Run (`validation`), or a Dead-Letter + alert + Run (`error`). | n8n workflow error branches; `/deadletter`; `/runs` | QA sign-off (workflow static analysis) |
| I3 | **The LLM classifies but does not decide routing alone.** The deterministic `tier → Slack channel` mapping is configuration (env vars), not the LLM's choice. | n8n route node; env vars | QA sign-off |
| I4 | **Required fields are enforced at the sidecar boundary.** Requests missing `key` (check/commit), `classification` (commit), `reason` or `payload` (deadletter), or `status` (runs) are rejected with HTTP 400. | `service/src/app.ts` field guards | Missing-field 400 tests (6 tests) |
| I5 | **Malformed JSON is rejected with HTTP 400 and a clear error.** The body `{ error: "Invalid JSON body" }` is returned for any unparseable request body. | `service/src/app.ts` try/catch on `c.req.json()` | Malformed JSON 400 tests (4 tests) |
| I6 | **A Run may have a null key.** Leads that fail before a key is computed (or workflow error conditions) may log a Run without a key; `key=null` is valid. | `service/src/app.ts` `key ?? null` | "POST /runs with no key field persists null key" |

---

## Bounded Contexts

This prototype is small enough to have a single bounded context. There is no term that changes meaning across subsystems.

```
┌─────────────────────────────────────────────────────────┐
│  Lead Triage Context                                     │
│                                                          │
│  Webhook ──► n8n Workflow ──► Sidecar API ──► SQLite     │
│                    │                                     │
│                    └──► LLM (Groq/Gemini)                │
│                    └──► Slack (webhooks)                 │
└─────────────────────────────────────────────────────────┘
```

The n8n workflow owns orchestration logic (key computation, validation, LLM call, routing). The sidecar owns persistent state (idempotency ledger, dead-letter store, run log). These are separate responsibilities; the sidecar has no knowledge of LLM or Slack.

---

## Key Domain Events / Workflow

1. `LeadReceived` — webhook fires with `{ email, name?, company?, message, source? }`.
2. `KeyComputed` — idempotency key assigned.
3. `LeadValidated` / `LeadRejected` — email + message presence check.
4. `DuplicateDetected` — `/idempotency/check` returns `seen:true`.
5. `LeadClassified` — LLM returns `{ tier, summary, reason, suggested_channel }`.
6. `LeadRouted` — Slack message posted to tier channel; `slack_ts` captured.
7. `LeadCommitted` — `/idempotency/commit` writes the Processed Lead record.
8. `RunLogged` — `/runs` records the outcome (`success` / `duplicate` / `error`).
9. `DeadLettered` — `/deadletter` records a failed lead with reason and payload.
