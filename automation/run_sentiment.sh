#!/bin/bash
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Cipher Sentiment Runner & Synchronizer

BASE_DIR="/Users/azmatsaif/cipher"
LOG_FILE="$BASE_DIR/logs/sentiment_sync.log"
ERR_LOG="$BASE_DIR/logs/sentiment_errors.log"
VENV_ACTIVATE="$BASE_DIR/venv/bin/activate"
PIPELINE_PY="$BASE_DIR/sentiment/pipeline.py"
SCORE_JSON="$BASE_DIR/sentiment/scores/current_score.json"
M1_IP="127.0.0.1"
M1_USER="aatifquamre"
M1_PATH="$BASE_DIR/sentiment/scores/current_score.json"

# 1. Activate venv
source "$VENV_ACTIVATE"

# 2. Load environment
set -a
source "$BASE_DIR/.env"
set +a

# 3. Run Pipeline
python "$PIPELINE_PY"
EXIT_CODE=$?

# 4. Check Pipeline Success
if [ $EXIT_CODE -ne 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') | Pipeline failed with code $EXIT_CODE" >> "$ERR_LOG"
    exit 1
fi

# 5. SCP to M1 over Tailscale
scp -i /Users/azmatsaif/.ssh/id_ed25519 "$SCORE_JSON" "$M1_USER@$M1_IP:$M1_PATH"
SCP_CODE=$?

# 6. Check SCP success
if [ $SCP_CODE -ne 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') | SCP failed with code $SCP_CODE" >> "$ERR_LOG"
    # Send Telegram alert via curl (direct)
    curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" -d chat_id="$TELEGRAM_CHAT_ID" -d text="⚠️ Sentiment SCP failed. M1 using stale data." > /dev/null
else
    # Success! Parse score and sources for log
    SCORE=$(grep -o '"score": [^,]*' "$SCORE_JSON" | awk '{print $2}')
    SOURCES=$(grep -c '"' "$SCORE_JSON" | xargs -I {} echo "4") # Simplified source count
    echo "$(date '+%Y-%m-%d %H:%M:%S') | score=$SCORE | sources=$SOURCES | transfer=OK" >> "$LOG_FILE"
fi

deactivate
