import os
import json
import sqlite3
import requests
import pandas as pd
import subprocess
import shutil
from datetime import datetime, timedelta, timezone

from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

def _claude_prompt(prompt: str, max_tokens: int = 200) -> str:
    """Call Claude API directly for intelligence summaries."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return "Intelligence unavailable: ANTHROPIC_API_KEY not set."
    try:
        import urllib.request
        import json as _json
        payload = _json.dumps({
            "model": "claude-3-5-haiku-latest",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = _json.loads(resp.read())
            return data["content"][0]["text"].strip()
    except Exception as e:
        return f"Intelligence error: {str(e)[:80]}"

load_dotenv(BASE_DIR / '.env')

TELEGRAM_TOKEN = os.getenv('QNT_TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('QNT_TELEGRAM_CHAT_ID')

DB_PATHS = [
    str(BASE_DIR / 'user_data/mean_reversion.sqlite'),
    str(BASE_DIR / 'user_data/trend_follow.sqlite'),
    str(BASE_DIR / 'user_data/scalp.sqlite'),
    str(BASE_DIR / 'user_data/swing.sqlite'),
    str(BASE_DIR / 'user_data/daily.sqlite'),
    str(BASE_DIR / 'user_data/micro.sqlite')
]
REPORT_DIR = BASE_DIR / 'logs/reports/'
REPORT_DIR.mkdir(parents=True, exist_ok=True)

SENTIMENT_PATH = str(BASE_DIR / 'sentiment/scores/history.csv')
RISK_LOG = str(BASE_DIR / 'logs/risk_manager.log')

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
    except Exception as e:
        print(f"Sentiment error: {e}")
        return None

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
    except Exception as e:
        print(f"Risk log parsing error: {e}")
    return events

def get_qnt_intelligence(current, sentiment):
    prompt = (
        f"Act as Cipher brain. Analyze: {current['total_profit_usdt']} USDT profit, "
        f"{current['win_rate_pct']}% win rate. "
        f"Sentiment: {sentiment.get('avg_sentiment_score', 'N/A')}. "
        f"Give exactly 2 sentences of tactical advice."
    )
    return _claude_prompt(prompt, max_tokens=100)

def get_qnt_weekly_brief() -> str:
    return _claude_prompt(
        "Generate a concise weekly crypto market intelligence summary. Maximum 100 words.",
        max_tokens=150,
    )

def get_m2_resource_report() -> str:
    try:
        M2_IP = os.getenv('M2_TAILSCALE_IP')
        cmd = ['ssh', f"azmatsaif@{M2_IP}", 
               '/Users/azmatsaif/cipher/venv/bin/python /Users/azmatsaif/cipher/qnt/shadow/resource_monitor.py']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout.strip()
    except Exception as e:
        return f"M2 resource report unavailable: {e}"

def get_strategy_win_rate_trend(db_paths: list, weeks: int = 4) -> dict:
    """
    Returns per-strategy win rate for each of the last `weeks` weeks.
    Result: {strategy: [wr_oldest, ..., wr_last_week, wr_this_week]}
    Each value is a float 0-100 or None if no trades that week.
    """
    now = datetime.now(timezone.utc)
    trend = {}

    for db_path in db_paths:
        if not os.path.exists(db_path):
            continue
        try:
            conn = sqlite3.connect(db_path)
            for w in range(weeks, -1, -1):  # weeks ago → this week (0)
                week_start = (now - timedelta(days=(w + 1) * 7)).strftime('%Y-%m-%d %H:%M:%S')
                week_end   = (now - timedelta(days=w * 7)).strftime('%Y-%m-%d %H:%M:%S')
                rows = conn.execute(
                    "SELECT strategy, close_profit FROM trades "
                    "WHERE is_open=0 AND close_date >= ? AND close_date < ?",
                    (week_start, week_end)
                ).fetchall()
                for strategy, profit in rows:
                    if strategy not in trend:
                        trend[strategy] = [None] * (weeks + 1)
                    idx = weeks - w
                    if trend[strategy][idx] is None:
                        trend[strategy][idx] = {'wins': 0, 'total': 0}
                    trend[strategy][idx]['total'] += 1
                    if profit and profit > 0:
                        trend[strategy][idx]['wins'] += 1
            conn.close()
        except Exception as e:
            print(f"Trend DB error ({os.path.basename(db_path)}): {e}")

    # Convert raw counts to percentages
    result = {}
    for strategy, weeks_data in trend.items():
        result[strategy] = [
            round(d['wins'] / d['total'] * 100, 1) if d and d['total'] > 0 else None
            for d in weeks_data
        ]
    return result


def format_trend_table(trend: dict, weeks: int = 4) -> str:
    """Format win-rate trend as a Telegram-friendly text table."""
    if not trend:
        return "No trade history yet."

    now = datetime.now(timezone.utc)
    headers = []
    for w in range(weeks, -1, -1):
        label = "Now" if w == 0 else f"W-{w}"
        headers.append(label)

    lines = ["<b>Win Rate Trend</b>"]
    lines.append("Strategy           " + "  ".join(f"{h:>5}" for h in headers) + "  Δ")
    lines.append("─" * 54)

    for strategy, wrs in sorted(trend.items()):
        name = strategy[:16].ljust(16)
        cells = []
        for wr in wrs:
            cells.append(f"{wr:.0f}%" if wr is not None else "  — ")
        # Trend arrow: compare last two non-None values
        non_none = [w for w in wrs if w is not None]
        if len(non_none) >= 2:
            delta = non_none[-1] - non_none[-2]
            arrow = f"{'📈' if delta > 0 else '📉' if delta < 0 else '➡️'}{delta:+.0f}pp"
        else:
            arrow = "  —"
        row = f"{name}  " + "  ".join(f"{c:>5}" for c in cells) + f"  {arrow}"
        lines.append(row)

    return "\n".join(lines)


def get_skeptic_summary() -> str:
    """Fetches skeptic agent stats for the report."""
    try:
        result = subprocess.run(
            [str(BASE_DIR / 'venv/bin/python'), '-c',
             f'import sys; sys.path.insert(0, "{BASE_DIR}/qnt/agents");'
             f'sys.path.insert(0, "{BASE_DIR}/qnt/memory");'
             'from trade_gate import get_skeptic_stats;'
             'print(get_skeptic_stats())'],
            capture_output=True, text=True, timeout=15
        )
        return result.stdout.strip()
    except Exception as e:
        return f"Skeptic stats unavailable: {e}"

def format_telegram_report(current, previous, sentiment, risk, intel, week_start, week_end, qnt_brief, trend_table=""):
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

    return f"""📈 Cipher Weekly Report
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
📈 Learning Progress
{trend_table}

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
    <h2>Cipher Weekly Performance</h2>
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

    sentiment  = get_sentiment_correlation()
    risk       = get_risk_events()
    intel      = get_qnt_intelligence(curr_metrics, sentiment or {})
    qnt_brief  = get_qnt_weekly_brief()
    trend_data = get_strategy_win_rate_trend(DB_PATHS, weeks=4)
    trend_table = format_trend_table(trend_data, weeks=4)

    report = format_telegram_report(curr_metrics, prev_metrics, sentiment or {}, risk, intel, week_start, week_end, qnt_brief, trend_table)
    
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={'chat_id': TELEGRAM_CHAT_ID, 'text': report})
        print("✅ Telegram report sent" if res.status_code == 200 else f"❌ Failed: {res.text}")
    
    save_html_report(curr_metrics, f"weekly_report_{today.strftime('%Y%m%d')}.html")
