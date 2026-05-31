#!/usr/bin/env python3
"""
Automated post-mortem analysis for losing and winning trades.
Runs every 2 hours via cron. Logs lessons to qnt vault.
"""

import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl
from dotenv import load_dotenv

# Detect BASE_DIR
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "qnt/oracle"))

# Load environment variables
load_dotenv(BASE_DIR / ".env")

from qnt.oracle.hmm_regime import detect_regime_full
from qnt.vault.vault import store_lesson


def analyze_recent_trades(db_path: str, hours: int = 2) -> list:
    """Extract losing and winning trades from last N hours."""
    if not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    since = (datetime.now() - timedelta(hours=hours)).timestamp()

    # Try to find the correct table structure
    try:
        # Fetch losses > 1% (close_profit < -0.01) and wins > 3% (close_profit > 0.03)
        query = """
        SELECT pair, open_date, close_date, close_profit as profit_ratio, 
               open_rate, close_rate, stake_amount, strategy
        FROM trades 
        WHERE close_date IS NOT NULL 
          AND close_date >= ?
          AND (close_profit < -0.01 OR close_profit > 0.03)
        ORDER BY close_date DESC
        """

        cursor.execute(query, (datetime.fromtimestamp(since).isoformat(),))
        trades = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Query error: {e}")
        trades = []

    conn.close()
    return trades


def get_market_context_at_open(trade: dict) -> dict:
    """Retrieves sentiment score and HMM regime at trade open time."""
    context = {"sentiment_score": "0.0", "regime": "RANGING", "regime_confidence": 0.5}

    # 1. Get sentiment score from sentiment/scores/history.csv
    try:
        sentiment_csv = BASE_DIR / "sentiment/scores/history.csv"
        if sentiment_csv.exists():
            hist = pl.read_csv(sentiment_csv)
            hist = hist.with_columns(pl.col("timestamp").str.to_datetime(strict=False))
            open_dt = datetime.fromisoformat(trade["open_date"].replace("Z", "+00:00")).replace(
                tzinfo=None
            )
            diffs = (hist["timestamp"] - open_dt).abs()
            idx = diffs.arg_min()
            if idx is not None:
                context["sentiment_score"] = f"{hist['score'][idx]:.4f}"
    except Exception as e:
        print(f"Error fetching sentiment at open: {e}")

    # 2. Get HMM regime from BTC_USDT-1h.feather
    try:
        feather_path = BASE_DIR / "user_data/data/binance/BTC_USDT-1h.feather"
        if feather_path.exists():
            df = pl.read_ipc(feather_path)
            open_dt = datetime.fromisoformat(trade["open_date"].replace("Z", "+00:00")).replace(
                tzinfo=None
            )
            # Strip timezone if present so comparison is naive
            if df["date"].dtype in (pl.Datetime("us", "UTC"), pl.Datetime("ms", "UTC")):
                df = df.with_columns(pl.col("date").dt.replace_time_zone(None))
            df_at_open = df.filter(pl.col("date") <= open_dt).tail(200).to_pandas()

            reg_info = detect_regime_full(df_at_open)
            context["regime"] = reg_info.get("current_regime", "RANGING")
            context["regime_confidence"] = reg_info.get("confidence", 0.5)
    except Exception as e:
        print(f"Error fetching HMM regime at open: {e}")

    return context


def generate_ai_analysis(trade: dict, context: dict) -> str:
    """Generates detailed Senior Quant analysis of a trade and its market context."""
    try:
        duration_minutes = (
            (
                datetime.fromisoformat(trade["close_date"].replace("Z", "+00:00"))
                - datetime.fromisoformat(trade["open_date"].replace("Z", "+00:00"))
            ).total_seconds()
            / 60
            if trade["close_date"]
            else 0
        )
    except Exception:
        duration_minutes = 0

    outcome = "WIN" if trade["profit_ratio"] > 0 else "LOSS"
    profit_pct = trade["profit_ratio"] * 100

    # Deterministic quantitative analysis based on rules
    assessment = ""
    hypothesis = ""
    recommendations = []

    # 1. Performance Assessment logic
    if outcome == "WIN":
        assessment += f"Trade executed successfully on **{trade['pair']}** via **{trade['strategy']}**, returning **+{profit_pct:.2f}%** profit. "
        try:
            score = float(context["sentiment_score"])
        except Exception:
            score = 0.0
        if score > 0.1 and context["regime"] == "BULL":
            assessment += "Entry aligned perfectly with macro tailwinds (Bullish regime & positive sentiment), enabling rapid profit target capture."
        else:
            assessment += f"Successful execution despite counter-trend environment (Regime: {context['regime']}, Sentiment: {context['sentiment_score']})."
    else:
        assessment += f"Trade on **{trade['pair']}** via **{trade['strategy']}** terminated at a loss of **{profit_pct:.2f}%**. "
        try:
            score = float(context["sentiment_score"])
        except Exception:
            score = 0.0
        if score < -0.1 or context["regime"] == "BEAR":
            assessment += f"Entry suffered from severe macro headwinds. Executing longs in a BEAR regime / negative sentiment ({context['sentiment_score']}) exposes positions to systemic selling pressure."
        else:
            assessment += f"Loss occurred during neutral/favorable conditions (Regime: {context['regime']}). This points to local micro-structure anomalies, sudden orderbook depletion, or premature stoploss triggering."

    # 2. Hypothesis logic
    if outcome == "LOSS":
        try:
            score = float(context["sentiment_score"])
        except Exception:
            score = 0.0
        if context["regime"] == "BEAR" and trade["strategy"] not in ["BearScalpV1"]:
            hypothesis += "Regime Mismatch: Non-bear strategy executed a long trade during a confirmed HMM BEAR regime. High probability of trend-continuation stopout."
        elif score < -0.2:
            hypothesis += f"Sentiment Lag / Headwind: Entered long while global sentiment was highly negative ({context['sentiment_score']}). Negative news or market-wide panic invalidated the technical triggers."
        elif duration_minutes < 15:
            hypothesis += "Premature Stopout: Trade duration was very short (under 15 mins). Stoploss might be set too tight relative to the current ATR volatility band."
        else:
            hypothesis += "Execution Slippage or Momentum Exhaustion: The trade was open for a standard duration but failed to reach take-profit targets, reversing as momentum exhausted."
    else:
        hypothesis += f"Trend Alignment: Strong momentum persistence under {context['regime']} regime. Sentiment of {context['sentiment_score']} supported buy-side liquidity."

    # 3. Recommendations
    if outcome == "LOSS":
        try:
            score = float(context["sentiment_score"])
        except Exception:
            score = 0.0
        recommendations.append(
            "Apply a hard regime filter: restrict long entries if the current HMM regime is BEAR."
        )
        if score < -0.1:
            recommendations.append(
                f"Implement a minimum sentiment threshold of -0.05 for {trade['strategy']} entries."
            )
        if duration_minutes < 15:
            recommendations.append(
                "Review ATR-based stoploss multiplier; consider expanding stops to avoid volatility noise."
            )
        else:
            recommendations.append(
                "Implement a time-based exit or trailing stop to lock in partial profits during stalling momentum."
            )
    else:
        recommendations.append(
            "Maintain current strategy entry/exit logic for this regime footprint."
        )
        recommendations.append(
            "Evaluate increasing capital allocation to this slot during rebalancing."
        )

    # Format report as Markdown
    report = f"""### Senior Quant Performance Assessment

#### 1. Performance Assessment
{assessment}
- **Duration**: `{duration_minutes:.1f} minutes`
- **Execution Rate**: `{trade["open_rate"]} -> {trade["close_rate"]}`

#### 2. Hypothesis
- **Primary Driver**: {hypothesis}

#### 3. Actionable Recommendations
- {recommendations[0]}
- {recommendations[1] if len(recommendations) > 1 else "Continue monitoring strategy performance."}
"""
    return report


