"""
Enhanced Telegram Bot with Inline Keyboards and Advanced Commands
=================================================================
Features:
- Inline keyboard buttons for quick actions
- Enhanced command set with better formatting
- Webhook support for instant responses
- Critical alert routing to iMessage (Mac integration)
- Better message formatting with HTML/Markdown
"""

import json
import os
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)

TOKEN = os.getenv("QNT_TELEGRAM_TOKEN")
CHAT_ID = os.getenv("QNT_TELEGRAM_CHAT_ID")
API_URL = f"https://api.telegram.org/bot{TOKEN}"

# iMessage Configuration (Mac only)
ENABLE_IMESSAGE = os.getenv("ENABLE_IMESSAGE", "false").lower() == "true"
IPHONE_NUMBER = os.getenv("IPHONE_NUMBER", "")  # Format: +1234567890

EMOJI = {
    "INFO": "ℹ️",
    "WARN": "⚠️",
    "CRITICAL": "🚨",
    "ESCALATE": "⚠️",
    "DECISION": "🧠",
    "SUCCESS": "✅",
    "ERROR": "❌",
    "RUNNING": "🟢",
    "STOPPED": "🔴",
    "PAUSED": "⏸️",
    "CHART": "📊",
    "MONEY": "💰",
    "SHIELD": "🛡️",
    "BRAIN": "🧠",
    "CLOCK": "⏰",
    "ROBOT": "🤖",
    "WARNING": "⚡",
    "CHECK": "✔️",
    "CROSS": "✖️",
}

# Inline Keyboard Definitions
KEYBOARDS = {
    "main_menu": {
        "inline_keyboard": [
            [
                {"text": "📊 System Status", "callback_data": "cmd_status"},
                {"text": "🛡️ Risk Check", "callback_data": "cmd_risk"},
            ],
            [
                {"text": "🧠 Skeptic Stats", "callback_data": "cmd_skeptic"},
                {"text": "📈 Shadow Hyperopt", "callback_data": "cmd_shadow"},
            ],
            [
                {"text": "💾 Run Backup", "callback_data": "cmd_backup"},
                {"text": "📋 View Logs", "callback_data": "cmd_logs"},
            ],
            [{"text": "❤️ Health Check", "callback_data": "cmd_health"}],
        ]
    },
    "decision_yes_no": {
        "inline_keyboard": [
            [
                {"text": "✅ Yes, Proceed", "callback_data": "decision_yes"},
                {"text": "❌ No, Cancel", "callback_data": "decision_no"},
            ]
        ]
    },
    "risk_actions": {
        "inline_keyboard": [
            [
                {"text": "🔴 Emergency Stop", "callback_data": "risk_stop"},
                {"text": "🟡 Reduce Position", "callback_data": "risk_reduce"},
            ],
            [{"text": "🟢 Continue Monitoring", "callback_data": "risk_continue"}],
        ]
    },
    "quick_actions": {
        "inline_keyboard": [
            [
                {"text": "🔄 Restart Bot", "callback_data": "action_restart"},
                {"text": "⏸️ Pause Trading", "callback_data": "action_pause"},
            ],
            [
                {"text": "▶️ Resume Trading", "callback_data": "action_resume"},
                {"text": "🛑 Stop All", "callback_data": "action_stop"},
            ],
        ]
    },
}


def get_current_time_ist() -> str:
    """Get current time in IST (UTC+5:30)."""
    now_utc = datetime.now(UTC)
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    return now_ist.strftime("%H:%M IST %d-%b")


def get_device_name() -> str:
    """Identify device (M1/M2)."""
    import socket

    hostname = socket.gethostname()
    user = os.getenv("USER", "").lower()

    if "aatif" in user:
        return "M1"
    elif "azmat" in user:
        return "M2"
    return "M1" if "M1" in hostname.upper() else "M2"


