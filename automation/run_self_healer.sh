#!/bin/bash
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Cipher Self-Healing Runner
# ============================
# This script runs the self-healing automation every 30 minutes.

WORKSPACE="$BASE_DIR"
PYTHON_BIN="$WORKSPACE/venv/bin/python"
SCRIPT="$WORKSPACE/automation/self_healer.py"

cd "$WORKSPACE"

while true; do
    echo "--- Starting Self-Healing Run at $(date) ---"
    $PYTHON_BIN "$SCRIPT"
    echo "--- Run Finished. Sleeping for 30 minutes ---"
    sleep 1800
done
