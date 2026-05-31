import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import psycopg
import requests
from dotenv import load_dotenv
from prefect import flow, task
from psycopg.rows import dict_row

# Load environment variables dynamically
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

# Configuration
DB_NAMES = {
    "micro": "cipher_micro",
    "scalp": "cipher_scalp",
    "mean_reversion": "cipher_mean_reversion",
    "trend_follow": "cipher_trend_follow",
    "daily": "cipher_daily",
    "swing": "cipher_swing",
    "bear_scalp": "cipher_bear_scalp",
    "hyperliquid": "cipher_hyperliquid",
}
SENTIMENT_PATH = str(BASE_DIR / "sentiment" / "scores" / "history.csv")
TELEGRAM_TOKEN = os.getenv("QNT_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("QNT_TELEGRAM_CHAT_ID")


@task(retries=3, retry_delay_seconds=10)
def gather_data():
    """Gathers all trade and sentiment metrics in a single pass from databases."""
    total_trades = 0
    total_profit_abs = 0.0
    total_profit_ratio = 0.0
    open_trades_list = []
    closed_trades_list = []
    by_strategy = {}

    for strat, db_name in DB_NAMES.items():
        try:
            conn = psycopg.connect(f"postgresql://aatifquamre:dummy@localhost/{db_name}")
            cursor = conn.cursor(row_factory=dict_row)

            cursor.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'trades')"
            )
            if not cursor.fetchone()[0]:
                conn.close()
                continue

            # Open trades
            cursor.execute("SELECT pair, strategy, open_date FROM trades WHERE is_open = true")
            for row in cursor.fetchall():
                open_trades_list.append(
                    {
                        "pair": row["pair"],
                        "strategy": row["strategy"],
                        "open_date": row["open_date"],
                    }
                )

            # Closed trades metrics
            cursor.execute(
                "SELECT COUNT(*), SUM(close_profit_abs), SUM(close_profit) FROM trades WHERE is_open = false"
            )
            count, profit_abs, profit_ratio = cursor.fetchone()
            if count:
                total_trades += count
                total_profit_abs += float(profit_abs) if profit_abs else 0.0
                total_profit_ratio += float(profit_ratio) if profit_ratio else 0.0

            # Strategy breakdown
            cursor.execute(
                "SELECT strategy, COUNT(*) as count, SUM(close_profit_abs) as profit FROM trades WHERE is_open = false GROUP BY strategy"
            )
            for row in cursor.fetchall():
                s = row["strategy"]
                if s not in by_strategy:
                    by_strategy[s] = {"trades": 0, "profit": 0.0}
                by_strategy[s]["trades"] += row["count"]
                by_strategy[s]["profit"] += float(row["profit"]) if row["profit"] else 0.0

            # Last 3 closed from this DB
            cursor.execute(
                "SELECT pair, strategy, close_profit, close_date FROM trades WHERE is_open = false ORDER BY close_date DESC LIMIT 3"
            )
            for row in cursor.fetchall():
                closed_trades_list.append(
                    {
                        "pair": row["pair"],
                        "strategy": row["strategy"],
                        "close_profit": float(row["close_profit"]) if row["close_profit"] else 0.0,
                        "close_date": row["close_date"],
                    }
                )

            conn.close()
        except Exception as e:
            print(f"Error reading database {db_name}: {e}")

    # Process sentiment average over last 7 days using Polars
    sentiment_data = "N/A"
    if os.path.exists(SENTIMENT_PATH):
        try:
            df = pl.read_csv(SENTIMENT_PATH)
            df = df.with_columns(pl.col("timestamp").str.slice(0, 19).str.to_datetime())
            cutoff = datetime.now() - timedelta(days=7)
            last_week = df.filter(pl.col("timestamp") >= cutoff)
            if not last_week.is_empty():
                avg = last_week["score"].mean()
                sentiment_data = f"{avg:.3f} ({'BULLISH' if avg > 0.3 else 'BEARISH' if avg < -0.3 else 'NEUTRAL'})"
        except Exception as e:
            print(f"Error reading sentiment history: {e}")

    return {
        "summary": {
            "total_trades": total_trades,
            "total_profit_abs": total_profit_abs,
            "total_profit_ratio": total_profit_ratio,
            "open_trades": open_trades_list,
            "closed_trades": closed_trades_list,
            "by_strategy": by_strategy,
        },
        "market_sentiment": sentiment_data,
        "timestamp": datetime.now().isoformat(),
    }