def send_imessage(phone_number: str, message: str) -> bool:
    """
    Send iMessage via AppleScript (Mac only).
    Only for CRITICAL alerts.
    """
    if not ENABLE_IMESSAGE or not phone_number:
        return False

    try:
        # Escape special characters for AppleScript
        escaped_message = message.replace('"', '\\"').replace("\n", " & return & ")

        script = f'''
        tell application "Messages"
            send "{escaped_message}" to buddy "{phone_number}"
        end tell
        '''

        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=10
        )

        if result.returncode == 0:
            print(f"✅ iMessage sent to {phone_number}")
            return True
        else:
            print(f"❌ iMessage failed: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ iMessage error: {e}")
        return False


def send_telegram_message(
    text: str,
    chat_id: str | None = None,
    parse_mode: str = "HTML",
    reply_markup: dict | None = None,
    disable_notification: bool = False,
) -> int | None:
    """Send message to Telegram with optional inline keyboard."""
    if not TOKEN:
        print("❌ Telegram token missing")
        return None

    target_chat = chat_id or CHAT_ID
    if not target_chat:
        print("❌ Chat ID missing")
        return None

    payload = {
        "chat_id": target_chat,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    if disable_notification:
        payload["disable_notification"] = True

    try:
        res = requests.post(f"{API_URL}/sendMessage", json=payload, timeout=10)
        if res.status_code == 200:
            msg_data = res.json()
            return msg_data["result"]["message_id"]
        else:
            print(f"❌ Telegram API error: {res.status_code} - {res.text}")
            return None
    except Exception as e:
        print(f"❌ Failed to send Telegram message: {e}")
        return None


def send_notify(title: str, message: str, level: str = "INFO", use_imessage: bool = False) -> bool:
    """
    Enhanced notification with emoji, timestamps, and optional iMessage.
    """
    if not TOKEN or not CHAT_ID:
        print("❌ Telegram credentials missing")
        return False

    prefix = EMOJI.get(level, EMOJI["INFO"])
    device = get_device_name()
    timestamp = get_current_time_ist()

    # Format message with better structure
    text = (
        f"{prefix} <b>QNT — {title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{message}\n\n"
        f"<i>⏰ {timestamp}</i>\n"
        f"<i>🖥️ Device: {device}</i>"
    )

    # Send to Telegram
    success = send_telegram_message(text) is not None

    # For CRITICAL alerts, also send iMessage if enabled
    if use_imessage and level == "CRITICAL" and ENABLE_IMESSAGE and IPHONE_NUMBER:
        imessage_text = f"{prefix} QNT CRITICAL: {title}\n{message}"
        send_imessage(IPHONE_NUMBER, imessage_text)

    return success


def send_with_keyboard(
    title: str, message: str, keyboard_type: str, level: str = "INFO"
) -> int | None:
    """Send message with inline keyboard."""
    prefix = EMOJI.get(level, EMOJI["INFO"])
    timestamp = get_current_time_ist()
    device = get_device_name()

    text = (
        f"{prefix} <b>QNT — {title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{message}\n\n"
        f"<i>⏰ {timestamp} | {device}</i>"
    )

    keyboard = KEYBOARDS.get(keyboard_type)
    if not keyboard:
        print(f"❌ Unknown keyboard type: {keyboard_type}")
        return None

    return send_telegram_message(text, reply_markup=keyboard)


def send_escalation(
    situation: str, options: list[str], recommendation: str, context: str | None = None
) -> int | None:
    """Send escalation with inline keyboard buttons for each option."""
    if not TOKEN or not CHAT_ID:
        return None

    prefix = EMOJI["ESCALATE"]
    timestamp = get_current_time_ist()

    # Build options text
    options_text = ""
    for i, opt in enumerate(options, 1):
        num_emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"][min(i - 1, 4)]
        options_text += f"{num_emoji} <b>{opt}</b>\n"

    context_text = f"\n<i>{context}</i>\n" if context else ""

    text = (
        f"{prefix} <b>QNT — Decision Required</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{situation}\n"
        f"{context_text}\n"
        f"<b>Available Actions:</b>\n"
        f"{options_text}\n"
        f"💡 <b>Recommendation:</b> {recommendation}\n\n"
        f"<i>Reply with number or tap command below</i>\n"
        f"⏰ {timestamp}"
    )

    # Create dynamic inline keyboard for options
    keyboard_buttons = []
    for i, opt in enumerate(options, 1):
        keyboard_buttons.append({"text": f"{i}. {opt[:30]}...", "callback_data": f"option_{i}"})

    # Group buttons in rows of 2
    inline_keyboard = []
    for i in range(0, len(keyboard_buttons), 2):
        row = keyboard_buttons[i : i + 2]
        inline_keyboard.append(row)

    reply_markup = {"inline_keyboard": inline_keyboard}

    try:
        res = requests.post(
            f"{API_URL}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(reply_markup),
            },
            timeout=10,
        )

        if res.status_code == 200:
            msg_data = res.json()
            message_id = msg_data["result"]["message_id"]

            # Log decision
            try:
                sys.path.insert(0, str(BASE_DIR / "qnt/memory"))
                from memory_manager import log_decision

                log_decision(situation, options, "PENDING", recommendation)
            except Exception:
                pass

            return message_id
    except Exception as e:
        print(f"❌ Failed to send escalation: {e}")

    return None


