#!/bin/bash
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# QNT Browser Bridge
# Triggers browser extraction on M2 via SSH
# Usage: bash browser_bridge.sh <command> [url]
# M1 calls this → M2 runs browser → result returned to M1

set -a
source $BASE_DIR/.env
set +a

COMMAND=${1:-feargreed}
URL=${2:-""}
M2_IP=${M2_TAILSCALE_IP}
M2_USER="azmatsaif"
M2_SCRIPT="/Users/azmatsaif/cipher/qnt/browser_fetch.js"
OUTPUT_SYNC="$BASE_DIR/qnt/browser_output/"

mkdir -p "$OUTPUT_SYNC"

# Run browser fetch on M2
echo "[qnt-browser] Fetching via M2 browser engine..."
RESULT=$(ssh ${M2_USER}@${M2_IP} \
  "node ${M2_SCRIPT} ${COMMAND} '${URL}'" \
  2>/dev/null)

if [ $? -eq 0 ]; then
  echo "$RESULT"
  
  # Sync any saved files from M2 to M1
  scp -r \
    ${M2_USER}@${M2_IP}:/Users/azmatsaif/cipher/qnt/browser_output/ \
    ${OUTPUT_SYNC} \
    2>/dev/null
    
  echo "[qnt-browser] Files synced to M1: ${OUTPUT_SYNC}"
  echo "[qnt-browser] Done"
else
  echo "[qnt-browser] M2 browser engine unavailable"
  echo "[qnt-browser] Falling back to direct HTTP fetch"
fi
