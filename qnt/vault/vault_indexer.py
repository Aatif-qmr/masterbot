import os
import sys
import sqlite3
import json
import subprocess
import pandas as pd
from datetime import datetime, timedelta, timezone

# Add paths
BASE_DIR = '/Users/aatifquamre/masterbot'
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/memory'))
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/vault'))

from memory_manager import load_memory, save_memory, log_action
from vault import add_trade_memory, add_entry, add_pattern, search

DB_PATH = os.path.join(BASE_DIR, 'user_data/tradesv3.dryrun.sqlite')
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(BASE_DIR, 'user_data/tradesv3.sqlite')

SENTIMENT_CSV = os.path.join(BASE_DIR, 'sentiment/scores/history.csv')

def index_recent_trades(days=7):
    """Index closed trades into the vault with AI analysis."""
    data = load_memory()
    indexed_ids = data.get('indexed_trade_ids', [])
    
    try:
        conn = sqlite3.connect(DB_PATH)
        # Get trades from last X days
        threshold = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        query = f"SELECT * FROM trades WHERE is_open=0 AND close_date >= '{threshold}'"
        df = pd.read_sql_query(query, conn)
        conn.close()
    except Exception as e:
        print(f"Error reading trades: {e}")
        return 0

    new_indices = 0
    for _, row in df.iterrows():
        trade_id = int(row['trade_id'])
        if trade_id in indexed_ids:
            continue
            
        print(f"Indexing trade {trade_id} ({row['pair']})...")
        
        # 1. Get market context (sentiment)
        market_context = "Market context unavailable."
        try:
            hist = pd.read_csv(SENTIMENT_CSV)
            # Find closest sentiment timestamp to trade close
            hist['timestamp'] = pd.to_datetime(hist['timestamp'])
            close_dt = pd.to_datetime(row['close_date'])
            closest = hist.iloc[(hist['timestamp'] - close_dt).abs().argsort()[:1]]
            if not closest.empty:
                market_context = f"Sentiment at close: {closest.iloc[0]['score']:.2f}"
        except: pass

        # 2. Generate analysis using qnt
        trade_summary = f"Pair: {row['pair']}, Profit: {row['profit_ratio']*100:.2f}%, Strategy: {row['strategy']}"
        prompt = f"Analyze this trade briefly. {trade_summary}. {market_context}. Why did this happen? Return 1-2 sentences."
        
        qnt_bin = '/Users/aatifquamre/.local/share/fnm/node-versions/v25.9.0/installation/bin/qnt'
        res = subprocess.run([qnt_bin, '-p', prompt, '--output-format', 'text'], capture_output=True, text=True)
        analysis = res.stdout.strip() if res.returncode == 0 else "Analysis failed."

        # 3. Store in vault
        add_trade_memory(row.to_dict(), analysis)
        indexed_ids.append(trade_id)
        new_indices += 1

    data['indexed_trade_ids'] = indexed_ids
    save_memory(data)
    return new_indices

def index_strategy_research():
    """Index research files."""
    research_dir = os.path.join(BASE_DIR, 'strategies/research')
    if not os.path.exists(research_dir): return 0
    
    data = load_memory()
    indexed_files = data.get('indexed_research_files', [])
    
    new_files = 0
    for filename in os.listdir(research_dir):
        if filename.endswith('.md') and filename not in indexed_files:
            filepath = os.path.join(research_dir, filename)
            with open(filepath, 'r') as f:
                content = f.read()
            
            metadata = {
                "timestamp": datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat(),
                "category": "strategy",
                "filename": filename,
                "tags": "research,scan"
            }
            
            add_entry("strategies", content, metadata)
            indexed_files.append(filename)
            new_files += 1
            
    data['indexed_research_files'] = indexed_files
    save_memory(data)
    return new_files

def detect_and_store_patterns():
    """Analyze last 50 memories for patterns."""
    memories = search("market behavior patterns", collection_name="trade_memory", n_results=50)
    if len(memories) < 10: return 0
    
    context = "\n".join([m['content'] for m in memories])
    prompt = f"Identify the top 2 recurring winning or losing patterns in these trades:\n{context}\nReturn only the patterns."
    
    qnt_bin = '/Users/aatifquamre/.local/share/fnm/node-versions/v25.9.0/installation/bin/qnt'
    res = subprocess.run([qnt_bin, '-p', prompt, '--output-format', 'text'], capture_output=True, text=True)
    
    if res.returncode == 0 and res.stdout.strip():
        pattern = res.stdout.strip()
        add_pattern(pattern, "automated_discovery")
        return 1
    return 0

def run_daily_indexing():
    print(f"[{datetime.now()}] Starting Vault Indexing...")
    t_count = index_recent_trades(days=1)
    r_count = index_strategy_research()
    p_count = detect_and_store_patterns()
    
    log_action('vault_indexed', f"Trades: {t_count}, Research: {r_count}, Patterns: {p_count}")
    
    if t_count + r_count + p_count > 0:
        from qnt_notifier import send_notify
        send_notify("Vault Indexed", f"📚 Vault updated:\n- {t_count} new trades\n- {r_count} research files\n- {p_count} patterns discovered")

if __name__ == "__main__":
    run_daily_indexing()