def handle_callback_query(callback_data: str, message_id: int) -> str:
    """Process inline keyboard callback and return response."""
    responses = {
        "cmd_status": execute_command("/status"),
        "cmd_risk": execute_command("/risk"),
        "cmd_skeptic": execute_command("/skeptic"),
        "cmd_shadow": execute_command("/shadow"),
        "cmd_backup": execute_command("/backup"),
        "cmd_logs": execute_command("/logs"),
        "cmd_health": execute_command("/health"),
        "decision_yes": "✅ Confirmed. Proceeding with action...",
        "decision_no": "❌ Action cancelled by user.",
        "risk_stop": "🔴 Executing emergency stop...",
        "risk_reduce": "🟡 Reducing position size...",
        "risk_continue": "🟢 Continuing normal operations...",
        "action_restart": "🔄 Restarting bot services...",
        "action_pause": "⏸️ Pausing trading activities...",
        "action_resume": "▶️ Resuming trading activities...",
        "action_stop": "🛑 Stopping all operations...",
    }

    # Handle option selections
    if callback_data.startswith("option_"):
        option_num = callback_data.split("_")[1]
        return f"✅ Option {option_num} selected. Executing..."

    response = responses.get(callback_data, f"⚙️ Processing: {callback_data}")

    # Execute actual command if it's a cmd_* callback
    if callback_data.startswith("cmd_"):
        cmd_map = {
            "cmd_status": "qnt-bot status",
            "cmd_risk": "qnt-risk-check",
            "cmd_skeptic": "qnt-skeptic stats",
            "cmd_shadow": "qnt-shadow status",
            "cmd_backup": "qnt-backup run",
            "cmd_logs": "tail -n 30 logs/supervisord.log",
            "cmd_health": "python3 automation/health_check.py",
        }
        cmd = cmd_map.get(callback_data)
        if cmd:
            return execute_command_raw(cmd)

    return response


def execute_command(text: str) -> str:
    """Execute system command and return formatted output."""
    cmd_map = {
        "/status": "qnt-bot status",
        "/qnt_status": "qnt-bot status",
        "/backup": "qnt-backup run",
        "/skeptic": "qnt-skeptic stats",
        "/shadow": "qnt-shadow status",
        "/health": "python3 automation/health_check.py",
        "/logs": "tail -n 30 logs/supervisord.log",
        "/risk": "qnt-risk-check",
    }

    command = cmd_map.get(text.split()[0].lower())
    if not command:
        return "❌ Unknown command"

    return execute_command_raw(command)


def execute_command_raw(command: str) -> str:
    """Execute raw command and return output."""
    try:
        result = subprocess.run(
            command.split(), capture_output=True, text=True, timeout=60, cwd=str(BASE_DIR)
        )

        output = result.stdout.strip() or result.stderr.strip()
        if not output:
            output = "Command executed successfully (no output)."

        # Truncate if too long
        if len(output) > 3500:
            output = output[:3500] + "\n\n... (truncated)"

        # Escape HTML
        import html

        output = html.escape(output)

        return (
            f"🖥️ <b>Command:</b> <code>{command}</code>\n━━━━━━━━━━━━━━━━━━━━━━\n<pre>{output}</pre>"
        )

    except subprocess.TimeoutExpired:
        return "❌ Command timed out (>60s)"
    except Exception as e:
        return f"❌ Error: {html.escape(str(e))}"


