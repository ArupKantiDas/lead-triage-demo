# Recording Runbook — Lead Triage Demo

Operational companion to [LOOM-SCRIPT.md](LOOM-SCRIPT.md) (the narration). This is
the *what-to-type / what-to-show* sheet. Every command below was tested live on
2026-06-11 against the running stack — they work as written.

> **Recording is yours to do** (your screen + voice + Loom). This sheet makes it
> push-button: pre-flight, the exact commands per beat, and how to reset between
> takes.

---

## 0. Pre-flight (before you hit record)

The stack is already up, clean, and verified. Confirm with these (all from the
project folder, in a normal terminal — `docker` is on your PATH):

```bash
cd "outputs/prototypes/lead-triage-demo"

docker compose ps                       # both containers Up; sidecar (healthy)
curl -s http://localhost:3001/runs      # -> {"runs":[]}        (clean)
curl -s http://localhost:3001/deadletter# -> {"dead_letter":[]} (clean)
```

If `docker compose ps` shows nothing (e.g. after a reboot), bring it back:
```bash
docker compose up -d
# wait ~15s, then if the webhook 404s, the workflow needs re-activating — see
# "If the webhook 404s" at the bottom.
```

**Window layout for the recording:**
- **Left:** terminal, in `outputs/prototypes/lead-triage-demo`, font bumped up.
- **Right:** Slack, with `#leads-hot` / `#leads-warm` / `#leads-cold` and `#alerts`
  visible (or just the one channel you used for all four if you pointed them at one).
- Optional 2nd terminal tab for the n8n UI walk (longer cut): http://localhost:5678

**Mic check, then record.** Read the narration from LOOM-SCRIPT.md; type the
commands below on cue.

---

## 1. The beats (commands matched to the narration)

| Beat | Say (see LOOM-SCRIPT.md) | Type | You'll see |
|------|--------------------------|------|------------|
| **Happy path** | "I'll fire in a real lead…" | `./scripts/send-good-lead.sh` | `{ "status": "ok", "tier": "hot\|warm\|cold" }` → then point at the new Slack message |
| **Idempotency** | "What if the same webhook fires twice?…" | `./scripts/replay-lead.sh` | `{ "status": "duplicate", "key": "…" }` → point at Slack: **no second message** |
| **Error handling** | "Bad input — a lead with no email…" | `./scripts/send-bad-lead.sh` | `{ "status": "rejected", "reason": "…" }` → point at Slack **#alerts** |
| **Observability** | "Everything's observable…" | `curl -s http://localhost:3001/runs \| jq .`  then  `curl -s http://localhost:3001/deadletter \| jq .` | the success + duplicate rows, and the dead-letter entry |

That's the 90-second core. For the 5–7 min cut (Gig 2 wants it), follow the
"longer cut" notes at the bottom of LOOM-SCRIPT.md (walk the n8n canvas, show the
prompt-injection hardening, show `.env.example`).

---

## 2. Reset between takes  ⚠️ important

The demo scripts use a **fixed idempotency key**, so if you run `send-good-lead`
twice without resetting, the second run returns `duplicate` instead of `ok`. Before
each new take, run:

```bash
./scripts/reset-demo.sh
```

It wipes the sidecar store (runs / dead-letter / idempotency), leaves n8n alone
(webhook stays registered), and prints the now-empty state. ~5 seconds.

---

## 3. Honesty note (already in LOOM-SCRIPT.md — don't skip)

The demo runs on a **free hosted model (Groq), not Claude.** Don't say or imply
Claude. If asked: *"the demo runs on a free model so I can share it openly; in your
build I wire whichever provider you want — Claude, GPT, Gemini — it's a two-env-var
swap."*

---

## 4. Troubleshooting (if something misbehaves on a take)

**A script shows no JSON / blank response** → the workflow isn't returning a body.
Re-activate: see below.

**The webhook 404s** (`Cannot POST /webhook/lead`) → n8n lost the active
registration (happens after a full `docker compose down` or a reboot). Re-import +
activate, then wait ~10s:
```bash
docker cp workflow/lead-triage.json lead-triage-n8n:/tmp/wf.json
docker exec lead-triage-n8n n8n import:workflow --input=/tmp/wf.json
docker exec lead-triage-n8n n8n publish:workflow --id=$(docker exec lead-triage-n8n n8n list:workflow | head -1 | cut -d'|' -f1)
docker compose restart n8n
# wait ~10–15s after it's healthy — the production webhook registers a few
# seconds AFTER the health check goes green. Then test:
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:5678/webhook/lead \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: ping' \
  -d '{"name":"x","email":"x@y.com","company":"c","message":"budget approved 500 seats now"}'
# expect 200, then ./scripts/reset-demo.sh to clean up the ping
```

**Slack message didn't appear** but the response was `ok` → check the webhook URL
in `.env` for that tier; `sidecar /runs` showing `success / tier=…` with
`slack_ts:"ok"` confirms Slack returned 200.

**Sidecar `curl localhost:3001` fails** → the sidecar port is published to
`127.0.0.1:3001` in docker-compose; make sure the sidecar container is `healthy`
(`docker compose ps`).

---

*Stack verified working end-to-end (all three paths + observability) on 2026-06-11.
Security ✅ PASS, QA ✅ PASS (runtime-verified). Sidecar: 22/22 automated tests pass.*
