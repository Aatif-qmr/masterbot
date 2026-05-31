import os
from datetime import datetime
from pathlib import Path

import duckdb

BASE_DIR = Path(__file__).resolve().parent.parent

DB_FILES = [
    str(BASE_DIR / "user_data/micro.sqlite"),
    str(BASE_DIR / "user_data/scalp.sqlite"),
    str(BASE_DIR / "user_data/mean_reversion.sqlite"),
    str(BASE_DIR / "user_data/trend_follow.sqlite"),
    str(BASE_DIR / "user_data/daily.sqlite"),
    str(BASE_DIR / "user_data/swing.sqlite"),
]

REPORTS_FOLDER_ID = "1Vdst3YI9wFFfFPurpVVGJfrA3y2aT9BI"
DEST_EMAIL = "aatifqmr@gmail.com"


def get_combined_stats():
    total_trades = 0
    total_profit_abs = 0.0
    open_trades_list = []
    closed_trades_list = []

    con = duckdb.connect()
    for i, db_path in enumerate(DB_FILES):
        if not os.path.exists(db_path):
            continue
        alias = f"d{i}"
        try:
            con.execute(f"ATTACH '{db_path}' AS {alias} (TYPE SQLITE)")

            # Open trades
            for pair, strategy, open_date in con.execute(
                f"SELECT pair, strategy, open_date FROM {alias}.trades WHERE is_open = 1"
            ).fetchall():
                open_trades_list.append(f"{pair} ({strategy}) - Opened: {open_date}")

            # Closed trades summary
            row = con.execute(
                f"SELECT COUNT(*), SUM(close_profit) FROM {alias}.trades WHERE is_open = 0"
            ).fetchone()
            if row and row[0]:
                total_trades += row[0]
                total_profit_abs += row[1] or 0.0

            # Last 3 closed from this db
            for pair, strategy, profit, close_date in con.execute(
                f"SELECT pair, strategy, close_profit, close_date FROM {alias}.trades"
                f" WHERE is_open = 0 ORDER BY close_date DESC LIMIT 3"
            ).fetchall():
                closed_trades_list.append(f"{pair} ({strategy}): {profit:.2%} at {close_date}")

            con.execute(f"DETACH {alias}")
        except Exception as e:
            print(f"Error reading {db_path}: {e}")
            try:
                con.execute(f"DETACH {alias}")
            except Exception:
                pass
    con.close()

    stats = "### Overall Summary\n"
    stats += f"- Total Closed Trades: {total_trades}\n"
    stats += f"- Total Cumulative Profit: {total_profit_abs:.2%}\n\n"

    stats += f"### Active/Open Trades ({len(open_trades_list)})\n"
    if open_trades_list:
        for t in open_trades_list:
            stats += f"- {t}\n"
    else:
        stats += "- No active trades found.\n"

    stats += "\n### Last Closed Trades\n"
    if closed_trades_list:
        for t in closed_trades_list[:5]:
            stats += f"- {t}\n"
    else:
        stats += "- No closed trades found.\n"

    return stats


def generate_report():
    print("Generating Cipher AGGREGATED Performance Report...")
    stats = get_combined_stats()
    date_str = datetime.now().strftime("%Y-%m-%d")
    title = f"Cipher Aggregated Report - {date_str}"
    content = (
        f"# {title}\n\nGenerated at: {datetime.now().isoformat()}\n\n"
        f"{stats}\n\n## Bot Status\nMode: MULTI-STRATEGY PAPER TRADING\nStatus: ACTIVE"
    )
    print(content)


if __name__ == "__main__":
    generate_report()
