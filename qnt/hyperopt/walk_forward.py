"""
qnt/hyperopt/walk_forward.py
─────────────────────────────
Walk-forward purged cross-validation for Freqtrade hyperopt.

Standard in-sample hyperopt leaks future data because feature lookback
windows (RSI-14, MACD-26) overlap fold boundaries.  This module wraps
the existing fitness function with a proper walk-forward evaluation:

  1. Split the timerange into N anchored folds.
  2. Each fold has a purge gap = max(strategy lookback) between train end
     and test start, preventing any look-ahead from lagged indicators.
  3. Evaluate parameters on the TEST window of each fold, average the
     fitness scores — the aggregate is the trial's objective value.

The result: Optuna optimises parameters that generalise across multiple
non-overlapping out-of-sample windows, not just one in-sample period.

Usage:
    from qnt.hyperopt.walk_forward import run_walk_forward_study
    best = run_walk_forward_study("ScalpV1", n_trials=50, n_folds=5)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# Lookback in days by strategy class name.
# Conservatively set to max(indicator_periods) × timeframe_minutes / 1440.
_STRATEGY_LOOKBACK_DAYS: dict[str, int] = {
    "ScalpV1": 3,  # RSI-14 on 5m → ~14 × 5min = 70min, round up to 3 days
    "BearScalpV1": 3,
    "MicroScalpV1": 2,
    "TrendFollowV1": 7,  # EMA-50 on 1h → 50h = ~2.1 days, round up to 7
    "DailyTrendV1": 7,
    "MeanReversionV1": 5,
    "SwingV1": 7,
    "VectorVaultV1": 14,  # FreqAI train lookback
    "Auto202605030340": 5,
}
DEFAULT_LOOKBACK_DAYS = 7


@dataclass
class WalkForwardFold:
    """One train/test fold with a purge gap between them."""

    train_start: str  # freqtrade timerange format: YYYYMMDD
    train_end: str
    test_start: str  # = train_end + purge_days
    test_end: str
    fold_index: int


def build_folds(
    start: str,
    end: str,
    n_folds: int,
    test_pct: float = 0.20,
    purge_days: int = DEFAULT_LOOKBACK_DAYS,
) -> list[WalkForwardFold]:
    """
    Build anchored walk-forward folds from a total timerange.

    Args:
        start:      ISO date string, e.g. "2024-01-01"
        end:        ISO date string, e.g. "2025-01-01"
        n_folds:    Number of folds to create.
        test_pct:   Fraction of the FOLD window held out for testing.
        purge_days: Gap in days between train end and test start.

    Returns:
        List of WalkForwardFold in chronological order.

    Layout per fold (anchored expanding window):
        [  train (grows fold-by-fold)  ] [gap] [ test ]
    """
    fmt = "%Y%m%d"
    t0 = datetime.fromisoformat(start)
    t1 = datetime.fromisoformat(end)
    total_days = (t1 - t0).days

    if total_days < n_folds * (1 + test_pct) + purge_days:
        raise ValueError(
            f"Timerange {start}→{end} ({total_days}d) too short for {n_folds} folds "
            f"with purge={purge_days}d and test_pct={test_pct}."
        )

    # Each fold covers `total_days / n_folds` days.
    # Train anchors at t0; test slides forward.
    fold_len = total_days / n_folds
    folds = []
    for i in range(n_folds):
        fold_end = t0 + timedelta(days=fold_len * (i + 1))
        test_end = min(fold_end, t1)
        test_size = timedelta(days=max(1, int(fold_len * test_pct)))
        test_start = fold_end - test_size - timedelta(days=purge_days)
        train_end = test_start - timedelta(days=purge_days)

        if train_end <= t0 or test_start >= test_end:
            continue  # degenerate fold, skip

        folds.append(
            WalkForwardFold(
                train_start=t0.strftime(fmt),
                train_end=train_end.strftime(fmt),
                test_start=test_start.strftime(fmt),
                test_end=test_end.strftime(fmt),
                fold_index=i,
            )
        )

    if not folds:
        raise ValueError("No valid folds could be constructed from the given parameters.")
    return folds


def evaluate_params_walk_forward(
    strategy: str,
    params: dict,
    folds: list[WalkForwardFold],
    pair: str = "BTC/USDT",
) -> float:
    """
    Evaluate *params* across all folds on their TEST windows.
    Returns the mean fitness score (higher = better).
    Returns -inf if more than half the folds fail.
    """
    from qnt.hyperopt.fitness import evaluate_params

    scores = []
    for fold in folds:
        timerange = f"{fold.test_start}-{fold.test_end}"
        score = evaluate_params(strategy, params, timerange=timerange, pair=pair)
        if score > float("-inf"):
            scores.append(score)
        logger.debug(
            "Fold %d [%s→%s]: score=%.4f",
            fold.fold_index,
            fold.test_start,
            fold.test_end,
            score,
        )

    if len(scores) < len(folds) // 2:
        return float("-inf")
    return sum(scores) / len(scores)


def run_walk_forward_study(
    strategy: str,
    n_trials: int = 50,
    n_folds: int = 5,
    start: str = "2024-01-01",
    end: str = "2025-01-01",
    pair: str = "BTC/USDT",
    purge_days: int | None = None,
    n_workers: int | None = None,
) -> dict[str, Any]:
    """
    Run an Optuna hyperopt study using walk-forward purged cross-validation.

    Parameters
    ----------
    strategy:   Strategy class name (must be in SEARCH_SPACES).
    n_trials:   Total Optuna trials.
    n_folds:    Number of walk-forward folds.
    start/end:  ISO dates bounding the total evaluation period.
    pair:       Trading pair for all backtest calls.
    purge_days: Override the strategy's default lookback gap.

    Returns
    -------
    dict with best_params, best_value, n_trials_completed, folds.
    """
    try:
        import optuna
        import ray
    except ImportError as e:
        raise ImportError("Install optuna and ray: uv add optuna 'ray[default]'") from e

    from qnt.hyperopt.distributed import SEARCH_SPACES, _storage_url, _suggest_params

    if strategy not in SEARCH_SPACES:
        raise ValueError(
            f"Strategy '{strategy}' not in SEARCH_SPACES. Available: {list(SEARCH_SPACES.keys())}"
        )

    gap = (
        purge_days
        if purge_days is not None
        else _STRATEGY_LOOKBACK_DAYS.get(strategy, DEFAULT_LOOKBACK_DAYS)
    )
    folds = build_folds(start, end, n_folds=n_folds, purge_days=gap)
    logger.info("Walk-forward study: %d folds, purge=%dd, strategy=%s", len(folds), gap, strategy)

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    storage_url = _storage_url(f"{strategy}_wf")
    study_name = f"{strategy}_walk_forward_v1"

    study = optuna.create_study(
        study_name=study_name,
        storage=storage_url,
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=42),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=2),
        load_if_exists=True,
    )

    def objective(trial):
        params = _suggest_params(trial, strategy)
        return evaluate_params_walk_forward(strategy, params, folds, pair=pair)

    workers = n_workers or max(1, __import__("os").cpu_count() - 1)
    if not ray.is_initialized():
        ray.init(num_cpus=workers, ignore_reinit_error=True)

    # Run trials via Ray remote workers sharing the Optuna storage
    batch_size = workers
    completed = 0
    while completed < n_trials:
        batch = min(batch_size, n_trials - completed)

        @ray.remote
        def _worker():
            import optuna as _opt

            _opt.logging.set_verbosity(_opt.logging.WARNING)
            s = _opt.load_study(study_name=study_name, storage=storage_url)
            s.optimize(objective, n_trials=1)

        ray.get([_worker.remote() for _ in range(batch)])
        completed += batch
        logger.info("Walk-forward: %d / %d trials", completed, n_trials)

    best = study.best_trial
    return {
        "strategy": strategy,
        "study_name": study_name,
        "best_params": best.params,
        "best_value": best.value,
        "n_trials_completed": len(study.trials),
        "n_folds": len(folds),
        "purge_days": gap,
        "folds": [
            {
                "fold": f.fold_index,
                "train": f"{f.train_start}→{f.train_end}",
                "test": f"{f.test_start}→{f.test_end}",
            }
            for f in folds
        ],
    }
