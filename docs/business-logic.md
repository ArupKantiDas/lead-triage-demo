# Business Logic — Lead Triage Demo

> The rules this system enforces and how it behaves, in plain terms. Pairs with
> `docs/spec.md` (the build spec) and `docs/gates/` (Security & QA sign-offs).
> Everything below is read from the shipped code (`service/src/*.ts`,
> `docker-compose.yml`, `workflow/lead-triage.json`) and `docs/spec.md` — nothing
> is invented. *(This demo predates the domain-first/TDD standards — see
> "Open items".)*

## 1. Purpose & context
A proof-of-work demo showing the company can deliver **Claude/LLM-powered workflow
automations** to a professional standard. An inbound **lead** arrives via webhook;
the system **qualifies and summarizes** it with an LLM and **routes** a structured
result to the correct **Slack** channel. Built for Arup to win three open freelance
automation gigs. It is a *demo, not a product*: thin, free to run, and impressive
in a ~90-second walkthrough — with nothing faked. It must visibly prove three
pro-grade properties: **idempotency**, **explicit error handling**, **observability**.

## 2. Key terms
- **Lead** — an inbound contact: `{ email, name?, company?, message, source? }`.
- **Idempotency key** — the identity of a submission: the `Idempotency-Key` header
  if supplied, else `sha256(email + "\n" + message)`.
- **Tier** — the LLM's qualification of a lead: `hot | warm | cold`.
- **Dead-letter** — a record of a lead that could not be processed (validation or
  error), kept instead of dropped.
- **Run** — one append-only log entry of an attempt: `success | duplicate | error`.

## 3. Inputs & outputs
- **Input:** `POST /webhook/lead` (n8n) — body `{ email, name?, company?, message,
  source? }`, optional `Idempotency-Key` header.
- **Outputs:**
  - A structured **Slack message** in the tier's channel (name, company, tier,
    summary, reason, source).
  - An HTTP response: `{status:"ok",tier}` · `{status:"duplicate",key}` ·
    `{status:"rejected",reason}` · `{status:"error",logged:true}`.
  - Persisted **state**: `processed_leads`, `dead_letter`, `runs` (SQLite).

## 4. Business rules
| # | Rule | Source | Where in code | Verified by |
|---|------|--------|---------------|-------------|
| R1 | A given lead is processed **once**; replays (same key) do not re-call the LLM or re-post to Slack. | CEO property: idempotency | `processed_leads.key` PK (`service/src/db.ts`); `/idempotency/check` + `/idempotency/commit` (`service/src/index.ts`); n8n key step | `scripts/replay-lead.sh` |
| R2 | Idempotency key = `Idempotency-Key` header if present, else `sha256(email + "\n" + message)`. | spec | n8n "compute key" node | walkthrough |
| R3 | A lead is **valid** only if `email` is present and email-shaped **and** `message` is non-empty. Invalid → dead-letter (`reason="validation"`) + Slack `#alerts`, **no LLM call**, return `rejected`. | spec | n8n validate node; `/deadletter` | `scripts/send-bad-lead.sh` |
| R4 | The lead's text is **data, never instructions** — wrapped in a delimited block; the model is told to ignore any embedded instructions; returned JSON is validated. | spec + Security gate | n8n LLM node system prompt | `docs/gates/security-review.md` |
| R5 | The LLM returns strict JSON `{ tier: hot\|warm\|cold, summary, suggested_channel, reason }`. Parse failure → error path. | spec | n8n LLM + parse nodes | `docs/gates/qa-signoff.md` |
| R6 | A lead is **routed** to a Slack channel by tier (`SLACK_CHANNEL_HOT/_WARM/_COLD`; alerts → `_ALERTS`). | spec | n8n route + Slack node | walkthrough |
| R7 | **No silent drops.** Any node failure (LLM timeout/5xx, Slack failure, bad JSON) → bounded retry on transient errors, then dead-letter (`reason="error"`) + Slack `#alerts` + `runs` row `error`; return `{status:"error",logged:true}`. | CEO property: error handling | n8n error workflow; `/deadletter`, `/runs` | `docs/gates/qa-signoff.md` |
| R8 | **Every** attempt is logged as a `run` (`success`/`duplicate`/`error`) and is queryable; dead-letters are queryable. | CEO property: observability | `GET /runs`, `GET /deadletter` (`service/src/index.ts`) | `curl /runs`, `/deadletter` |
| R9 | State **survives restarts** via named Docker volumes (SQLite + n8n). | self-host requirement | `docker-compose.yml` volumes; `db.ts` `/data` | README self-host notes |