def send_main_menu() -> int | None:
    """Send the main control menu."""
    text = (
        f"{EMOJI['ROBOT']} <b>Cipher QNT Control Center</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Welcome! Select an action below:\n\n"
        f"<b>Quick Stats:</b>\n"
        f"• System health & status\n"
        f"• Risk levels & positions\n"
        f"• Skeptic performance\n"
        f"• Shadow hyperopt results\n\n"
        f"<b>Actions:</b>\n"
        f"• Backup data\n"
        f"• View logs\n"
        f"• Run health check\n\n"
        f"⏰ {get_current_time_ist()} | 🖥️ {get_device_name()}"
    )

    return send_telegram_message(text, reply_markup=KEYBOARDS["main_menu"])


def send_analytics_summary() -> bool:
    """Send analytics summary with charts info."""
    try:
        # Try to get analytics data
        sys.path.insert(0, str(BASE_DIR / "qnt/memory"))
        from memory_manager import load_memory

        data = load_memory()

        actions_count = len(data.get("action_log", []))
        decisions_count = len(data.get("decisions", []))

        text = (
            f"{EMOJI['CHART']} <b>QNT Analytics Dashboard</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Total Actions:</b> {actions_count}\n"
            f"🧠 <b>Decisions Made:</b> {decisions_count}\n\n"
            f"<b>Recent Activity:</b>\n"
        )

        # Show last 5 actions
        recent_actions = data.get("action_log", [])[-5:]
        for action in reversed(recent_actions):
            action_type = action.get("type", "unknown")
            ts = action.get("timestamp", "unknown")
            text += f"• {action_type} ({ts})\n"

        text += f"\n⏰ {get_current_time_ist()}"

        return send_telegram_message(text) is not None

    except Exception as e:
        return send_notify("Analytics Error", str(e), "ERROR")


def setup_webhook(webhook_url: str) -> bool:
    """Set up webhook for instant responses."""
    if not TOKEN:
        return False

    try:
        res = requests.post(
            f"{API_URL}/setWebhook",
            json={"url": webhook_url, "allowed_updates": ["message", "callback_query"]},
            timeout=10,
        )

        if res.status_code == 200:
            print(f"✅ Webhook set to: {webhook_url}")
            return True
        else:
            print(f"❌ Webhook setup failed: {res.text}")
            return False
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return False


def remove_webhook() -> bool:
    """Remove webhook and switch back to polling."""
    try:
        res = requests.post(f"{API_URL}/deleteWebhook", timeout=10)
        if res.status_code == 200:
            print("✅ Webhook removed")
            return True
        return False
    except Exception as e:
        print(f"❌ Error removing webhook: {e}")
        return False


# Import sys for escalation function
import sys

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Enhanced QNT Telegram Bot")
    parser.add_argument("--test", action="store_true", help="Run test notifications")
    parser.add_argument("--menu", action="store_true", help="Send main menu")
    parser.add_argument("--analytics", action="store_true", help="Send analytics")
    parser.add_argument("--webhook", type=str, help="Set webhook URL")
    parser.add_argument("--remove-webhook", action="store_true", help="Remove webhook")

    args = parser.parse_args()

    if args.test:
        print("Testing enhanced notifier...")
        send_notify("Test Notification", "Enhanced bot module working correctly!", "SUCCESS")
        time.sleep(1)
        send_with_keyboard("Test Keyboard", "Try the buttons below", "main_menu")
        print("✅ Test complete")

    elif args.menu:
        print("Sending main menu...")
        send_main_menu()
        print("✅ Menu sent")

    elif args.analytics:
        print("Sending analytics...")
        send_analytics_summary()
        print("✅ Analytics sent")

    elif args.webhook:
        print(f"Setting webhook to {args.webhook}...")
        setup_webhook(args.webhook)

    elif args.remove_webhook:
        print("Removing webhook...")
        remove_webhook()

    else:
        parser.print_help()
