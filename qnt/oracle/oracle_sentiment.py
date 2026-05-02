import os
import sys
import json
import pandas as pd
from datetime import datetime, timezone, timedelta

# Add paths
BASE_DIR = '/Users/aatifquamre/masterbot'
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/memory'))

from memory_manager import load_memory, log_action
from qnt_notifier import send_notify

SENTIMENT_JSON = os.path.join(BASE_DIR, 'sentiment/scores/current_score.json')
SENTIMENT_CSV = os.path.join(BASE_DIR, 'sentiment/scores/history.csv')

def get_current_sentiment():
    """Read current score and breakdown."""
    try:
        with open(SENTIMENT_JSON, 'r') as f:
            return json.load(f)
    except:
        return None

def explain_sentiment():
    """Generate plain English explanation of the current sentiment."""
    data = get_current_sentiment()
    if not data:
        return "Sentiment data unavailable."

    score = data.get('score', 0)
    components = data.get('component_scores', {})
    weights = data.get('weights', {})
    
    regime = "NEUTRAL"
    if score >= 0.3: regime = "BULLISH"
    elif score <= -0.3: regime = "BEARISH"

    # Simple logic to find the biggest driver
    driver_name = "Mixed"
    max_impact = 0
    for name, s in components.items():
        impact = abs(s * weights.get(name, 0))
        if impact > max_impact:
            max_impact = impact
            driver_name = name

    explanation = ""
    if score > 0.5:
        explanation = f"Strong bullish momentum across major indicators, led by {driver_name} activity."
    elif score > 0.1:
        explanation = f"Cautious optimism in the market. {driver_name} is currently the primary positive influence."
    elif score < -0.5:
        explanation = f"Significant market fear detected. {driver_name} signals suggest heavy selling pressure or high uncertainty."
    elif score < -0.1:
        explanation = f"Market showing bearish tendencies, primarily driven by {driver_name} sentiment."
    else:
        explanation = "Market is in a balanced, range-bound state with no clear directional bias from news or funding."

    # Trend detection
    trend_str = "STABLE"
    try:
        df = pd.read_csv(SENTIMENT_CSV)
        if len(df) > 12: # ~6 hours of 30min data
            old_score = df.iloc[-12]['score']
            diff = score - old_score
            if diff > 0.2: trend_str = "IMPROVING"
            elif diff < -0.2: trend_str = "DECLINING"
    except: pass

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    output = [
        f"🧠 QNT Sentiment Analysis — {now}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Overall Score: {score:.3f} → {regime}",
        "",
        "Source Breakdown:",
        f"Reddit:         {components.get('reddit', 0):.2f} ({weights.get('reddit',0)*100:.0f}% weight)",
        f"CoinGecko:      {components.get('coingecko', 0):.2f} ({weights.get('coingecko',0)*100:.0f}% weight)",
        f"Fear & Greed:   {components.get('feargreed', 0):.2f} ({weights.get('feargreed',0)*100:.0f}% weight)",
        f"Funding Rate:   {components.get('funding', 0):.4f} ({weights.get('funding',0)*100:.0f}% weight)",
        "",
        "Why this score:",
        explanation,
        "",
        "Bot Impact:",
        f"MeanReversionV1: {'TRADING' if score >= -0.3 else 'PAUSED'} (needs > -0.3)",
        f"TrendFollowV1:   {'TRADING' if score >= 0.3 else 'PAUSED'} (needs > +0.3)",
        "",
        f"Trend (last 6h): {trend_str}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    return "\n".join(output)

def detect_sentiment_shift():
    """Detect significant moves in sentiment over 6 hours."""
    current = get_current_sentiment()
    if not current: return {"shifted": False}
    
    score = current.get('score', 0)
    
    try:
        df = pd.read_csv(SENTIMENT_CSV)
        if len(df) > 12:
            old_score = df.iloc[-12]['score']
            magnitude = abs(score - old_score)
            
            if magnitude >= 0.3:
                return {
                    "shifted": True,
                    "direction": "up" if score > old_score else "down",
                    "magnitude": round(magnitude, 3),
                    "old": round(old_score, 3),
                    "new": round(score, 3)
                }
    except: pass
    
    return {"shifted": False}

def check_and_act():
    """30-minute check for sentiment shifts."""
    shift = detect_sentiment_shift()
    if shift.get('shifted'):
        regime = "BULLISH" if shift['new'] >= 0.3 else "BEARISH" if shift['new'] <= -0.3 else "NEUTRAL"
        
        # Decide if we notify
        should_notify = False
        if shift['magnitude'] >= 0.4: should_notify = True
        
        # Check if threshold crossed
        if (shift['old'] > -0.3 and shift['new'] <= -0.3) or (shift['old'] < 0.3 and shift['new'] >= 0.3):
            should_notify = True
            
        if should_notify:
            reason = "Sentiment dropped sharply" if shift['direction'] == "down" else "Sentiment surged upward"
            msg = (
                f"📊 Sentiment shifted {shift['new'] - shift['old']:+.2f} in 6 hours.\n"
                f"New score: {shift['new']} ({regime})\n"
                f"{reason}.\n"
                f"Bot impact: MeanReversion {'PAUSED' if shift['new'] < -0.3 else 'TRADING'}, "
                f"TrendFollow {'TRADING' if shift['new'] >= 0.3 else 'PAUSED'}."
            )
            send_notify("Sentiment Shift", msg)
            log_action("sentiment_shift_detected", f"Shift: {shift['magnitude']} to {regime}")

if __name__ == "__main__":
    print(explain_sentiment())
