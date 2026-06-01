"""
qnt/tools/benchmark.py
───────────────────────
Run all active strategies against the same backtest period and rank them.

Spawns one Freqtrade backtest subprocess per strategy in parallel (Ray),
collects Sharpe, Calmar, max-drawdown, win-rate, profit-factor, and trade
count, then returns a ranked Polars DataFrame (best Sharpe first).

Usage:
    from qnt.tools.benchmark import run_benchmark
    df = run_benchmark(period="2024-01-01:2025-01-01", pairs=["BTC/USDT"])
    print(df)

CLI: python qnt/agent.py benchmark --period 2024-01-01:2025-01-01
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)

_BASE = Path(__file__).resolve().parent.parent.parent
_STRATEGY_DIR = _BASE / "strategies" / "active"
_DATA_DIR = _BASE / "user_data" / "data"
_CONFIG_DIR = _BASE / "config"

ACTIVE_STRATEGIES = [
    "ScalpV1",
    "BearScalpV1",
    "MicroScalpV1",
    "TrendFollowV1",
    "DailyTrendV1",
    "MeanReversionV1",
    "SwingV1",
    "VectorVaultV1",
]

_STRATEGY_TIMEFRAME: dict[str, str] = {
    "ScalpV1": "5m",
    "BearScalpV1": "5m",
    "MicroScalpV1": "1m",
    "TrendFollowV1": "1h",
    "DailyTrendV1": "1d",
    "MeanReversionV1": "15m",
    "SwingV1": "4h",
    "VectorVaultV1": "15m",
}


def _run_single_backtest(
    strategy: str,
    period: str,
    pairs: list[str],
    config_path: str | None = None,
) -> dict[str, Any]:
    """
    Run a single freqtrade backtest and return parsed metrics.
    Returns a dict with all stats, or an 'error' key on failure.
    """
    # Build pair args
    pair_args = []
    for p in pairs:
        pair_args.extend(["--pairs", p])

    # Choose a config: per-strategy if it exists, else base paper config
    if config_path is None:
        slug = strategy.lower().replace("v1", "").rstrip("_")
        candidates = [
            _CONFIG_DIR / f"config_{slug}.json",
            _CONFIG_DIR / "config_paper.json",
        ]
        config_path = str(next((c for c in candidates if c.exists()), candidates[-1]))

    cmd = [
        "freqtrade",
        "backtesting",
        "--strategy",
        strategy,
        "--strategy-path",
        str(_STRATEGY_DIR),
        "--config",
        config_path,
        "--timerange",
        period.replace(":", "-"),
        "--datadir",
        str(_DATA_DIR),
        "--export",
        "none",
        "--print-json",
    ] + pair_args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(_BASE),
            env={**os.environ, "PYTHONPATH": str(_BASE)},
        )
        if result.returncode != 0:
            logger.warning("Backtest failed for %s: %s", strategy, result.stderr[:200])
            return {"strategy": strategy, "error": result.stderr[:200]}

        # Parse last JSON object from stdout
        for line in reversed(result.stdout.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                    return _extract_metrics(strategy, data)
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
        return {"strategy": strategy, "error": "no JSON output"}
    except subprocess.TimeoutExpired:
        return {"strategy": strategy, "error": "timeout"}
    except FileNotFoundError:
        return {"strategy": strategy, "error": "freqtrade not found in PATH"}
    except Exception as exc:
        return {"strategy": strategy, "error": str(exc)}


def _extract_metrics(strategy: str, data: dict) -> dict[str, Any]:
    """Extract and normalise key metrics from freqtrade JSON output."""

    def _f(key: str, default: float = 0.0) -> float:
        val = data.get(key, default)
        try:
            return float(val) if val is not None else default
        except (TypeError, ValueError):
            return default

    sharpe = _f("sharpe_ratio")
    calmar = _f("calmar")
    max_dd = abs(_f("max_drawdown_account") or _f("max_relative_drawdown"))
    win_rate = _f("winrate") or _f("win_rate")
    total_trades = int(_f("total_trades"))
    profit_total = _f("profit_total") or _f("profit_total_abs")
    profit_factor = _f("profit_factor")
    trades_per_day = _f("trades_per_day")

    return {
        "strategy": strategy,
        "sharpe": sharpe,
        "calmar": calmar,
        "max_drawdown_pct": max_dd * 100,
        "win_rate_pct": win_rate * 100 if win_rate <= 1.0 else win_rate,
        "profit_factor": profit_factor,
        "total_trades": total_trades,
        "trades_per_day": trades_per_day,
        "total_profit_pct": profit_total * 100,
        "error": None,
    }


def run_benchmark(
    period: str = "2024-01-01:2025-01-01",
    strategies: list[str] | None = None,
    pairs: list[str] | None = None,
    parallel: bool = True,
) -> pl.DataFrame:
    """
    Run all (or specified) strategies on the same period and return ranked results.

    Args:
        period:     "YYYY-MM-DD:YYYY-MM-DD" date range.
        strategies: Override the default ACTIVE_STRATEGIES list.
        pairs:      Trading pairs. Default: ["BTC/USDT"].
        parallel:   Use Ray for parallel execution (default True).

    Returns:
        Polars DataFrame sorted by Sharpe descending.
        Rows with errors have null metric values.
    """
    strats = strategies or ACTIVE_STRATEGIES
    pairs = pairs or ["BTC/USDT"]

    if parallel:
        try:
            import ray

            if not ray.is_initialized():
                ray.init(ignore_reinit_error=True)

            @ray.remote
            def _remote(s: str) -> dict:
                return _run_single_backtest(s, period, pairs)

            futures = [_remote.remote(s) for s in strats]
            results = ray.get(futures)
        except ImportError:
            logger.warning("ray not available — falling back to sequential execution")
            results = [_run_single_backtest(s, period, pairs) for s in strats]
    else:
        results = [_run_single_backtest(s, period, pairs) for s in strats]

    # Normalise all result dicts to the same schema
    schema_keys = [
        "strategy",
        "sharpe",
        "calmar",
        "max_drawdown_pct",
        "win_rate_pct",
        "profit_factor",
        "total_trades",
        "trades_per_day",
        "total_profit_pct",
        "error",
    ]
    rows = []
    for r in results:
        row = {k: r.get(k) for k in schema_keys}
        rows.append(row)

    df = pl.DataFrame(rows)

    # Sort by sharpe (nulls last)
    if "sharpe" in df.columns:
        df = df.sort("sharpe", descending=True, nulls_last=True)

    return df
