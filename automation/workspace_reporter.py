import sqlite3
import json
import subprocess
import os
from datetime import datetime

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Database files to check
DB_FILES = [
    str(BASE_DIR / 'user_data/micro.sqlite'),
    str(BASE_DIR / 'user_data/scalp.sqlite'),
    str(BASE_DIR / 'user_data/mean_reversion.sqlite'),
    str(BASE_DIR / 'user_data/trend_follow.sqlite'),
    str(BASE_DIR / 'user_data/daily.sqlite'),
    str(BASE_DIR / 'user_data/swing.sqlite')
]

REPORTS_FOLDER_ID = '1Vdst3YI9wFFfFPurpVVGJfrA3y2aT9BI'
DEST_EMAIL = 'aatifqmr@gmail.com'

def get_combined_stats():
    total_trades = 0
    total_profit_abs = 0.0
    open_trades_list = []
    closed_trades_list = []
    
    for db_path in DB_FILES:
        if not os.path.exists(db_path):
            continue
            
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if trades table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
            if not cursor.fetchone():
                conn.close()
                continue

            # Open trades
            cursor.execute("SELECT pair, strategy, open_date FROM trades WHERE is_open = 1")
            for row in cursor.fetchall():
                open_trades_list.append(f"{row[0]} ({row[1]}) - Opened: {row[2]}")

            # Closed trades summary
            cursor.execute("SELECT COUNT(*), SUM(close_profit) FROM trades WHERE is_open = 0")
            count, profit = cursor.fetchone()
            if count:
                total_trades += count
                total_profit_abs += (profit if profit else 0.0)
            
            # Last 3 closed from this db
            cursor.execute("SELECT pair, strategy, close_profit, close_date FROM trades WHERE is_open = 0 ORDER BY close_date DESC LIMIT 3")
            for row in cursor.fetchall():
                closed_trades_list.append(f"{row[0]} ({row[1]}): {row[2]:.2%} at {row[3]}")
                
            conn.close()
        except Exception as e:
            print(f"Error reading {db_path}: {e}")
            
    stats = f"### Overall Summary\n"
    stats += f"- Total Closed Trades: {total_trades}\n"
    stats += f"- Total Cumulative Profit: {total_profit_abs:.2%}\n\n"
    
    stats += f"### 🟢 Active/Open Trades ({len(open_trades_list)})\n"
    if open_trades_list:
        for t in open_trades_list:
            stats += f"- {t}\n"
    else:
        stats += "- No active trades found.\n"
        
    stats += f"\n### 🔴 Last Closed Trades\n"
    if closed_trades_list:
        # Sort and take top 5 overall if we wanted, but for now just list them
        for t in closed_trades_list[:5]:
            stats += f"- {t}\n"
    else:
        stats += "- No closed trades found.\n"
        
    return stats

def generate_report():
    print("Generating Cipher AGGREGATED Performance Report...")
    stats = get_combined_stats()
    date_str = datetime.now().strftime("%Y-%m-%d")
    title = f"Cipher Aggregated Report - {date_str}"
    
    # Content
    content = f"# {title}\n\nGenerated at: {datetime.now().isoformat()}\n\n{stats}\n\n## Bot Status\nMode: MULTI-STRATEGY PAPER TRADING\nStatus: ACTIVE"

    # Use qnt CLI to create the doc
    prompt = f"Create a Google Doc in folder '{REPORTS_FOLDER_ID}' with title '{title}' and this content: {content}. Then email a link to this doc to {DEST_EMAIL}."
    
    print(f"Executing qnt command to sync with Google Workspace...")
    try:
        subprocess.run(['qnt', '-p', prompt], check=True)
        print("Aggregated report successfully synced to Google Workspace.")
    except Exception as e:
        print(f"Failed to sync report: {e}")

if __name__ == "__main__":
    generate_report()
