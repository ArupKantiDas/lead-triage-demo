# Decisions — Lead Triage Demo

Every decision traces to an input (CEO or a designated expert agent). Nothing invented.

| # | Decision | Rationale | Traces to |
|---|---|---|---|
| 1 | Trigger = **webhook** (POST /webhook/lead), not Sheets/Airtable polling | The CEO explicitly wants to demo *replaying a webhook* to prove idempotency — a webhook is the only shape that makes "replay the exact same request" a clean demo beat. Also the lowest-credential path to run locally. | CEO goal (idempotency = replay a webhook); EM judgment |
| 2 | Runtime LLM = **Groq free tier**, OpenAI-compatible, env-swappable to Gemini | CEO constraint: no per-token cash spend, use a free LLM tier. Env-driven so the CEO's actual provider/key is a go-live input, not a rebuild. | CEO constraint; Cost Optimizer ratified 2026-06-11 |
| 3 | Idempotency/dead-letter/runs store = **SQLite** via a thin Node/Hono sidecar | Zero-ops local/edge store per Stack Doctrine; keeps everything free and self-contained. | Stack Doctrine; Cost Optimizer ratified |
| 4 | n8n = **open-source, self-hosted via Docker** | CEO constraint: no paid Make/n8n account. | CEO constraint |
| 5 | Scenario = **inbound lead → LLM qualifies (tier+summary+routing) → right Slack channel; bad inputs dead-lettered + alerted** | CEO's suggested concrete, relatable scenario; confirmed as a direct hit on what all three target gigs ask for (idempotency, error handling, monitoring, Claude/LLM, Slack). | CEO goal; Integration Research gig analysis 2026-06-11 |
| 6 | Rejected/duplicate/error responses return **HTTP 200** with a status field | A permanently-bad payload should NOT trigger infinite sender retries; we ack receipt and dead-letter deliberately. Transient infra failures are retried internally before dead-lettering. | EM judgment (deliberate error-handling design) |
| 7 | Build-time tiers: EM=Opus, IR/Backend/QA=Sonnet, **Security=Opus** | Policy default keeps Security on Opus; CEO flagged artifact as public-facing/"represents us". | MODEL-COST-POLICY; Cost Optimizer ratified |
| 8 | Idempotency key = `Idempotency-Key` header if present, else `sha256(email + message)` | Standard idempotency pattern; deterministic for replay demo. | EM judgment; Integration Research (gig 1 names idempotency/state mgmt) |
| 9 | n8n HTTP Request node: use `specifyBody:"json"` + `jsonBody` expression for all structured JSON bodies (LLM, Slack webhooks) | n8n 2.25.7 (typeVersion 4.2) ignores the `body` template string when `contentType:"json"` is set and strips it to empty keypairs on import. `specifyBody:"string"` parses the string as URL-encoded form data (not raw JSON). Only `specifyBody:"json"` + `jsonBody` correctly sends a JS object as JSON. | Integration Research Engineer fix 2026-06-11 (verified via n8n V3 source) |
| 10 | `continueErrorOutput` connections must use `main[1]` in the connections JSON, NOT the `"error"` key | In n8n 2.25.7, `handleNodeErrorOutput` moves error items to `nodeSuccessData[lastMainOutput]`, and the execution loop only follows `main` connections. The `"error"` connection key is for workflow-level error handlers only and is never triggered by `continueErrorOutput`. | Integration Research Engineer fix 2026-06-11 (verified via n8n-core workflow-execute.js source) |
| 11 | IF nodes (`Valid?`, `Already Seen?`) use `typeValidation:"loose"` | n8n 2.25.7 IF node typeVersion 2 defaults to `strict` type validation. Strict mode throws `Wrong type: '' is a string but was expecting a boolean` even when the Code node correctly emits JS booleans, because the expression evaluator round-trips values through the condition engine. Loose mode resolves this. | Integration Research Engineer fix 2026-06-11 |
| 12 | `NODE_FUNCTION_ALLOW_BUILTIN: crypto` env var required in docker-compose.yml | n8n 2.25.7 blocks `require('crypto')` in Code nodes by default. The Compute Key node uses `crypto.createHash` for the fallback idempotency key. Set at infra level so no workflow change is needed. | EM decision (already applied 2026-06-11) |

## Notes for CEO outreach (from gig analysis 2026-06-11)
- Gig 1 (Make, Slack+ClickUp+Claude) explicitly lists idempotency, error handling, monitoring/failure alerts, Claude for structured extraction — our exact pillars.
- Gig 2 (n8n) requires a **5–7 minute Loom** (longer than 90s). Our 90s script is the core; extend by walking the workflow JSON and the dead-letter/replay tables on camera.
- Gig 3 (Make, sales diagnosis/quote) wants scoring logic + audit trails + retries — our runs/dead-letter tables and the tiering prompt demonstrate this shape.
