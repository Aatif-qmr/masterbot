#!/bin/bash
# Weekly Strategy Research via qnt
# Runs Saturday 10pm on M2
# Research -> Generate -> Backtest -> Escalate Deploy

LOG=/Users/azmatsaif/cipher/logs/strategy_scan.log
RESEARCH_DIR=/Users/azmatsaif/cipher/strategies/research/
PATH=$PATH:/Users/azmatsaif/cipher/qnt/bin

echo "[$(date)] Autonomous strategy loop started" >> $LOG

set -a
source /Users/azmatsaif/cipher/.env
set +a

mkdir -p $RESEARCH_DIR
cd /Users/azmatsaif/cipher

# 1. Research
OUTPUT=$(qnt -p \
  "Search arXiv for BTC mean reversion or momentum strategies from last 7 days. Extract title and a concise 1-sentence technical hypothesis for the best one found. Return format: Hypothesis: [1-sentence hypothesis]" \
  --output-format text \
  2>/dev/null)

if [ -n "$OUTPUT" ]; then
  # 2. Extract Hypothesis
  HYPOTHESIS=$(echo "$OUTPUT" | grep "Hypothesis:" | sed 's/Hypothesis: //')
  
  if [ -n "$HYPOTHESIS" ]; then
    echo "[$(date)] Top Hypothesis: $HYPOTHESIS" >> $LOG
    
    # 3. Generate
    echo "[$(date)] Generating strategy..." >> $LOG
    STRAT_FILE=$(qnt-strategy-gen "$HYPOTHESIS" | grep "Generated:" | awk '{print $2}')
    
    if [ -n "$STRAT_FILE" ]; then
      STRAT_NAME=$(basename "$STRAT_FILE" .py)
      echo "[$(date)] Generated: $STRAT_NAME" >> $LOG
      
      # 4. Backtest
      echo "[$(date)] Running backtest..." >> $LOG
      BT_RESULTS=$(qnt-backtest "$STRAT_NAME" "20250101-20260401")
      
      # 5. Escalate if Pass
      if [[ "$BT_RESULTS" == *"✅ PASS"* ]]; then
        echo "[$(date)] Backtest PASSED. Escalating for deployment." >> $LOG
        qnt-deploy "$STRAT_FILE"
      else
        echo "[$(date)] Backtest FAILED. Storing in research." >> $LOG
      fi
    fi
  fi
fi

echo "[$(date)] Autonomous strategy loop complete" >> $LOG
