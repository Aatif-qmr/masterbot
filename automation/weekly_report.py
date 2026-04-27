import os
import json
import sqlite3
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv('/Users/aatifquamre/masterbot/.env')

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

DB_PATH = '/Users/aatifquamre/masterbot/user_data/tradesv3.dryrun.sqlite'
REPORT_DIR = Path('/Users/aatifquamre/masterbot/logs/reports/')
REPORT_DIR.mkdir(parents=True, exist_ok=True)

SENTIMENT_PATH = '/Users/aatifquamre/masterbot/sentiment/scores/history.csv'
RISK_LOG = '/Users/aatifquamre/masterbot/logs/risk_manager.log'

def get_weekly_trades(db_path: str, days_ago_start=7, days_ago_end=0) -> list:
    if not os.path.exists(db_path):
        return []
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        now = datetime.now(timezone.utc)
        start_date = (now - timedelta(days=days_ago_start)).strftime('%Y-%m-%d %H:%M:%S')
        end_date = (now - timedelta(days=days_ago_end)).strftime('%Y-%m-%d %H:%M:%S')
        
        query = """
            SELECT * FROM trades 
            WHERE close_date >= ? AND close_date <= ? AND is_open = 0
            ORDER BY close_date DESC
        """
        cursor.execute(query, (start_date, end_date))
        trades = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return trades
    except Exception as e:
        print(f"DB Error: {e}")
        return []

def calculate_metrics(trades: list) -> dict:
    if not trades:
        return {
            "total_trades": 0, "winning_trades": 0, "losing_trades": 0, "win_rate_pct": 0.0,
            "total_profit_usdt": 0.0, "total_profit_pct": 0.0, "avg_profit_per_trade_usdt": 0.0,
            "best_trade_usdt": 0.0, "worst_trade_usdt": 0.0, "best_trade_pair": "N/A", "worst_trade_pair": "N/A",
            "total_fees_usdt": 0.0, "fees_as_pct_of_profit": 0.0, "by_strategy": {}
        }
    
    winning = [t for t in trades if t.get('profit_ratio', 0) > 0]
    total_profit = sum(t.get('profit_abs', 0) for t in trades)
    total_fees = sum(t.get('fee_open', 0) + t.get('fee_close', 0) for t in trades)
    
    best = max(trades, key=lambda x: x.get('profit_abs', 0))
    worst = min(trades, key=lambda x: x.get('profit_abs', 0))
    
    by_strat = {}
    for t in trades:
        s = t.get('strategy', 'Unknown')
        if s not in by_strat: by_strat[s] = {"trades": 0, "profit": 0.0, "wins": 0}
        by_strat[s]["trades"] += 1
        by_strat[s]["profit"] += t.get('profit_abs', 0)
        if t.get('profit_ratio', 0) > 0: by_strat[s]["wins"] += 1
        
    for s in by_strat:
        by_strat[s]["win_rate"] = round((by_strat[s]["wins"] / by_strat[s]["trades"]) * 100, 1)

    return {
        "total_trades": len(trades),
        "winning_trades": len(winning),
        "losing_trades": len(trades) - len(winning),
        "win_rate_pct": round((len(winning) / len(trades)) * 100, 1),
        "total_profit_usdt": round(total_profit, 2),
        "total_profit_pct": round(sum(t.get('profit_ratio', 0) for t in trades) * 100, 2),
        "avg_profit_per_trade_usdt": round(total_profit / len(trades), 2),
        "best_trade_usdt": round(best.get('profit_abs', 0), 2),
        "worst_trade_usdt": round(worst.get('profit_abs', 0), 2),
        "best_trade_pair": best.get('pair', 'N/A'),
        "worst_trade_pair": worst.get('pair', 'N/A'),
        "total_fees_usdt": round(total_fees, 4),
        "fees_as_pct_of_profit": round((total_fees / abs(total_profit) * 100), 2) if total_profit != 0 else 0,
        "by_strategy": by_strat
    }

