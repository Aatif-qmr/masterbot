# qnt/learning/outcome_validator.py
import csv
import glob
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

HOME = Path.home()
BASE_DIR = HOME / "cipher"
SCORES_PATH = BASE_DIR / "qnt/learning/scores.json"
SENTIMENT_HISTORY = BASE_DIR / "sentiment/scores/history.csv"
THESIS_DIR = BASE_DIR / "thesis/history"
SKEPTIC_LOG = BASE_DIR / "logs/skeptic.log"


def _load_sentiment_history() -> list:
    rows = []
    try:
        with open(SENTIMENT_HISTORY) as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    rows.append(
                        {
                            "ts": datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")),
                            "score": float(row["score"]),
                            "reddit": float(row.get("reddit", 0)),
                            "news": float(row.get("news", 0)),
                            "coingecko": float(row.get("coingecko", 0)),
                            "feargreed": float(row.get("feargreed", 0)),
                            "funding": float(row.get("funding", 0)),
                        }
                    )
                except Exception:
                    pass
    except Exception:
        pass
    return rows


def _closest_sentiment(sentiment_rows: list, ts: datetime) -> dict:
    if not sentiment_rows:
        return {}
    best = min(sentiment_rows, key=lambda r: abs((r["ts"] - ts).total_seconds()))
    return best


def _load_closed_trades() -> list:
    trades = []
    for db_path in glob.glob(str(BASE_DIR / "user_data/*.sqlite")):
        try:
            conn = sqlite3.connect(db_path)
            rows = conn.execute(
                "SELECT pair, strategy, open_date, close_date, close_profit "
                "FROM trades WHERE is_open=0 AND close_profit IS NOT NULL "
                "ORDER BY close_date DESC LIMIT 200"
            ).fetchall()
            conn.close()
            for r in rows:
                try:
                    open_dt = datetime.fromisoformat(r[2]).replace(tzinfo=UTC)
                    trades.append(
                        {"pair": r[0], "strategy": r[1], "open_dt": open_dt, "profit": float(r[4])}
                    )
                except Exception:
                    pass
        except Exception:
            pass
    return trades


def _score_thesis_accuracy(trades: list, sentiment_rows: list) -> dict:
    # Load thesis history files — one JSON per (pair, timestamp) snapshot
    pair_scores = {}
    thesis_history = list(THESIS_DIR.glob("*.json")) if THESIS_DIR.exists() else []

    thesis_snapshots = []
    for f in thesis_history:
        try:
            data = json.loads(f.read_text())
            ts = datetime.fromisoformat(data["generated_at"].replace("Z", "+00:00"))
            thesis_snapshots.append(
                {
                    "pair": data["pair"].replace("/", "_"),
                    "bias": data["bias"],
                    "confidence": data.get("confidence", 0.5),
                    "ts": ts,
                }
            )
        except Exception:
            pass

    for trade in trades:
        pair_slug = trade["pair"].replace("/", "_")
        # Find closest thesis snapshot before trade open
        candidates = [
            s for s in thesis_snapshots if s["pair"] == pair_slug and s["ts"] <= trade["open_dt"]
        ]
        if not candidates:
            continue
        snap = max(candidates, key=lambda s: s["ts"])
        # Was the bias correct?
        bias = snap["bias"]
        profit = trade["profit"]
        correct = (
            (bias == "BUY" and profit > 0) or (bias == "SELL" and profit < 0) or (bias == "HOLD")
        )
        if pair_slug not in pair_scores:
            pair_scores[pair_slug] = []
        pair_scores[pair_slug].append(1.0 if correct else 0.0)

    return {p: round(sum(v[-20:]) / len(v[-20:]), 3) for p, v in pair_scores.items() if v}


def _score_sentiment_correlation(trades: list, sentiment_rows: list) -> dict:
    if not trades or not sentiment_rows:
        return {}
    components = ["reddit", "news", "coingecko", "feargreed", "funding"]
    component_data = {c: [] for c in components}
    profits = []

    for trade in trades:
        snap = _closest_sentiment(sentiment_rows, trade["open_dt"])
        if not snap:
            continue
        profits.append(trade["profit"])
        for c in components:
            component_data[c].append(snap.get(c, 0.0))

    if len(profits) < 5:
        return {}

    correlations = {}
    n = len(profits)
    profit_mean = sum(profits) / n
    profit_std = (sum((p - profit_mean) ** 2 for p in profits) / n) ** 0.5
    if profit_std == 0:
        return {}

    for c in components:
        vals = component_data[c]
        if not vals:
            continue
        v_mean = sum(vals) / n
        v_std = (sum((v - v_mean) ** 2 for v in vals) / n) ** 0.5
        if v_std == 0:
            correlations[c] = 0.0
            continue
        cov = sum((vals[i] - v_mean) * (profits[i] - profit_mean) for i in range(n)) / n
        correlations[c] = round(cov / (v_std * profit_std), 4)

    return correlations


def _score_skeptic_false_positives() -> float:
    if not SKEPTIC_LOG.exists():
        return 0.0
    blocks = []
    try:
        with open(SKEPTIC_LOG) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("decision") == "BLOCK":
                        blocks.append(entry)
                except Exception:
                    pass
    except Exception:
        return 0.0

    if not blocks:
        return 0.0

    # We can't know counterfactuals easily — use a proxy:
    # blocks where failure_confidence < 0.5 are considered uncertain blocks
    # (the skeptic wasn't very sure but still blocked)
    uncertain = sum(1 for b in blocks if float(b.get("failure_confidence", 1.0)) < 0.5)
    return round(uncertain / len(blocks), 3)


def _score_regime_accuracy(trades: list) -> float:
    # Proxy: trades that entered in correct regime assumption (non-RANGING) that won
    # vs entered in wrong regime that lost — approximated from trade stats
    wins = sum(1 for t in trades if t["profit"] > 0)
    total = len(trades)
    if total == 0:
        return 0.5
    return round(wins / total, 3)


def run() -> dict:
    trades = _load_closed_trades()
    sentiment_rows = _load_sentiment_history()

    scores = {
        "updated_at": datetime.now(UTC).isoformat(),
        "trade_count": len(trades),
        "thesis_accuracy": _score_thesis_accuracy(trades, sentiment_rows),
        "regime_accuracy": _score_regime_accuracy(trades),
        "skeptic_false_positive_rate": _score_skeptic_false_positives(),
        "sentiment_correlations": _score_sentiment_correlation(trades, sentiment_rows),
    }

    SCORES_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCORES_PATH.write_text(json.dumps(scores, indent=2))
    print(f"[outcome_validator] Scored {len(trades)} trades → {SCORES_PATH}")
    return scores


if __name__ == "__main__":
    import pprint

    pprint.pprint(run())
