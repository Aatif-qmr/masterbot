import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime

# Add paths
from pathlib import Path as _Path

import pandas as pd

BASE_DIR = str(_Path(__file__).resolve().parent.parent.parent)
sys.path.insert(0, os.path.join(BASE_DIR, "qnt/memory"))
sys.path.insert(0, os.path.join(BASE_DIR, "qnt/bridge"))
sys.path.insert(0, os.path.join(BASE_DIR, "qnt/shield"))

from device_router import get_current_device, run_on_m1, run_on_m2
from memory_manager import log_action
from qnt_notifier import send_escalation, send_notify

DEVICE = get_current_device()
M2_PATH = "/Users/azmatsaif/cipher"  # remote machine
M1_PATH = BASE_DIR
CANDIDATES_DIR = os.path.join(DEVICE["cipher_path"], "strategies/candidates")
ACTIVE_DIR = os.path.join(DEVICE["cipher_path"], "strategies/active")

os.makedirs(CANDIDATES_DIR, exist_ok=True)


def generate_strategy(hypothesis):
    """Generate a Freqtrade strategy based on a hypothesis."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    class_name = f"Auto{timestamp}"

    prompt = f"""Write a complete Freqtrade strategy Python file based on this hypothesis: {hypothesis}
    
    Requirements:
    - Follow exact Freqtrade v3 format
    - Include populate_indicators, populate_entry_trend, populate_exit_trend
    - Use pandas_ta for indicators
    - Include stoploss = -0.04
    - Include stoploss_on_exchange = True
    - Include sentiment gate (import from {M1_PATH}/sentiment/reader.py)
    - Include risk manager integration (import run_all_checks from {M1_PATH}/risk/risk_manager.py)
    - IMPORTANT: When calling run_all_checks, pass recent_trades as a list of dicts including 'profit_ratio' AND 'close_date' from Trade.get_trades_proxy(is_open=False).
    - Add detailed comments explaining logic
    - Class name: {class_name}
    
    Return ONLY the Python code, no explanation."""

    print(f"Generating strategy for hypothesis: {hypothesis}...")

    qnt_path = "/Users/aatifquamre/.local/share/fnm/node-versions/v25.9.0/installation/bin/qnt"
    result = subprocess.run(
        [qnt_path, "-p", prompt, "--output-format", "text"],
        capture_output=True,
        text=True,
        timeout=180,
    )

    if result.returncode != 0:
        print(f"Generation failed: {result.stderr}")
        return None

    code = result.stdout.strip()
    # Remove markdown code fences
    code = re.sub(r"^```python\s*", "", code)
    code = re.sub(r"^```\s*", "", code)
    code = re.sub(r"\s*```$", "", code)

    # Basic validation
    if "class " + class_name not in code:
        print("Generated code lacks correct class name.")
        # Try to fix class name if it chose a different one
        code = re.sub(r"class \w+\(IStrategy\):", f"class {class_name}(IStrategy):", code)

    filename = f"{class_name}_{hypothesis[:20].lower().replace(' ', '_')}.py"
    filepath = os.path.join(CANDIDATES_DIR, filename)

    with open(filepath, "w") as f:
        f.write(code)

    # Syntax check
    try:
        subprocess.run(["python3", "-m", "py_compile", filepath], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"Syntax check failed: {e.stderr}")
        log_action("strategy_gen_failed", f"Syntax error in {filename}", DEVICE["device"])
        return None

    log_action("strategy_generated", filename, DEVICE["device"])
    send_notify(
        "Lab — Strategy Generated",
        f"🧪 New strategy generated: {filename}\nHypothesis: {hypothesis[:100]}\nSaved to: strategies/candidates/\nRun qnt-backtest to test it.",
    )

    return filepath


def run_backtest(strategy_name, timerange="20240101-20260101", timeframe=None):
    """Run backtest on M2."""
    strat_file = os.path.join(CANDIDATES_DIR, f"{strategy_name}.py")
    if not os.path.exists(strat_file):
        # Try finding it if it has a suffix
        matches = [f for f in os.listdir(CANDIDATES_DIR) if f.startswith(strategy_name)]
        if matches:
            strat_file = os.path.join(CANDIDATES_DIR, matches[0])

    # Auto-detect timeframe if not provided
    if not timeframe and os.path.exists(strat_file):
        with open(strat_file) as f:
            content = f.read()
            match = re.search(r"timeframe\s*=\s*['\"]([^'\"]+)['\"]", content)
            if match:
                timeframe = match.group(1)

    if not timeframe:
        timeframe = "1h"  # Default fallback

    if DEVICE["device"] == "M1":
        if not os.path.exists(strat_file):
            return "FAIL", f"Strategy {strategy_name} not found in candidates.", {}

        # Copy to M2
        subprocess.run(
            ["scp", strat_file, f"azmatsaif@100.74.110.36:{M2_PATH}/strategies/candidates/"]
        )

    print(f"Running backtest for {strategy_name} on M2 ({timeframe})...")

    bt_cmd = f"""
      cd {M2_PATH} &&
      unset PYTHONPATH &&
      source venv/bin/activate &&
      freqtrade backtesting \
        --strategy {strategy_name} \
        --strategy-path strategies/candidates/ \
        --config config/config_paper.json \
        --timerange {timerange} \
        --timeframe {timeframe} \
        --datadir data/
    """

    stdout, stderr, code = run_on_m2(bt_cmd)

    if code != 0:
        return "FAIL", f"Backtest execution failed:\n{stderr}", {}

    # Parse metrics (simplified regex parsing)
    metrics = {}
    try:
        # Regex for Freqtrade backtest table values
        metrics["total_profit_pct"] = (
            float(re.search(r"Total profit %.*?([\d.-]+)", stdout).group(1))
            if re.search(r"Total profit %.*?([\d.-]+)", stdout)
            else 0
        )
        metrics["total_trades"] = (
            int(re.search(r"Total trades.*?(\d+)", stdout).group(1))
            if re.search(r"Total trades.*?(\d+)", stdout)
            else 0
        )
        metrics["win_rate"] = (
            float(re.search(r"Win rate.*?([\d.]+)", stdout).group(1))
            if re.search(r"Win rate.*?([\d.]+)", stdout)
            else 0
        )
        metrics["max_drawdown"] = (
            float(re.search(r"Max drawdown.*?([\d.]+)", stdout).group(1))
            if re.search(r"Max drawdown.*?([\d.]+)", stdout)
            else 0
        )
        metrics["sharpe"] = (
            float(re.search(r"Sharpe ratio.*?([\d.-]+)", stdout).group(1))
            if re.search(r"Sharpe ratio.*?([\d.-]+)", stdout)
            else 0
        )
    except Exception:
        metrics = {"error": "Could not parse all metrics"}

    # Pass/Fail Criteria
    failed_criteria = []
    if metrics.get("total_profit_pct", 0) <= 0:
        failed_criteria.append("Profit <= 0%")
    if metrics.get("win_rate", 0) < 45:
        failed_criteria.append("Win rate < 45%")
    if metrics.get("max_drawdown", 0) > 20:
        failed_criteria.append("Max drawdown > 20%")
    if metrics.get("total_trades", 0) < 20:
        failed_criteria.append("Trades < 20")

    verdict = "PASS" if not failed_criteria else "FAIL"

    report = f"""
