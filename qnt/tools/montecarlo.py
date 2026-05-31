"""
qnt/tools/montecarlo.py
───────────────────────
Monte Carlo stress test for Freqtrade strategies.

Runs N simulations in two complementary modes:

  shuffle   — randomly permutes the order of historical trades.
              Tests whether the *timing* of wins/losses drove the result,
              not the edge itself.  Immune to overfitting on entry timing.

  resample  — samples trades with replacement (bootstrap).
              Tests robustness under different market regimes/paths.

Key outputs per mode:
  return_p10/p50/p90     — distribution of final portfolio returns
  drawdown_p10/p50/p90   — distribution of max drawdown (positive fraction)
  ruin_probability        — P(max_drawdown > ruin_threshold)
  median_equity_curve     — representative path for plotting

Usage:
    from qnt.tools.montecarlo import run_monte_carlo
    from qnt.tools.significance import load_trades

    trades, _ = load_trades("SwingV1")
    result = run_monte_carlo(trades, n_simulations=1000)
    print(result["shuffle"]["ruin_probability"])
"""

from __future__ import annotations

from typing import Any

import numpy as np

DEFAULT_RUIN = 0.20      # 20 % drawdown triggers ruin
MIN_TRADES = 10


def run_monte_carlo(
    trades: list[dict],
    n_simulations: int = 1000,
    starting_balance: float = 10_000.0,
    ruin_threshold: float = DEFAULT_RUIN,
    random_seed: int = 42,
    mode: str = "both",  # "shuffle" | "resample" | "both"
) -> dict[str, Any]:
    """
    Run Monte Carlo stress test on a list of Freqtrade trade dicts.

    Each trade dict must have a ``profit_ratio`` key (float).

    Args:
        trades:            List of closed trade dicts from backtest or live DB.
        n_simulations:     Number of simulated equity paths per mode.
        starting_balance:  Initial portfolio value (normalises the equity curve).
        ruin_threshold:    Max-drawdown fraction that constitutes "ruin"
                           (default 0.20 = 20 %).
        random_seed:       Seed for reproducibility.
        mode:              Which simulation modes to run.

    Returns:
        Dict with keys "shuffle" and/or "resample", each containing:
            n_simulations       int
            return_p10          float   10th pct final return
            return_p50          float   median final return
            return_p90          float   90th pct final return
            drawdown_p10        float   10th pct max drawdown (least bad)
            drawdown_p50        float   median max drawdown
            drawdown_p90        float   90th pct max drawdown (worst)
            ruin_probability    float   P(max_drawdown > ruin_threshold)
            median_equity_curve np.ndarray  shape (n_trades,)
        Plus top-level:
            n_trades            int
            observed_return     float   actual backtest final return
            observed_drawdown   float   actual backtest max drawdown
    """
    returns = np.array([float(t["profit_ratio"]) for t in trades], dtype=np.float64)
    n = len(returns)
    if n < MIN_TRADES:
        raise ValueError(
            f"Need at least {MIN_TRADES} trades for Monte Carlo; got {n}."
        )

    rng = np.random.default_rng(random_seed)
    result: dict[str, Any] = {
        "n_trades": n,
        "observed_return": float(_final_return(returns, starting_balance)),
        "observed_drawdown": float(_max_drawdown(returns, starting_balance)),
    }

    if mode in ("shuffle", "both"):
        result["shuffle"] = _run_mode_shuffle(returns, n, n_simulations, starting_balance, ruin_threshold, rng)

    if mode in ("resample", "both"):
        result["resample"] = _run_mode_resample(returns, n, n_simulations, starting_balance, ruin_threshold, rng)

    return result


# ── Private simulation engines ────────────────────────────────────────────────


def _run_mode_shuffle(
    returns: np.ndarray,
    n: int,
    n_sims: int,
    starting_balance: float,
    ruin_threshold: float,
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Each row is a random permutation of the original trade sequence."""
    tile = np.tile(returns, (n_sims, 1))               # (n_sims, n)
    shuffled = rng.permuted(tile, axis=1)              # permute each row
    return _stats(shuffled, n_sims, starting_balance, ruin_threshold)


def _run_mode_resample(
    returns: np.ndarray,
    n: int,
    n_sims: int,
    starting_balance: float,
    ruin_threshold: float,
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Each row is n trades sampled with replacement from the original set."""
    idx = rng.integers(0, n, size=(n_sims, n))         # (n_sims, n)
    resampled = returns[idx]                            # (n_sims, n)
    return _stats(resampled, n_sims, starting_balance, ruin_threshold)


def _stats(
    sim_returns: np.ndarray,
    n_sims: int,
    starting_balance: float,
    ruin_threshold: float,
) -> dict[str, Any]:
    """Compute summary statistics from a (n_sims × n_trades) returns matrix."""
    equity = starting_balance * np.cumprod(1.0 + sim_returns, axis=1)  # (n_sims, n)

    final_balance = equity[:, -1]
    final_return = (final_balance - starting_balance) / starting_balance

    # Max drawdown per simulation (positive fraction, 0 = no drawdown)
    peak = np.maximum.accumulate(equity, axis=1)
    # Avoid div-by-zero on zero peak (shouldn't happen with positive starting_balance)
    drawdown_frac = np.where(peak > 0, (peak - equity) / peak, 0.0)
    max_dd = drawdown_frac.max(axis=1)

    # Median equity curve — useful for plotting
    median_idx = np.argsort(final_return)[n_sims // 2]
    median_equity = equity[median_idx]

    return {
        "n_simulations": n_sims,
        "return_p10": float(np.percentile(final_return, 10)),
        "return_p50": float(np.percentile(final_return, 50)),
        "return_p90": float(np.percentile(final_return, 90)),
        "drawdown_p10": float(np.percentile(max_dd, 10)),
        "drawdown_p50": float(np.percentile(max_dd, 50)),
        "drawdown_p90": float(np.percentile(max_dd, 90)),
        "ruin_probability": float(np.mean(max_dd >= ruin_threshold)),
        "median_equity_curve": median_equity,
    }


def _final_return(returns: np.ndarray, starting_balance: float) -> float:
    equity = starting_balance * float(np.prod(1.0 + returns))
    return (equity - starting_balance) / starting_balance


def _max_drawdown(returns: np.ndarray, starting_balance: float) -> float:
    equity = starting_balance * np.cumprod(1.0 + returns)
    peak = np.maximum.accumulate(equity)
    dd = np.where(peak > 0, (peak - equity) / peak, 0.0)
    return float(dd.max())
