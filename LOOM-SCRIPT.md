# Loom Script — Lead Triage Demo (~90 seconds)

> Record in QuickTime/Loom with your screen showing: a terminal (left) and Slack
> (right). Have these ready before you hit record:
> - `docker compose up` already running (n8n + sidecar healthy).
> - The three scripts in `scripts/` ready to run.
> - Slack open to your `#leads-hot` (or whichever) channel and `#alerts`.
> - A terminal tab with `watch -n1 'curl -s localhost:3001/runs | jq .'` optional.
>
> Speak in first person as Arup. Don't rush — the responses carry the story.

---

**[0:00–0:12] — What it is**
"Hi, I'm Arup. This is a working n8n automation — fully self-hosted, open-source.
An inbound lead hits a webhook, a hosted LLM qualifies and summarizes it, and it
gets routed to the right Slack channel. But the point of this demo isn't the happy
path — it's the three things that separate a pro automation from a fragile one.
Let me show you."

**[0:12–0:35] — Happy path (the baseline)**
[Run `./scripts/send-good-lead.sh`]
"I'll fire in a real lead. The workflow validates it, computes an idempotency key,
calls the LLM to classify it — hot, warm, or cold — with a one-line summary and a
routing decision..."
[Switch to Slack — point at the new structured message in the leads channel]
"...and here it is in Slack: tiered, summarized, routed. One clean message."

**[0:35–0:55] — Idempotency (replay safety)**
"Now — what happens if that same webhook fires twice? Network retries, a double
submit, a replayed event. An amateur automation posts to Slack twice and creates a
duplicate record. Watch."
[Run `./scripts/replay-lead.sh` — same payload]
"Same lead, replayed."
[Point at the terminal response: `{status:"duplicate"}`]
"It returns 'duplicate' — and notice..."
[Switch to Slack]
"...no second message. The idempotency key already existed, so it short-circuited
before calling the LLM or posting again. Safe to re-run, every time."

**[0:55–1:18] — Explicit error handling (no silent drops)**
"Second: bad input. A lead comes in with no email."
[Run `./scripts/send-bad-lead.sh`]
[Point at terminal: `{status:"rejected"}`]
"It's rejected cleanly — and crucially, it's not silently dropped."
[Switch to Slack #alerts — point at the alert]
"It goes to a dead-letter store and fires an alert in #alerts. Same thing if the
LLM or Slack is down mid-run — the failure is caught, dead-lettered, and alerted,
never lost."

**[1:18–1:30] — Observability + close**
[Switch to terminal — run `curl -s localhost:3001/runs | jq .` and `.../deadletter | jq .`]
"And everything's observable — every run, every success, duplicate, and failure is
logged and queryable, plus n8n's own execution view. Idempotent, fault-tolerant,
and monitored. That's the difference. If you want this kind of reliability in your
workflows, let's talk — arupd557@gmail.com."

---

## Honesty / model note (read before sending)
This demo runs on a **free hosted model** (Groq) to keep it free to share — it is
NOT Claude. Do not say or imply it's Claude. Two of the target gigs ask for Claude
specifically; the truthful, strong framing is: *"the demo runs on a free model so I
can share it openly; in your build I wire whichever provider you want — Claude,
GPT, Gemini — it's a two-env-var swap."* That's the line to use if a client asks.

## Notes for the longer (5–7 min) cut — Gig 2 (n8n) requires it
After the 90s core above, extend by:
- Open the workflow canvas in n8n and walk the node graph: webhook → validate →
  idempotency check → LLM classify → route → Slack → commit, and the error branch
  fanning in from every fallible node to the dead-letter + alert.
- Show the LLM node's prompt — point out the lead text is wrapped as DATA so a
  malicious lead can't hijack the classification (prompt-injection hardening).
- Show `.env.example` and explain everything is env-driven — no secrets in the
  workflow, swap Groq for Gemini by changing two env vars.
- Show the dead_letter and runs tables filling up live as you fire test cases.
