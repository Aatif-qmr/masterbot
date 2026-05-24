# 🤖 Enhanced Telegram Bot for Cipher QNT

## Overview

Your Telegram bot has been upgraded with **inline keyboards**, **better commands**, and **iMessage integration** for iPhone alerts!

## ✨ New Features

### 1. Inline Keyboard Buttons
- Tap buttons instead of typing commands
- Quick access to system status, risk checks, analytics
- Interactive decision-making for escalations

### 2. Enhanced Commands
```
/start or /help    - Show interactive help menu
/menu              - Display main control panel with buttons
/status            - System status overview  
/risk              - Current risk levels
/skeptic           - Skeptic Agent performance stats
/shadow            - Shadow hyperopt status
/backup            - Trigger cloud backup
/logs              - View recent system logs
/health            - Run 11-point health audit
/analytics         - View analytics dashboard
```

### 3. iMessage Integration (Mac + iPhone)
- CRITICAL alerts sent directly to your iPhone
- Uses AppleScript on macOS
- Only for urgent situations (bypasses Do Not Disturb)

### 4. Webhook Support
- Instant responses (no polling delay)
- More efficient than polling
- Supports HTTPS with SSL

## 📁 Files Created

```
/workspace/qnt/memory/enhanced_bot.py          # Main enhanced bot module
/workspace/qnt/memory/telegram_webhook_server.py # Webhook server for instant responses
/workspace/setup_enhanced_bot.sh               # Interactive setup script
```

## 🚀 Quick Start

### Option A: Interactive Setup (Recommended)
```bash
cd /workspace
./setup_enhanced_bot.sh
```

This will guide you through:
1. Testing the enhanced bot
2. Configuring iMessage
3. Setting up webhooks

### Option B: Manual Testing

1. **Test inline keyboards:**
   ```bash
   python3 qnt/memory/enhanced_bot.py --test
   ```

2. **Send main menu:**
   ```bash
   python3 qnt/memory/enhanced_bot.py --menu
   ```

3. **Send analytics:**
   ```bash
   python3 qnt/memory/enhanced_bot.py --analytics
   ```

## 📱 iMessage Setup (iPhone + Mac)

### Configuration Steps:

1. **Run the setup script:**
   ```bash
   ./setup_enhanced_bot.sh
   # Select option 3: Configure iMessage integration
   ```

2. **Enter your iPhone number** (with country code):
   ```
   Example: +1234567890
   ```

3. **On your Mac, ensure:**
   - Messages app is open and signed in
   - iMessage is enabled in System Preferences → Internet Accounts
   - Your iPhone number is registered with iMessage

4. **Test iMessage:**
   ```bash
   ./setup_enhanced_bot.sh
   # Select option 4: Test iMessage
   ```

### How It Works:
- Only **CRITICAL** level alerts trigger iMessage
- Regular notifications still go to Telegram
- Prevents alert fatigue while ensuring you never miss critical issues

## 🌐 Webhook Setup (For Instant Responses)

### Why Use Webhooks?
- **Instant**: No polling delay (responses in <1 second)
- **Efficient**: Telegram pushes updates to you
- **Scalable**: Better for high-frequency interactions

### Setup with ngrok (Local Testing):

1. **Install ngrok:**
   ```bash
   brew install ngrok  # On Mac
   ```

2. **Start ngrok tunnel:**
   ```bash
   ngrok http 8443
   ```

3. **Copy the HTTPS URL** (e.g., `https://abc123.ngrok.io`)

4. **Setup webhook:**
   ```bash
   python3 qnt/memory/telegram_webhook_server.py \
     --webhook-url https://abc123.ngrok.io/webhook \
     --setup-only
   ```

5. **Run the webhook server:**
   ```bash
   python3 qnt/memory/telegram_webhook_server.py \
     --webhook-url https://abc123.ngrok.io/webhook \
     --port 8443
   ```

### Production Setup:
For production, use a proper domain with SSL certificate:
```bash
python3 qnt/memory/telegram_webhook_server.py \
  --webhook-url https://your-domain.com:8443/webhook \
  --port 8443 \
  --cert /path/to/cert.pem \
  --key /path/to/key.pem
```

## 🔧 Integration with Existing Code

### Update `qnt_notifier.py` calls:

Replace simple notifications with enhanced versions:

```python
# OLD
from qnt_notifier import send_notify

send_notify("Alert", "Something happened", "WARN")

# NEW - with iMessage for critical alerts
from enhanced_bot import send_notify

send_notify("Alert", "Something happened", "WARN", use_imessage=False)
send_notify("CRITICAL", "System failure!", "CRITICAL", use_imessage=True)
```

### Add inline keyboards to escalations:

```python
# OLD
from qnt_notifier import send_escalation

msg_id = send_escalation(situation, options, recommendation)

# NEW - with inline buttons
from enhanced_bot import send_escalation

msg_id = send_escalation(situation, options, recommendation)
# Now users can tap buttons OR reply with numbers!
```

### Send interactive menus:

```python
from enhanced_bot import send_main_menu, send_with_keyboard

# Send main control menu
send_main_menu()

# Send custom message with keyboard
send_with_keyboard(
    title="Risk Alert",
    message="High volatility detected!",
    keyboard_type="risk_actions",
    level="WARN"
)
```

## 🎯 Inline Keyboard Types

Available keyboard templates:

| Type | Use Case | Buttons |
|------|----------|---------|
| `main_menu` | Main control panel | Status, Risk, Skeptic, Shadow, Backup, Logs, Health |
| `decision_yes_no` | Simple confirmations | Yes/No |
| `risk_actions` | Risk management | Emergency Stop, Reduce Position, Continue |
| `quick_actions` | Bot control | Restart, Pause, Resume, Stop |

## 📊 Message Formatting

The enhanced bot uses HTML formatting:
- `<b>Bold text</b>` for emphasis
- `<i>Italic text</i>` for timestamps/details
- `<pre>Code blocks</pre>` for command output
- `<code>Inline code</code>` for commands
- Emojis for visual clarity

## 🔍 Troubleshooting

### Bot not responding?
1. Check token and chat ID in `.env`:
   ```bash
   grep QNT_TELEGRAM /workspace/.env
   ```

2. Verify bot is alive:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/getMe"
   ```

### iMessage not working?
1. Ensure running on macOS
2. Check Messages app is open
3. Verify phone number format (+country code)
4. Test manually:
   ```bash
   osascript -e 'tell application "Messages" to send "Test" to buddy "+1234567890"'
   ```

### Webhook errors?
1. Check webhook status:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
   ```

2. Remove and re-setup:
   ```bash
   python3 qnt/memory/enhanced_bot.py --remove-webhook
   # Then setup again
   ```

## 📈 Next Steps

1. **Test the enhancements:**
   ```bash
   ./setup_enhanced_bot.sh
   ```

2. **Configure iMessage** for critical alerts

3. **Update existing code** to use new functions

4. **Consider webhook deployment** for production

5. **Customize keyboards** for your specific workflows

---

**Questions?** The setup script (`./setup_enhanced_bot.sh`) provides interactive guidance for all features!
