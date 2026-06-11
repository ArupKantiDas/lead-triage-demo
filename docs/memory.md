# Project Memory — Lead Triage Demo

> Living context for this project. Read first before any change; keep current.
> (Structured per `docs/templates/memory.md`.)

## What this is (1-2 lines)

A self-hosted n8n workflow + Node/TypeScript/Hono sidecar that proves delivery
of LLM-powered workflow automations (idempotency, explicit error-handling,
observability). Built to win three open freelance automation gigs for Arup.
See `docs/spec.md` for full build spec.

## Current state — what is built and working

- **Sidecar** (`service/src/`): Hono app exposing `/healthz`, `/idempotency/check`,
  `/idempotency/commit`, `/deadletter` (GET + POST), `/runs` (GET + POST), backed
  by SQLite via Node's built-in `node:sqlite`. Zero external runtime dependencies.
- **n8n workflow** (`workflow/lead-triage.json`): statically verified correct by
  QA. All four paths (happy, duplicate, reject, error) wired properly. Not
  unit-tested (n8n graphs are not testable code — QA verified the graph statically).
- **Infrastructure** (`docker-compose.yml`): n8n + sidecar on one Docker network,
  SQLite + n8n data on named volumes (survive restarts). Fixed: `N8N_BLOCK_ENV_ACCESS_IN_NODE: "false"` per QA Defect 1.
- **Demo scripts** (`scripts/`): `send-good-lead.sh`, `replay-lead.sh`, `send-bad-lead.sh`.
- **Automated test suite** (`service/src/sidecar.test.ts`): 22 integration tests
  covering every QA-verified behavior; all green. Added 2026-06-11 (retrofit).
- **Domain model** (`docs/domain.md`): DDD domain model added 2026-06-11 (retrofit).
- **Gates**: Security PASS, QA CONDITIONAL PASS (both defects fixed). Awaiting CEO
  go-live inputs (host, LLM key, Slack webhooks) and CEO go.

## Key decisions (link the ADRs)

See `docs/decisions.md` for the full decision log. Headline decisions:

1. **Webhook trigger** — enables clean idempotency replay demo (header or sha256 key).
2. **Groq free tier LLM** — CEO constraint: no per-token cash; OpenAI-compatible; env-swappable to Gemini.
3. **SQLite via sidecar** — zero-ops, no paid infra, Stack Doctrine default for edge stores.
4. **n8n OSS, self-hosted** — CEO constraint: no paid n8n/Make account.
5. **HTTP 200 for rejected/duplicate** — deliberate: prevents infinite sender retries; bad leads are dead-lettered, not bounced.
6. **Build-time models**: EM=Opus, Backend/QA/IR=Sonnet, Security=Opus (public-facing artifact).

## Gotchas and non-obvious context

- **`node:sqlite` is experimental** in Node 22/23; stable in Node 24. The `DatabaseSync`
  singleton in `db.ts` is reset per test via `resetDb()` — do not remove that export.
- **The sidecar does NOT validate Classification values** (hot/warm/cold). The workflow
  owns that constraint; the sidecar stores whatever the workflow sends.
- **n8n `$env` access** requires `N8N_BLOCK_ENV_ACCESS_IN_NODE: "false"` in
  `docker-compose.yml` — without it every env reference returns undefined and the
  demo silently breaks (QA Defect 1, now fixed).
- **`INSERT OR REPLACE`** is the idempotency upsert mechanism. It replaces the whole
  row (SQLite semantics), not just updated fields. Do not change it to `INSERT OR IGNORE`.
- **No public port on the sidecar** — it is on the Docker internal network only,
  callable only by the n8n container. This is intentional (security boundary).
- **Test placement**: test file lives in `src/` (with the code, per the standard).
  It is excluded from the build output by `tsconfig.json` include patterns (only
  `app.ts`, `db.ts`, `index.ts` are needed in `dist/`).
- **`app.ts` vs `index.ts` split**: `index.ts` is the server entry point only
  (calls `serve`). `app.ts` exports the Hono `app` instance for test access via
  `app.fetch`. This split was introduced 2026-06-11 during the test retrofit;
  runtime behavior is unchanged.

## Open TODOs / next steps

- [ ] CEO go-live inputs: persistent host + LLM API key + Slack webhook URLs.
- [ ] Release gate (release-agent) — blocked on CEO go-live inputs.
- [ ] CEO final go.

## Project-specific lessons

- Splitting the Hono app from the server entry point (`app.ts` / `index.ts`) is
  required for testability without starting a real TCP server. Do this from day one
  on future projects.
- `node:sqlite` singleton needs an explicit reset function for test isolation.
  Pattern: export `resetDb()` that closes and nulls the singleton; call in test
  `afterEach`.
- n8n workflow `$env` access is off by default since v0.213.0. Always set
  `N8N_BLOCK_ENV_ACCESS_IN_NODE: "false"` for env-driven n8n workflows.
