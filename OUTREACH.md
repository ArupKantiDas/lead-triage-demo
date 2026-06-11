# Outreach blurb + go-live inputs

## One-paragraph description (paste into outreach)

I built a self-hosted, open-source n8n automation that takes an inbound lead
through a webhook, uses an LLM to qualify and summarize it (hot / warm / cold,
with a one-line summary and a routing decision), and posts a structured result to
the right Slack channel. What makes it production-grade rather than a toy: it's
idempotent — replaying the same webhook never duplicates a Slack post or a record;
it has explicit error handling — bad inputs and any node failure are caught,
sent to a dead-letter store, and alerted in Slack, never silently dropped; and
it's fully observable — every run, success, duplicate, and failure is logged and
queryable. It's all env-driven with no secrets in the workflow, and the LLM
provider is swappable. Happy to walk you through it live or adapt the same
patterns to your Make.com or n8n stack.

---

## INPUTS NEEDED FROM CEO TO GO LIVE

The demo runs locally end-to-end with just the first two items below. The rest are
only needed to host it on a public URL for a live link.

1. **Free-LLM-tier API key** — a Groq key (free, https://console.groq.com) is the
   default. Set `LLM_API_KEY` in `.env`. (To use Gemini's free tier instead, set
   `LLM_BASE_URL` and `LLM_MODEL` per the comments in `.env.example` — same key
   field.) We are deliberately NOT using any paid API.

2. **Slack incoming webhook URL(s)** — create at https://api.slack.com/apps →
   Incoming Webhooks. At minimum one for `#alerts`; ideally one each for the
   hot/warm/cold channels (they fall back to #alerts if unset). Set the
   `SLACK_WEBHOOK_*` vars in `.env`. (A free Slack workspace works fine.)

3. **Cloud host (only to make it a live, shareable link)** — a host with a
   **persistent disk/volume**. IMPORTANT: avoid hosts with an ephemeral filesystem
   (some free Render/Heroku tiers) — they wipe the SQLite idempotency store and
   n8n's own data on restart, which would break the demo. A small VPS
   (DigitalOcean/Hetzner/Fly.io with a volume) or any box where Docker volumes
   persist is ideal. We need the host + login from you; we do not assume one.
   - Before pointing it at a public URL, flip `N8N_BASIC_AUTH_ACTIVE=true` (the
     n8n editor holds your keys), and ideally put a body-size limit / proxy in
     front. See README "Security / go-live hardening."

4. **(Optional, not needed for this demo)** Google Sheets / Airtable workspace
   creds — only if you later want to swap the webhook trigger for a
   "new row in a sheet/base" trigger. The current webhook shape is what makes the
   idempotency replay demo clean, so this is optional.

For recording the Loom, you only need items 1 and 2 plus running `docker compose
up` locally — no cloud host required to record.
