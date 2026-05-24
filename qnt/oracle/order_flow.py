#!/usr/bin/env python3
"""
Order Flow Oracle: Fetches Liquidation and CVD data.
Runs on M2, pushes state to M1.
"""
import requests
import json
from pathlib import Path
from datetime import datetime, timedelta

# Configuration
STATE_FILE = Path("/Users/azmatsaif/cipher/qnt/oracle/order_flow_state.json")
BINANCE_LIQ_URL = "https://fapi.binance.com/futures/data/topLongShortAccountRatio"

def fetch_binance_liquidation_ratio(symbol="BTCUSDT"):
    """
    Fetches Long/Short ratio and estimates liquidation pressure.
    """
    try:
        # Period: 5m (matches MicroScalp context), Limit: 12 (last hour)
        res = requests.get(BINANCE_LIQ_URL, params={"symbol": symbol, "period": "5m", "limit": 12}, timeout=10)
        data = res.json()
        if not isinstance(data, list): return {"ratio": 1.0, "trend": "neutral"}

        # Calculate average ratio
        ratios = [float(d['longShortRatio']) for d in data]
        if not ratios: return {"ratio": 1.0, "trend": "neutral"}
        
        avg_ratio = sum(ratios) / len(ratios)
        
        # Interpret: High ratio (> 1.5) = Too many longs = Potential long squeeze (Bearish)
        # Low ratio (< 0.7) = Too many shorts = Potential short squeeze (Bullish)
        trend = "neutral"
        if avg_ratio > 1.5: trend = "long_squeeze_risk"
        elif avg_ratio < 0.8: trend = "short_squeeze_risk"

        return {"ratio": avg_ratio, "trend": trend, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"error": str(e)}

def fetch_cvd_divergence(symbol="BTCUSDT"):
    """
    Simplified CVD check using volume/price divergence logic.
    """
    try:
        # Check recent price vs volume momentum
        res = requests.get(f"https://api.binance.com/api/v3/klines", 
                           params={"symbol": symbol, "interval": "15m", "limit": 4}, timeout=10)
        data = res.json()
        
        # Simple logic: Price up + Volume down = Divergence (Bearish)
        last_price = float(data[-1][4])
        prev_price = float(data[0][4])
        last_vol = float(data[-1][5])
        avg_vol = sum(float(k[5]) for k in data) / len(data)
        
        if last_price > prev_price and last_vol < (avg_vol * 0.5):
            return "bearish_divergence"
        elif last_price < prev_price and last_vol < (avg_vol * 0.5):
            return "bullish_divergence"
            
        return "neutral"
    except Exception as e:
        return "neutral"

def update_state():
    """Fetch and save order flow state."""
    state = {
        "last_updated": datetime.now().isoformat(),
        "liquidation": fetch_binance_liquidation_ratio(),
        "cvd_divergence": fetch_cvd_divergence()
    }
    
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    print(f"[{state['last_updated']}] Order Flow State Updated.")

if __name__ == "__main__":
    update_state()
