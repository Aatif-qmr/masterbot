#!/bin/bash
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MEMORY_FILE="$BASE_DIR/qnt/memory/qnt_memory.json"
QUEUE_FILE="$BASE_DIR/qnt/memory/.sync_queue"
LOG="$BASE_DIR/logs/memory_sync.log"

set -a
source $BASE_DIR/.env
set +a

# Check internet connectivity
check_internet() {
  nc -zw3 8.8.8.8 53 2>/dev/null
  return $?
}

# Sync memory file to M2
sync_to_m2() {
  scp "$MEMORY_FILE" "azmatsaif@${M2_TAILSCALE_IP}:/Users/azmatsaif/cipher/qnt/memory/qnt_memory.json" 2>/dev/null
  return $?
}

# Main logic
if check_internet; then
  if sync_to_m2; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] SYNC_OK" >> "$LOG"
    # Update last_sync_m2 in memory
    python3 -c "
import json, datetime
with open('$MEMORY_FILE', 'r') as f:
    d = json.load(f)
d['last_sync_m2'] = datetime.datetime.utcnow().isoformat() + 'Z'
with open('$MEMORY_FILE', 'w') as f:
    json.dump(d, f, indent=2)
"
    # Clear queue if sync succeeded
    rm -f "$QUEUE_FILE"
  else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] SYNC_FAILED" >> "$LOG"
    touch "$QUEUE_FILE"
  fi
else
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] OFFLINE_QUEUED" >> "$LOG"
  touch "$QUEUE_FILE"
fi
