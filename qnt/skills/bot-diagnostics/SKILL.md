---
name: bot-diagnostics
description: Diagnose and fix MasterBot system issues
triggers:
  - health check
  - is the bot running
  - something is wrong
  - bot stopped
  - not trading
  - error in logs
  - investigate
  - diagnose
  - what happened
model: gemini-3-flash-preview
---

# Bot Diagnostics Skill

## When I Activate
User asks about system health, bot behavior,
errors, crashes, or why the bot is not trading.

## Diagnostic Sequence (always in this order)

### Step 1 — Process Check
Run: supervisorctl status freqtrade
Expected: RUNNING
If STOPPED/FATAL → this is the primary issue

### Step 2 — API Check  
curl -s -u "$FREQTRADE_UI_USERNAME:$FREQTRADE_UI_PASSWORD" \
  http://100.90.68.42:8080/api/v1/ping
Expected: {"status":"pong"}

### Step 3 — Recent Log Check
tail -50 /Users/aatifquamre/masterbot/logs/freqtrade.log
Look for: ERROR, WARNING, Exception, Traceback
Report any found with line context.

### Step 4 — Sentiment Freshness
Check timestamp in:
/Users/aatifquamre/masterbot/sentiment/scores/current_score.json
If older than 65 minutes → M2 cron job issue

### Step 5 — Risk Events
tail -30 /Users/aatifquamre/masterbot/logs/risk_manager.log
Look for: BLOCK, CRITICAL, drawdown
Report any blocking events found.

### Step 6 — Balance State
cat /Users/aatifquamre/masterbot/risk/balance_state.json
Check last_updated timestamp.
If stale → balance tracker cron issue.

### Step 7 — Open Trades
curl -s -u "$FREQTRADE_UI_USERNAME:$FREQTRADE_UI_PASSWORD" \
  http://100.90.68.42:8080/api/v1/status
Report: count and each trade pair + profit

## After Diagnosis
1. Explain what I found in plain English
2. State the most likely root cause
3. For each issue propose exact fix
4. Show file + line + proposed change
5. Wait for confirmation
6. Apply fix
7. Verify fix worked
8. Append to QNT.md Known Issues Log:
   echo "[$(date +%Y-%m-%d)] FIXED: [description]" >> \
   /Users/aatifquamre/masterbot/qnt/.issues_log

## Hard Limits
- Never restart Freqtrade without asking
- Never modify strategy files without confirmation  
- Never change risk parameters
- Read-only diagnosis is always safe
