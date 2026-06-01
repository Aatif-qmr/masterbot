# risk/stake_sizer.py
# Kelly-lite dynamic stake sizing with Decimal precision.
# Reads each strategy's rolling win rate from its DB and returns
# a stake multiplier: 0.5x (poor edge) → 1.0x (baseline) → 2.0x (strong edge).
#
# Formula: multiplier = clamp(1.0 + (win_rate - 0.50) * 2, 0.5, 2.0)
#   50% WR → 1.0x  |  65% WR → 1.3x  |  75% WR → 1.5x
#   35% WR → 0.7x  |  25% WR → 0.5x  |  80% WR → 1.6x
#
# Decimal precision:
#   All Kelly arithmetic uses decimal.Decimal (ROUND_HALF_EVEN) to avoid
#   float accumulation errors.  quantize_stake() rounds DOWN to the exchange
#   tick size so we never exceed the intended allocation.
#
# DB resolution order:
#   1. FREQTRADE_DB_{STRATEGY_UPPER} env var → PostgreSQL (live/dry_run via supervisord)
#   2. SQLite file in user_data/            → research/backtest fallback

import os
import sqlite3
import time
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Decimal, InvalidOperation
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DB_MAP = {
    "ScalpV1": BASE_DIR / "user_data/scalp.sqlite",
    "MeanReversionV1": BASE_DIR / "user_data/mean_reversion.sqlite",
    "SwingV1": BASE_DIR / "user_data/swing.sqlite",
    "TrendFollowV1": BASE_DIR / "user_data/trend_follow.sqlite",
    "BearScalpV1": BASE_DIR / "user_data/bear_scalp.sqlite",
    "DailyTrendV1": BASE_DIR / "user_data/daily.sqlite",
    "MicroScalpV1": BASE_DIR / "user_data/tradesv3_micro.sqlite",
}

MIN_TRADES = 15
ROLLING_N = 40
FLOOR = 0.5
CEILING = 2.0
CACHE_TTL = 1800  # 30 minutes

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
    """Kelly multiplier computed in Decimal to avoid float accumulation error."""
    wr = Decimal(str(win_rate))
    floor = Decimal(str(FLOOR))
    ceiling = Decimal(str(CEILING))
    raw = Decimal("1.0") + (wr - Decimal("0.50")) * Decimal("2.0")
    clamped = max(floor, min(ceiling, raw))
    return float(clamped.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))


def quantize_stake(amount: float, tick_size: float | str = "0.00000001") -> float:
    """
    Round *amount* DOWN to the exchange's minimum tick size.

    Args:
        amount:    Raw stake in quote currency (e.g. USDT).
        tick_size: Minimum order increment.  Pass as string for exact Decimal
                   representation (e.g. "0.001"), or as float (converted via str).

    Returns:
        float — amount rounded down to tick_size precision.
        Returns 0.0 on invalid input rather than raising.

    Examples:
        quantize_stake(10.123456789, "0.001")  → 10.123
        quantize_stake(10.999,       "1")      → 10.0
        quantize_stake(10.005,       "0.01")   → 10.0   (ROUND_DOWN, not up)
    """
    try:
        tick = Decimal(str(tick_size))
        amt = Decimal(str(amount))
        if tick <= 0 or amt < 0:
            return 0.0
        quantized = (amt / tick).to_integral_value(rounding=ROUND_DOWN) * tick
        return float(quantized)
    except (InvalidOperation, ZeroDivisionError):
        return 0.0


def get_stake_amount(
    strategy: str,
    proposed_stake: float,
    tick_size: float | str | None = None,
) -> float:
    """
    Apply Kelly multiplier to *proposed_stake* and quantize to exchange precision.

    Args:
        strategy:       Strategy class name.
        proposed_stake: Freqtrade's proposed stake (quote currency).
        tick_size:      Exchange tick size for rounding.  None → no rounding.

    Returns:
        float — adjusted stake, safe for submission to exchange.
    """
    multiplier = get_stake_multiplier(strategy)
    raw = Decimal(str(proposed_stake)) * Decimal(str(multiplier))
    amount = float(raw)
    if tick_size is not None:
        amount = quantize_stake(amount, tick_size)
    return amount


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
