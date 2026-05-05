import sys, os; home = os.path.expanduser('~'); sys.path.append(os.path.join(home, 'masterbot')); sys.path.append(os.path.join(home, 'masterbot', 'qnt', 'memory')); sys.path.append(os.path.join(home, 'masterbot', 'qnt', 'oracle')); sys.path.append(os.path.join(home, 'masterbot', 'qnt', 'shadow'));
import json
import time
import subprocess
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Machine-agnostic path setup
HOME = Path.home()
BASE_DIR = HOME / 'masterbot'
sys.path.insert(0, str(BASE_DIR / 'qnt/shadow'))

from resource_monitor import get_resource_snapshot

# Constants
STRATEGIES = [
    'MeanReversionV1',
    'TrendFollowV1',
    'ScalpV1',
    'SwingV1',
    'DailyTrendV1',
    'MicroScalpV1'
]

STRATEGY_TIMEFRAMES = {
    'MeanReversionV1': '1h',
    'TrendFollowV1': '4h',
    'ScalpV1': '5m',
    'SwingV1': '15m',
    'DailyTrendV1': '1d',
    'MicroScalpV1': '1m'
}

IMPROVEMENT_THRESHOLD = 0.20  # 20% better Sharpe
COOLDOWN_MINUTES = 120  # wait 2h between runs

logger = logging.getLogger(__name__)

def get_live_sharpe(strategy_name):
    """Reads latest hyperopt results for strategy to get current Sharpe."""
    results_dir = BASE_DIR / 'user_data/hyperopt_results'
    if not results_dir.exists():
        return 0.0
        
    try:
        # Find latest .json for this strategy
        latest_file = None
        latest_time = 0
        for f in results_dir.glob(f"hyperopt_results_{strategy_name}*.json"):
            mtime = f.stat().st_mtime
            if mtime > latest_time:
                latest_time = mtime
                latest_file = f
                
        if not latest_file: return 1.0 # Default starting baseline
        
        with open(latest_file, 'r') as f:
            data = json.load(f)
            # Assuming freqtrade format: results are in a list
            return data.get('best_sharpe', 1.0)
    except:
        return 1.0

def run_shadow_hyperopt(strategy_name, epochs=100):
    """Runs a targeted hyperopt on recent data."""
    snapshot = get_resource_snapshot()
    
    if snapshot['ram']['pressure'] == "critical":
        print(f"[{datetime.now()}] Skipping {strategy_name} - RAM critical ({snapshot['ram']['percent_used']}%)")
        return False, 0.0, {}
        
    if snapshot['ram']['percent_used'] > 80:
        epochs = 50 # Reduce load
        print(f"[{datetime.now()}] Throttling {strategy_name} to {epochs} epochs due to RAM pressure.")

    # 48h timerange
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(hours=48)
    timerange = f"{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"
    
    print(f"[{datetime.now()}] Starting Shadow Hyperopt for {strategy_name}...")
    
    cmd = [
        "/Users/azmatsaif/masterbot/venv/bin/freqtrade", "hyperopt",
        "--strategy", strategy_name,
        "--strategy-path", "strategies/active/",
        "--config", "config/config_paper.json",
        "--hyperopt-loss", "SharpeHyperOptLoss",
        "--spaces", "buy", "sell", "stoploss", "roi",
        "--epochs", str(epochs),
        "--timerange", timerange,
        "--timeframe", STRATEGY_TIMEFRAMES[strategy_name],
        "--datadir", "data/",
        "-j", "-1"
    ]
    
    env = os.environ.copy()
    env['PYTHONPATH'] = f"{BASE_DIR}:{BASE_DIR}/freqtrade"
    
    try:
        # Run with 1 hour timeout
        res = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True, timeout=3600, env=env)
        
        if res.returncode != 0:
            print(f"Hyperopt failed for {strategy_name}: {res.stderr}")
            return False, 0.0, {}
            
        # Parse output for Sharpe
        # 'Best result: ... Sharpe: 2.34'
        output = res.stdout
        new_sharpe = 0.0
        if "Best result:" in output:
            import re
            match = re.search(r"Sharpe:\s+([\d\.]+)", output)
            if match:
                new_sharpe = float(match.group(1))
                
        # Extract params (this is tricky from raw stdout, usually saved to file)
        # For now, we return dummy params or assuming they are in the latest result file
        return True, new_sharpe, {"timestamp": datetime.now().isoformat()}
        
    except subprocess.TimeoutExpired:
        print(f"Hyperopt timed out for {strategy_name}")
        return False, 0.0, {}
    except Exception as e:
        print(f"Shadow error: {e}")
        return False, 0.0, {}

