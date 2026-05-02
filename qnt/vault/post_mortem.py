import os
import sys
import sqlite3
import json
import subprocess
import pandas as pd
from datetime import datetime, timezone

# Add paths
BASE_DIR = '/Users/aatifquamre/masterbot'
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/memory'))
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/vault'))
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/oracle'))

from memory_manager import load_memory, log_action
from vault import add_trade_memory, add_entry
from oracle_calendar import calculate_risk_level

DB_PATH = os.path.join(BASE_DIR, 'user_data/tradesv3.dryrun.sqlite')
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(BASE_DIR, 'user_data/tradesv3.sqlite')

SENTIMENT_CSV = os.path.join(BASE_DIR, 'sentiment/scores/history.csv')

def generate_post_mortem(trade_id):
    """Generate detailed AI analysis of a specific trade."""
    print(f"Generating post-mortem for trade {trade_id}...")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        query = f"SELECT * FROM trades WHERE trade_id={trade_id}"
        trades = pd.read_sql_query(query, conn)
        conn.close()
        
        if trades.empty: return f"Trade {trade_id} not found."
        trade = trades.iloc[0]
        
        # 1. Get Market Context
        sentiment_at_open = "0.0"
        sentiment_at_close = "0.0"
        funding_rate = "0.0"
        
        try:
            hist = pd.read_csv(SENTIMENT_CSV)
            hist['timestamp'] = pd.to_datetime(hist['timestamp'])
            
            # Sentiment at open
            open_dt = pd.to_datetime(trade['open_date'])
            closest_open = hist.iloc[(hist['timestamp'] - open_dt).abs().argsort()[:1]]
            if not closest_open.empty: sentiment_at_open = f"{closest_open.iloc[0]['score']:.2f}"
            
            # Sentiment at close
            close_dt = pd.to_datetime(trade['close_date'])
            closest_close = hist.iloc[(hist['timestamp'] - close_dt).abs().argsort()[:1]]
            if not closest_close.empty: 
                sentiment_at_close = f"{closest_close.iloc[0]['score']:.2f}"
                # Get funding from metadata if stored or use closest hist
                # For now we'll assume it's part of the sentiment logic
        except: pass
        
        # 2. Calendar Events
        cal = calculate_risk_level(trade['close_date'][:10])
        calendar_events = cal.get('description', 'None')
        
        # 3. Call QNT for analysis
        trade_details = {
            "pair": trade['pair'],
            "profit": f"{trade['profit_ratio']*100:.2f}%",
            "duration": trade.get('duration', 'unknown'),
            "strategy": trade['strategy'],
            "exit_reason": trade.get('exit_reason', 'unknown')
        }
        
        prompt = f"""Analyze this trade and explain what happened:
        
        Trade data: {json.dumps(trade_details)}
        Sentiment at entry: {sentiment_at_open}
        Sentiment at exit: {sentiment_at_close}
        Calendar events on close day: {calendar_events}
        
        Provide:
        1. Why the trade was entered (market conditions)
        2. What happened during the trade
        3. Why it closed with this outcome
        4. What could have been done differently
        5. Pattern to remember for future trades
        
        Be specific. Use the data provided."""

        qnt_bin = '/Users/aatifquamre/.local/share/fnm/node-versions/v25.9.0/installation/bin/qnt'
        res = subprocess.run([qnt_bin, '-p', prompt, '--output-format', 'text'], capture_output=True, text=True)
        
        analysis = res.stdout.strip() if res.returncode == 0 else "Post-mortem analysis failed."
        
        # 4. Store in vault
        add_trade_memory(trade.to_dict(), analysis)
        
        report = f"""
💀 QNT Post-Mortem: Trade {trade_id}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{analysis}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return report

    except Exception as e:
        return f"Error generating post-mortem: {e}"

def generate_weekly_post_mortem():
    """Analyze all losses from the past week."""
    print("Generating weekly loss post-mortem summary...")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        # Last 7 days, losses only
        threshold = (datetime.now(timezone.utc) - pd.Timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        query = f"SELECT trade_id FROM trades WHERE is_open=0 AND profit_ratio < 0 AND close_date >= '{threshold}'"
        losses = pd.read_sql_query(query, conn)
        conn.close()
        
        if losses.empty:
            return "No losing trades to analyze this week. Excellent performance."
            
        reports = []
        for tid in losses['trade_id']:
            reports.append(generate_post_mortem(tid))
            
        summary_prompt = f"Summarize these weekly trading post-mortems into 3 key lessons:\n\n" + "\n".join(reports)
        
        qnt_bin = '/Users/aatifquamre/.local/share/fnm/node-versions/v25.9.0/installation/bin/qnt'
        res = subprocess.run([qnt_bin, '-p', summary_prompt, '--output-format', 'text'], capture_output=True, text=True)
        
        summary = res.stdout.strip() if res.returncode == 0 else "Summary failed."
        
        # Store in vault
        metadata = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "category": "strategy",
            "tags": "weekly,lessons,post-mortem"
        }
        add_entry("strategies", f"Weekly Lessons Summary:\n{summary}", metadata)
        
        final_report = f"""
🧠 Weekly Intelligence Lessons
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{summary}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return final_report
        
    except Exception as e:
        return f"Error in weekly post-mortem: {e}"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "weekly":
            print(generate_weekly_post_mortem())
        else:
            print(generate_post_mortem(int(sys.argv[1])))