@task
def generate_quant_report(data: dict) -> str:
    """Generates the rule-based Senior Quant report from gathered data."""
    summary = data["summary"]
    by_strategy = summary["by_strategy"]

    # Identify most profitable strategy
    best_strategy = "None"
    best_profit = -999999.0
    for strat, stats in by_strategy.items():
        profit = stats.get("profit", 0.0)
        if profit > best_profit:
            best_profit = profit
            best_strategy = strat

    best_strategy_str = (
        f"**{best_strategy}** (Profit: `{best_profit:.2f}` USDT)"
        if best_strategy != "None"
        else "No active profitable strategies recorded."
    )

    # Risk suggestions based on sentiment score
    sentiment_str = data["market_sentiment"]
    sentiment_score = 0.0
    if sentiment_str != "N/A":
        try:
            sentiment_score = float(sentiment_str.split()[0])
        except Exception:
            pass

    risk_action = "MAINTAIN NEUTRAL/BALANCED RISK STATE"
    risk_rationale = "Global sentiment is in a neutral range. Execute baseline position sizes and monitor key strategy boundaries."

    if sentiment_score > 0.3:
        risk_action = "DELEGATE DYNAMIC STAKE EXPANSION (INCREASE RISK)"
        risk_rationale = f"Global sentiment is highly bullish ({sentiment_score:.3f}). Expand trending/daily cross allocations and allow trend-following strategies full leverage parameters."
    elif sentiment_score < -0.3:
        risk_action = "DELEGATE DYNAMIC STAKE CONTRACTION (DECREASE RISK / ENFORCE HEDGE)"
        risk_rationale = f"Global sentiment is highly bearish ({sentiment_score:.3f}). Contraction phase active. Reduce maximum position slots to 1, enforce tight stoplosses, and prioritize BearScalp allocations."

    # Directives
    directives = []
    if best_strategy != "None":
        directives.append(
            f"Capitalize on **{best_strategy}** outperformance; consider routing 10% more allocation to this slot during the next rebalancing cycle."
        )
    else:
        directives.append(
            "Prioritize dry-run capital preservation across all slots until a strategy demonstrates positive expectancy."
        )

    if sentiment_score > 0.3:
        directives.append(
            "Execute full size entries on TrendFollowV1 and DailyTrendV1. Ranging strategies should run with a 0.5x Kelly multiplier."
        )
    elif sentiment_score < -0.3:
        directives.append(
            "Trigger safe-mode circuit breakers on MeanReversionV1 and SwingV1. Ensure BearScalpV1 is fully online to capture downside velocity."
        )
    else:
        directives.append(
            "Enforce baseline capital allocations. Maintain standard stoploss settings and run ScalpV1/SwingV1 at standard risk parameters."
        )

    open_trades_count = len(summary["open_trades"])
    if open_trades_count >= 10:
        directives.append(
            f"Enforce strict correlation checks. With {open_trades_count} active slots, do not allow further asset overlap to prevent tail-risk clustering."
        )
    else:
        directives.append(
            "Monitor cluster health and ensure Tailscale link connectivity to M1/M2 remains stable for automated SCP model updates."
        )

    report = f"""### Senior Quant Executive Assessment

#### 1. Detailed Performance Assessment
- **Total Trades executed**: `{summary["total_trades"]}`
- **Total Net Profit**: `{summary["total_profit_abs"]:.2f} USDT`
- **Active Open Trades**: `{open_trades_count}`
- **Most Profitable Strategy**: {best_strategy_str}

#### 2. Risk Allocation Decision
- **Action**: **{risk_action}**
- **Rationale**: {risk_rationale}
- **Market Sentiment context**: `{sentiment_str}`

#### 3. Cipher Directives
- {directives[0]}
- {directives[1]}
- {directives[2]}
"""
    return report


