#!/usr/bin/env bash
# Whole-path check: start API, inspect demo photo, profile edit, generate, download files.
# Exit 0 = demo path works. Usage: scripts/smoke.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${SMOKE_PORT:-8765}"
LOG="$(mktemp -t gridmend-smoke.XXXX)"
uv run uvicorn api.main:app --port "$PORT" >"$LOG" 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT
for _ in $(seq 1 40); do
  curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null && break
  sleep 0.5
done
if ! curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null; then
  echo "FAIL api did not start"; tail -20 "$LOG"; exit 1
fi
SMOKE_BASE="http://127.0.0.1:$PORT" uv run python scripts/smoke.py || { echo "--- api log ---"; tail -30 "$LOG"; exit 1; }
