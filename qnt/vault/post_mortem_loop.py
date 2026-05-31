import json
import logging
import os
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "qnt/memory"))
sys.path.insert(0, str(BASE_DIR / "qnt/vault"))
sys.path.insert(0, str(BASE_DIR / "qnt/oracle"))

import freqtrade.data.history as history
from hmm_regime import detect_regime
from vault import store_lesson

logger = logging.getLogger(__name__)

DB_PATHS = [
    BASE_DIR / "user_data/tradesv3.dryrun.sqlite",
    BASE_DIR / "user_data/tradesv3.sqlite",
    BASE_DIR / "user_data/mean_reversion.sqlite",
    BASE_DIR / "user_data/trend_follow.sqlite",
    BASE_DIR / "user_data/scalp.sqlite",
    BASE_DIR / "user_data/swing.sqlite",
    BASE_DIR / "user_data/daily.sqlite",
    BASE_DIR / "user_data/micro.sqlite",
]

PROCESSED_TRADES_FILE = BASE_DIR / "qnt/vault/processed_trades.json"
CONSTRAINTS_DIR = BASE_DIR / "qnt/vault/constraints"
SENTIMENT_CSV = BASE_DIR / "sentiment/scores/history.csv"

os.makedirs(CONSTRAINTS_DIR, exist_ok=True)


def get_unprocessed_trades():
    """Queries all SQLite instances for new closed trades."""
    processed_ids = []
    if PROCESSED_TRADES_FILE.exists():
        with open(PROCESSED_TRADES_FILE) as f:
            processed_ids = json.load(f)

    new_trades = []

    for db_path in DB_PATHS:
        if not db_path.exists():
            continue

        try:
            conn = sqlite3.connect(db_path)
            query = "SELECT * FROM trades WHERE is_open=0"
            df = pd.read_sql_query(query, conn)
            conn.close()

            for _, row in df.iterrows():
                trade_id = f"{db_path.name}_{row['id']}"
                if trade_id not in processed_ids:
                    trade_dict = row.to_dict()
                    trade_dict["unique_id"] = trade_id
                    new_trades.append(trade_dict)
        except Exception as e:
            print(f"Error reading {db_path.name}: {e}")

    return new_trades, processed_ids


def generate_trade_analysis(trade):
    """Generates AI analysis for a losing trade."""
    if trade["profit_ratio"] >= 0:
        return None

    print(f"Analyzing losing trade {trade['unique_id']} ({trade['pair']})...")

    # 1. Gather Context
    sentiment_at_open = "0.0"
    try:
        hist = pd.read_csv(SENTIMENT_CSV)
        hist["timestamp"] = pd.to_datetime(hist["timestamp"])
        open_dt = pd.to_datetime(trade["open_date"]).replace(tzinfo=None)
        hist["timestamp"] = hist["timestamp"].dt.replace(tzinfo=None)
        closest = hist.iloc[(hist["timestamp"] - open_dt).abs().argsort()[:1]]
        if not closest.empty:
            sentiment_at_open = f"{closest.iloc[0]['score']:.2f}"
    except Exception:
        pass

    # 2. HMM Regime at Open
    regime_at_open = "Unknown"
    try:
        # Load 1h BTC history for regime context
        data = history.load_pair_history(
            pair="BTC/USDT",
            timeframe="1h",
            datadir=BASE_DIR / "data",  # Assumes synced from M2
        )
        # Filter data up to open_date
        open_dt_aware = pd.to_datetime(trade["open_date"]).replace(tzinfo=UTC)
        data_at_open = data[data["date"] <= open_dt_aware].tail(200)
        regime_data = detect_regime(data_at_open)
        regime_at_open = f"{regime_data['regime']} (Conf: {regime_data['confidence']:.2f})"
    except Exception:
        pass

    # 3. Call QNT AI
    prompt = f"""
    Analyze this losing trade and extract a lesson:
    
    Strategy: {trade["strategy"]}
    Pair: {trade["pair"]}
    Entry: {trade["open_rate"]} at {trade["open_date"]}
    Exit: {trade["close_rate"]} at {trade["close_date"]}
    Loss: {trade["profit_ratio"] * 100:.2f}%
    
    Market context at entry:
    - Sentiment Score: {sentiment_at_open}
    - Market Regime: {regime_at_open}
    
    Provide:
    1. Most likely cause of this loss (1 sentence)
    2. Market condition that made this trade fail
    3. A specific rule to avoid this in future
       Format: "AVOID [StrategyName] when [condition]"
    4. Confidence this rule is generalizable (0-10)
    
    Be specific and quantitative.
    """

    qnt_bin = "/Users/aatifquamre/.local/share/fnm/node-versions/v25.9.0/installation/bin/qnt"
    res = subprocess.run(
        [qnt_bin, "-p", prompt, "--output-format", "text"], capture_output=True, text=True
    )

    if res.returncode != 0:
        return None

    analysis_text = res.stdout.strip()
    return analysis_text


