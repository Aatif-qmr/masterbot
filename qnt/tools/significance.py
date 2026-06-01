"""
qnt/tools/significance.py
─────────────────────────
Bootstrap significance test for Freqtrade strategies.

Null hypothesis H₀: the strategy's returns are due to random chance.
Method: resample trade returns (with replacement, zero-centered under H₀)
N times and compute the fraction of simulated means ≥ the observed mean.
That fraction is the p-value.

p < 0.05 → reject H₀ at 95% confidence → edge is statistically real.
p < 0.01 → reject H₀ at 99% confidence → strong evidence of real edge.

Usage:
    from qnt.tools.significance import run_significance_test, load_trades

    trades, meta = load_trades("ScalpV1")           # auto-selects source
    result = run_significance_test(trades, n_simulations=2000)
    print(result["verdict"])
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

_BASE = Path(__file__).resolve().parent.parent.parent
_RESULTS_DIR = _BASE / "user_data" / "backtest_results"

# Map strategy class name → SQLite filename (live/dry-run trades)
_STRATEGY_DB: dict[str, str] = {
    "ScalpV1": "scalp.sqlite",
    "BearScalpV1": "bear_scalp.sqlite",
    "DailyTrendV1": "daily.sqlite",
    "MeanReversionV1": "mean_reversion.sqlite",
    "SwingV1": "swing.sqlite",
    "MicroScalpV1": "tradesv3_micro.sqlite",
    "TrendFollowV1": "trend_follow.sqlite",
    "VectorVaultV1": "tradesv3.sqlite",
    "Auto202605030340": "tradesv3.sqlite",
}

MIN_TRADES_ERROR = 10  # fewer than this → raise ValueError
MIN_TRADES_WARN = 30  # fewer than this → set low_sample_warning = True


# ── Trade loaders ─────────────────────────────────────────────────────────────


def load_trades_from_backtest(strategy: str) -> tuple[list[dict], dict]:
    """
    Find the latest backtest ZIP for *strategy* and extract its trade list.

    Returns (trades, meta) where each trade dict has at minimum:
        profit_ratio, open_date, close_date, pair, exit_reason
    """
    meta_files = sorted(_RESULTS_DIR.glob("*.meta.json"))
    best_zip: Path | None = None
    best_ts = 0

    for mf in meta_files:
        try:
            d = json.loads(mf.read_text())
            if strategy in d:
                ts = d[strategy].get("backtest_start_time", 0)
                if ts > best_ts:
                    best_ts = ts
                    best_zip = Path(str(mf).replace(".meta.json", ".zip"))
        except Exception:
            pass

    if best_zip is None or not best_zip.exists():
        raise FileNotFoundError(
            f"No backtest result found for strategy '{strategy}'. "
            f"Run: freqtrade backtesting --strategy {strategy}"
        )

    with zipfile.ZipFile(best_zip) as z:
        for name in z.namelist():
            if name.endswith(".json") and "_config" not in name:
                data = json.loads(z.read(name))
                strat_data = data.get("strategy", {}).get(strategy, {})
                trades = strat_data.get("trades", [])
                meta = {
                    "source": "backtest",
                    "zip_file": best_zip.name,
                    "backtest_start": strat_data.get("backtest_start"),
                    "backtest_end": strat_data.get("backtest_end"),
                    "strategy": strategy,
                    "total_trades": len(trades),
                }
                return trades, meta

    raise ValueError(f"Could not read trade data from {best_zip}")


def load_trades_from_db(strategy: str) -> tuple[list[dict], dict]:
    """
    Load closed trades from the live/dry-run SQLite database for *strategy*.
    Uses the db mapping in _STRATEGY_DB; falls back to tradesv3.sqlite.
    """
    import sqlite3

    db_name = _STRATEGY_DB.get(strategy, "tradesv3.sqlite")
    db_path = _BASE / "user_data" / db_name

    if not db_path.exists():
        raise FileNotFoundError(
            f"SQLite database not found: {db_path}. Has this strategy ever run live/dry-run?"
        )

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT close_profit, open_date, close_date, pair, exit_reason, enter_tag "
            "FROM trades "
            "WHERE strategy = ? AND is_open = 0 AND close_profit IS NOT NULL "
            "ORDER BY close_date",
            (strategy,),
        ).fetchall()
    finally:
        conn.close()

    trades = [
        {
            "profit_ratio": float(r[0]),
            "open_date": r[1],
            "close_date": r[2],
            "pair": r[3],
            "exit_reason": r[4] or "",
            "enter_tag": r[5] or "",
        }
        for r in rows
    ]
    meta = {
        "source": "live_db",
        "db_file": db_name,
        "strategy": strategy,
        "total_trades": len(trades),
    }
    return trades, meta


def load_trades(
    strategy: str,
    *,
    prefer: str = "backtest",
) -> tuple[list[dict], dict]:
    """
    Load trades for *strategy*, trying sources in preferred order.

    Args:
        prefer: "backtest" (default) tries backtest first, falls back to live DB.
                "live" tries live DB first, falls back to backtest.
    """
    loaders = (
        [load_trades_from_backtest, load_trades_from_db]
        if prefer == "backtest"
        else [load_trades_from_db, load_trades_from_backtest]
    )
    last_exc: Exception | None = None
    for loader in loaders:
        try:
            trades, meta = loader(strategy)
            if trades:
                return trades, meta
        except Exception as exc:
            last_exc = exc
    raise ValueError(
        f"No trade data found for '{strategy}' from any source. Last error: {last_exc}"
    )


# ── Core significance test ────────────────────────────────────────────────────


def run_significance_test(
    trades: list[dict],
    n_simulations: int = 2000,
    random_seed: int = 42,
) -> dict[str, Any]:
    """
    Bootstrap significance test on a list of Freqtrade trade dicts.

    Each trade dict must contain at minimum: ``profit_ratio`` (float).

    Returns a dict with:
        n_trades            int       number of trades analysed
        observed_mean       float     mean per-trade return
        win_rate            float     fraction of profitable trades
        avg_win             float     mean return of winning trades
        avg_loss            float     mean magnitude of losing trades
        expectancy          float     risk-weighted expected return per trade
        profit_factor       float     gross profit / gross loss
        sqn                 float     System Quality Number (√n × mean/σ)
        p_value             float     bootstrap p-value (H₀: no edge)
        significant_5pct    bool      p_value < 0.05
        significant_1pct    bool      p_value < 0.01
        verdict             str       human-readable conclusion
        n_simulations       int       simulations actually run
        null_p5             float     5th pct of null distribution
        null_p50            float     50th pct of null distribution
        null_p95            float     95th pct of null distribution
        low_sample_warning  bool      fewer than MIN_TRADES_WARN trades
    """
    returns = np.array([float(t["profit_ratio"]) for t in trades], dtype=np.float64)
    n = len(returns)

    if n < MIN_TRADES_ERROR:
        raise ValueError(
            f"Only {n} trades — need at least {MIN_TRADES_ERROR} for a meaningful test. "
            f"Run a longer backtest (12+ months recommended)."
        )

    wins = returns[returns > 0]
    losses = returns[returns <= 0]

    observed_mean = float(returns.mean())
    observed_std = float(returns.std(ddof=1)) if n > 1 else 0.0
    win_rate = float(len(wins) / n)
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(abs(losses.mean())) if len(losses) else 0.0
    expectancy = win_rate * avg_win - (1.0 - win_rate) * avg_loss
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(abs(losses.sum())) if len(losses) else 1e-9
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    sqn = (observed_mean / (observed_std + 1e-9)) * (n**0.5)

    # ── Bootstrap under H₀ ────────────────────────────────────────────────────
    # Enforce H₀ (no edge) by zero-centering returns.
    # Resample with replacement → build null sampling distribution of means.
    centered = returns - observed_mean
    rng = np.random.default_rng(random_seed)
    idx = rng.integers(0, n, size=(n_simulations, n))
    sim_means = centered[idx].mean(axis=1)

    p_value = float(np.mean(sim_means >= observed_mean))

    # ── Verdict ────────────────────────────────────────────────────────────────
    if p_value < 0.01:
        verdict = "SIGNIFICANT at 99% confidence — strong evidence of real edge (p < 0.01)"
    elif p_value < 0.05:
        verdict = "SIGNIFICANT at 95% confidence — edge is statistically real (p < 0.05)"
    elif p_value < 0.10:
        verdict = "MARGINAL — weak evidence of edge (p < 0.10), run more trades to confirm"
    else:
        verdict = "NOT SIGNIFICANT — cannot reject H₀; returns are consistent with random chance"

    return {
        "n_trades": n,
        "observed_mean": observed_mean,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "expectancy": expectancy,
        "profit_factor": profit_factor,
        "sqn": sqn,
        "p_value": p_value,
        "significant_5pct": p_value < 0.05,
        "significant_1pct": p_value < 0.01,
        "verdict": verdict,
        "n_simulations": n_simulations,
        "null_p5": float(np.percentile(sim_means, 5)),
        "null_p50": float(np.percentile(sim_means, 50)),
        "null_p95": float(np.percentile(sim_means, 95)),
        "low_sample_warning": n < MIN_TRADES_WARN,
    }
