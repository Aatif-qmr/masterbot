import os
import json
import time
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

# --- CONFIGURATION ---
ENV_PATH = "/Users/aatifquamre/masterbot/.env"
load_dotenv(ENV_PATH)

TOKEN = os.getenv("QNT_TELEGRAM_TOKEN")
CHAT_ID = os.getenv("QNT_TELEGRAM_CHAT_ID")
API_URL = f"https://api.telegram.org/bot{TOKEN}"

EMOJI = {
    "INFO": "ℹ️",
    "WARN": "⚠️",
    "CRITICAL": "🚨",
    "ESCALATE": "⚠️",
    "DECISION": "🧠",
    "SUCCESS": "✅"
}

def get_current_time_ist():
    """Simple IST time for display (UTC+5:30)."""
    # Assuming M1/M2 are in UTC or similar
    from datetime import timedelta
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    return now_ist.strftime("%H:%M IST")

def get_device_name():
    import socket
    hostname = socket.gethostname()
    if "aatif" in os.getenv("USER", "").lower():
        return "M1"
    elif "azmat" in os.getenv("USER", "").lower():
        return "M2"
    return "M1" if "M1" in hostname.upper() else "M2"

def send_notify(title, message, level='INFO'):
    """Sends a simple notification to Telegram."""
    if not TOKEN or not CHAT_ID:
        print("Telegram credentials missing.")
        return False

    prefix = EMOJI.get(level, "ℹ️")
    device = get_device_name()
    timestamp = get_current_time_ist()
    
    text = (
        f"{prefix} QNT — {title}\n"
        f"─────────────────────\n"
        f"{message}\n\n"
        f"Time: {timestamp}\n"
        f"Device: {device}"
    )
    
    try:
        res = requests.post(f"{API_URL}/sendMessage", json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)
        return res.status_code == 200
    except Exception as e:
        print(f"Failed to send Telegram notify: {e}")
        return False

def send_escalation(situation, options, recommendation, context=None):
    """Sends escalation message with numbered options."""
    if not TOKEN or not CHAT_ID:
        return None

    prefix = EMOJI["ESCALATE"]
    timestamp = get_current_time_ist()
    
    options_text = ""
    for i, opt in enumerate(options, 1):
        num_emoji = f"{i}️⃣"
        options_text += f"{num_emoji} {opt}\n"
        
    context_text = f"\n{context}\n" if context else ""
    
    text = (
        f"{prefix} QNT — Decision Required\n"
        f"─────────────────────────────\n"
        f"{situation}\n"
        f"{context_text}\n"
        f"<b>Options:</b>\n"
        f"{options_text}\n"
        f"💡 <b>My recommendation:</b> {recommendation}\n\n"
        f"Reply with 1/2/3/4 or your own instruction.\n"
        f"Time: {timestamp}"
    )
    
    try:
        res = requests.post(f"{API_URL}/sendMessage", json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)
        if res.status_code == 200:
            msg_data = res.json()
            message_id = msg_data['result']['message_id']
            
            # Log to memory
            try:
                import sys
                sys.path.insert(0, '/Users/aatifquamre/masterbot/qnt/memory')
                from memory_manager import log_decision
                log_decision(situation, options, "PENDING", recommendation)
            except ImportError:
                pass
                
            return message_id
    except Exception as e:
        print(f"Failed to send Telegram escalation: {e}")
    return None

def get_pending_reply(timeout_minutes=60):
    """Poll Telegram for a reply to the last escalation."""
    start_time = time.time()
    last_update_id = 0
    
    # Get initial offset to skip old messages
    try:
        res = requests.get(f"{API_URL}/getUpdates", params={"limit": 1}, timeout=10)
        updates = res.json().get('result', [])
        if updates:
            last_update_id = updates[-1]['update_id']
    except:
        pass

    print(f"Polling for reply (timeout {timeout_minutes}m)...")
    while (time.time() - start_time) < (timeout_minutes * 60):
        try:
            res = requests.get(f"{API_URL}/getUpdates", params={
                "offset": last_update_id + 1,
                "timeout": 20
            }, timeout=30)
            updates = res.json().get('result', [])
            
            for update in updates:
                last_update_id = update['update_id']
                if 'message' in update and 'text' in update['message']:
                    msg_text = update['message']['text'].strip()
                    # Verify it's from the allowed user
                    if str(update['message']['chat']['id']) == str(CHAT_ID):
                        return msg_text
        except Exception as e:
            print(f"Polling error: {e}")
            
        time.sleep(10)
        
    return None

def parse_reply(reply_text, options_count=4):
    """Parse reply into choice or custom instruction."""
    text = reply_text.strip()
    if text.isdigit():
        val = int(text)
        if 1 <= val <= options_count:
            return {"type": "choice", "value": val}
    
    return {"type": "custom", "value": text}

def send_weekly_summary(actions_count, decisions_count, autonomous_count, escalations_count, top_actions):
    """Sends weekly intelligence summary."""
    try:
        import sys
        sys.path.insert(0, '/Users/aatifquamre/masterbot/qnt/memory')
        from memory_manager import load_memory
        total_logs = len(load_memory().get('action_log', []))
    except:
        total_logs = "unknown"

    actions_list = "\n".join([f"• {a}" for a in top_actions])
    
    text = (
        f"🧠 <b>QNT Weekly Intelligence Summary</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Autonomous actions taken: {actions_count}\n"
        f"Decisions made: {decisions_count}\n"
        f"  → Handled autonomously: {autonomous_count}\n"
        f"  → Escalated to you: {escalations_count}\n\n"
        f"<b>Top actions this week:</b>\n"
        f"{actions_list}\n\n"
        f"Memory log entries: {total_logs}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    try:
        requests.post(f"{API_URL}/sendMessage", json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)
    except:
        pass

if __name__ == "__main__":
    # Quick module test
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("Testing notify...")
        send_notify("Test Run", "Notifier module self-test active.")
