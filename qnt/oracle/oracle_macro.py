import os
import json
import requests
import yfinance as yf
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Machine-agnostic path setup
_BASE = Path(__file__).resolve().parent.parent.parent
load_dotenv(_BASE / '.env')

MACRO_STATE_FILE = _BASE / 'risk/macro_state.json'
MACRO_HISTORY_FILE = _BASE / 'risk/macro_history.json'

def fetch_dxy_change():
    """Fetches DXY daily percentage change from Yahoo Finance."""
    try:
        dxy = yf.Ticker("DX-Y.NYB")
        hist = dxy.history(period="2d")
        if len(hist) < 2:
            return 0.0
        
        prev_close = hist['Close'].iloc[-2]
        curr_price = hist['Close'].iloc[-1]
        pct_change = ((curr_price - prev_close) / prev_close) * 100
        return round(pct_change, 4)
    except Exception as e:
        print(f"Error fetching DXY: {e}")
        return 0.0

def fetch_binance_macro():
    """Fetches BTC/USDT Funding Rate and Open Interest from Binance."""
    try:
        fund_res = requests.get("https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT", timeout=5)
        funding_rate = float(fund_res.json().get('lastFundingRate', 0))
        
        oi_res = requests.get("https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT", timeout=5)
        open_interest = float(oi_res.json().get('openInterest', 0))
        
        return funding_rate, open_interest
    except Exception as e:
        print(f"Error fetching Binance macro: {e}")
        return 0.0, 0.0

def main():
    print(f"[{datetime.now()}] Starting Macro Oracle fetch...")
    
    dxy_change = fetch_dxy_change()
    funding_rate, open_interest = fetch_binance_macro()
    
    macro_state = {
        "timestamp": datetime.now(timezone.utc).isoformat() + 'Z',
        "dxy_24h_change": dxy_change,
        "btc_funding_rate": funding_rate,
        "btc_open_interest": open_interest,
        "status": "HEALTHY" if dxy_change != 0 else "DEGRADED"
    }
    
    os.makedirs(MACRO_STATE_FILE.parent, exist_ok=True)
    with open(MACRO_STATE_FILE, 'w') as f:
        json.dump(macro_state, f, indent=2)
        
    history = []
    if MACRO_HISTORY_FILE.exists():
        try:
            with open(MACRO_HISTORY_FILE, 'r') as f:
                history = json.load(f)
        except Exception as e:
            history = []
    
    history.append(macro_state)
    seen_ts = set()
    unique_history = []
    for entry in reversed(history):
        if entry['timestamp'] not in seen_ts:
            unique_history.append(entry)
            seen_ts.add(entry['timestamp'])
    
    history = list(reversed(unique_history))[-1000:]
    
    with open(MACRO_HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)
    
    print(f"Macro state updated: DXY {dxy_change:+.2f}%, Funding {funding_rate:.6f}")

    # Publish to NATS
    try:
        import sys
        sys.path.insert(0, str(_BASE / 'qnt'))
        from nats_publisher import publish_sync
        from nats_subjects import SUBJECTS
        publish_sync(SUBJECTS['MACRO'], macro_state)
        print("[NATS] Macro published to M1")
    except Exception as e:
        print(f"[NATS] Macro publish error: {e}")

if __name__ == "__main__":
    main()
