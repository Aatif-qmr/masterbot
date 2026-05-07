import os
import subprocess
import argparse
from datetime import datetime

# Define standard market regimes and their representative dates
REGIMES = {
    "bull_trend": "20240101-20240331",
    "sideways": "20240401-20240630",
    "volatile_crash": "20240801-20240831",
    "bear_trend": "20220101-20221231"
}

BASE_DIR = '/Users/aatifquamre/masterbot'
FREQTRADE_BIN = os.path.join(BASE_DIR, 'venv/bin/freqtrade')

def run_backtest(strategy, timerange, config):
    print(f"🚀 Running backtest for {strategy} in range {timerange}...")
    cmd = [
        FREQTRADE_BIN, "backtesting",
        "--strategy", strategy,
        "--timerange", timerange,
        "-c", config
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=BASE_DIR)
        return result.stdout
    except Exception as e:
        return f"Error: {e}"

def main():
    parser = argparse.ArgumentParser(description="QNT Backtest Sweep - Multi-regime analysis")
    parser.add_argument("strategy", help="Strategy name")
    parser.add_argument("--config", default="config/config_paper.json", help="Config file path")
    args = parser.parse_args()

    results = {}
    print(f"🧠 QNT Backtest Sweep: Analyzing {args.strategy}")
    
    for regime, timerange in REGIMES.items():
        print(f"\n--- Regime: {regime} ({timerange}) ---")
        output = run_backtest(args.strategy, timerange, args.config)
        
        # Simple extraction of key metrics from Freqtrade table
        # We'll look for the 'Total profit %' line
        profit = "N/A"
        for line in output.split('\n'):
            if 'Total profit %' in line:
                profit = line.split('|')[2].strip()
                break
        
        results[regime] = profit
        print(f"Result for {regime}: {profit}")

    print("\n" + "="*40)
    print(f"📊 SUMMARY: {args.strategy}")
    for regime, profit in results.items():
        print(f"{regime.ljust(15)}: {profit}")
    print("="*40)

if __name__ == '__main__':
    main()
