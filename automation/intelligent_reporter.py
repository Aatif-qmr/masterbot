import os
import sqlite3
import json
import requests
import subprocess
import pandas as pd
from datetime import datetime, timedelta, timezone
from tenacity import retry, stop_after_attempt, wait_exponential

from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Configuration
DB_FILES = [
    str(BASE_DIR / 'user_data' / 'micro.sqlite'),
    str(BASE_DIR / 'user_data' / 'scalp.sqlite'),
    str(BASE_DIR / 'user_data' / 'mean_reversion.sqlite'),
    str(BASE_DIR / 'user_data' / 'trend_follow.sqlite'),
    str(BASE_DIR / 'user_data' / 'daily.sqlite'),
    str(BASE_DIR / 'user_data' / 'swing.sqlite')
]
SENTIMENT_PATH = str(BASE_DIR / 'sentiment' / 'scores' / 'history.csv')
REPORTS_FOLDER_ID = '1Vdst3YI9wFFfFPurpVVGJfrA3y2aT9BI'
DEST_EMAIL = 'aatifqmr@gmail.com'

# API Keys from env
load_dotenv(BASE_DIR / '.env')

TELEGRAM_TOKEN = os.getenv('QNT_TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('QNT_TELEGRAM_CHAT_ID')

def gather_data():
    """Gathers all relevant data from Cipher databases and sentiment files."""
    total_trades = 0
    total_profit_abs = 0.0
    open_trades_list = []
    closed_trades_list = []
    by_strategy = {}
    
    for db_path in DB_FILES:
        if not os.path.exists(db_path): continue
            
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
            if not cursor.fetchone():
                conn.close()
                continue

            # Open trades
            cursor.execute("SELECT pair, strategy, open_date FROM trades WHERE is_open = 1")
            for row in cursor.fetchall():
                open_trades_list.append(f"{row['pair']} ({row['strategy']})")

            # Closed trades summary
            cursor.execute("SELECT COUNT(*), SUM(close_profit_abs) FROM trades WHERE is_open = 0")
            count, profit_abs = cursor.fetchone()
            if count:
                total_trades += count
                total_profit_abs += (profit_abs if profit_abs else 0.0)
            
            # Strategy Breakdown
            cursor.execute("SELECT strategy, COUNT(*) as count, SUM(close_profit_abs) as profit FROM trades WHERE is_open = 0 GROUP BY strategy")
            for row in cursor.fetchall():
                s = row['strategy']
                if s not in by_strategy: by_strategy[s] = {"trades": 0, "profit": 0.0}
                by_strategy[s]["trades"] += row['count']
                by_strategy[s]["profit"] += row['profit']

            conn.close()
        except Exception as e:
            print(f"Error reading {db_path}: {e}")

    # Sentiment
    sentiment_data = "N/A"
    if os.path.exists(SENTIMENT_PATH):
        try:
            df = pd.read_csv(SENTIMENT_PATH)
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_localize(None)
            last_week = df[df['timestamp'] >= (datetime.now() - timedelta(days=7))]
            if not last_week.empty:
                avg = last_week['score'].mean()
                sentiment_data = f"{avg:.3f} ({'BULLISH' if avg > 0.3 else 'BEARISH' if avg < -0.3 else 'NEUTRAL'})"
        except Exception as e:
            print(f"Sentiment reading error: {e}")

    return {
        "summary": {
            "total_trades": total_trades,
            "total_profit": f"{total_profit_abs:.2f} USDT",
            "open_trades_count": len(open_trades_list),
            "by_strategy": by_strategy
        },
        "market_sentiment": sentiment_data,
        "timestamp": datetime.now().isoformat()
    }

def generate_quant_report(data: dict) -> str:
    """Generates a detailed rule-based Senior Quant report from gathered data."""
    summary = data.get("summary", {})
    by_strategy = summary.get("by_strategy", {})
    
    # 1. Identify most profitable strategy
    best_strategy = "None"
    best_profit = -999999.0
    for strat, stats in by_strategy.items():
        profit = stats.get("profit", 0.0)
        if profit > best_profit:
            best_profit = profit
            best_strategy = strat
            
    best_strategy_str = f"**{best_strategy}** (Profit: `{best_profit:.2f}` USDT)" if best_strategy != "None" else "No active profitable strategies recorded."
    
    # 2. Risk suggestion based on sentiment
    sentiment_str = data.get("market_sentiment", "N/A")
    sentiment_score = 0.0
    if sentiment_str != "N/A":
        try:
            sentiment_score = float(sentiment_str.split()[0])
        except Exception:
            pass
            
    risk_action = "MAINTAIN NEUTRAL/BALANCED RISK STATE"
    risk_rationale = "Global sentiment is in a neutral range. Execute baseline position sizes and monitor key strategy boundaries."
    
    if sentiment_score > 0.3:
        risk_action = "DELEGATE DYNAMIC STAKE EXPANSION (INCREASE RISK)"
        risk_rationale = f"Global sentiment is highly bullish ({sentiment_score:.3f}). Expand trending/daily cross allocations and allow trend-following strategies full leverage parameters."
    elif sentiment_score < -0.3:
        risk_action = "DELEGATE DYNAMIC STAKE CONTRACTION (DECREASE RISK / ENFORCE HEDGE)"
        risk_rationale = f"Global sentiment is highly bearish ({sentiment_score:.3f}). Contraction phase active. Reduce maximum position slots to 1, enforce tight stoplosses, and prioritize BearScalp allocations."

    # 3. Formulate Cipher Directives (3 concise bullet points)
    directives = []
    # Directive 1 based on best strategy
    if best_strategy != "None":
        directives.append(f"Capitalize on **{best_strategy}** outperformance; consider routing 10% more allocation to this slot during the next rebalancing cycle.")
    else:
        directives.append("Prioritize dry-run capital preservation across all slots until a strategy demonstrates positive expectancy.")
        
    # Directive 2 based on sentiment
    if sentiment_score > 0.3:
        directives.append(f"Execute full size entries on TrendFollowV1 and DailyTrendV1. Ranging strategies should run with a 0.5x Kelly multiplier.")
    elif sentiment_score < -0.3:
        directives.append(f"Trigger safe-mode circuit breakers on MeanReversionV1 and SwingV1. Ensure BearScalpV1 is fully online to capture downside velocity.")
    else:
        directives.append("Enforce baseline capital allocations. Maintain standard stoploss settings and run ScalpV1/SwingV1 at standard risk parameters.")
        
    # Directive 3 general quant recommendation
    open_trades_count = summary.get("open_trades_count", 0)
    if open_trades_count >= 10:
        directives.append(f"Enforce strict correlation checks. With {open_trades_count} active slots, do not allow further asset overlap to prevent tail-risk clustering.")
    else:
        directives.append(f"Monitor cluster health and ensure Tailscale link connectivity to M1/M2 remains stable for automated SCP model updates.")

    report = f"""### Senior Quant Executive Assessment

#### 1. Detailed Performance Assessment
- **Total Trades executed**: `{summary.get("total_trades", 0)}`
- **Total Net Profit**: `{summary.get("total_profit", "0.00 USDT")}`
- **Active Open Trades**: `{open_trades_count}`
- **Most Profitable Strategy**: {best_strategy_str}

#### 2. Risk Allocation Decision
- **Action**: **{risk_action}**
- **Rationale**: {risk_rationale}
- **Market Sentiment context**: `{sentiment_str}`

#### 3. Cipher Directives
- {directives[0]}
- {directives[1]}
- {directives[2]}
"""
    return report

def notify(analysis, data):
    """Generates the Google Doc and sends Telegram notification."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    title = f"Cipher Intelligence Report - {date_str}"
    
    # 1. Google Doc via qnt CLI
    report_content = f"# {title}\n\nGenerated at: {data['timestamp']}\n\n## Analysis\n{analysis}\n\n## Raw Stats Summary\n{json.dumps(data['summary'], indent=2)}"
    doc_prompt = f"Create a Google Doc in folder '{REPORTS_FOLDER_ID}' with title '{title}' and this content: {report_content}. Then email a link to this doc to {DEST_EMAIL}."
    
    print("Syncing with Google Workspace...")
    try:
        subprocess.run(['qnt', '-p', doc_prompt], check=True)
    except Exception as e:
        print(f"Google Workspace sync failed: {e}. Proceeding with Telegram.")

    # 2. Telegram
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        short_analysis = analysis[:3500] # Telegram limit is 4096
        msg = f"🧠 *Cipher Intelligence Brief - {date_str}*\n\n{short_analysis}\n\n_Full report synced to Cipher_Vault_"
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={'chat_id': TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'})

if __name__ == "__main__":
    print("Cipher Intelligent Reporter starting...")
    data = gather_data()
    print("Data gathered. Synthesizing quantitative intelligence...")
    analysis = generate_quant_report(data)
    print("Analysis complete. Dispatching notifications...")
    notify(analysis, data)
    print("Done.")
