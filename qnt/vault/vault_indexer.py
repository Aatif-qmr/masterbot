import sqlite3
import sys
from pathlib import Path

import pandas as pd

# Machine-agnostic path setup
HOME = Path.home()
BASE_DIR = HOME / "cipher"
sys.path.insert(0, str(BASE_DIR / "qnt/memory"))
sys.path.insert(0, str(BASE_DIR / "qnt/vault"))

from vault import store_lesson


def index_new_trades():
    """Polls Freqtrade DB for new closed trades and vaults them."""
    # This runs on M2, so it needs to look at the mirrored trade DB or query M1
    # For now, we assume the user_data/tradesv3.dryrun.sqlite is synced or accessible
    db_path = BASE_DIR / "user_data/tradesv3.dryrun.sqlite"
    if not db_path.exists():
        print("Trade database not found on M2. Skipping index.")
        return

    try:
        conn = sqlite3.connect(db_path)
        # Fetch trades closed since last scan (logic to be refined with a state file)
        query = "SELECT * FROM trades WHERE is_open=0 ORDER BY close_date DESC LIMIT 5"
        trades_df = pd.read_sql_query(query, conn)
        conn.close()

        if trades_df.empty:
            return

        for _, trade in trades_df.iterrows():
            lesson_id = f"trade_{trade['id']}"

            # Simple narrative generation (to be upgraded with PRO LLM later)
            narrative = (
                f"Trade {trade['id']}: {trade['pair']} {trade['strategy']} on {trade['close_date']}. "
                f"Result: {trade['profit_ratio'] * 100:.2f}% profit. "
                f"Entry reason: {trade['enter_tag']}. Exit reason: {trade['exit_reason']}."
            )

            metadata = {
                "pair": trade["pair"],
                "strategy": trade["strategy"],
                "profit_ratio": trade["profit_ratio"],
                "close_date": trade["close_date"],
                "type": "trade_result",
            }

            store_lesson(lesson_id, narrative, metadata)

        print(f"Indexed {len(trades_df)} trades into The Vault.")
    except Exception as e:
        print(f"Indexing error: {e}")


if __name__ == "__main__":
    index_new_trades()
