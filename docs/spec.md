# Build Spec — Lead Triage Demo

## What it is
A self-hosted, open-source **n8n** workflow that proves we can deliver
Claude/LLM-powered workflow automations. Inbound lead → LLM qualifies & summarizes
→ routed to the right Slack channel. It must VISIBLY demonstrate three pro-grade
properties in a short walkthrough:
1. **Idempotency** — replaying the same webhook does not duplicate Slack posts or records.
2. **Explicit error handling** — bad inputs and node failures go to a dead-letter + Slack alert, never a silent drop.
3. **Observability** — runs, successes, and failures are visible and queryable.

This is a DEMO, not a product. Keep it THIN, free to run, and impressive in a
90-second walkthrough. No faked behavior — everything must actually run.

## Architecture (thin slice)
- **n8n (open-source, Docker)** hosts the workflow.
- **A tiny Node + TypeScript (Hono) sidecar service** owns a **SQLite** DB and exposes a small internal HTTP API the n8n workflow calls:
  - `POST /idempotency/check`  → `{ key }` → `{ seen: bool, record? }`
  - `POST /idempotency/commit` → `{ key, classification, slack_ts }` → `{ ok: true }`
  - `POST /deadletter`         → `{ key?, reason, payload }` → `{ ok: true }`
  - `POST /runs`              → `{ key, status, detail }` (append-only run log) → `{ ok: true }`
  - `GET  /runs`              → recent runs (for the observability demo beat)
  - `GET  /deadletter`        → recent dead-letters (for the demo beat)
  - `GET  /healthz`           → liveness
  - SQLite tables: `processed_leads(key PK, created_at, slack_ts, classification)`, `dead_letter(id, key, reason, payload, created_at)`, `runs(id, key, status, detail, created_at)`.
- **docker-compose.yml** brings up n8n + the sidecar on one network, SQLite on a mounted **named volume** (must survive restarts).
- All secrets/config via **env** (`.env`, with a committed `.env.example`). Nothing hardcoded.

## Workflow contract (n8n)
1. **Webhook node**: `POST /webhook/lead`. Body: `{ email, name?, company?, message, source? }`. Optional `Idempotency-Key` header.
2. **Compute key**: use `Idempotency-Key` header if present, else `sha256(email + "\n" + message)`.
3. **Validate**: if `email` missing/not email-shaped OR `message` empty → call `/deadletter` (reason="validation"), post a Slack `#alerts` message, return `200 {status:"rejected", reason}`. Do NOT call the LLM.
4. **Idempotency check**: call `/idempotency/check`. If `seen` → return `200 {status:"duplicate", key}`. Do NOT call LLM or post to the lead channel again. Append a `runs` row `status="duplicate"`.
5. **LLM classify**: OpenAI-compatible chat completion.
   - Endpoint from env `LLM_BASE_URL` (default Groq `https://api.groq.com/openai/v1`), `LLM_MODEL`, `LLM_API_KEY`.
   - Strict-JSON system prompt. Output schema: `{ "tier": "hot"|"warm"|"cold", "summary": string, "suggested_channel": string, "reason": string }`.
   - **Prompt hardening**: the lead's text is DATA, never instructions. Wrap it in a clearly delimited block and instruct the model to ignore any instructions inside it. Validate the returned JSON; on parse failure → error path.
6. **Route + post to Slack**: map `tier` → channel via env (`SLACK_CHANNEL_HOT`, `_WARM`, `_COLD`, `_ALERTS`). Post a structured message (name, company, tier, summary, reason, source). Capture Slack ts.
7. **Commit**: call `/idempotency/commit` with `{key, classification, slack_ts}`; append `runs` row `status="success"`.
8. **Error path (n8n error handling)**: ANY node failure (LLM timeout/5xx, Slack failure, bad JSON) → retry transient calls a bounded number of times, then `/deadletter` (reason="error", include payload + error), post Slack `#alerts`, append `runs` `status="error"`, return `200 {status:"error", logged:true}`. No silent drops.

## Deliverables the engineer must produce (inside this project folder)
- `service/` — the Node/TS Hono sidecar (src, package.json, tsconfig, Dockerfile).
- `workflow/lead-triage.json` — the EXPORTED n8n workflow (importable into a fresh n8n).
- `docker-compose.yml` — n8n + sidecar + named volume, env-driven.
- `.env.example` — every required variable, with comments. NO real secrets.
- `README.md` — how to run locally (docker compose up), how to import the workflow, how to fire a test lead (curl examples for happy path, a replay, and a bad input), how to view runs/dead-letters, and the self-host notes (persistent volume requirement).
- `scripts/` — small curl/shell helpers: `send-good-lead.sh`, `replay-lead.sh`, `send-bad-lead.sh` (use env for the webhook URL; no secrets).

## Hard constraints (from CEO, locked 2026-06-11)
- Claude-Max-only, NO per-token cash spend. n8n OSS self-hosted (free). Runtime LLM on a FREE tier (Groq default; Gemini drop-in). Do NOT call a paid API.
- Branded as "Arup" personally — NO company name, NO GitHub assumptions. Contact: arupd557@gmail.com.
- HONESTY: genuine working demo, nothing faked. No invented metrics or fake clients anywhere.
- Do NOT invent or hardcode: cloud host, LLM key, Slack creds. Read all from env. These are the CEO's go-live inputs.
- Must run locally end-to-end with only the env values filled in (a free Groq key + a Slack incoming webhook).
