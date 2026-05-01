import os
import json
import time
import requests
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add memory dir to path for imports
sys.path.insert(0, '/Users/aatifquamre/masterbot/qnt/memory')
from memory_manager import load_memory, save_memory, log_action
from qnt_notifier import parse_reply, TOKEN, CHAT_ID, API_URL

def process_update(update):
    if 'message' not in update or 'text' not in update['message']:
        return

    msg = update['message']
    chat_id = str(msg['chat']['id'])
    text = msg['text'].strip()
    
    # Only listen to authorized chat
    if chat_id != str(CHAT_ID):
        return

    print(f"Received reply: {text}")
    
    # Parse reply
    parsed = parse_reply(text)
    
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
    exec_desc = ""
    if parsed['type'] == 'choice':
        # Try to get the option text from the decision
        if last_escalation and 'options_presented' in last_escalation:
            idx = parsed['value'] - 1
            if 0 <= idx < len(last_escalation['options_presented']):
                exec_desc = f" [{last_escalation['options_presented'][idx]}]"
        
        ack_text = f"✅ Got it. Executing: <b>Option {parsed['value']}</b>{exec_desc}"
    else:
        ack_text = f"✅ Got it. Executing custom instruction: <i>{text}</i>"
        
    try:
        requests.post(f"{API_URL}/sendMessage", json={
            "chat_id": CHAT_ID,
            "text": ack_text,
            "parse_mode": "HTML"
        })
    except:
        pass
        
    log_action(f"telegram_reply_received", f"User replied: {text} to escalation {escalation_ts}")

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
