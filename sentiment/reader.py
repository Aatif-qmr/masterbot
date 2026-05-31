import json
import os
from datetime import UTC, datetime
from pathlib import Path

_SENTIMENT_SCORE = Path(__file__).resolve().parent / "scores/current_score.json"


def get_current_sentiment() -> dict:
    """
    Reads the current sentiment score from disk.
    """
    path = str(_SENTIMENT_SCORE)

    fallback = {
        "score": 0.0,
        "available": False,
        "age_minutes": 0.0,
        "sources_used": [],
        "warning": None,
    }

    if not os.path.exists(path):
        return fallback

    try:
        with open(path) as f:
            data = json.load(f)

        ts_str = data.get("timestamp")
        if not ts_str:
            return fallback

        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            now = datetime.now()
        else:
            now = datetime.now(UTC)

        age_seconds = (now - dt).total_seconds()
        age_minutes = age_seconds / 60.0

        result = {
            "score": float(data.get("score", 0.0)),
            "available": age_minutes < 120,
            "age_minutes": age_minutes,
            "sources_used": data.get("sources_used", []),
            "warning": data.get("warning"),
        }

        if not result["available"]:
            result["warning"] = f"Data stale ({age_minutes:.1f} min old)"

        return result

    except (json.JSONDecodeError, ValueError, TypeError) as e:
        fallback["warning"] = f"Error reading JSON: {str(e)}"
        return fallback


def get_funding_rate() -> float:
    """Returns normalized funding rate component (-1 to 1). 0.0 if unavailable."""
    try:
        with open(_SENTIMENT_SCORE) as f:
            data = json.load(f)
        return float(data.get("component_scores", {}).get("funding", 0.0))
    except Exception:
        return 0.0


def get_sentiment_signal(threshold_bearish=-0.3, threshold_bullish=0.3) -> str:
    """
    Returns one of: 'BULLISH', 'NEUTRAL', 'BEARISH', 'UNAVAILABLE'
    """
    sentiment = get_current_sentiment()

    if not sentiment["available"]:
        return "UNAVAILABLE"

    score = sentiment["score"]
    if score >= threshold_bullish:
        return "BULLISH"
    elif score <= threshold_bearish:
        return "BEARISH"
    else:
        return "NEUTRAL"


if __name__ == "__main__":
    sentiment = get_current_sentiment()
    signal = get_sentiment_signal()
    print("--- Sentiment Reader Test ---")
    print(f"Raw Data: {sentiment}")
    print(f"Signal:   {signal}")