@task
def generate_aggregated_report(data: dict) -> str:
    """Generates the aggregated stats report from gathered data."""
    summary = data["summary"]

    stats_md = "### Overall Summary\n"
    stats_md += f"- Total Closed Trades: {summary['total_trades']}\n"
    stats_md += f"- Total Cumulative Profit: {summary['total_profit_ratio']:.2%}\n\n"

    stats_md += f"### 🟢 Active/Open Trades ({len(summary['open_trades'])})\n"
    if summary["open_trades"]:
        for t in summary["open_trades"]:
            stats_md += f"- {t['pair']} ({t['strategy']}) - Opened: {t['open_date']}\n"
    else:
        stats_md += "- No active trades found.\n"

    stats_md += "\n### 🔴 Last Closed Trades\n"
    if summary["closed_trades"]:
        for t in summary["closed_trades"][:5]:
            stats_md += (
                f"- {t['pair']} ({t['strategy']}): {t['close_profit']:.2%} at {t['close_date']}\n"
            )
    else:
        stats_md += "- No closed trades found.\n"

    return stats_md


@task(retries=2, retry_delay_seconds=10)
def send_telegram_brief(date_str: str, analysis: str, aggregated: str):
    """Sends the quant intelligence brief and aggregated summary to Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram configuration missing. Skipping telegram notification.")
        return

    # Telegram message limit is 4096 characters
    short_analysis = analysis[:3500]
    msg = f"🧠 *Cipher Intelligence Brief - {date_str}*\n\n{short_analysis}"

    try:
        res = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=15,
        )
        res.raise_for_status()
        print("✓ Telegram quant briefing dispatched.")
    except Exception as e:
        print(f"❌ Failed to send Telegram quant brief: {e}")
        raise e

    # Send aggregated summary as a second message
    agg_msg = f"📊 *Cipher Aggregated Summary - {date_str}*\n\n{aggregated[:3500]}"
    try:
        res = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": agg_msg, "parse_mode": "Markdown"},
            timeout=15,
        )
        res.raise_for_status()
        print("✓ Telegram aggregated summary dispatched.")
    except Exception as e:
        print(f"❌ Failed to send Telegram aggregated summary: {e}")
        raise e


@task
def save_report_locally(date_str: str, quant_report: str, aggregated_report: str, raw_data: dict):
    """Saves reports locally as JSON for archival and downstream consumption."""
    reports_dir = BASE_DIR / "logs" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    report_payload = {
        "date": date_str,
        "generated_at": datetime.now(UTC).isoformat(),
        "quant_report": quant_report,
        "aggregated_report": aggregated_report,
        "raw_summary": raw_data["summary"]["by_strategy"],
        "sentiment": raw_data["market_sentiment"],
    }

    report_path = reports_dir / f"report_{date_str}.json"
    with open(report_path, "w") as f:
        json.dump(report_payload, f, indent=2, default=str)

    print(f"✓ Report saved locally: {report_path}")


@flow(name="Cipher Reporting Flow")
def run_reporting_flow():
    """Orchestrates Cipher's reporting pipeline.

    Tasks:
      1. gather_data — queries all SQLite databases and sentiment history
      2. generate_quant_report — builds the Senior Quant executive assessment
      3. generate_aggregated_report — builds the aggregated performance summary
      4. save_report_locally — archives the report as JSON in logs/reports/
      5. send_telegram_brief — dispatches both reports to Telegram
    """
    print("Cipher Reporting Flow starting...")

    # 1. Gather all trade data
    raw_data = gather_data()

    # 2. Generate reports
    quant_report_content = generate_quant_report(raw_data)
    aggregated_report_content = generate_aggregated_report(raw_data)

    date_str = datetime.now().strftime("%Y-%m-%d")

    # 3. Save reports locally
    save_report_locally(
        date_str=date_str,
        quant_report=quant_report_content,
        aggregated_report=aggregated_report_content,
        raw_data=raw_data,
    )

    # 4. Dispatch Telegram briefings
    send_telegram_brief(
        date_str=date_str, analysis=quant_report_content, aggregated=aggregated_report_content
    )

    print("✓ Cipher Reporting Flow complete.")


if __name__ == "__main__":
    run_reporting_flow()
