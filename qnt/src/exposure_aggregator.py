import sys
import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = '/Users/aatifquamre/masterbot'
load_dotenv(os.path.join(BASE_DIR, '.env'))

def get_exposure():
    user = os.getenv('FREQTRADE_UI_USERNAME')
    pwd = os.getenv('FREQTRADE_UI_PASSWORD')
    
    instances = [
        {"name": "Mean Reversion", "port": 8080},
        {"name": "Trend Follow", "port": 8081},
        {"name": "Scalp", "port": 8082},
        {"name": "Swing", "port": 8083},
        {"name": "Daily", "port": 8084}
    ]
    
    total_balance = 0.0
    total_stake = 0.0
    active_trades = 0
    
    print("🧠 QNT Global Exposure Report")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"{'Instance':<20} | {'Status':<8} | {'Balance':<10} | {'Stake':<8}")
    print("-------------------------------------------------")
    
    for inst in instances:
        try:
            # 1. Get Balance
            r_bal = requests.get(f'http://100.90.68.42:{inst["port"]}/api/v1/balance', auth=(user, pwd), timeout=2)
            # 2. Get Status (Active Trades)
            r_stat = requests.get(f'http://100.90.68.42:{inst["port"]}/api/v1/status', auth=(user, pwd), timeout=2)
            
            if r_bal.status_code == 200:
                bal = float(r_bal.json().get('total', 0))
                total_balance += bal
                
                # Calculate current stake (sum of cost of open trades)
                inst_stake = 0.0
                inst_trades = 0
                if r_stat.status_code == 200:
                    trades = r_stat.json()
                    inst_trades = len(trades)
                    active_trades += inst_trades
                    for t in trades:
                        inst_stake += t.get('cost', 0)
                
                total_stake += inst_stake
                
                status = "RUNNING" if inst_trades > 0 else "IDLE"
                print(f"{inst['name']:<20} | {status:<8} | ${bal:>8.2f} | ${inst_stake:>7.2f} ({inst_trades})")
            else:
                print(f"{inst['name']:<20} | OFFLINE  | {'-':>10} | {'-':>8}")
        except:
            print(f"{inst['name']:<20} | OFFLINE  | {'-':>10} | {'-':>8}")

    leverage = (total_stake / total_balance) if total_balance > 0 else 0
    
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"TOTAL GLOBAL BALANCE: ${total_balance:,.2f}")
    print(f"TOTAL ACTIVE STAKE:   ${total_stake:,.2f}")
    print(f"TOTAL OPEN TRADES:    {active_trades}")
    print(f"GLOBAL LEVERAGE:      {leverage:.2f}x")
    
    # Risk Warnings
    if leverage > 0.8:
        print("\n🚨 CRITICAL: Global leverage exceeding 0.8x! High risk of liquidation.")
    elif leverage > 0.5:
        print("\n⚠️ WARNING: Global leverage elevated (>0.5x).")
    else:
        print("\n✅ Risk levels within normal parameters.")

if __name__ == '__main__':
    get_exposure()
