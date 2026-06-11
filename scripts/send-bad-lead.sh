#!/usr/bin/env bash
# send-bad-lead.sh — Fire a malformed lead (missing email, empty message) to demonstrate
# the validation → dead-letter → Slack #alerts path.
# Usage: ./scripts/send-bad-lead.sh
# Reads WEBHOOK_BASE from env; defaults to http://localhost:5678.
set -euo pipefail

BASE="${WEBHOOK_BASE:-http://localhost:5678}"
ENDPOINT="${BASE}/webhook/lead"

echo "[send-bad-lead] POST ${ENDPOINT} (missing email and empty message)"

curl -sS -X POST "${ENDPOINT}" \
  -H "Content-Type: application/json" \
  -d '{
    "email":   "not-an-email",
    "name":    "Bad Actor",
    "message": "",
    "source":  "spam"
  }' | jq . 2>/dev/null || true

echo ""
echo "[send-bad-lead] Expected: { status: 'rejected', reason: '...' }"
echo "[send-bad-lead] Check GET http://localhost:3001/deadletter for the logged entry."
