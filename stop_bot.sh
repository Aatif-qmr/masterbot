#!/bin/bash
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/." && pwd)"
# MasterBot Stop Script
EMERGENCY=${1:-normal}
MASTERBOT_DIR="$BASE_DIR"
LOG="$MASTERBOT_DIR/logs/shutdown.log"
source "$MASTERBOT_DIR/.env"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG"
echo "  MasterBot Stopping — $(date)" | tee -a "$LOG"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG"

curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" -d chat_id="$TELEGRAM_CHAT_ID" -d text="🟡 MasterBot Stopping (Mode: $EMERGENCY)..." > /dev/null

if [ "$EMERGENCY" == "emergency" ]; then
    echo "[EMERGENCY] Force closing all positions..." | tee -a "$LOG"
    curl -s -X POST -u "$FREQTRADE_UI_USERNAME:$FREQTRADE_UI_PASSWORD" "http://127.0.0.1:8080/api/v1/forceexit" -H "Content-Type: application/json" -d '{"tradeid": "all"}'
    curl -s -X POST -u "$FREQTRADE_UI_USERNAME:$FREQTRADE_UI_PASSWORD" "http://127.0.0.1:8081/api/v1/forceexit" -H "Content-Type: application/json" -d '{"tradeid": "all"}'
    sleep 20
else
    echo "[NORMAL] Stopping new entries..." | tee -a "$LOG"
    curl -s -X POST -u "$FREQTRADE_UI_USERNAME:$FREQTRADE_UI_PASSWORD" "http://127.0.0.1:8080/api/v1/stopentry" -H "Content-Type: application/json"
    curl -s -X POST -u "$FREQTRADE_UI_USERNAME:$FREQTRADE_UI_PASSWORD" "http://127.0.0.1:8081/api/v1/stopentry" -H "Content-Type: application/json"
fi

FINAL_BALANCE=$(curl -s -u "$FREQTRADE_UI_USERNAME:$FREQTRADE_UI_PASSWORD" http://127.0.0.1:8080/api/v1/balance | python3 -c "import sys, json; data=json.load(sys.stdin); print(next((b['total'] for b in data.get('currencies', []) if b['currency']=='USDT'), 'unknown'))" 2>/dev/null)

echo "[3/5] Stopping Freqtrade instances..." | tee -a "$LOG"
"$MASTERBOT_DIR/venv/bin/supervisorctl" -c "$MASTERBOT_DIR/config/supervisord.conf" stop freqtrade_mean_reversion
"$MASTERBOT_DIR/venv/bin/supervisorctl" -c "$MASTERBOT_DIR/config/supervisord.conf" stop freqtrade_trend_follow

echo "[4/5] Releasing caffeinate..." | tee -a "$LOG"
[ -f "$MASTERBOT_DIR/.caffeinate_pid" ] && kill $(cat "$MASTERBOT_DIR/.caffeinate_pid") 2>/dev/null && rm "$MASTERBOT_DIR/.caffeinate_pid"
pkill caffeinate 2>/dev/null

echo "[5/5] Running backup..." | tee -a "$LOG"
bash "$MASTERBOT_DIR/automation/backup.sh"

curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" -d chat_id="$TELEGRAM_CHAT_ID" -d text="🔴 MasterBot Stopped. Final Balance: ${FINAL_BALANCE} USDT" > /dev/null
echo -e "\n✅ MasterBot is stopped\n" | tee -a "$LOG"