STRATEGY_DBS = {
    "ScalpV1": BASE_DIR / "user_data/scalp.sqlite",
    "SwingV1": BASE_DIR / "user_data/swing.sqlite",
    "MeanReversionV1": BASE_DIR / "user_data/mean_reversion.sqlite",
    "TrendFollowV1": BASE_DIR / "user_data/trend_follow.sqlite",
    "DailyTrendV1": BASE_DIR / "user_data/daily.sqlite",
    "BearScalpV1": BASE_DIR / "user_data/bear_scalp.sqlite",
    "MicroScalpV1": BASE_DIR / "user_data/tradesv3_micro.sqlite",
}


def main():
    hours = 2
    if len(sys.argv) > 1:
        try:
            hours = int(sys.argv[1])
        except ValueError:
            pass

    all_trades = []
    for strategy_name, db_path in STRATEGY_DBS.items():
        if not db_path.exists():
            continue
        trades = analyze_recent_trades(str(db_path), hours=hours)
        # Tag with strategy name in case the DB column is missing
        for t in trades:
            if not t.get("strategy"):
                t["strategy"] = strategy_name
        all_trades.extend(trades)

    if not all_trades:
        print(f"No notable trades in last {hours}h across all strategy DBs.")
        return

    # Group summary by strategy
    by_strategy: dict = {}
    for t in all_trades:
        s = t.get("strategy", "unknown")
        by_strategy.setdefault(s, []).append(t)

    for s, trades in by_strategy.items():
        wins = [t for t in trades if t["profit_ratio"] > 0]
        losses = [t for t in trades if t["profit_ratio"] <= 0]
        avg_profit = sum(t["profit_ratio"] for t in trades) / len(trades)
        print(
            f"[{s}] {len(trades)} trades | {len(wins)}W/{len(losses)}L | avg {avg_profit * 100:+.2f}%"
        )

    for trade in all_trades:
        is_win = trade["profit_ratio"] > 0
        outcome_type = "trade_success" if is_win else "trade_postmortem"

        context = get_market_context_at_open(trade)
        analysis_text = generate_ai_analysis(trade, context)

        timestamp_str = datetime.now().isoformat()
        timestamp_clean = timestamp_str.replace(":", "-").replace(".", "_")
        lesson_id = f"{outcome_type}_{trade.get('pair', 'unk').replace('/', '_')}_{timestamp_clean}"

        metadata = {
            "pair": trade["pair"],
            "strategy": trade["strategy"],
            "type": outcome_type,
            "timestamp": timestamp_str,
            "profit_ratio": float(trade["profit_ratio"]),
            "sentiment_score": float(context["sentiment_score"])
            if context["sentiment_score"] != "N/A"
            else 0.0,
            "regime": context["regime"],
            "regime_confidence": float(context["regime_confidence"]),
        }

        store_lesson(lesson_id, analysis_text, metadata)
        outcome_str = (
            f"Win (+{trade['profit_ratio'] * 100:.2f}%)"
            if is_win
            else f"Loss ({trade['profit_ratio'] * 100:.2f}%)"
        )
        print(f"Logged {outcome_type}: {trade['pair']} [{trade['strategy']}] {outcome_str}")

    print(
        f"Post-mortem complete. Processed {len(all_trades)} trades across {len(by_strategy)} strategies."
    )


if __name__ == "__main__":
    main()
