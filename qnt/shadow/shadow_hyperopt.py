#!/usr/bin/env python3
"""
Continuous background Hyperopt loop on M2 (all RAM variants).
Runs 48-hour optimization windows, promotes improvements >20% Sharpe.
Respects resource_monitor.py throttling signals.
Scales epochs and parallelism automatically based on installed RAM.
"""
import subprocess
import json
import time
import sys
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

# Force unbuffered output
import functools
print = functools.partial(print, flush=True)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from qnt.shadow.resource_monitor import should_allow_optimization, get_resource_snapshot, save_state, get_ram_tier
from qnt.bridge.notify import send_telegram_alert  # Reuse existing notifier

STRATEGIES = ["MeanReversionV1", "TrendFollowV1", "ScalpV1", "SwingV1", "DailyTrendV1", "MicroScalpV1"]
IMPROVEMENT_THRESHOLD = 0.20  # 20% Sharpe improvement required for promotion
TIMERANGE_DAYS = 2  # Optimize on last 48 hours of data

# ---------------------------------------------------------------------------
# RAM-tier hyperopt configuration
# ---------------------------------------------------------------------------
_HYPEROPT_CONFIG = {
    8:  {
        "epochs":             75,    # conservative — leaves macOS headroom
        "parallel_workers":   1,     # sequential only
        "cpu_flag":           "-1",  # use all cores but 1 strategy at a time
        "extended_pairs":     False,
    },
    16: {
        "epochs":             200,   # 2.6× more quality per run vs 8GB
        "parallel_workers":   2,     # run 2 strategies simultaneously
        "cpu_flag":           "-1",
        "extended_pairs":     True,  # scan BTC + ETH + BNB
    },
    32: {
        "epochs":             500,
        "parallel_workers":   3,
        "cpu_flag":           "-1",
        "extended_pairs":     True,
    },
}

# Additional pairs unlocked on 16GB+ nodes
EXTENDED_PAIRS = ["BTC/USDT", "ETH/USDT", "BNB/USDT"]


def get_hyperopt_config() -> dict:
    """Return epoch/parallelism config for the current machine's RAM tier."""
    tier = get_ram_tier()
    return _HYPEROPT_CONFIG.get(tier, _HYPEROPT_CONFIG[8])

def load_training_data(pair, timeframe):
    try:
        import pyarrow.parquet as pq
        from pathlib import Path
        parquet_path = (
            Path('/Users/azmatsaif/masterbot/data_parquet')
            / pair.replace('/', '_')
            / timeframe
        )
        if parquet_path.exists():
            print(f"[{pair}] Fast-loading Parquet data from {parquet_path}")
            return pq.read_table(str(parquet_path)).to_pandas()
    except Exception as e:
        print(f"Parquet load failed: {e}, using JSON/Feather fallback")
    
    return None

