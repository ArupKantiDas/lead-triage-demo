#!/usr/bin/env bash
# send-good-lead.sh — Fire a well-formed lead to the webhook.
# Usage: ./scripts/send-good-lead.sh
# Reads WEBHOOK_BASE from env; defaults to http://localhost:5678.
set -euo pipefail

BASE="${WEBHOOK_BASE:-http://localhost:5678}"
ENDPOINT="${BASE}/webhook/lead"

echo "[send-good-lead] POST ${ENDPOINT}"

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
echo "[send-good-lead] Done."
