#!/bin/bash
# MasterBot Start Script
MODE=${1:-paper}
MASTERBOT_DIR="/Users/aatifquamre/masterbot"
LOG="$MASTERBOT_DIR/logs/startup.log"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG"
echo "  MasterBot Starting — Mode: $MODE" | tee -a "$LOG"
echo "  $(date)" | tee -a "$LOG"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG"

if [[ "$MODE" != "paper" && "$MODE" != "live" ]]; then
    echo "ERROR: Invalid mode. Use: bash start_bot.sh paper|live"
    exit 1
fi

echo "[1/7] Running security check..." | tee -a "$LOG"
bash "$MASTERBOT_DIR/automation/security_check.sh" || exit 1

if [ "$MODE" == "paper" ]; then
    CONFIG="$MASTERBOT_DIR/config/config_paper.json"
else
    CONFIG="$MASTERBOT_DIR/config/config_live_spot.json"
    echo -e "\n⚠️ LIVE MODE SELECTED. Press ENTER to confirm."
    read -r
fi

echo "[2/7] Config: $CONFIG" | tee -a "$LOG"
echo "[3/7] Updating supervisord config..." | tee -a "$LOG"
sed -i '' "s|--config .*config.*\.json|--config $CONFIG|g" "$MASTERBOT_DIR/config/supervisord.conf"

echo "[4/7] Starting supervisord..." | tee -a "$LOG"
SCTL="$MASTERBOT_DIR/venv/bin/supervisorctl -c $MASTERBOT_DIR/config/supervisord.conf"
if $SCTL status > /dev/null 2>&1; then
    $SCTL reload
else
    "$MASTERBOT_DIR/venv/bin/supervisord" -c "$MASTERBOT_DIR/config/supervisord.conf"
fi
sleep 30

echo "[5/7] Running health check..." | tee -a "$LOG"
"$MASTERBOT_DIR/venv/bin/python" "$MASTERBOT_DIR/automation/health_check.py"

echo "[6/7] Enabling caffeinate..." | tee -a "$LOG"
pkill caffeinate 2>/dev/null
caffeinate -i -w $(pgrep -f "supervisord") &
echo $! > "$MASTERBOT_DIR/.caffeinate_pid"

echo "[7/7] Sending startup notification..." | tee -a "$LOG"
source "$MASTERBOT_DIR/.env"
BALANCE=$(curl -s -u "$FREQTRADE_UI_USERNAME:$FREQTRADE_UI_PASSWORD" http://100.90.68.42:8080/api/v1/balance | python3 -c "import sys, json; data=json.load(sys.stdin); print(next((b['total'] for b in data.get('currencies', []) if b['currency']=='USDT'), 'unknown'))" 2>/dev/null)
SENTIMENT=$(python3 -c "import json; d=json.load(open('$MASTERBOT_DIR/sentiment/scores/current_score.json')); print(f\"{d['score']:.3f}\")" 2>/dev/null)

SUMMARY="🟢 MasterBot Started
━━━━━━━━━━━━━━━━━━━━
Mode: $(echo $MODE | tr '[:lower:]' '[:upper:]')
Time: $(date)
Balance: ${BALANCE} USDT
Sentiment: ${SENTIMENT}
Strategies: MeanReversionV1 + TrendFollowV1
Risk limits: 3% daily / 7% weekly
Health: All systems nominal
🧠 Intelligence: qnt active
━━━━━━━━━━━━━━━━━━━━
Web UI: http://127.0.0.1:8080
qnt: type 'qnt' to interact with the brain
Next report: Monday 7:00 AM"

curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" -d chat_id="$TELEGRAM_CHAT_ID" -d text="$SUMMARY" > /dev/null

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG"
echo "  ✅ MASTERBOT STARTED SUCCESSFULLY" | tee -a "$LOG"
echo "  Mode: $MODE | Balance: $BALANCE USDT" | tee -a "$LOG"
echo "  🧠 Intelligence: qnt active" | tee -a "$LOG"
echo "  Telegram commands: /status /profit /balance" | tee -a "$LOG"
echo "  qnt commands: qnt -p \"your question\"" | tee -a "$LOG"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG"