def get_sentiment_correlation():
    if not os.path.exists(SENTIMENT_PATH): return None
    try:
        df = pd.read_csv(SENTIMENT_PATH)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        last_week = df[df['timestamp'] >= (datetime.now() - timedelta(days=7))]
        if last_week.empty: return None
        
        avg = last_week['final_score'].mean()
        return {
            "avg_sentiment_score": round(avg, 3),
            "sentiment_label": "BULLISH" if avg > 0.3 else "BEARISH" if avg < -0.3 else "NEUTRAL",
            "days_bullish": len(last_week[last_week['final_score'] > 0.3]),
            "days_bearish": len(last_week[last_week['final_score'] < -0.3]),
            "days_neutral": len(last_week[(last_week['final_score'] >= -0.3) & (last_week['final_score'] <= 0.3)])
        }
    except: return None

def get_risk_events():
    events = {"drawdown_warnings": 0, "drawdown_blocks": 0, "sentiment_blocks": 0, "risk_blocks": 0}
    if not os.path.exists(RISK_LOG): return events
    try:
        with open(RISK_LOG, 'r') as f:
            for line in f:
                if 'WARNING' in line and 'drawdown' in line: events['drawdown_warnings'] += 1
                if 'CRITICAL' in line and 'LIMIT HIT' in line: events['drawdown_blocks'] += 1
                if 'Sentiment BLOCK' in line: events['sentiment_blocks'] += 1
                if 'RISK BLOCK' in line: events['risk_blocks'] += 1
    except: pass
    return events

def get_qnt_intelligence(current, sentiment):
    import subprocess
    # Use a simpler prompt for faster response
    prompt = f"Act as MasterBot brain. Analyze: {current['total_profit_usdt']} USDT profit, {current['win_rate_pct']}% win rate. Sentiment: {sentiment.get('avg_sentiment_score', 'N/A')}. Give exactly 2 sentences of tactical advice."
    try:
        result = subprocess.run(
            ['qnt', '-p', prompt, '--output-format', 'text'],
            capture_output=True, text=True, timeout=60, cwd='/Users/aatifquamre/masterbot'
        )
        if result.returncode == 0 and result.stdout.strip():
            # Extract first two sentences to be safe
            text = result.stdout.strip()
            sentences = text.split('.')
            return '.'.join(sentences[:2]) + '.'
    except:
        pass
    return "Intelligence node busy. Continuing with standard protocols."

def get_qnt_weekly_brief() -> str:
    """
    Ask qnt for a market intelligence summary
    to append to the weekly Telegram report.
    Timeout after 60 seconds — report sends
    even if qnt is slow or unavailable.
    """
    import subprocess

    try:
        result = subprocess.run(
            ['qnt', '-p',
             'Generate a concise weekly market '
             'intelligence summary for MasterBot. '
             'Cover: overall market sentiment this week, '
             'any major crypto events or news, '
             'funding rate trend, and one sentence on '
             'what to watch next week. '
             'Maximum 150 words. Plain text only.'],
            capture_output=True,
            text=True,
            timeout=60,
            cwd='/Users/aatifquamre/masterbot'
        )
        if result.stdout.strip():
            return result.stdout.strip()
        return "qnt market brief unavailable this week."
    except Exception as e:
        return f"qnt brief error: {str(e)[:80]}"

