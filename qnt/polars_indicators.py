"""
qnt/polars_indicators.py
────────────────────────
Polars-based technical indicator library for Cipher strategies.
Replaces Pandas-based indicator calculations with Rust-compiled Polars
expressions that release the GIL and run on all CPU cores.

Usage:
    import polars as pl
    from qnt.polars_indicators import add_rsi, add_bollinger_bands, add_ema

    df = pl.read_csv("data/BTC_USDT_1h.csv")
    df = add_rsi(df, period=14)
    df = add_bollinger_bands(df, period=20, std_dev=2.0)
"""

from __future__ import annotations

try:
    import polars as pl
    _HAS_POLARS = True
except ImportError:
    _HAS_POLARS = False


def _require_polars():
    if not _HAS_POLARS:
        raise ImportError(
            "Polars is required for this module. Install with: pip install polars"
        )


def add_ema(df: "pl.DataFrame", column: str = "close", period: int = 20, alias: str | None = None) -> "pl.DataFrame":
    """
    Add Exponential Moving Average column.

    Polars `ewm_mean` uses span-based smoothing (alpha = 2 / (span + 1)),
    identical to Pandas/ta-lib EMA.
    """
    _require_polars()
    col_alias = alias or f"ema_{period}"
    return df.with_columns(
        pl.col(column)
        .ewm_mean(span=period, ignore_nulls=True)
        .alias(col_alias)
    )


def add_sma(df: "pl.DataFrame", column: str = "close", period: int = 20, alias: str | None = None) -> "pl.DataFrame":
    """Add Simple Moving Average column."""
    _require_polars()
    col_alias = alias or f"sma_{period}"
    return df.with_columns(
        pl.col(column)
        .rolling_mean(window_size=period)
        .alias(col_alias)
    )


def add_rsi(df: "pl.DataFrame", column: str = "close", period: int = 14, alias: str = "rsi") -> "pl.DataFrame":
    """
    Add Relative Strength Index column.

    Uses Wilder's smoothing method (exponential moving average of gains/losses).
    """
    _require_polars()
    delta = pl.col(column).diff()

    gain = delta.clip(lower_bound=0.0).ewm_mean(span=period * 2 - 1, ignore_nulls=True)
    loss = (-delta.clip(upper_bound=0.0)).ewm_mean(span=period * 2 - 1, ignore_nulls=True)

    # RS = avg_gain / avg_loss, RSI = 100 - (100 / (1 + RS))
    rs = gain / loss
    rsi_expr = (100.0 - (100.0 / (1.0 + rs)))

    return df.with_columns(rsi_expr.alias(alias))


def add_bollinger_bands(
    df: "pl.DataFrame",
    column: str = "close",
    period: int = 20,
    std_dev: float = 2.0,
    prefix: str = "bb",
) -> "pl.DataFrame":
    """Add Bollinger Bands (upper, middle, lower) columns."""
    _require_polars()
    mid = pl.col(column).rolling_mean(window_size=period)
    std = pl.col(column).rolling_std(window_size=period)

    return df.with_columns([
        mid.alias(f"{prefix}_mid"),
        (mid + std_dev * std).alias(f"{prefix}_upper"),
        (mid - std_dev * std).alias(f"{prefix}_lower"),
    ])


def add_atr(
    df: "pl.DataFrame",
    period: int = 14,
    alias: str = "atr",
) -> "pl.DataFrame":
    """
    Add Average True Range column.

    True Range = max(high - low, |high - prev_close|, |low - prev_close|)
    """
    _require_polars()
    prev_close = pl.col("close").shift(1)
    tr1 = pl.col("high") - pl.col("low")
    tr2 = (pl.col("high") - prev_close).abs()
    tr3 = (pl.col("low") - prev_close).abs()

    # Element-wise max across the three TR components
    true_range = pl.max_horizontal(tr1, tr2, tr3)

    return df.with_columns(
        true_range.ewm_mean(span=period * 2 - 1, ignore_nulls=True).alias(alias)
    )


def add_macd(
    df: "pl.DataFrame",
    column: str = "close",
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    prefix: str = "macd",
) -> "pl.DataFrame":
    """Add MACD line, signal line, and histogram columns."""
    _require_polars()
    ema_fast = pl.col(column).ewm_mean(span=fast, ignore_nulls=True)
    ema_slow = pl.col(column).ewm_mean(span=slow, ignore_nulls=True)
    macd_line = ema_fast - ema_slow

    df = df.with_columns(macd_line.alias(f"{prefix}_line"))
    df = df.with_columns(
        pl.col(f"{prefix}_line")
        .ewm_mean(span=signal, ignore_nulls=True)
        .alias(f"{prefix}_signal")
    )
    df = df.with_columns(
        (pl.col(f"{prefix}_line") - pl.col(f"{prefix}_signal")).alias(f"{prefix}_hist")
    )
    return df


def add_vwap(df: "pl.DataFrame", alias: str = "vwap") -> "pl.DataFrame":
    """
    Add Volume-Weighted Average Price (cumulative).
    Requires 'high', 'low', 'close', 'volume' columns.
    """
    _require_polars()
    typical_price = (pl.col("high") + pl.col("low") + pl.col("close")) / 3.0
    tp_volume = typical_price * pl.col("volume")

    return df.with_columns(
        (tp_volume.cum_sum() / pl.col("volume").cum_sum()).alias(alias)
    )


def add_log_returns(df: "pl.DataFrame", column: str = "close", alias: str = "log_return") -> "pl.DataFrame":
    """Add log returns column: ln(close / prev_close)."""
    _require_polars()
    return df.with_columns(
        (pl.col(column) / pl.col(column).shift(1)).log().alias(alias)
    )


def add_all_indicators(
    df: "pl.DataFrame",
    rsi_period: int = 14,
    bb_period: int = 20,
    bb_std: float = 2.0,
    atr_period: int = 14,
    ema_periods: list[int] | None = None,
) -> "pl.DataFrame":
    """
    Convenience function: add all standard indicators in a single pass.
    Polars optimizes the computation graph internally.
    """
    _require_polars()
    if ema_periods is None:
        ema_periods = [9, 21, 50, 200]

    df = add_rsi(df, period=rsi_period)
    df = add_bollinger_bands(df, period=bb_period, std_dev=bb_std)
    df = add_atr(df, period=atr_period)
    df = add_macd(df)
    df = add_log_returns(df)
    df = add_vwap(df)

    for p in ema_periods:
        df = add_ema(df, period=p)

    return df
