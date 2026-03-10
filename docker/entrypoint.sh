#!/bin/sh
set -eu

log() {
  echo "[entrypoint] $1"
}

run_sync() {
  log "running edge sync"
  python /app/edge_sync.py
}

RUN_ON_STARTUP="${RUN_ON_STARTUP:-true}"
ENABLE_INTERNAL_SCHEDULER="${ENABLE_INTERNAL_SCHEDULER:-false}"
SYNC_INTERVAL_SECONDS="${SYNC_INTERVAL_SECONDS:-300}"
IDLE_AFTER_START="${IDLE_AFTER_START:-true}"

if [ "$RUN_ON_STARTUP" = "true" ]; then
  run_sync || true
fi

if [ "$ENABLE_INTERNAL_SCHEDULER" = "true" ]; then
  log "internal scheduler enabled, interval=${SYNC_INTERVAL_SECONDS}s"
  while true; do
    sleep "$SYNC_INTERVAL_SECONDS"
    run_sync || true
  done
fi

if [ "$IDLE_AFTER_START" = "true" ]; then
  log "scheduler disabled, container will stay alive for manual or external scheduled runs"
  tail -f /dev/null
fi

log "nothing else to do, exiting"
exit 0