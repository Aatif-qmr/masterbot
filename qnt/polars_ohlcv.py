"""
qnt/polars_ohlcv.py
───────────────────
Polars-based OHLCV data loader for Cipher.
Replaces Pandas read_csv / DataFrame manipulation with Polars
for 5-20x lower memory usage and faster I/O.

Usage:
    from qnt.polars_ohlcv import load_ohlcv, ohlcv_to_pandas

    # Load directly as Polars DataFrame
    df = load_ohlcv("data/BTC_USDT_1h.csv")

    # Or convert to Pandas for Freqtrade compatibility
    pdf = ohlcv_to_pandas(df)
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    import polars as pl
    _HAS_POLARS = True
except ImportError:
    _HAS_POLARS = False


BASE_DIR = Path.home() / "cipher"


def load_ohlcv(
    path: str | Path,
    date_column: str = "date",
    sort: bool = True,
) -> "pl.DataFrame":
    """
    Load OHLCV CSV data into a Polars DataFrame.

    Polars reads CSVs using a multi-threaded Rust parser that is
    significantly faster than Pandas (typically 3-10x on large files).

    Args:
        path: Path to the CSV file (absolute or relative to BASE_DIR/data/)
        date_column: Name of the date/timestamp column
        sort: Whether to sort by date ascending

    Returns:
        Polars DataFrame with typed columns
    """
    if not _HAS_POLARS:
        raise ImportError("Polars is required. Install with: pip install polars")

    filepath = Path(path)
    if not filepath.is_absolute():
        filepath = BASE_DIR / "data" / filepath

    if not filepath.exists():
        raise FileNotFoundError(f"OHLCV data file not found: {filepath}")

    # Polars auto-infers types; we parse dates explicitly
    df = pl.read_csv(
        str(filepath),
        try_parse_dates=True,
        ignore_errors=True,
    )

    # Ensure date column is datetime
    if date_column in df.columns and df[date_column].dtype != pl.Datetime:
        df = df.with_columns(
            pl.col(date_column).str.to_datetime(strict=False).alias(date_column)
        )

    # Sort by date ascending for time-series operations
    if sort and date_column in df.columns:
        df = df.sort(date_column)

    return df


def load_ohlcv_lazy(
    path: str | Path,
    date_column: str = "date",
) -> "pl.LazyFrame":
    """
    Load OHLCV data as a Polars LazyFrame for deferred execution.

    Lazy evaluation allows Polars to optimize the entire query plan
    before executing, eliminating unnecessary column reads and fusing
    operations for maximum throughput.

    Usage:
        lf = load_ohlcv_lazy("BTC_USDT_1h.csv")
        result = (
            lf.filter(pl.col("volume") > 0)
            .select(["date", "close", "volume"])
            .collect()  # execution happens here
        )
    """
    if not _HAS_POLARS:
        raise ImportError("Polars is required. Install with: pip install polars")

    filepath = Path(path)
    if not filepath.is_absolute():
        filepath = BASE_DIR / "data" / filepath

    if not filepath.exists():
        raise FileNotFoundError(f"OHLCV data file not found: {filepath}")

    return pl.scan_csv(
        str(filepath),
        try_parse_dates=True,
        ignore_errors=True,
    )


def ohlcv_to_pandas(df: "pl.DataFrame") -> "object":
    """
    Convert a Polars DataFrame to a Pandas DataFrame for Freqtrade
    strategy compatibility.

    This uses Arrow-based zero-copy conversion where possible,
    avoiding memory duplication for numeric columns.
    """
    return df.to_pandas()


def pandas_to_polars(pdf: "object") -> "pl.DataFrame":
    """
    Convert a Pandas DataFrame to a Polars DataFrame.
    Useful for bridging Freqtrade's Pandas-based DataProvider
    output into the Polars indicator pipeline.
    """
    if not _HAS_POLARS:
        raise ImportError("Polars is required. Install with: pip install polars")
    return pl.from_pandas(pdf)


def load_multiple_pairs(
    data_dir: str | Path | None = None,
    pattern: str = "*_USDT_*.csv",
) -> dict[str, "pl.DataFrame"]:
    """
    Load multiple pair CSVs from a directory into a dict.

    Returns:
        Dict mapping pair name (e.g. "BTC_USDT_1h") to Polars DataFrame
    """
    if not _HAS_POLARS:
        raise ImportError("Polars is required. Install with: pip install polars")

    directory = Path(data_dir) if data_dir else BASE_DIR / "data"
    result = {}

    for csv_file in sorted(directory.glob(pattern)):
        pair_name = csv_file.stem  # e.g. "BTC_USDT_1h"
        result[pair_name] = load_ohlcv(csv_file)

    return result


def memory_comparison(path: str | Path) -> dict:
    """
    Benchmark: Load the same CSV with both Pandas and Polars,
    report memory usage difference.

    Returns dict with memory usage in MB for each library.
    """
    import sys

    filepath = Path(path)
    if not filepath.is_absolute():
        filepath = BASE_DIR / "data" / filepath

    results = {}

    # Polars
    if _HAS_POLARS:
        df_pl = pl.read_csv(str(filepath), try_parse_dates=True, ignore_errors=True)
        results["polars_mb"] = round(df_pl.estimated_size("mb"), 2)
        results["polars_rows"] = len(df_pl)
        del df_pl

    # Pandas
    try:
        import pandas as pd
        df_pd = pd.read_csv(str(filepath), parse_dates=["date"])
        results["pandas_mb"] = round(df_pd.memory_usage(deep=True).sum() / (1024 * 1024), 2)
        results["pandas_rows"] = len(df_pd)
        del df_pd
    except Exception as e:
        results["pandas_error"] = str(e)

    if "polars_mb" in results and "pandas_mb" in results:
        results["savings_pct"] = round(
            (1 - results["polars_mb"] / results["pandas_mb"]) * 100, 1
        )

    return results
