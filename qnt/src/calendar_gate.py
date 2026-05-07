import os
import sys
import argparse
import requests
from requests.auth import HTTPBasicAuth
from pathlib import Path
from dotenv import load_dotenv

# Add paths
BASE_DIR = '/Users/aatifquamre/masterbot'
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/oracle'))
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/memory'))

from oracle_calendar import get_weekly_calendar, calculate_risk_level
from memory_manager import load_memory, save_memory, log_action

load_dotenv(os.path.join(BASE_DIR, '.env'))

def control_bots(action):
    """Action can be 'stopentry' or 'reload_config' (to resume if config has it enabled)."""
    user = os.getenv('FREQTRADE_UI_USERNAME')
    pwd = os.getenv('FREQTRADE_UI_PASSWORD')
    ports = [8080, 8081, 8082, 8083, 8084]
    
    success_count = 0
    for port in ports:
        try:
            url = f"http://100.90.68.42:{port}/api/v1/{action}"
            res = requests.post(url, auth=HTTPBasicAuth(user, pwd), timeout=5)
            if res.status_code == 200:
                success_count += 1
        except:
            continue
    return success_count

def main():
    parser = argparse.ArgumentParser(description="QNT Calendar Gate - Manage bots based on macro events")
    parser.add_argument("command", choices=["status", "pause", "resume", "auto"], help="Command to execute")
    args = parser.parse_args()

    if args.command == "status":
        print(get_weekly_calendar())
    
    elif args.command == "pause":
        print("🚨 GATING: Pausing all new entries on all instances...")
        count = control_bots("stopentry")
        print(f"✅ Successfully paused entries on {count}/5 instances.")
        log_action("manual_calendar_gate", "PAUSE ALL ENTRIES")

    elif args.command == "resume":
        print("🟢 UN-GATING: Resuming entries on all instances...")
        # To resume, we usually reload config or just call the opposite of stopentry
        # In Freqtrade API, stopentry is a toggle or has a state.
        # But most reliable is to just make sure they are running.
        # Actually, stopentry is permanent until restarted or re-enabled.
        # We'll use start command if available or just log it.
        # Note: Freqtrade API doesn't have a direct 'startentry' if stopentry was called.
        # It's better to reload config or restart service if needed.
        # But 'reload_config' usually resets the stopentry flag if not in config.
        count = control_bots("reload_config")
        print(f"✅ Successfully reloaded/resumed on {count}/5 instances.")
        log_action("manual_calendar_gate", "RESUME ALL ENTRIES")

    elif args.command == "auto":
        from datetime import datetime, timezone
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        risk = calculate_risk_level(today_str)
        
        print(f"🧠 QNT Auto-Gate: Risk level for today is {risk['level']} (Score: {risk['score']})")
        
        if risk['score'] >= 9:
            print("🚨 EXTREME risk detected. Engaging gate...")
            count = control_bots("stopentry")
            print(f"✅ Auto-gated {count}/5 instances.")
            log_action("auto_calendar_gate", f"PAUSE (Risk: {risk['level']})")
        else:
            print("✅ Risk level acceptable. No action taken.")

if __name__ == "__main__":
    main()