def extract_lesson(analysis_text):
    """Parses analysis text to structured lesson."""
    lines = analysis_text.split("\n")
    lesson = {"cause": "Unknown", "condition": "Unknown", "rule": "Unknown", "confidence": 5}

    for line in lines:
        line = line.strip()
        if "1." in line or "cause" in line.lower():
            lesson["cause"] = line.split(":", 1)[-1].strip() if ":" in line else line
        elif "2." in line or "condition" in line.lower():
            lesson["condition"] = line.split(":", 1)[-1].strip() if ":" in line else line
        elif "3." in line or "AVOID" in line:
            lesson["rule"] = line.split(":", 1)[-1].strip() if ":" in line else line
        elif "4." in line or "confidence" in line.lower():
            try:
                import re

                match = re.search(r"\d+", line)
                if match:
                    lesson["confidence"] = int(match.group())
            except Exception:
                pass

    return lesson


def store_lesson_in_vault(lesson, trade, analysis_text):
    """Stores lesson in ChromaDB."""
    content = f"""
    LESSON from losing trade:
    Strategy: {trade["strategy"]}
    Pair: {trade["pair"]}
    Loss: {trade["profit_ratio"] * 100:.2f}%
    
    Cause: {lesson["cause"]}
    Condition: {lesson["condition"]}
    Rule: {lesson["rule"]}
    Confidence: {lesson["confidence"]}/10
    
    Full Analysis:
    {analysis_text}
    """

    metadata = {
        "timestamp": trade["close_date"],
        "strategy": trade["strategy"],
        "pair": trade["pair"],
        "outcome": "loss",
        "profit": str(trade["profit_ratio"]),
        "rule": lesson["rule"],
        "confidence": str(lesson["confidence"]),
        "category": "lesson",
    }

    lesson_id = f"trade_memory_{trade.get('unique_id', trade.get('id', 'unk'))}_{int(time.time())}"
    store_lesson(lesson_id, content, metadata)


def generate_negative_constraint(lesson, trade):
    """Converts lesson into a FreqAI-compatible negative constraint."""
    timestamp = int(time.time())
    constraint = {
        "rule": lesson["rule"],
        "strategy": trade["strategy"],
        "condition_features": ["sentiment_score", "regime"],
        "avoid_when": {"condition": lesson["condition"], "cause": lesson["cause"]},
        "confidence": lesson["confidence"],
        "created": datetime.now(UTC).isoformat(),
        "trade_id": trade["unique_id"],
    }

    file_path = CONSTRAINTS_DIR / f"constraint_{trade['unique_id']}_{timestamp}.json"
    with open(file_path, "w") as f:
        json.dump(constraint, f, indent=2)


def run_post_mortem_loop():
    """Main execution loop."""
    print(f"Starting post-mortem loop at {datetime.now()}...")
    new_trades, processed_ids = get_unprocessed_trades()

    if not new_trades:
        print("No new trades to process.")
        return

    print(f"Found {len(new_trades)} new trades.")
    lessons_count = 0

    for trade in new_trades:
        try:
            if trade["profit_ratio"] < 0:
                analysis = generate_trade_analysis(trade)
                if analysis:
                    lesson = extract_lesson(analysis)
                    store_lesson_in_vault(lesson, trade, analysis)
                    generate_negative_constraint(lesson, trade)
                    lessons_count += 1

            processed_ids.append(trade["unique_id"])
        except Exception as e:
            print(f"Error processing trade {trade['unique_id']}: {e}")

    # Save processed list
    with open(PROCESSED_TRADES_FILE, "w") as f:
        json.dump(processed_ids, f)

    print(f"Loop complete. {lessons_count} new lessons added.")

    if lessons_count > 0:
        # Send notification (placeholder for bridge logic)
        msg = (
            f"📚 {lessons_count} new lessons added to Vault. Run qnt-recall to search past lessons."
        )
        print(msg)


if __name__ == "__main__":
    run_post_mortem_loop()