📊 Backtest Results: {strategy_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Period:      {timerange}
Timeframe:   {timeframe}

Total Profit:  {metrics.get("total_profit_pct", 0):.2f}%
Total Trades:  {metrics.get("total_trades", 0)}
Win Rate:      {metrics.get("win_rate", 0):.1f}%
Max Drawdown:  {metrics.get("max_drawdown", 0):.2f}%
Sharpe Ratio:  {metrics.get("sharpe", 0):.2f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Verdict: {"✅ PASS — Ready for walk-forward" if verdict == "PASS" else "❌ FAIL — Needs revision"}
"""
    if failed_criteria:
        report += f"\nCriteria failed: {', '.join(failed_criteria)}"

    log_action("backtest_completed", f"{strategy_name}: {verdict}", DEVICE["device"])
    send_notify(f"Backtest: {strategy_name}", report, level="INFO" if verdict == "PASS" else "WARN")

    return verdict, report, metrics


def evolve_strategy(strategy_name, lookback_trades=20):
    """Analyze losers and generate a V2."""
    db_path = os.path.join(M1_PATH, "user_data/tradesv3.dryrun.sqlite")
    if not os.path.exists(db_path):
        db_path = os.path.join(M1_PATH, "user_data/tradesv3.sqlite")

    try:
        conn = sqlite3.connect(db_path)
        query = f"SELECT * FROM trades WHERE strategy='{strategy_name}' AND is_open=0 ORDER BY close_date DESC LIMIT {lookback_trades}"
        df = pd.read_sql_query(query, conn)
        conn.close()
    except Exception:
        return None

    if df.empty or len(df[df["profit_ratio"] < 0]) < 3:
        return None

    losers = df[df["profit_ratio"] < 0]

    # Simple pattern analysis
    failure_pattern = f"Analyzed {len(losers)} losing trades. "
    # Add more logic here to check sentiment history or time of day

    # Read original strategy code
    strat_file = os.path.join(ACTIVE_DIR, f"{strategy_name}.py")
    if not os.path.exists(strat_file):
        strat_file = os.path.join(CANDIDATES_DIR, f"{strategy_name}.py")

    if not os.path.exists(strat_file):
        return None

    with open(strat_file) as f:
        original_code = f.read()

    prompt = f"""Read this existing Freqtrade strategy:
    {original_code}
    
    Analysis of its {len(losers)} losing trades:
    {failure_pattern}
    
    Generate an improved V2 that:
    1. Adds filters to avoid the identified failure patterns
    2. Keeps all existing winning logic
    3. Maintains all safety integrations (risk manager, sentiment gate, stop loss)
    4. Names the class: {strategy_name}V2
    
    Return ONLY the improved Python code."""

    qnt_path = "/Users/aatifquamre/.local/share/fnm/node-versions/v25.9.0/installation/bin/qnt"
    result = subprocess.run(
        [qnt_path, "-p", prompt, "--output-format", "text"],
        capture_output=True,
        text=True,
        timeout=180,
    )

    if result.returncode != 0:
        return None

    code = result.stdout.strip()
    code = re.sub(r"^```python\s*", "", code)
    code = re.sub(r"^```\s*", "", code)
    code = re.sub(r"\s*```$", "", code)

    v2_filename = f"{strategy_name}V2_{int(time.time())}.py"
    v2_path = os.path.join(CANDIDATES_DIR, v2_filename)

    with open(v2_path, "w") as f:
        f.write(code)

    send_notify(
        "Lab — Strategy Evolved",
        f"🔬 Strategy evolved: {strategy_name}V2\nAnalyzed {len(df)} trades\nV2 saved to candidates/.",
    )
    return v2_path


def optimize_strategy(strategy_name, epochs=200):
    """Run Hyperopt on M2."""
    print(f"Starting Hyperopt for {strategy_name} on M2...")

    hyp_cmd = f"""
      cd {M2_PATH} &&
      unset PYTHONPATH &&
      source venv/bin/activate &&
      nohup freqtrade hyperopt \
        --strategy {strategy_name} \
        --strategy-path strategies/active/ \
        --config config/config_paper.json \
        --hyperopt-loss SharpeHyperOptLoss \
        --spaces buy sell stoploss roi \
        --epochs {epochs} \
        --timerange 20240101-20260101 \
        -j -1 \
        > logs/hyperopt_{strategy_name}.log 2>&1 &
      echo $! > logs/hyperopt_{strategy_name}.pid
    """

    run_on_m2(hyp_cmd)

    send_notify(
        "Lab — Hyperopt Started",
        f"⚙️ Hyperopt started for {strategy_name}\nEpochs: {epochs}\nRunning on M2 in background.\nWill notify when complete.",
    )
    return True


def deploy_strategy(strategy_file, force=False):
    """Deploy strategy to active/ folder."""
    filename = os.path.basename(strategy_file)
    strategy_name = filename.split("_")[0].split(".")[0]

    if not force:
        # Check current active
        active_strats = [f for f in os.listdir(ACTIVE_DIR) if f.endswith(".py")]

        msg_id = send_escalation(
            situation=f"Strategy {strategy_name} ready to deploy.",
            options=[
                "Deploy alongside existing strategies",
                "Deploy and replace existing Strategy 2",
                "Deploy and replace ALL active strategies",
                "Cancel deployment",
            ],
            recommendation="Option 1 (add alongside)",
            context=f"Backtest results were positive. Current active: {active_strats}",
        )
        return "Escalated"

    # Force deployment logic
    target_path = os.path.join(ACTIVE_DIR, filename)
    subprocess.run(["cp", strategy_file, target_path])

    # Reload bot

    run_on_m1(
        'curl -s -X POST -u "$FREQTRADE_UI_USERNAME:$FREQTRADE_UI_PASSWORD" http://100.90.68.42:8080/api/v1/reload_config'
    )

    send_notify(
        "Lab — Strategy Deployed",
        f"✅ Strategy deployed: {strategy_name}\nNow active in Freqtrade.",
    )
    log_action("strategy_deployed", strategy_name, DEVICE["device"])
    return True


if __name__ == "__main__":
    # Test gen
    if len(sys.argv) > 1 and sys.argv[1] == "test-gen":
        generate_strategy("RSI under 30 buy, RSI over 70 sell")
