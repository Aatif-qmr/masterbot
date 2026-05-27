"""Oracle tools: macro headwinds, sentiment, regime."""

import json
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_BASE / "qnt/oracle"))
sys.path.insert(0, str(_BASE / "qnt/memory"))


def get_macro_headwinds() -> dict:
    """Read cached macro state (DXY, BTC funding rate, open interest)."""
    macro_file = _BASE / "risk/macro_state.json"
    if macro_file.exists():
        try:
            return json.loads(macro_file.read_text())
        except Exception as e:
            return {"error": str(e)}
    return {"status": "unavailable", "reason": "macro_state.json not found"}


def get_macro_history(n: int = 5) -> list:
    """Read last N entries from macro history file."""
    history_file = _BASE / "risk/macro_history.json"
    if not history_file.exists():
        return []
    try:
        entries = json.loads(history_file.read_text())
        return entries[-n:] if entries else []
    except Exception:
        return []


def get_sentiment_summary() -> str:
    """Get current sentiment explanation from all sources."""
    try:
        from oracle_sentiment import explain_sentiment
        return explain_sentiment()
    except Exception as e:
        return f"Sentiment unavailable: {e}"


def get_current_sentiment() -> dict:
    """Get raw sentiment scores from all sources."""
    try:
        from oracle_sentiment import get_current_sentiment
        return get_current_sentiment()
    except Exception as e:
        return {"error": str(e)}


def get_calendar_risk() -> dict:
    """Get macro calendar risk level for current date."""
    try:
        from oracle_calendar import calculate_risk_level
        from datetime import datetime, timezone
        return calculate_risk_level(datetime.now(timezone.utc))
    except Exception as e:
        return {"error": str(e), "level": "UNKNOWN"}


def get_anomaly_scan() -> dict:
    """Run market anomaly detection."""
    try:
        from oracle_anomaly import detect_anomalies
        return detect_anomalies()
    except Exception as e:
        return {"error": str(e)}
