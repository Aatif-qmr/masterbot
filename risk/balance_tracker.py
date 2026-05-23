import json
import os
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path.home() / 'masterbot'
load_dotenv(BASE_DIR / '.env')

STATE_FILE = BASE_DIR / 'risk' / 'balance_state.json'
API_URL = f'http://{os.getenv("M1_TAILSCALE_IP", "127.0.0.1")}:8080/api/v1/balance'
USERNAME = os.getenv('API_USERNAME')
PASSWORD = os.getenv('API_PASSWORD')

def update_balance_state(current_balance: float):
    now = datetime.now(timezone.utc)
    today = now.strftime('%Y-%m-%d')
    # ISO week Monday
    monday = (now - timedelta(days=now.weekday())).strftime('%Y-%m-%d')
    
    state = {
        "start_of_day": current_balance,
        "start_of_week": current_balance,
        "last_seen_balance": current_balance,
        "last_updated": now.isoformat(),
        "day_date": today,
        "week_monday": monday
    }
    
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            old_state = json.load(f)
        
        # Keep old start_of_day if same day
        if old_state.get('day_date') == today:
            state['start_of_day'] = old_state['start_of_day']
            
        # Keep old start_of_week if same week
        if old_state.get('week_monday') == monday:
            state['start_of_week'] = old_state['start_of_week']
            
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)
    return state

from concurrent.futures import ThreadPoolExecutor, as_completed

def _fetch_balance(port, ip, user, pwd):
    url = f'http://{ip}:{port}/api/v1/balance'
    try:
        res = requests.get(url, auth=(user, pwd), timeout=1.5)
        if res.status_code == 200:
            return float(res.json().get('total', 0))
    except Exception as e:
        print(f"API Error on port {port}: {e}")
    return None

def get_balance_from_freqtrade_api():
    """
    Fetches COMBINED USDT balance from all 6 Freqtrade instances concurrently.
    Returns sum of all running instance balances.
    """
    total = 0.0
    found = 0
    ports = [8080, 8081, 8082, 8083, 8084, 8085]
    ip = os.getenv('M1_TAILSCALE_IP', '127.0.0.1')

    with ThreadPoolExecutor(max_workers=len(ports)) as executor:
        futures = {executor.submit(_fetch_balance, port, ip, USERNAME, PASSWORD): port for port in ports}
        for future in as_completed(futures):
            res = future.result()
            if res is not None:
                total += res
                found += 1
    
    return total if found > 0 else None

if __name__ == '__main__':
    balance = get_balance_from_freqtrade_api()
    if balance is not None:
        state = update_balance_state(balance)
        print(f"Balance state updated. Current: {balance} USDT")
        print(json.dumps(state, indent=4))
    else:
        print("Could not reach Freqtrade API or find USDT balance")
