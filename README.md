# Lead Triage Demo

A self-hosted n8n workflow that qualifies inbound leads with an LLM and routes them to Slack.
Built by Arup — contact: arupd557@gmail.com.

**Demonstrates three pro-grade automation properties in a 90-second walkthrough:**
1. Idempotency — replaying the same webhook never duplicates a Slack post or DB record.
2. Explicit error handling — bad inputs and failures go to a dead-letter queue and Slack #alerts, never silently dropped.
3. Observability — every run is logged and queryable via the sidecar API.

---

## Architecture

```
[POST /webhook/lead]
        │
        ▼
  n8n workflow (OSS, Docker)
   ├─ Compute idempotency key (header or sha256(email+message))
   ├─ Validate (email + non-empty message)
   │   └─ Invalid → dead-letter + Slack #alerts → 200 {status:"rejected"}
   ├─ Idempotency check (sidecar /idempotency/check)
   │   └─ Seen → log run duplicate → 200 {status:"duplicate"}
   ├─ LLM classify (Groq free tier, OpenAI-compatible)
   │   └─ Parse failure → error path
   ├─ Route + post to Slack (tier → channel)
   ├─ Idempotency commit (sidecar /idempotency/commit)
   ├─ Log run success (sidecar /runs)
   └─ 200 {status:"ok", tier:"hot"|"warm"|"cold"}
        │
        ▼ (any node failure)
  Error path → dead-letter + Slack #alerts + log run error → 200 {status:"error",logged:true}

[Sidecar — Node/TypeScript/Hono, SQLite]
  POST /idempotency/check   POST /idempotency/commit
  POST /deadletter          POST /runs
  GET  /runs                GET  /deadletter
  GET  /healthz
```

---

## Prerequisites

- Docker and Docker Compose (v2+)
- A free Groq API key: https://console.groq.com
- A Slack workspace with Incoming Webhooks enabled: https://api.slack.com/apps

---

## 1. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in:
#   LLM_API_KEY        — your free Groq key
#   SLACK_WEBHOOK_*    — your Slack incoming webhook URLs
#   WEBHOOK_URL        — the public base URL for n8n (http://localhost:5678 for local dev)
```

For local dev, the four SLACK_WEBHOOK_* variables can all point to a single test channel.

---

## 2. Start the stack

```bash
docker compose up --build -d
```

Wait about 15 seconds for both services to be healthy, then verify:

```bash
# Sidecar health
curl http://localhost:3001/healthz

# n8n UI
open http://localhost:5678
```

---

## 3. Import the workflow into n8n

1. Open http://localhost:5678 in your browser.
2. Go to **Workflows** → **Import from file**.
3. Select `workflow/lead-triage.json`.
4. Open the workflow, click **Activate** (toggle in the top-right).

The LLM key is read automatically from the `LLM_API_KEY` value you set in `.env` (step 1).
No separate credential needs to be created inside n8n — the workflow injects the key directly
from the environment variable.

---

## 4. Test the three cases

Make sure the workflow is active first (step 3 above).

### Happy path — good lead

```bash
./scripts/send-good-lead.sh
# Or with a custom base URL:
WEBHOOK_BASE=http://localhost:5678 ./scripts/send-good-lead.sh
```

Expected response: `{"status":"ok","tier":"hot"}` (or warm/cold depending on LLM output).
Check Slack — a structured message should appear in the configured tier channel.

### Idempotent replay — same lead again

```bash
./scripts/replay-lead.sh
```

Expected response: `{"status":"duplicate","key":"good-lead-demo-001"}`.
No new Slack post. The LLM was NOT called again.

### Bad input — validation failure

```bash
./scripts/send-bad-lead.sh
```

Expected response: `{"status":"rejected","reason":"missing or invalid email; missing message"}`.
Check Slack #alerts — an alert message should appear.

---

## 5. Observe runs and dead-letters

```bash
# Last 50 runs (success, duplicate, error)
curl http://localhost:3001/runs | jq .

# Last 50 dead-letter entries
curl http://localhost:3001/deadletter | jq .
```

You can also view full execution history in the n8n UI under **Executions**.

---

## 6. Swap the LLM provider

The workflow uses any OpenAI-compatible endpoint. To switch to Gemini free tier:

```bash
# In .env:
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_MODEL=gemini-1.5-flash
LLM_API_KEY=<your-google-ai-studio-key>
```

Then restart: `docker compose restart n8n`.

---

## n8n version note

This workflow is tested and verified on **n8n 2.25.7** (`n8nio/n8n:latest` as of 2026-06-11).
The docker-compose.yml sets two required env vars for this n8n version:
- `N8N_BLOCK_ENV_ACCESS_IN_NODE: "false"` — allows `$env.VAR` in expressions and Code nodes.
- `NODE_FUNCTION_ALLOW_BUILTIN: crypto` — allows `require('crypto')` in Code nodes (used for the idempotency key hash).

These are already present in the shipped `docker-compose.yml`. No manual action needed.

---

## Self-host notes — persistent volumes

**This demo uses named Docker volumes (`lead_triage_n8n_data`, `lead_triage_sqlite_data`).**
Named volumes survive `docker compose down` and `docker compose up`. Your workflow, credentials, run history, and idempotency records persist across restarts.

`docker compose down -v` will WIPE the volumes. Only do this if you want a clean slate.

**Deployment warning:** Do NOT deploy to platforms with ephemeral filesystems (Render free tier, Heroku dynos). The SQLite database and n8n data will be wiped on every restart. Use a platform that supports persistent block storage, such as:
- Railway (persistent volumes available)
- Fly.io (attached volumes)
- Any VPS (DigitalOcean, Hetzner, Linode) running Docker

---

## Security / go-live hardening

The following must be addressed before exposing this stack to any public network:

- Never add a `ports:` mapping to the sidecar service; it is internal-only on the docker network. If it ever must be exposed, put it behind a proxy with a shared secret and treat /deadletter and /runs as PII endpoints.
- Set a request body-size limit (e.g. `client_max_body_size` at a reverse proxy) before any public exposure.
- Flip `N8N_BASIC_AUTH_ACTIVE=true` before hosting publicly — the n8n editor holds the LLM key and Slack webhooks.

---

## Stopping the stack

```bash
docker compose down        # Stop containers, keep volumes
docker compose down -v     # Stop and wipe all data (fresh start)
```

---

## File layout

```
lead-triage-demo/
├── .env.example           # Template — copy to .env and fill in values
├── .gitignore             # Excludes .env, *.sqlite, node_modules, dist
├── docker-compose.yml     # n8n + sidecar + named volumes
├── README.md              # This file
├── docs/
│   └── spec.md            # Full build specification
├── scripts/
│   ├── send-good-lead.sh  # Test: happy path
│   ├── replay-lead.sh     # Test: idempotent replay
│   └── send-bad-lead.sh   # Test: validation failure → dead-letter
├── service/               # Node/TypeScript/Hono sidecar
│   ├── src/
│   │   ├── index.ts       # All HTTP routes
│   │   └── db.ts          # SQLite setup and migration
│   ├── package.json
│   ├── tsconfig.json
│   └── Dockerfile
└── workflow/
    └── lead-triage.json   # Importable n8n workflow export
```
