# 📋 Telegram Bot System Audit Report

## Executive Summary

Your MasterBot has **TWO separate Telegram integrations**:

### 1. QNT Intelligence Bot (Primary)
- **Token Variable**: `QNT_TELEGRAM_TOKEN`
- **Chat ID Variable**: `QNT_TELEGRAM_CHAT_ID`
- **Purpose**: AI intelligence, decision escalations, system control
- **Location**: `/workspace/qnt/memory/`

### 2. Trading Bot Notifications (Secondary)
- **Token Variable**: `TELEGRAM_BOT_TOKEN`
- **Chat ID Variable**: `TELEGRAM_CHAT_ID`
- **Purpose**: Trading alerts, risk warnings, health checks
- **Location**: Multiple files across `/workspace/`

---

## 📁 File Inventory

### QNT Intelligence Bot Files

| File | Purpose | Status |
|------|---------|--------|
| `qnt/memory/qnt_notifier.py` | Core notification module | ✅ Active |
| `qnt/memory/reply_listener.py` | Polls for user replies to escalations | ✅ Active |
| `qnt/memory/enhanced_bot.py` | Enhanced version with inline keyboards | ✅ Created |
| `qnt/memory/telegram_webhook_server.py` | Webhook server for instant responses | ✅ Created |
| `qnt/memory/autonomy_router.py` | Routes decisions to QNT | ⚠️ Needs review |
| `qnt/memory/memory_manager.py` | Logs decisions and actions | ✅ Active |

### Trading Bot Integration Files

| File | Purpose | Status |
|------|---------|--------|
| `risk/risk_manager.py` | Risk alerts (drawdown, macro, etc.) | ✅ Uses TELEGRAM_BOT_TOKEN |
| `automation/health_check.py` | Health check results | ⚠️ Variables defined but not sending |
| `automation/weekly_report.py` | Weekly summaries | ✅ Uses QNT_TELEGRAM_TOKEN |
| `start_bot.sh` | Startup notifications | ✅ Uses TELEGRAM_BOT_TOKEN |
| `stop_bot.sh` | Shutdown notifications | ✅ Uses TELEGRAM_BOT_TOKEN |

---

## 🔍 Configuration Analysis

### Environment Variables Required

```bash
# For QNT Intelligence Bot
QNT_TELEGRAM_TOKEN=your_bot_token_here
QNT_TELEGRAM_CHAT_ID=your_chat_id_here

# For Trading Bot Notifications  
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Optional: iMessage Integration (Mac + iPhone)
ENABLE_IMESSAGE=true
IPHONE_NUMBER=+1234567890
```

### Current Status

⚠️ **ISSUE DETECTED**: No `.env` file found with actual credentials!

The system expects these variables but they must be configured in:
- `/workspace/.env` (create from `.env.example`)

---

## ✨ Enhancement Features Available

### 1. Inline Keyboards (NEW)
Interactive buttons instead of text commands:
- Main menu with 8 quick action buttons
- Decision buttons (Yes/No, Risk actions)
- Custom keyboards for different scenarios

### 2. Enhanced Commands (NEW)
```
/menu       - Interactive control panel
/analytics  - Performance dashboard  
/status     - System status
/risk       - Risk levels
/skeptic    - Skeptic stats
/shadow     - Hyperopt status
/health     - Health check
/logs       - Recent logs
```

### 3. iMessage Integration (NEW)
For your iPhone + Mac setup:
- CRITICAL alerts sent directly to iPhone
- Uses AppleScript on macOS
- Configured via `setup_enhanced_bot.sh`

### 4. Webhook Support (NEW)
- Instant responses (no polling delay)
- More efficient than long polling
- Setup via `setup_enhanced_bot.sh` option 5

---

## 🧪 Testing Procedures

### Test QNT Intelligence Bot
```bash
cd /workspace

# Test enhanced bot with inline keyboards
python3 qnt/memory/enhanced_bot.py --test

# Send main menu
python3 qnt/memory/enhanced_bot.py --menu

# Send analytics
python3 qnt/memory/enhanced_bot.py --analytics
```

### Test Trading Bot Notifications
```bash
# Test risk manager alert
python3 -c "
import sys
sys.path.insert(0, '/workspace')
from risk.risk_manager import send_telegram_alert
send_telegram_alert('Test alert from risk manager', 'INFO')
"

# Test health check (doesn't send to Telegram by default)
python3 automation/health_check.py
```

### Interactive Setup
```bash
./setup_enhanced_bot.sh
```

