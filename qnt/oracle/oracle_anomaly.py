import os
import sys
import json
import sqlite3
import polars as pl
from datetime import datetime, timezone, timedelta

# Add paths
BASE_DIR = '/Users/aatifquamre/cipher'
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/memory'))

from memory_manager import load_memory, log_action
from qnt_notifier import send_notify, send_escalation

DB_PATH = os.path.join(BASE_DIR, 'user_data/tradesv3.sqlite')
SENTIMENT_JSON = os.path.join(BASE_DIR, 'sentiment/scores/current_score.json')
SENTIMENT_CSV = os.path.join(BASE_DIR, 'sentiment/scores/history.csv')

def check_funding_sentiment_divergence():
    """Detect when news/social sentiment disagrees with leverage (funding)."""
    try:
        with open(SENTIMENT_JSON, 'r') as f:
            data = json.load(f)
        
        funding = data.get('component_scores', {}).get('funding', 0)
        sentiment = data.get('score', 0)
        
        # Divergence threshold
        # High funding (>0.0002) means long leverage is high
        # Negative sentiment (< -0.2) means news is bearish
        if funding > 0.0002 and sentiment < -0.2:
            return {"divergence": True, "type": "BEARISH DIVERGENCE", "severity": "HIGH", 
                    "reason": "High long leverage despite bearish news (Long Squeeze risk)"}
        
        if funding < -0.0002 and sentiment > 0.2:
            return {"divergence": True, "type": "BULLISH DIVERGENCE", "severity": "HIGH", 
                    "reason": "High short leverage despite bullish news (Short Squeeze potential)"}
            
    except Exception as e: pass
    return {"divergence": False}

def check_fear_greed_extreme():
    """Detect contrarian signals from extreme Fear & Greed."""
    try:
        with open(SENTIMENT_JSON, 'r') as f:
            data = json.load(f)
        
        # raw value is normalized in our current pipeline to -1..1
        # so we need to reverse normalize to 0..100 if we want exact thresholds
        # but let's use the -1..1 scale: 15/100 -> -0.7, 85/100 -> 0.7
        val = data.get('component_scores', {}).get('feargreed', 0)
        
        if val <= -0.7:
            return {"extreme": True, "type": "EXTREME FEAR", "value": val}
        if val >= 0.7:
            return {"extreme": True, "type": "EXTREME GREED", "value": val}
    except Exception as e: pass
    return {"extreme": False}

def check_sentiment_velocity():
    """Detect rapid changes in sentiment (flash moves)."""
    try:
        df = pl.read_csv(SENTIMENT_CSV)
        if len(df) > 4: # 2 hours
            current = df.tail(1)["score"][0]
            old = df.tail(4)["score"][0]
            change = abs(current - old)
            
            if change > 0.5:
                return {"alert": True, "magnitude": change, "direction": "up" if current > old else "down"}
    except Exception as e: pass
    return {"alert": False}

def check_performance_divergence():
    """Check if strategy performance is decoupled from market sentiment."""
    try:
        conn = sqlite3.connect(DB_PATH)
        query = "SELECT close_date, profit_ratio FROM trades WHERE is_open=0 ORDER BY close_date DESC LIMIT 20"
        cursor = conn.cursor()
        rows = cursor.execute(query).fetchall()
        conn.close()
        
        df = pl.DataFrame(rows, schema=["close_date", "profit_ratio"])
        
        if len(df) < 10: return {"divergence": False}
        
        win_rate = (df.get_column('profit_ratio') > 0).sum() / len(df)
        
        with open(SENTIMENT_JSON, 'r') as f:
            sentiment = json.load(f).get('score', 0)
            
        if win_rate < 0.35 and sentiment > 0.2:
            return {"divergence": True, "reason": f"Low win rate ({win_rate*100:.0f}%) despite bullish sentiment"}
    except Exception as e: pass
    return {"divergence": False}

def run_all_anomaly_checks():
    """Run checks and notify if anomalies found."""
    anomalies = []
    
    div = check_funding_sentiment_divergence()
    if div['divergence']:
        anomalies.append(f"⚠️ {div['type']}: {div['reason']}")
        
    fg = check_fear_greed_extreme()
    if fg['extreme']:
        anomalies.append(f"🧠 {fg['type']} DETECTED: Value {fg['value']}")
        
    vel = check_sentiment_velocity()
    if vel['alert']:
        dir_emoji = "📈" if vel['direction'] == "up" else "📉"
        anomalies.append(f"🚨 SENTIMENT VELOCITY: {dir_emoji} {vel['magnitude']:.2f} in 2 hours")
        
    perf = check_performance_divergence()
    if perf['divergence']:
        anomalies.append(f"⚠️ PERFORMANCE DIVERGENCE: {perf['reason']}")
        
    if not anomalies:
        print("No anomalies detected.")
        return
        
    # Log and Notify
    report = "\n".join(anomalies)
    log_action("oracle_anomaly_detected", report)
    
    if len(anomalies) > 2:
        send_escalation(
            situation="Multiple market anomalies detected simultaneously.",
            options=["Pause bot for 24h", "Continue with 50% position size", "Maintain current settings"],
            recommendation="Pause bot for 24h — market is decoupling from strategies.",
            context=report
        )
    else:
        send_notify("Market Anomaly", report, level="WARN")

if __name__ == "__main__":
    run_all_anomaly_checks()
