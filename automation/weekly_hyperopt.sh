#!/bin/bash
# Cipher Weekly Hyperopt Automation (SCALED)

BASE_DIR="/Users/azmatsaif/cipher"
LOG="$BASE_DIR/logs/hyperopt_log.txt"
mkdir -p "$BASE_DIR/logs"

echo "[$(date)] === Scaled Hyperopt Started ===" >> "$LOG"

set -a
source "$BASE_DIR/.env"
set +a
source "$BASE_DIR/venv/bin/activate"
cd "$BASE_DIR"

# 1. Download fresh data
freqtrade download-data --exchange binance --pairs BTC/USDT ETH/USDT SOL/USDT BNB/USDT XRP/USDT --timeframes 5m 15m 1h 4h 1d --days 14 --datadir data/
echo "[$(date)] Data download complete" >> "$LOG"

# 2. Hyperopt Rotation (500 epochs)
STRATS=("MeanReversionV1" "TrendFollowV1" "ScalpV1" "SwingV1" "DailyTrendV1")
TFS=("1h" "4h" "5m" "15m" "1d")

for i in "${!STRATS[@]}"; do
  STRAT=${STRATS[$i]}
  TF=${TFS[$i]}
  echo "[$(date)] Starting Hyperopt for $STRAT ($TF)..." >> "$LOG"
  
  freqtrade hyperopt \
    --strategy $STRAT \
    --strategy-path strategies/active/ \
    --config config/config_paper.json \
    --hyperopt-loss SharpeHyperOptLoss \
    --spaces buy sell stoploss roi \
    --epochs 500 \
    --timerange 20250101-20260101 \
    --timeframe $TF \
    --datadir data/ \
    -j -1 2>> "$LOG"
done

# 3. Final Parse & Report
# (Assuming parse_hyperopt.py is updated to handle all)
python "$BASE_DIR/automation/parse_hyperopt.py"

echo "[$(date)] === Scaled Hyperopt Complete ===" >> "$LOG"
deactivate