Menu options:
1. Test enhanced bot (inline keyboards)
2. Send main menu to Telegram
3. Configure iMessage integration
4. Test iMessage (Mac only)
5. Setup webhook for instant responses
6. Remove webhook (use polling instead)
7. View bot status
8. Exit

---

## 🔧 How Both Bots Work Together

### Scenario 1: System Startup
1. `start_bot.sh` runs
2. Sends startup notification via **Trading Bot** (`TELEGRAM_BOT_TOKEN`)
3. Message includes: Mode, Balance, Sentiment, Strategies

### Scenario 2: Risk Alert
1. `risk_manager.py` detects drawdown
2. Sends CRITICAL alert via **Trading Bot** (`TELEGRAM_BOT_TOKEN`)
3. Cooldown enforced (1 hour between critical alerts)

### Scenario 3: Decision Escalation
1. QNT needs human input
2. `qnt_notifier.py` sends escalation via **QNT Bot** (`QNT_TELEGRAM_TOKEN`)
3. `reply_listener.py` polls for your response
4. You reply with number (1/2/3) or custom instruction
5. Decision logged to memory

### Scenario 4: Interactive Control
1. You send `/menu` to **QNT Bot**
2. Enhanced bot shows inline keyboard
3. Tap buttons for instant status/actions
4. Webhook provides instant response (if configured)

---

## ⚠️ Issues Found & Recommendations

### Issue 1: Missing .env Configuration
**Problem**: No `.env` file with actual credentials
**Fix**: 
```bash
cp /workspace/.env.example /workspace/.env
# Edit .env and add your tokens
```

### Issue 2: Two Separate Bot Tokens
**Problem**: Confusion between `QNT_TELEGRAM_TOKEN` and `TELEGRAM_BOT_TOKEN`
**Recommendation**: 
- Option A: Use SAME token for both (simpler, one bot)
- Option B: Keep separate (QNT for intelligence, Trading for alerts)

### Issue 3: Health Check Not Sending to Telegram
**Problem**: `health_check.py` defines Telegram vars but doesn't send results
**Fix**: Add Telegram notification at end of `run_all()` function

### Issue 4: Reply Listener Uses Polling
**Problem**: `reply_listener.py` uses long polling (delayed responses)
**Fix**: Enable webhook mode for instant callback handling

---

## 📱 iMessage Setup for iPhone

Since you're on Mac with iPhone, enable iMessage for CRITICAL alerts:

```bash
./setup_enhanced_bot.sh
# Select option 3: Configure iMessage
# Enter your iPhone number (e.g., +1234567890)
# Select option 4: Test iMessage
```

**Requirements**:
- macOS with Messages app running
- Signed into iMessage
- iPhone number registered

**What Gets Sent via iMessage**:
- Only CRITICAL level alerts
- Daily drawdown hits
- Weekly drawdown hits
- Circuit breaker triggers
- Emergency stops

---

## 🎯 Recommended Next Steps

1. **Configure Environment**:
   ```bash
   cp /workspace/.env.example /workspace/.env
   # Add your Telegram tokens and chat IDs
   ```

2. **Test Enhanced Bot**:
   ```bash
   python3 qnt/memory/enhanced_bot.py --test
   ```

3. **Setup iMessage** (Optional but recommended):
   ```bash
   ./setup_enhanced_bot.sh
   # Options 3 and 4
   ```

4. **Decide on Token Strategy**:
   - Use one bot token for everything? OR
   - Keep two bots (QNT + Trading)?

5. **Enable Webhook** (Optional):
   ```bash
   ./setup_enhanced_bot.sh
   # Option 5 (requires public HTTPS URL)
   ```

---

## 📞 Quick Reference

### Send Test Notification
```bash
# QNT Bot
python3 qnt/memory/qnt_notifier.py --test

# Enhanced Bot
python3 qnt/memory/enhanced_bot.py --test
```

### View Bot Status
```bash
./setup_enhanced_bot.sh
# Option 7
```

### Check Webhook Info
```bash
curl -s "https://api.telegram.org/botYOUR_TOKEN/getWebhookInfo" | python3 -m json.tool
```

### Manual Telegram Send Test
```bash
curl -X POST "https://api.telegram.org/botYOUR_TOKEN/sendMessage" \
  -d chat_id=YOUR_CHAT_ID \
  -d text="Test message from MasterBot"
```

---

## 📚 Documentation Files

- `/workspace/ENHANCED_BOT_README.md` - Enhanced bot features
- `/workspace/TELEGRAM_BOT_AUDIT.md` - This audit report
- `/workspace/qnt/memory/enhanced_bot.py` - Enhanced bot source code
- `/workspace/setup_enhanced_bot.sh` - Interactive setup script

