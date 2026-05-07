import sqlite3
import pandas as pd
import os
import argparse
from datetime import datetime

BASE_DIR = '/Users/aatifquamre/masterbot'
DB_PATH = os.path.join(BASE_DIR, 'user_data/tradesv3.dryrun.sqlite')
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(BASE_DIR, 'user_data/tradesv3.sqlite')

def get_trades():
    databases = [
        os.path.join(BASE_DIR, 'user_data/tradesv3.dryrun.sqlite'),
        os.path.join(BASE_DIR, 'user_data/tradesv3.sqlite'),
        os.path.join(BASE_DIR, 'user_data/mean_reversion.sqlite'),
        os.path.join(BASE_DIR, 'user_data/trend_follow.sqlite'),
        os.path.join(BASE_DIR, 'user_data/scalp.sqlite'),
        os.path.join(BASE_DIR, 'user_data/swing.sqlite'),
        os.path.join(BASE_DIR, 'user_data/daily.sqlite'),
    ]
    
    all_dfs = []
    for db in databases:
        if not os.path.exists(db): continue
        try:
            conn = sqlite3.connect(db)
            query = "SELECT trade_id, pair, strategy, open_date, close_date, profit_ratio FROM trades"
            df = pd.read_sql_query(query, conn)
            conn.close()
            if not df.empty:
                all_dfs.append(df)
        except:
            continue
            
    if not all_dfs:
        return pd.DataFrame()
    
    return pd.concat(all_dfs, ignore_index=True)

def analyze_correlation(df):
    if df.empty:
        print("No trades found in database.")
        return

    df['open_date'] = pd.to_datetime(df['open_date'])
    
    # Check for overlapping trades on the same pair
    print("🧠 QNT Correlation Analysis: Detecting Overlapping Trades")
    
    # Group by pair and date to see if multiple strategies were in the same pair
    # We'll use a 4-hour window for "same time"
    df['time_bucket'] = df['open_date'].dt.floor('4H')
    
    overlaps = df.groupby(['pair', 'time_bucket']).filter(lambda x: len(x['strategy'].unique()) > 1)
    
    if overlaps.empty:
        print("✅ No major strategy overlaps detected. Good diversification.")
    else:
        print("⚠️ Found overlapping trades (Multiple strategies in the same pair at once):")
        summary = overlaps.groupby(['pair', 'time_bucket'])['strategy'].apply(lambda x: ', '.join(x.unique())).reset_index()
        print(summary.head(20))

    # Calculate overall strategy performance correlation
    print("\n📊 Strategy Profitability Correlation:")
    pivoted = df.pivot_table(index='time_bucket', columns='strategy', values='profit_ratio', aggfunc='mean').fillna(0)
    if pivoted.shape[1] > 1:
        corr = pivoted.corr()
        print(corr)
    else:
        print("Not enough strategies to calculate correlation.")

def main():
    df = get_trades()
    analyze_correlation(df)

if __name__ == '__main__':
    main()