def format_telegram_report(current, previous, sentiment, risk, intel, week_start, week_end, qnt_brief):
    next_monday = (datetime.now() + timedelta(days=(7 - datetime.now().weekday()))).strftime('%Y-%m-%d')
    
    if current['total_trades'] == 0:
        perf_str = "No trades closed this week."
    else:
        perf_str = (f"Trades: {current['total_trades']} ({current['winning_trades']}W / {current['losing_trades']}L)\n"
                    f"Win Rate: {current['win_rate_pct']}%\n"
                    f"Net P&L: {current['total_profit_usdt']:+} USDT\n"
                    f"Avg per trade: {current['avg_profit_per_trade_usdt']:+} USDT\n"
                    f"Fees paid: {current['total_fees_usdt']} USDT")

    strat_str = ""
    for name, data in current['by_strategy'].items():
        strat_str += f"• {name} | {data['trades']} trades | {data['profit']:+.2f} | {data['win_rate']}%\n"

    sent_str = "No data"
    if sentiment:
        sent_str = (f"Avg Score: {sentiment['avg_sentiment_score']} ({sentiment['sentiment_label']})\n"
                    f"Bullish: {sentiment['days_bullish']} | Neutral: {sentiment['days_neutral']} | Bearish: {sentiment['days_bearish']}")

    comp_trades = f"{current['total_trades']} vs {previous['total_trades']}"
    wr_arrow = "↑" if current['win_rate_pct'] > previous['win_rate_pct'] else "↓" if current['win_rate_pct'] < previous['win_rate_pct'] else "→"
    pl_arrow = "↑" if current['total_profit_usdt'] > previous['total_profit_usdt'] else "↓"

    return f"""📈 MasterBot Weekly Report
Week: {week_start} → {week_end}
──────────────────────

🧠 QNT Analysis
{intel}

💰 Performance
{perf_str}

🏆 Best Trade: {current['best_trade_usdt']:+.2f} USDT ({current['best_trade_pair']})
💔 Worst Trade: {current['worst_trade_usdt']:.2f} USDT ({current['worst_trade_pair']})

📊 vs Last Week
Trades: {comp_trades}
Win Rate: {current['win_rate_pct']}% vs {previous['win_rate_pct']}% {wr_arrow}
P&L: {current['total_profit_usdt']:.2f} vs {previous['total_profit_usdt']:.2f} USDT {pl_arrow}

🤖 Strategy Breakdown
{strat_str if strat_str else 'No strategy data available.'}

🧠 Sentiment This Week
{sent_str}

🛡️ Risk Events
Drawdown warnings: {risk['drawdown_warnings']}
Entry blocks: {risk['risk_blocks']}
Sentiment blocks: {risk['sentiment_blocks']}

🧠 QNT Intelligence Brief
{qnt_brief}

──────────────────────
Mode: PAPER TRADING
Next report: Monday {next_monday}
"""

def save_html_report(metrics, filename):
    path = REPORT_DIR / filename
    html = f"""
    <html><body style='font-family: sans-serif; padding: 20px;'>
    <h2>MasterBot Weekly Performance</h2>
    <table border='1' cellpadding='10' style='border-collapse: collapse;'>
    <tr style='background: #eee;'><td>Metric</td><td>Value</td></tr>
    <tr><td>Total Trades</td><td>{metrics['total_trades']}</td></tr>
    <tr><td>Win Rate</td><td>{metrics['win_rate_pct']}%</td></tr>
    <tr><td>Net P&L</td><td>{metrics['total_profit_usdt']} USDT</td></tr>
    <tr><td>Best Trade</td><td>{metrics['best_trade_usdt']} ({metrics['best_trade_pair']})</td></tr>
    <tr><td>Worst Trade</td><td>{metrics['worst_trade_usdt']} ({metrics['worst_trade_pair']})</td></tr>
    </table>
    </body></html>
    """
    with open(path, 'w') as f: f.write(html)

if __name__ == '__main__':
    today = datetime.now(timezone.utc)
    week_start, week_end = (today - timedelta(days=7)).strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')
    
    trades = get_weekly_trades(DB_PATH, 7, 0)
    prev_trades = get_weekly_trades(DB_PATH, 14, 7)
    
    curr_metrics = calculate_metrics(trades)
    prev_metrics = calculate_metrics(prev_trades)
    
    sentiment = get_sentiment_correlation()
    risk = get_risk_events()
    intel = get_qnt_intelligence(curr_metrics, sentiment or {})
    qnt_brief = get_qnt_weekly_brief()
    
    report = format_telegram_report(curr_metrics, prev_metrics, sentiment, risk, intel, week_start, week_end, qnt_brief)
    
    res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={'chat_id': TELEGRAM_CHAT_ID, 'text': report})
    print("✅ Telegram report sent" if res.status_code == 200 else f"❌ Failed: {res.text}")
    
    save_html_report(curr_metrics, f"weekly_report_{today.strftime('%Y%m%d')}.html")
