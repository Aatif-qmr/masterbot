import os
import json
import time
import requests
import sys
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add memory dir to path for imports
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / 'qnt/memory'))
from memory_manager import load_memory, save_memory, log_action
from enhanced_bot import (
    TOKEN, CHAT_ID, API_URL, send_telegram_message, 
    send_main_menu, execute_command_raw, KEYBOARDS
)

def handle_command(text):
    """Executes system commands and returns output with inline keyboard options."""
    cmd_map = {
        "/status": "qnt-bot status",
        "/qnt_status": "qnt-bot status",
        "/backup": "qnt-backup run",
        "/skeptic": "qnt-skeptic stats",
        "/shadow": "qnt-shadow status",
        "/health": "python3 automation/health_check.py",
        "/logs": "tail -n 20 logs/supervisord.log",
        "/risk": "qnt-risk-check"
    }
    
    # Handle help/menu specifically
    if text in ["/start", "/help"]:
        help_text = """🚀 <b>MasterBot QNT Controller</b>
━━━━━━━━━━━━━━━━━━━━━
/status  - Overall system status
/health  - Run 11-point health audit
/skeptic - Skeptic Agent performance
/shadow  - M2 Shadow Hyperopt status
/backup  - Trigger Cloud/GDrive backup
/risk    - Current risk levels
/logs    - Recent system logs
/menu    - Interactive control panel
━━━━━━━━━━━━━━━━━━━━━
💡 Tip: Use inline buttons for faster access!"""
        return help_text, None
    
    if text == "/menu":
        return None, "main_menu"
    
    command = cmd_map.get(text.split()[0].lower())
    if not command:
        return None, None

    print(f"Executing command: {command}")
    try:
        # Run command from project root
        result = subprocess.run(
            command.split(), 
            capture_output=True, 
            text=True, 
            timeout=60,
            cwd=str(BASE_DIR)
        )
        
        output = result.stdout.strip() or result.stderr.strip()
        if not output:
            output = "Command executed with no output."
            
        # Clean output for Telegram (HTML)
        import html
        output = html.escape(output)
        
        response = f"🖥️ <b>{command}</b>\n<pre>{output[:3500]}</pre>"
        return response, None
    except Exception as e:
        return f"❌ <b>Error:</b> {str(e)}", None

def process_update(update):
    if 'message' not in update or 'text' not in update['message']:
        return

    msg = update['message']
    chat_id = str(msg['chat']['id'])
    text = msg['text'].strip()
    
    # Only listen to authorized chat
    if chat_id != str(CHAT_ID):
        return

    print(f"Received from Telegram: {text}")
    
    # Check if it's a command
    if text.startswith('/'):
        response, keyboard_type = handle_command(text)
        
        # Send menu if requested
        if keyboard_type == "main_menu":
            try:
                send_main_menu()
                log_action("telegram_menu_sent", f"Command: {text}")
                return
            except Exception as e:
                print(f"Error sending menu: {e}")
                return
        
        if response:
            try:
                requests.post(f"{API_URL}/sendMessage", json={
                    "chat_id": CHAT_ID,
                    "text": response,
                    "parse_mode": "HTML"
                })
                log_action("telegram_command_executed", f"Command: {text}")
                return
            except Exception as e:
                print(f"Error sending response: {e}")
                pass
    
    # Parse as reply to escalation (import parse_reply locally to avoid circular dependency)
    try:
        from enhanced_bot import EMOJI
        parsed = {"type": "custom", "value": text}  # Simplified parsing
        
        # Load memory to find what we are responding to
        data = load_memory()
        
        # Find last escalation that hasn't been replied to yet
        last_escalation = None
        if data.get('decisions'):
            # Decisions are appended, so last is newest
            for d in reversed(data['decisions']):
                if d.get('outcome') is None:
                    last_escalation = d
                    break
                    
        escalation_ts = last_escalation['timestamp'] if last_escalation else "unknown"
        
        # Add to pending_replies
        if 'pending_replies' not in data:
            data['pending_replies'] = []
            
        entry = {
            "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "raw_text": text,
            "parsed": parsed,
            "responded_to": escalation_ts,
            "processed": False
        }
        
        data['pending_replies'].append(entry)
        
        # Update the decision outcome if found
        if last_escalation:
            for d in data['decisions']:
                if d['timestamp'] == last_escalation['timestamp']:
                    exec_val = f"Choice {parsed['value']}" if parsed['type'] == 'choice' else parsed['value']
                    d['outcome'] = f"User instructed: {exec_val}"
                    break
                    
        save_memory(data)
        
        # Send acknowledgment
        ack_text = f"✅ Got it. Executing: <i>{text}</i>"
            
        try:
            requests.post(f"{API_URL}/sendMessage", json={
                "chat_id": CHAT_ID,
                "text": ack_text,
                "parse_mode": "HTML"
            })
        except:
            pass
            
        log_action(f"telegram_reply_received", f"User replied: {text} to escalation {escalation_ts}")
    except Exception as e:
        print(f"Error processing reply: {e}")

def main():
    print("Starting QNT Reply Listener...")
    offset = 0
    
    # Get initial offset to skip history
    try:
        res = requests.get(f"{API_URL}/getUpdates", params={"limit": 1}, timeout=10)
        updates = res.json().get('result', [])
        if updates:
            offset = updates[-1]['update_id'] + 1
    except:
        pass

    while True:
        try:
            res = requests.get(f"{API_URL}/getUpdates", params={
                "offset": offset,
                "timeout": 30
            }, timeout=40)
            
            if res.status_code == 200:
                updates = res.json().get('result', [])
                for update in updates:
                    process_update(update)
                    offset = update['update_id'] + 1
            else:
                print(f"Error polling: {res.status_code}")
                time.sleep(5)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Listener error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
