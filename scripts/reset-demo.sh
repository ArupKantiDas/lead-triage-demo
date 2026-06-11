#!/usr/bin/env bash
# reset-demo.sh — Clear the sidecar's stores (idempotency / runs / dead-letter)
# so the demo scripts (which use a FIXED idempotency key) behave fresh on the
# next take. Leaves n8n untouched, so the webhook stays registered — no need to
# re-import or re-activate the workflow between takes.
#
# Usage:  ./scripts/reset-demo.sh
set -euo pipefail

SIDECAR="${SIDECAR_CONTAINER:-lead-triage-sidecar}"

echo "[reset] wiping sidecar store…"
docker exec "$SIDECAR" sh -c 'rm -f /data/lead-triage.sqlite /data/lead-triage.sqlite-shm /data/lead-triage.sqlite-wal'
docker compose restart sidecar >/dev/null

echo -n "[reset] waiting for sidecar to be healthy"
for _ in $(seq 1 30); do
  if [ "$(docker inspect --format '{{.State.Health.Status}}' "$SIDECAR" 2>/dev/null)" = "healthy" ]; then
    echo " — ready."
    break
  fi
  echo -n "."; sleep 1
done

echo "[reset] state now:"
echo "  /runs       -> $(curl -s --max-time 4 http://localhost:3001/runs)"
echo "  /deadletter -> $(curl -s --max-time 4 http://localhost:3001/deadletter)"
echo "[reset] Clean. Ready for the next take."
