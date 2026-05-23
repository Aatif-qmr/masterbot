# risk/stake_sizer.py
# Kelly-lite dynamic stake sizing.
# Reads each strategy's rolling win rate from its SQLite DB and returns
# a stake multiplier: 0.5x (poor edge) → 1.0x (baseline) → 2.0x (strong edge).
#
# Formula: multiplier = clamp(1.0 + (win_rate - 0.50) * 2, 0.5, 2.0)
#   50% WR → 1.0x  |  65% WR → 1.3x  |  75% WR → 1.5x
#   35% WR → 0.7x  |  25% WR → 0.5x  |  80% WR → 1.6x

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

MIN_TRADES   = 15     # below this, return neutral 1.0x (not enough signal)
ROLLING_N    = 40     # use last N closed trades for win rate
FLOOR        = 0.5    # minimum multiplier (never stake less than half)
CEILING      = 2.0    # maximum multiplier (never more than double during dry_run)
CACHE_TTL    = 1800   # re-query DB every 30 minutes

_cache: dict[str, tuple[float, float]] = {}  # strategy → (multiplier, expires_at)


try:
    from risk_checks import compute_stake_multiplier as _compute_stake_multiplier
except ImportError:
    def _compute_stake_multiplier(win_rate: float, floor: float, ceiling: float) -> float:
        raw = 1.0 + (win_rate - 0.50) * 2.0
        return max(floor, min(ceiling, raw))

def _compute_multiplier(win_rate: float) -> float:
    return round(_compute_stake_multiplier(win_rate, FLOOR, CEILING), 2)


def get_stake_multiplier(strategy: str) -> float:
    """
    Return stake multiplier for the given strategy.
    Falls back to 1.0 if DB missing, insufficient trades, or any error.
    """
    now = time.time()
    cached = _cache.get(strategy)
    if cached and now < cached[1]:
        return cached[0]

    db_path = DB_MAP.get(strategy)
    if not db_path or not db_path.exists():
        return 1.0

    try:
        con = sqlite3.connect(str(db_path))
        con.execute("PRAGMA journal_mode=WAL;")
        rows = con.execute(
            "SELECT close_profit FROM trades "
            "WHERE is_open=0 AND close_profit IS NOT NULL "
            "ORDER BY close_date DESC LIMIT ?",
            (ROLLING_N,)
        ).fetchall()
        con.close()

        if len(rows) < MIN_TRADES:
            return 1.0

        profits = [r[0] for r in rows]
        win_rate = sum(1 for p in profits if p > 0) / len(profits)
        multiplier = _compute_multiplier(win_rate)

        _cache[strategy] = (multiplier, now + CACHE_TTL)
        return multiplier

    except Exception:
        return 1.0
