# risk/stake_sizer.py
# Kelly-lite dynamic stake sizing.
# Reads each strategy's rolling win rate from its DB and returns
# a stake multiplier: 0.5x (poor edge) → 1.0x (baseline) → 2.0x (strong edge).
#
# Formula: multiplier = clamp(1.0 + (win_rate - 0.50) * 2, 0.5, 2.0)
#   50% WR → 1.0x  |  65% WR → 1.3x  |  75% WR → 1.5x
#   35% WR → 0.7x  |  25% WR → 0.5x  |  80% WR → 1.6x
#
# DB resolution order:
#   1. FREQTRADE_DB_{STRATEGY_UPPER} env var → PostgreSQL (live/dry_run via supervisord)
#   2. SQLite file in user_data/            → research/backtest fallback

import os
import sqlite3
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DB_MAP = {
    'ScalpV1':         BASE_DIR / 'user_data/scalp.sqlite',
    'MeanReversionV1': BASE_DIR / 'user_data/mean_reversion.sqlite',
    'SwingV1':         BASE_DIR / 'user_data/swing.sqlite',
    'TrendFollowV1':   BASE_DIR / 'user_data/trend_follow.sqlite',
    'BearScalpV1':     BASE_DIR / 'user_data/bear_scalp.sqlite',
    'DailyTrendV1':    BASE_DIR / 'user_data/daily.sqlite',
    'MicroScalpV1':    BASE_DIR / 'user_data/tradesv3_micro.sqlite',
}

MIN_TRADES = 15
ROLLING_N  = 40
FLOOR      = 0.5
CEILING    = 2.0
CACHE_TTL  = 1800  # 30 minutes

_cache: dict[str, tuple[float, float]] = {}

_TRADE_QUERY = (
    "SELECT close_profit FROM trades "
    "WHERE is_open=0 AND close_profit IS NOT NULL "
    "ORDER BY close_date DESC LIMIT %s"
)
_TRADE_QUERY_SQLITE = (
    "SELECT close_profit FROM trades "
    "WHERE is_open=0 AND close_profit IS NOT NULL "
    "ORDER BY close_date DESC LIMIT ?"
)


def _compute_multiplier(win_rate: float) -> float:
    raw = 1.0 + (win_rate - 0.50) * 2.0
    return round(max(FLOOR, min(CEILING, raw)), 2)


def _fetch_via_postgres(dsn: str) -> list[float] | None:
    """Return list of close_profit values via psycopg3, or None on failure."""
    try:
        import psycopg
        con = psycopg.connect(dsn)
        cur = con.cursor()
        cur.execute(_TRADE_QUERY, (ROLLING_N,))
        rows = cur.fetchall()
        con.close()
        return [r[0] for r in rows]
    except Exception:
        return None


def _fetch_via_sqlite(db_path: Path) -> list[float] | None:
    """Return list of close_profit values via SQLite, or None on failure."""
    if not db_path.exists():
        return None
    try:
        con = sqlite3.connect(str(db_path))
        con.execute("PRAGMA journal_mode=WAL;")
        rows = con.execute(_TRADE_QUERY_SQLITE, (ROLLING_N,)).fetchall()
        con.close()
        return [r[0] for r in rows]
    except Exception:
        return None


def get_stake_multiplier(strategy: str) -> float:
    """
    Return stake multiplier for the given strategy.
    Falls back to 1.0 if DB unavailable or fewer than MIN_TRADES records.
    """
    now = time.time()
    cached = _cache.get(strategy)
    if cached and now < cached[1]:
        return cached[0]

    # Try PostgreSQL first (live/dry_run via supervisord)
    env_key = f"FREQTRADE_DB_{strategy.upper()}"
    dsn = os.environ.get(env_key)
    if dsn:
        profits = _fetch_via_postgres(dsn)
    else:
        profits = _fetch_via_sqlite(DB_MAP.get(strategy, Path("/nonexistent")))

    if profits is None or len(profits) < MIN_TRADES:
        return 1.0

    win_rate = sum(1 for p in profits if p > 0) / len(profits)
    multiplier = _compute_multiplier(win_rate)
    _cache[strategy] = (multiplier, now + CACHE_TTL)
    return multiplier
