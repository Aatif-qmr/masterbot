import os
import json
import sqlite3
import requests
import pandas as pd
import subprocess
import shutil
from datetime import datetime, timedelta, timezone

def get_qnt_path():
    path = shutil.which('qnt')
    if path and os.path.exists(path):
        return path
    for p in ['/Users/aatifquamre/masterbot/qnt/bin/qnt', '/Users/aatifquamre/.nvm/versions/node/v20.20.2/bin/qnt']:
        if os.path.exists(p): return p
    return 'qnt'
from pathlib import Path
from dotenv import load_dotenv

load_dotenv('/Users/aatifquamre/masterbot/.env')

TELEGRAM_TOKEN = os.getenv('QNT_TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('QNT_TELEGRAM_CHAT_ID')

DB_PATHS = [
    '/Users/aatifquamre/masterbot/user_data/mean_reversion.sqlite',
    '/Users/aatifquamre/masterbot/user_data/trend_follow.sqlite',
    '/Users/aatifquamre/masterbot/user_data/scalp.sqlite',
    '/Users/aatifquamre/masterbot/user_data/swing.sqlite',
    '/Users/aatifquamre/masterbot/user_data/daily.sqlite',
    '/Users/aatifquamre/masterbot/user_data/micro.sqlite'
]
REPORT_DIR = Path('/Users/aatifquamre/masterbot/logs/reports/')
REPORT_DIR.mkdir(parents=True, exist_ok=True)

SENTIMENT_PATH = '/Users/aatifquamre/masterbot/sentiment/scores/history.csv'
RISK_LOG = '/Users/aatifquamre/masterbot/logs/risk_manager.log'

def get_weekly_trades(db_paths: list, days_ago_start=7, days_ago_end=0) -> list:
    all_trades = []
    
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days_ago_start)).strftime('%Y-%m-%d %H:%M:%S')
    end_date = (now - timedelta(days=days_ago_end)).strftime('%Y-%m-%d %H:%M:%S')

    for db_path in db_paths:
        if not os.path.exists(db_path):
            continue
        
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
                SELECT *, 
                       close_profit AS profit_ratio, 
                       close_profit_abs AS profit_abs
                FROM trades 
                WHERE close_date >= ? AND close_date <= ? AND is_open = 0
                ORDER BY close_date DESC
            """
            cursor.execute(query, (start_date, end_date))
            trades = [dict(row) for row in cursor.fetchall()]
            all_trades.extend(trades)
            conn.close()
        except Exception as e:
            print(f"DB Error ({os.path.basename(db_path)}): {e}")
            
    return all_trades

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
        
        avg = last_week['score'].mean() # Fixed column name from final_score to score
        return {
            "avg_sentiment_score": round(avg, 3),
            "sentiment_label": "BULLISH" if avg > 0.3 else "BEARISH" if avg < -0.3 else "NEUTRAL",
            "days_bullish": len(last_week[last_week['score'] > 0.3]),
            "days_bearish": len(last_week[last_week['score'] < -0.3]),
            "days_neutral": len(last_week[(last_week['score'] >= -0.3) & (last_week['score'] <= 0.3)])
        }
    except: return None

def get_risk_events():
    events = {"drawdown_warnings": 0, "drawdown_blocks": 0, "sentiment_blocks": 0, "risk_blocks": 0}
    if not os.path.exists(RISK_LOG): return events
    
    now = datetime.now()
    one_week_ago = now - timedelta(days=7)
    
    try:
        with open(RISK_LOG, 'r') as f:
            for line in f:
                line_upper = line.upper()
                if 'WARNING' in line_upper and 'DRAWDOWN' in line_upper: events['drawdown_warnings'] += 1
                if 'LIMIT HIT' in line_upper: events['drawdown_blocks'] += 1
                if 'SENTIMENT BLOCK' in line_upper: events['sentiment_blocks'] += 1
                if 'RISK BLOCK' in line_upper or 'RISK CHECKS BLOCKED' in line_upper: events['risk_blocks'] += 1
    except: pass
    return events

def get_qnt_intelligence(current, sentiment):
    prompt = f"Act as MasterBot brain. Analyze: {current['total_profit_usdt']} USDT profit, {current['win_rate_pct']}% win rate. Sentiment: {sentiment.get('avg_sentiment_score', 'N/A')}. Give exactly 2 sentences of tactical advice."
    qnt_path = get_qnt_path()
    try:
        result = subprocess.run(
            [qnt_path, '-m', 'flash', '-p', prompt, '--output-format', 'text'],
            capture_output=True, text=True, timeout=180, cwd='/Users/aatifquamre/masterbot'
        )
        if result.returncode == 0 and result.stdout.strip():
            text = result.stdout.strip()
            sentences = text.split('.')
            return '.'.join(sentences[:2]) + '.'
    except:
        pass
    return "Intelligence node busy. Continuing with standard protocols."

def get_qnt_weekly_brief() -> str:
    qnt_path = get_qnt_path()
    try:
        result = subprocess.run(
            [qnt_path, '-m', 'flash', '-p',
             'Generate a concise weekly market intelligence summary. Maximum 100 words.'],
            capture_output=True, text=True, timeout=180, cwd='/Users/aatifquamre/masterbot'
        )
        return result.stdout.strip() or "Empty response"
    except Exception as e:
        return f"qnt brief error: {str(e)[:80]}"

def get_m2_resource_report() -> str:
    try:
        M2_IP = os.getenv('M2_TAILSCALE_IP')
        cmd = ['ssh', f"azmatsaif@{M2_IP}", 
               '/Users/azmatsaif/masterbot/venv/bin/python /Users/azmatsaif/masterbot/qnt/shadow/resource_monitor.py']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout.strip()
    except:
        return "M2 resource report unavailable"

def get_skeptic_summary() -> str:
    """Fetches skeptic agent stats for the report."""
    try:
        result = subprocess.run(
            ['/Users/aatifquamre/masterbot/venv/bin/python', '-c',
             'import sys; sys.path.insert(0, "/Users/aatifquamre/masterbot/qnt/agents");'
             'sys.path.insert(0, "/Users/aatifquamre/masterbot/qnt/memory");'
             'from trade_gate import get_skeptic_stats;'
             'print(get_skeptic_stats())'],
            capture_output=True, text=True, timeout=15
        )
        return result.stdout.strip()
    except:
        return "Skeptic stats unavailable"

def format_telegram_report(current, previous, sentiment, risk, intel, week_start, week_end, qnt_brief):
    next_monday = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    m2_report = get_m2_resource_report()
    skeptic_summary = get_skeptic_summary()

    perf_str = f"Net P&L: {current['total_profit_usdt']} USDT ({current['total_profit_pct']}% of ${current.get('cluster_balance', 50000):,.0f} portfolio)"
    comp_trades = f"{current['total_trades']} vs {previous['total_trades']}"
    
    wr_arrow = "📈" if current['win_rate_pct'] >= previous['win_rate_pct'] else "📉"
    pl_arrow = "📈" if current['total_profit_usdt'] >= previous['total_profit_usdt'] else "📉"
    
    strat_str = ""
    for s, data in current['by_strategy'].items():
        strat_str += f"• {s}: {data['trades']} trades, {data['profit']:.2f} USDT, {data['win_rate']}% WR\n"

    sent_str = f"Avg: {sentiment.get('avg_sentiment_score', 'N/A')} ({sentiment.get('sentiment_label', 'N/A')})"

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

🔍 Skeptic Agent
{skeptic_summary}

🧠 QNT Intelligence Brief
{qnt_brief}

🖥️ M2 RESOURCE REPORT
{m2_report}

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
    </table>
    </body></html>
    """
    with open(path, 'w') as f: f.write(html)

if __name__ == '__main__':
    today = datetime.now(timezone.utc)
    week_start, week_end = (today - timedelta(days=7)).strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')
    
    trades = get_weekly_trades(DB_PATHS, 7, 0)
    prev_trades = get_weekly_trades(DB_PATHS, 14, 7)
    
    curr_metrics = calculate_metrics(trades)
    prev_metrics = calculate_metrics(prev_trades)
    
    sentiment = get_sentiment_correlation()
    risk = get_risk_events()
    intel = get_qnt_intelligence(curr_metrics, sentiment or {})
    qnt_brief = get_qnt_weekly_brief()
    
    report = format_telegram_report(curr_metrics, prev_metrics, sentiment or {}, risk, intel, week_start, week_end, qnt_brief)
    
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={'chat_id': TELEGRAM_CHAT_ID, 'text': report})
        print("✅ Telegram report sent" if res.status_code == 200 else f"❌ Failed: {res.text}")
    
    save_html_report(curr_metrics, f"weekly_report_{today.strftime('%Y%m%d')}.html")
