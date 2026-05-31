"""Cockpit tools: system status, open trades, Freqtrade health."""

import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_BASE / "qnt/cockpit"))
sys.path.insert(0, str(_BASE / "qnt/shield"))
sys.path.insert(0, str(_BASE / "qnt/memory"))
sys.path.insert(0, str(_BASE / "qnt/bridge"))
sys.path.insert(0, str(_BASE / "qnt/oracle"))


def get_system_status() -> dict:
    """Get system-wide status: open trades, balance, shield summary, logs tail."""
    try:
        from cockpit_static import get_global_status_panel, get_shield_panel, get_trades_panel

        return {
            "status": get_global_status_panel(),
            "shield": get_shield_panel(),
            "trades": get_trades_panel(),
        }
    except Exception as e:
        return {"error": str(e), "status": "unavailable"}


def get_balance() -> dict:
    """Get current balance state from all Freqtrade instances."""
    balance_file = _BASE / "risk/balance_state.json"
    if balance_file.exists():
        import json

        try:
            return json.loads(balance_file.read_text())
        except Exception as e:
            return {"error": str(e)}
    return {"status": "unavailable", "reason": "balance_state.json not found"}


def get_open_trades() -> list:
    """Get list of currently open trades from SQLite databases."""
    import glob
    import sqlite3

    db_pattern = str(_BASE / "user_data/*.sqlite")
    trades = []
    for db_path in glob.glob(db_pattern):
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT trade_id, pair, open_rate, stake_amount, open_date "
                "FROM trades WHERE is_open = 1 LIMIT 20"
            )
            for row in cursor.fetchall():
                trades.append(dict(row))
            conn.close()
        except Exception:
            continue
    return trades