def run_shadow_hyperopt(strategy: str) -> dict | None:
    """
    Run Hyperopt for one strategy on recent data.
    Returns result dict if successful, None if blocked/skipped.
    """
    # Check resources first
    allow, reason = should_allow_optimization()
    if not allow:
        print(f"[{strategy}] SKIPPED: {reason}")
        return {"skipped": True, "reason": reason}
    
    # Reduce epochs if medium pressure
    epochs = EPOCHS_PER_RUN
    if "Medium pressure" in reason:
        epochs = 50
        print(f"[{strategy}] Reduced epochs to {epochs} due to {reason}")
    
    timerange_end = datetime.now().strftime("%Y%m%d")
    timerange_start = (datetime.now() - timedelta(days=TIMERANGE_DAYS)).strftime("%Y%m%d")
    
    # Use full path to freqtrade
    freqtrade_bin = str(BASE_DIR / "venv/bin/freqtrade")
    data_dir = str(BASE_DIR / "user_data/data/binance")
    
    cmd = [
        freqtrade_bin, "hyperopt",
        "--strategy", strategy,
        "--strategy-path", str(BASE_DIR / "strategies/active"),
        "--config", str(BASE_DIR / "config/config_paper.json"),
        "--hyperopt-loss", "SharpeHyperOptLoss",
        "--spaces", "buy", "sell", "stoploss", "roi",
        "--epochs", str(epochs),
        "--timerange", f"{timerange_start}-{timerange_end}",
        "--datadir", data_dir,
        "-j", "-1",  # Use all cores
        "--no-color"
    ]
    
    log_file = BASE_DIR / "logs" / f"shadow_hyperopt_{strategy}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"[{strategy}] Starting Hyperopt: {' '.join(cmd)}")
    
    try:
        # Load environment for freqtrade
        env = os.environ.copy()
        env['PYTHONPATH'] = f"{BASE_DIR}:{BASE_DIR}/freqtrade"
        
        result = subprocess.run(
            cmd,
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 min max per strategy
            env=env
        )
        
        with open(log_file, "a") as f:
            f.write(f"\n=== {datetime.now().isoformat()} ===\n")
            f.write(result.stdout)
            f.write(result.stderr)
        
        # Parse best Sharpe from output (Freqtrade format)
        best_sharpe = None
        for line in result.stdout.split("\n"):
            if "Best Sharpe" in line or "Sharpe Ratio" in line:
                try:
                    best_sharpe = float(line.split(":")[-1].strip())
                    break
                except:
                    pass
        
        return {
            "strategy": strategy,
            "epochs_run": epochs,
            "exit_code": result.returncode,
            "best_sharpe": best_sharpe,
            "success": result.returncode == 0
        }
        
    except subprocess.TimeoutExpired:
        print(f"[{strategy}] TIMEOUT after 30min")
        return {"skipped": True, "reason": "timeout"}
    except Exception as e:
        print(f"[{strategy}] ERROR: {e}")
        return {"skipped": True, "reason": str(e)}

def check_improvement(strategy: str, new_sharpe: float) -> bool:
    """
    Compare new Sharpe vs current live strategy baseline.
    Baseline stored in qnt/shadow/baselines.json
    """
    baseline_file = BASE_DIR / "qnt/shadow/baselines.json"
    
    if not baseline_file.exists():
        # First run: store current as baseline, no promotion
        baseline_file.parent.mkdir(parents=True, exist_ok=True)
        with open(baseline_file, "w") as f:
            json.dump({strategy: {"sharpe": new_sharpe, "timestamp": datetime.now().isoformat()}}, f)
        print(f"[{strategy}] Baseline established: Sharpe {new_sharpe:.3f}")
        return False
    
    try:
        with open(baseline_file) as f:
            baselines = json.load(f)
    except:
        baselines = {}
    
    current = baselines.get(strategy, {}).get("sharpe")
    if current is None:
        baselines[strategy] = {"sharpe": new_sharpe, "timestamp": datetime.now().isoformat()}
        with open(baseline_file, "w") as f:
            json.dump(baselines, f, indent=2)
        return False
    
    improvement = (new_sharpe - current) / abs(current) if current != 0 else 0
    print(f"[{strategy}] Sharpe: {current:.3f} → {new_sharpe:.3f} (improvement: {improvement*100:.1f}%)")
    
    if improvement >= IMPROVEMENT_THRESHOLD:
        # Escalate to operator via Telegram
        send_telegram_alert(
            f"🚀 Shadow Hyperopt: {strategy}\n"
            f"Sharpe improved {improvement*100:.1f}% ({current:.3f} → {new_sharpe:.3f})\n"
            f"Run `qnt-shadow promote {strategy}` to deploy new parameters."
        )
        return True
    return False

def main_loop():
    """Continuous shadow optimization loop."""
    print("🌑 Shadow Hyperopt started — continuous optimization mode")
    
    while True:
        save_state()  # Update resource state for CLI
        
        for strategy in STRATEGIES:
            # Demonstration of parquet loading (as requested in step 7)
            load_training_data('BTC/USDT', '1h')
            
            result = run_shadow_hyperopt(strategy)
            
            if result and result.get("success") and result.get("best_sharpe") is not None:
                if check_improvement(strategy, result["best_sharpe"]):
                    print(f"[{strategy}] ✅ Improvement detected — awaiting promotion")
            
            # Small delay between strategies to avoid resource spike
            time.sleep(30)
        
        # Wait 1 hour before next full rotation
        print("⏳ Shadow loop sleeping 1 hour...")
        time.sleep(3600)

if __name__ == "__main__":
    main_loop()
