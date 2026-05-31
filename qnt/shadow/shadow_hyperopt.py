#!/usr/bin/env python3
"""
Continuous background Hyperopt loop on M2.
Runs Out-of-Sample Validation: Trains on Days 1-5, Tests on Day 6.
Enforces max 5% drawdown and auto-promotes successful configurations.
"""

# Force unbuffered output
import functools
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

print = functools.partial(print, flush=True)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from qnt.shadow.resource_monitor import save_state, should_allow_optimization
from risk.risk_manager import send_telegram_alert  # Reuse existing notifier

STRATEGIES = [
    "MeanReversionV1",
    "TrendFollowV1",
    "ScalpV1",
    "SwingV1",
    "DailyTrendV1",
    "MicroScalpV1",
]
IMPROVEMENT_THRESHOLD = 0.20  # 20% Sharpe improvement required for promotion
EPOCHS_PER_RUN = 100
TIMERANGE_TRAIN_DAYS = 5
TIMERANGE_TEST_DAYS = 1
MAX_DRAWDOWN_LIMIT = 0.05  # 5% max drawdown allowed in OOS testing


def load_training_data(pair, timeframe):
    pass  # Dummy implementation for Parquet


def get_latest_fthypt(strategy: str) -> Path | None:
    """Finds the most recently created .fthypt file for the given strategy"""
    res_dir = BASE_DIR / "user_data/hyperopt_results"
    files = list(res_dir.glob(f"strategy_{strategy}_*.fthypt"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def run_shadow_hyperopt(strategy: str) -> dict | None:
    allow, reason = should_allow_optimization()
    if not allow:
        print(f"[{strategy}] SKIPPED: {reason}")
        return {"skipped": True, "reason": reason}

    epochs = EPOCHS_PER_RUN
    if "Medium pressure" in reason:
        epochs = 50

    # Train Window (e.g., Day -6 to Day -1)
    train_end_dt = datetime.now() - timedelta(days=TIMERANGE_TEST_DAYS)
    train_start_dt = train_end_dt - timedelta(days=TIMERANGE_TRAIN_DAYS)
    train_end = train_end_dt.strftime("%Y%m%d")
    train_start = train_start_dt.strftime("%Y%m%d")

    # Test Window (e.g., Day -1 to Day 0)
    test_end = datetime.now().strftime("%Y%m%d")
    test_start = train_end

    freqtrade_bin = str(BASE_DIR / "venv/bin/freqtrade")
    data_dir = str(BASE_DIR / "user_data/data/binance")

    config_map = {
        "MeanReversionV1": "config_mean_reversion.json",
        "TrendFollowV1": "config_trend_follow.json",
        "ScalpV1": "config_scalp.json",
        "SwingV1": "config_swing.json",
        "DailyTrendV1": "config_daily.json",
        "MicroScalpV1": "config_micro.json",
    }
    strat_config = config_map.get(strategy, "config_paper.json")

    tf_map = {
        "MeanReversionV1": "1h",
        "TrendFollowV1": "4h",
        "ScalpV1": "5m",
        "SwingV1": "15m",
        "DailyTrendV1": "1d",
        "MicroScalpV1": "1m",
    }
    timeframe = tf_map.get(strategy, "5m")

    cmd = [
        freqtrade_bin,
        "hyperopt",
        "--strategy",
        strategy,
        "--strategy-path",
        str(BASE_DIR / "strategies/active"),
        "--config",
        str(BASE_DIR / "config/config_paper.json"),
        "--config",
        str(BASE_DIR / f"config/{strat_config}"),
        "--hyperopt-loss",
        "SharpeHyperOptLoss",
        "--spaces",
        "buy",
        "sell",
        "stoploss",
        "roi",
        "--epochs",
        str(epochs),
        "--timeframe",
        timeframe,
        "--timerange",
        f"{train_start}-{train_end}",
        "--datadir",
        data_dir,
        "-j",
        "-1",
        "--no-color",
        "--disable-param-export",  # Don't overwrite live strategy yet!
    ]

    log_file = BASE_DIR / "logs" / f"shadow_hyperopt_{strategy}.log"
    print(f"[{strategy}] Starting IN-SAMPLE Train ({train_start}-{train_end})")

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{BASE_DIR}:{BASE_DIR}/freqtrade"

    result = subprocess.run(
        cmd, cwd=BASE_DIR, capture_output=True, text=True, timeout=1800, env=env
    )

    with open(log_file, "a") as f:
        f.write(f"\n=== IN-SAMPLE TRAIN {datetime.now().isoformat()} ===\n")
        f.write(result.stdout)
        f.write(result.stderr)

    if result.returncode != 0:
        print(f"[{strategy}] Hyperopt failed.")
        return {"success": False}

    best_sharpe = None
    for line in result.stdout.split("\n"):
        if "Best Sharpe" in line or "Sharpe Ratio" in line:
            try:
                best_sharpe = float(line.split(":")[-1].strip())
            except Exception:
                pass

    # ---------------------------------------------------------
    # OUT-OF-SAMPLE VALIDATION PHASE
    # ---------------------------------------------------------
    latest_fthypt = get_latest_fthypt(strategy)
    if not latest_fthypt:
        print(f"[{strategy}] No .fthypt file found for extraction.")
        return {"success": False}

    print(f"[{strategy}] Extracting params from {latest_fthypt.name}")
    show_cmd = [
        freqtrade_bin,
        "hyperopt-show",
        "--hyperopt-filename",
        latest_fthypt.name,
        "-n",
        "-1",
        "--print-json",
    ]
    show_res = subprocess.run(show_cmd, cwd=BASE_DIR, capture_output=True, text=True, env=env)

    json_str = None
    for line in show_res.stdout.split("\n"):
        if line.startswith("{") and '"params"' in line:
            json_str = line
            break

    if not json_str:
        print(f"[{strategy}] Failed to parse JSON parameters from hyperopt-show.")
        return {"success": False}

    # Setup test sandbox
    test_dir = BASE_DIR / "user_data/shadow_test"
    test_dir.mkdir(parents=True, exist_ok=True)

    # Write JSON params to sandbox
    with open(test_dir / f"{strategy}.json", "w") as f:
        f.write(json_str)

    # Copy strategy python file to sandbox
    strat_src = BASE_DIR / f"strategies/active/{strategy}.py"
    shutil.copy(strat_src, test_dir / f"{strategy}.py")

    print(f"[{strategy}] Running OUT-OF-SAMPLE Backtest ({test_start}-{test_end})")
    bt_cmd = [
        freqtrade_bin,
        "backtesting",
        "--strategy",
        strategy,
        "--strategy-path",
        str(test_dir),
        "--config",
        str(BASE_DIR / "config/config_paper.json"),
        "--config",
        str(BASE_DIR / f"config/{strat_config}"),
        "--timerange",
        f"{test_start}-{test_end}",
        "--timeframe",
        timeframe,
        "--datadir",
        data_dir,
        "--export",
        "trades",
        "--export-directory",
        str(BASE_DIR / "user_data/backtest_results"),
    ]
    bt_res = subprocess.run(bt_cmd, cwd=BASE_DIR, capture_output=True, text=True, env=env)

    with open(log_file, "a") as f:
        f.write(f"\n=== OUT-OF-SAMPLE VALIDATION {datetime.now().isoformat()} ===\n")
        f.write(bt_res.stdout)

    # Parse backtest results
    bt_results_file = BASE_DIR / "user_data/backtest_results/.last_result.json"
    try:
        with open(bt_results_file) as f:
            bt_data = json.load(f)
            strat_stats = bt_data["strategy"][strategy]
            oos_profit_pct = strat_stats["profit_total_pct"]
            oos_drawdown = strat_stats["max_drawdown_account"]

            print(
                f"[{strategy}] OOS Results -> Profit: {oos_profit_pct * 100:.2f}%, Drawdown: {oos_drawdown * 100:.2f}%"
            )

            if oos_profit_pct <= 0:
                print(f"[{strategy}] ❌ REJECTED: OOS Profit is negative.")
                return {"success": False}

            if oos_drawdown > MAX_DRAWDOWN_LIMIT:
                print(
                    f"[{strategy}] ❌ REJECTED: OOS Drawdown {oos_drawdown * 100:.2f}% > {MAX_DRAWDOWN_LIMIT * 100:.0f}%"
                )
                return {"success": False}

    except Exception as e:
        print(f"[{strategy}] Failed to parse backtest results: {e}")
        return {"success": False}

    print(f"[{strategy}] ✅ PASSED OOS Validation!")
    return {
        "strategy": strategy,
        "best_sharpe": best_sharpe,
        "success": True,
        "oos_profit": oos_profit_pct,
        "oos_drawdown": oos_drawdown,
    }


def check_improvement(result: dict) -> bool:
    strategy = result["strategy"]
    new_sharpe = result["best_sharpe"]

    baseline_file = BASE_DIR / "qnt/shadow/baselines.json"

    if not baseline_file.exists():
        baseline_file.parent.mkdir(parents=True, exist_ok=True)
        with open(baseline_file, "w") as f:
            json.dump(
                {strategy: {"sharpe": new_sharpe, "timestamp": datetime.now().isoformat()}}, f
            )
        return False

    try:
        with open(baseline_file) as f:
            baselines = json.load(f)
    except Exception:
        baselines = {}

    current = baselines.get(strategy, {}).get("sharpe")
    if current is None:
        baselines[strategy] = {"sharpe": new_sharpe, "timestamp": datetime.now().isoformat()}
        with open(baseline_file, "w") as f:
            json.dump(baselines, f, indent=2)
        return False

    improvement = (new_sharpe - current) / abs(current) if current != 0 else 0
    print(
        f"[{strategy}] Sharpe: {current:.3f} → {new_sharpe:.3f} (improvement: {improvement * 100:.1f}%)"
    )

    if improvement >= IMPROVEMENT_THRESHOLD:
        print(f"[{strategy}] 🔥 AUTO-PROMOTING NEW PARAMETERS!")

        # Auto-Promote
        src_json = BASE_DIR / f"user_data/shadow_test/{strategy}.json"
        dest_json = BASE_DIR / f"strategies/active/{strategy}.json"
        shutil.copy(src_json, dest_json)

        # Update baseline
        baselines[strategy] = {"sharpe": new_sharpe, "timestamp": datetime.now().isoformat()}
        with open(baseline_file, "w") as f:
            json.dump(baselines, f, indent=2)

        send_telegram_alert(
            f"🚀 **Shadow Auto-Promotion:** {strategy}\n\n"
            f"✅ Passed OOS Validation (Profit: {result['oos_profit'] * 100:.2f}%, Drawdown: {result['oos_drawdown'] * 100:.2f}%)\n"
            f"📈 Sharpe improved {improvement * 100:.1f}% ({current:.3f} → {new_sharpe:.3f})\n"
            f"⚡ Parameters automatically injected into live bot!"
        )
        return True
    return False


def main_loop():
    print("🌑 Shadow Hyperopt started — Train/Test Validation Mode Active")

    while True:
        save_state()

        for strategy in STRATEGIES:
            result = run_shadow_hyperopt(strategy)

            if result and result.get("success") and result.get("best_sharpe") is not None:
                check_improvement(result)

            time.sleep(30)

        print("⏳ Shadow loop sleeping 1 hour...")
        time.sleep(3600)


if __name__ == "__main__":
    main_loop()
