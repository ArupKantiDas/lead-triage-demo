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

## Notes for CEO outreach (from gig analysis 2026-06-11)
- Gig 1 (Make, Slack+ClickUp+Claude) explicitly lists idempotency, error handling, monitoring/failure alerts, Claude for structured extraction — our exact pillars.
- Gig 2 (n8n) requires a **5–7 minute Loom** (longer than 90s). Our 90s script is the core; extend by walking the workflow JSON and the dead-letter/replay tables on camera.
- Gig 3 (Make, sales diagnosis/quote) wants scoring logic + audit trails + retries — our runs/dead-letter tables and the tiering prompt demonstrate this shape.
