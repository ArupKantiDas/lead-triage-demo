# PROJECT — Lead Triage Demo (Claude-powered n8n automation)

| Field | Value |
|---|---|
| **Slug** | `lead-triage-demo` |
| **Type** | prototype |
| **Status** | in-gates (Security PASS, QA PASS; awaiting CEO go-live inputs + Release) |
| **One-liner** | A self-hosted n8n workflow that takes an inbound lead webhook, qualifies & summarizes it with an LLM, and routes a structured result to the right Slack channel — with idempotency, explicit error-handling/dead-letter, and observability. |
| **Origin / traceability** | CEO request 2026-06-11: proof-of-work demo to win three open freelance automation gigs (Make/n8n + Claude + Slack). |
| **Owner** | engineering-manager |
| **Engineers assigned** | integration-research-engineer (n8n workflow), backend-engineer (idempotency/dead-letter service), security-agent (gate), qa-agent (gate) |
| **Stack** | n8n open-source (self-hosted, Docker) + a tiny Node/TypeScript (Hono) sidecar for the SQLite idempotency/dead-letter/runs store + Groq free-tier LLM (OpenAI-compatible, env-swappable to Gemini) + Slack incoming webhook. All config env-driven. |
| **Stack rationale** | n8n OSS = free, no paid Make/n8n account (CEO constraint). SQLite = zero-ops local/edge store per Stack Doctrine. Node/Hono sidecar = thin, shares no paid infra. Groq free tier = no per-token cash spend (CEO constraint). Ratified by Cost Optimizer 2026-06-11. |
| **Repo remote** | none yet (CEO: no GitHub for this artifact; ships as live self-host + Loom) |
| **Created** | 2026-06-11 |
| **Last updated** | 2026-06-11 |

## Gates (nothing ships until all are ✅)
| Gate | Status | By | Notes |
|---|---|---|---|
| Security | ✅ | security-agent | PASS — fixed dead error-branch (was a silent-drop); no secret leakage, parameterized SQL, prompt-injection hardened. See docs/gates/security-review.md |
| QA (market-ready) | ✅ | qa-agent | PASS — happy/duplicate/reject/error paths all correct; fixed n8n $env-access block + false README credential step. See docs/gates/qa-signoff.md |
| Release | ⬜ | release-agent | Deferred until CEO supplies host + creds (go-live inputs in OUTREACH.md) |
| CEO go | ⬜ | CEO | |

## Cost / usage notes
Build-time tiers (Cost Optimizer ratified 2026-06-11): EM=Opus, Integration Research=Sonnet, Backend=Sonnet, QA=Sonnet, Security=Opus (policy default; CEO flagged artifact as public-facing). Runtime: zero cash spend — n8n OSS + SQLite + Groq free tier, all env-driven.

## Key decisions
See `docs/decisions.md`.

## Open inputs needed from the CEO
- [ ] Cloud host (with a PERSISTENT volume — Render/Heroku-style ephemeral FS would wipe SQLite + n8n data) + login.
- [ ] Free-LLM-tier API key (Groq or Gemini) + which provider.
- [ ] Slack incoming webhook URL(s) (or bot token) + target channel names.
- [ ] (Optional, only if switching trigger to Sheets/Airtable later) those workspace creds.
