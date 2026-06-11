#!/usr/bin/env bash
# replay-lead.sh — Replay the SAME lead a second time (same Idempotency-Key).
# The workflow must return { status: "duplicate" } without calling LLM or posting to Slack again.
# Usage: ./scripts/replay-lead.sh
# Reads WEBHOOK_BASE from env; defaults to http://localhost:5678.
set -euo pipefail

BASE="${WEBHOOK_BASE:-http://localhost:5678}"
ENDPOINT="${BASE}/webhook/lead"

echo "[replay-lead] POST ${ENDPOINT} (same Idempotency-Key as send-good-lead)"

curl -sS -X POST "${ENDPOINT}" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: good-lead-demo-001" \
  -d '{
    "email":   "sarah.chen@acmecorp.io",
    "name":    "Sarah Chen",
    "company": "Acme Corp",
    "message": "Hi, we are looking to automate our entire sales pipeline using AI agents. Budget is around $50k. Can we book a call this week?",
    "source":  "website-contact-form"
  }' | jq . 2>/dev/null || true

echo ""
echo "[replay-lead] Expected: { status: 'duplicate', key: 'good-lead-demo-001' }"
