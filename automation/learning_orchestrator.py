# automation/learning_orchestrator.py
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import requests

HOME = Path.home()
BASE_DIR = HOME / "cipher"
LOG_PATH = BASE_DIR / "logs/learning.log"

sys.path.insert(0, str(BASE_DIR / "qnt/learning"))
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT_ID")
QNT_TOKEN = os.getenv("QNT_TELEGRAM_TOKEN")
QNT_CHAT = os.getenv("QNT_TELEGRAM_CHAT_ID")


def _send_telegram(text: str):
    for token, chat in [(TELEGRAM_TOKEN, TELEGRAM_CHAT), (QNT_TOKEN, QNT_CHAT)]:
        if token and chat:
            try:
                requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat, "text": text, "parse_mode": "HTML"},
                    timeout=10,
                )
            except Exception as e:
                print(f"Telegram send error: {e}")


def _log(msg: str):
    ts = datetime.now(UTC).isoformat()
    line = f"[{ts}] {msg}"
    print(line)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def run():
    start = datetime.now(UTC)
    _log("=== Learning cycle started ===")
    results = {}

    # 1. Outcome Validator
    try:
        from outcome_validator import run as run_validator

        scores = run_validator()
        results["scores"] = scores
        _log(f"Outcome validator: {scores.get('trade_count', 0)} trades scored")
    except Exception as e:
        _log(f"Outcome validator FAILED: {e}")
        results["scores"] = {}

    # 2. Param Optimizer
    try:
        from param_optimizer import run as run_params

        param_changes = run_params()
        results["param_changes"] = param_changes
        _log(f"Param optimizer: {len(param_changes)} strategies updated")
    except Exception as e:
        _log(f"Param optimizer FAILED: {e}")
        results["param_changes"] = {}

    # 3. Sentiment Calibrator
    try:
        from sentiment_calibrator import run as run_sentiment

        new_weights = run_sentiment()
        results["sentiment_weights"] = new_weights
        _log("Sentiment calibrator: weights updated")
    except Exception as e:
        _log(f"Sentiment calibrator FAILED: {e}")
        results["sentiment_weights"] = {}

    # 4. Constraint Extractor
    try:
        from constraint_extractor import run as run_constraints

        constraints = run_constraints()
        n_rules = sum(len(v) for v in constraints.get("constraints", {}).values())
        results["constraint_rules"] = n_rules
        _log(f"Constraint extractor: {n_rules} active rules")
    except Exception as e:
        _log(f"Constraint extractor FAILED: {e}")
        results["constraint_rules"] = 0

    elapsed = (datetime.now(UTC) - start).seconds

    # Build Telegram summary
    scores = results.get("scores", {})
    thesis_acc = scores.get("thesis_accuracy", {})
    thesis_str = " | ".join(f"{p}: {v:.0%}" for p, v in thesis_acc.items()) or "n/a"
    regime_acc = scores.get("regime_accuracy", 0)
    fp_rate = scores.get("skeptic_false_positive_rate", 0)

    param_changes = results.get("param_changes", {})
    param_str = ""
    for strat, changes in param_changes.items():
        for param, delta in changes.items():
            param_str += f"\n  • {strat}.{param}: {delta['from']} → {delta['to']}"

    weights = results.get("sentiment_weights", {})
    if isinstance(weights, dict) and "weights" not in weights:
        top_source = max(weights, key=weights.get) if weights else "n/a"
    else:
        top_source = "n/a"

    text = (
        f"🧠 <b>Learning Cycle Complete</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Signal Accuracy</b>\n"
        f"• Thesis: {thesis_str}\n"
        f"• Regime: {regime_acc:.0%}\n"
        f"• Skeptic false-positive: {fp_rate:.0%}\n\n"
        f"<b>Adaptations</b>\n"
        f"• Params changed:{param_str if param_str else ' none'}\n"
        f"• Top sentiment source: {top_source}\n"
        f"• Active vault constraints: {results.get('constraint_rules', 0)}\n\n"
        f"<i>⏱ {elapsed}s | {start.strftime('%Y-%m-%dT%H:%M')}Z</i>"
    )

    _send_telegram(text)
    _log(f"=== Learning cycle done ({elapsed}s) ===")
    return results


if __name__ == "__main__":
    run()
