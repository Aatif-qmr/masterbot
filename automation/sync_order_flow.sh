#!/bin/bash
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Syncs Order Flow data from M2 to M1
set -a
source $BASE_DIR/.env
set +a

M2_IP=$(grep M2_TAILSCALE_IP $BASE_DIR/.env | cut -d= -f2)
M2_PATH="/Users/azmatsaif/cipher/qnt/oracle/order_flow_state.json"
M1_PATH="$BASE_DIR/qnt/oracle/order_flow_state.json"

# Ensure directory exists on M1
mkdir -p "$(dirname "$M1_PATH")"

echo "⏳ Waiting 30s for M2 Oracle to finish..."
sleep 30

echo "📡 Syncing Order Flow from M2..."
scp -q azmatsaif@$M2_IP:$M2_PATH $M1_PATH