def compare_and_promote(strategy_name, live_sharpe, new_sharpe, new_params):
    """Evaluates if new results are worth escalating."""
    if new_sharpe > live_sharpe * (1 + IMPROVEMENT_THRESHOLD):
        improvement = ((new_sharpe / live_sharpe) - 1) * 100
        print(f"🌟 IMPROVEMENT FOUND: {strategy_name} improved by {improvement:.1f}% ({live_sharpe:.2f} -> {new_sharpe:.2f})")
        
        timestamp = int(time.time())
        msg = f"""
🔬 Shadow Hyperopt found improvement
Strategy: {strategy_name}
Old Sharpe: {live_sharpe:.2f}
New Sharpe: {new_sharpe:.2f}
Improvement: {improvement:.1f}%

Options:
1️⃣ Promote new params to active immediately
2️⃣ Run 7-day backtest first then decide
3️⃣ Paper test for 24h then decide
4️⃣ Ignore this improvement

Recommendation: Option 2 (backtest first)
"""
        # SSH to M1 for notification
        subprocess.run(['ssh', 'aatifquamre@100.90.68.42', f'source ~/.zshrc && echo "{msg}" | qnt-notify'], stderr=subprocess.DEVNULL)
        
        # Save placeholder for candidate
        candidates_dir = BASE_DIR / 'strategies/candidates'
        os.makedirs(candidates_dir, exist_ok=True)
        with open(candidates_dir / f"Shadow_{strategy_name}_{timestamp}.json", 'w') as f:
            json.dump({"new_sharpe": new_sharpe, "old_sharpe": live_sharpe, "params": new_params}, f)
    else:
        print(f"No significant improvement for {strategy_name} (New: {new_sharpe:.2f}, Live: {live_sharpe:.2f})")

def continuous_shadow_loop():
    """Main infinite rotation loop."""
    print("Continuous Shadow Hyperopt Loop initiated.", flush=True)
    strategy_index = 0
    
    while True:
        strategy = STRATEGIES[strategy_index]
        print(f"[{datetime.now()}] Attempting {strategy}...", flush=True)
        
        try:
            success, new_sharpe, new_params = run_shadow_hyperopt(strategy)
            
            if success:
                print(f"[{datetime.now()}] {strategy} hyperopt success. Sharpe: {new_sharpe}", flush=True)
                live_sharpe = get_live_sharpe(strategy)
                compare_and_promote(strategy, live_sharpe, new_sharpe, new_params)
            else:
                print(f"[{datetime.now()}] {strategy} hyperopt failed or skipped.", flush=True)
        except Exception as e:
            print(f"[{datetime.now()}] Loop error on {strategy}: {e}", flush=True)
            
        # Rotation
        strategy_index = (strategy_index + 1) % len(STRATEGIES)
        
        print(f"[{datetime.now()}] Waiting {COOLDOWN_MINUTES}m cooldown...", flush=True)
        # Check resources every 5m during wait
        for _ in range(COOLDOWN_MINUTES // 5):
            time.sleep(300)
            get_resource_snapshot()

if __name__ == "__main__":
    continuous_shadow_loop()