## 5. Core workflow
1. **Receive** `POST /webhook/lead`.
2. **Compute key** (R2).
3. **Validate** (R3) — invalid → *rejected* branch (dead-letter + `#alerts`).
4. **Idempotency check** (`/idempotency/check`) — seen → *duplicate* branch (log run
   `duplicate`, return), no LLM/Slack call.
5. **LLM classify** (R4, R5) — Groq free tier, OpenAI-compatible.
6. **Route + post to Slack** (R6); capture Slack `ts`.
7. **Commit** (`/idempotency/commit`) + log run `success` (R1, R8).
8. **Any failure anywhere** → *error* branch (R7).

## 6. Decision logic
The only judgment in the system is the **LLM tier classification**: given the
lead's text (as data), the model outputs `tier ∈ {hot, warm, cold}`, a one-line
`summary`, a `suggested_channel`, and a `reason`. The deterministic **routing**
then maps `tier → Slack channel` via env. No scoring math is hand-coded — the
qualification is the model's; the routing is configuration.

## 7. Data & state (SQLite, WAL, persistent volume)
- `processed_leads(key PK, created_at, slack_ts, classification)` — idempotency ledger.
- `dead_letter(id, key, reason, payload, created_at)` — failed/rejected leads.
- `runs(id, key, status, detail, created_at)` — append-only attempt log.
- Indexes on `runs.key`, `dead_letter.key`. DB at `/data/lead-triage.sqlite`
  (Node built-in `node:sqlite`, WAL mode).

## 8. Integrations & external systems
- **n8n (OSS, Docker)** — hosts the workflow; holds the LLM key + Slack webhooks.
- **LLM** — OpenAI-compatible chat completion; default **Groq free tier**
  (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`); drop-in swap to **Gemini free tier**.
- **Slack** — incoming webhooks, one per tier channel plus `#alerts`.
- **Sidecar** — internal-only Node/Hono service on the Docker network (no public
  port). All config via env; nothing hardcoded.

## 9. Failure modes & handling
- Invalid JSON to a sidecar endpoint → `400`.
- Missing required field on an endpoint → `400` naming the field.
- Invalid lead → R3 (rejected + dead-letter + alert).
- LLM parse failure / any node failure → R7 (error + dead-letter + alert + run `error`).
- Transient LLM/Slack errors → bounded retries before dead-lettering.
- Restart → state preserved (R9). `docker compose down -v` intentionally wipes it.

## 10. Assumptions, constraints & non-goals
- **Constraints (CEO-locked 2026-06-11):** Claude-Max-only, **no per-token cash** →
  free LLM tier only; n8n OSS self-hosted; env-driven secrets; branded "Arup", no
  company name, no GitHub for this artifact; honesty — nothing faked.
- **Assumptions (CEO go-live inputs, not invented):** a free Groq/Gemini key, a
  Slack incoming webhook, and a host with a **persistent** volume exist at go-live.
- **Non-goals:** not multi-tenant; no CRM write-back; no analytics dashboard; no
  auth/UI beyond the demo.

## 11. Open items (traceable, not invented)
- **No `docs/domain.md`** — this demo predates the domain-first (DDD) standard.
- **No automated test suite** — verification is via the three demo scripts + the
  QA/Security gate docs; it predates the TDD standard (no `tests/` folder).
  Retrofitting `tests/` would bring it to current standard.
- **Go-live inputs pending** (see `PROJECT.md`): host w/ persistent volume,
  free-LLM key + provider, Slack webhook URL(s)/channels.
