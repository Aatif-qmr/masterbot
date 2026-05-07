import sys
import os
import json
import re
from pathlib import Path

# Base paths
BASE_DIR = '/Users/aatifquamre/masterbot'
STRATEGIES_DIR = os.path.join(BASE_DIR, 'strategies/active')
SUMMARY_PATH = os.path.join(BASE_DIR, 'logs/hyperopt_summary.json')

def update_strategy_file(strategy_name, new_params):
    file_path = os.path.join(STRATEGIES_DIR, f"{strategy_name}.py")
    if not os.path.exists(file_path):
        print(f"❌ Strategy file {file_path} not found.")
        return False

    with open(file_path, 'r') as f:
        content = f.read()

    # Simple regex-based update for buy_params and sell_params
    # This is a bit naive but works for standard Freqtrade strategy structures
    updated = content
    
    if 'buy_params' in new_params:
        # Match "buy_params = { ... }" and replace with new dict
        new_buy = json.dumps(new_params['buy_params'], indent=8).replace('{', '{\n').replace('}', '\n    }')
        updated = re.sub(r'buy_params\s*=\s*\{[^}]*\}', f"buy_params = {new_buy}", updated, flags=re.DOTALL)

    if 'sell_params' in new_params:
        new_sell = json.dumps(new_params['sell_params'], indent=8).replace('{', '{\n').replace('}', '\n    }')
        updated = re.sub(r'sell_params\s*=\s*\{[^}]*\}', f"sell_params = {new_sell}", updated, flags=re.DOTALL)

    if updated != content:
        with open(file_path, 'w') as f:
            f.write(updated)
        print(f"✅ Updated {strategy_name}.py with new parameters.")
        return True
    else:
        print(f"⚠️ No changes applied to {strategy_name}.py (regex mismatch or same values).")
        return False

def main():
    if not os.path.exists(SUMMARY_PATH):
        print(f"❌ Hyperopt summary not found at {SUMMARY_PATH}")
        return

    with open(SUMMARY_PATH, 'r') as f:
        summary = json.load(f)

    print(f"🧠 QNT Hyperopt Sync - Summary Date: {summary.get('date', 'Unknown')}")
    
    for strategy, data in summary.items():
        if strategy == 'date': continue
        
        if data.get('decision') == 'CANDIDATE' and 'new_params' in data:
            print(f"⚙️ Syncing {strategy}...")
            update_strategy_file(strategy, data['new_params'])
        else:
            print(f"⏭️ Skipping {strategy} (Decision: {data.get('decision', 'NONE')})")

if __name__ == '__main__':
    main()
