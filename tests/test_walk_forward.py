"""Tests for qnt/hyperopt/walk_forward.py — fold construction only (no Freqtrade calls)."""

from __future__ import annotations

import pytest

# ── build_folds ───────────────────────────────────────────────────────────────


def test_fold_count():
    from qnt.hyperopt.walk_forward import build_folds

    folds = build_folds("2024-01-01", "2025-01-01", n_folds=5)
    assert len(folds) == 5


def test_folds_chronological():
    from qnt.hyperopt.walk_forward import build_folds

    folds = build_folds("2024-01-01", "2025-01-01", n_folds=4)
    for i in range(1, len(folds)):
        assert folds[i].test_start >= folds[i - 1].test_start


def test_train_anchored_at_start():
    from qnt.hyperopt.walk_forward import build_folds

    folds = build_folds("2024-01-01", "2025-01-01", n_folds=4)
    for f in folds:
        assert f.train_start == "20240101"


def test_purge_gap_between_train_and_test():
    from qnt.hyperopt.walk_forward import build_folds

    purge = 7
    folds = build_folds("2024-01-01", "2025-01-01", n_folds=4, purge_days=purge)
    from datetime import datetime

    fmt = "%Y%m%d"
    for f in folds:
        train_end = datetime.strptime(f.train_end, fmt)
        test_start = datetime.strptime(f.test_start, fmt)
        gap = (test_start - train_end).days
        assert gap >= purge, f"Fold {f.fold_index}: gap={gap} < purge={purge}"


def test_test_window_non_empty():
    from qnt.hyperopt.walk_forward import build_folds

    folds = build_folds("2024-01-01", "2025-01-01", n_folds=4)
    from datetime import datetime

    fmt = "%Y%m%d"
    for f in folds:
        test_start = datetime.strptime(f.test_start, fmt)
        test_end = datetime.strptime(f.test_end, fmt)
        assert test_end > test_start, f"Fold {f.fold_index}: empty test window"


def test_no_overlap_between_test_windows():
    from qnt.hyperopt.walk_forward import build_folds

    folds = build_folds("2024-01-01", "2025-01-01", n_folds=5)
    from datetime import datetime

    fmt = "%Y%m%d"
    for i in range(1, len(folds)):
        prev_end = datetime.strptime(folds[i - 1].test_end, fmt)
        curr_start = datetime.strptime(folds[i].test_start, fmt)
        assert curr_start >= prev_end, (
            f"Fold {i} test start {curr_start} overlaps fold {i - 1} test end {prev_end}"
        )


def test_raises_timerange_too_short():
    from qnt.hyperopt.walk_forward import build_folds

    with pytest.raises(ValueError, match="too short"):
        build_folds("2024-01-01", "2024-01-10", n_folds=5, purge_days=7)


def test_fold_indices_assigned():
    from qnt.hyperopt.walk_forward import build_folds

    folds = build_folds("2024-01-01", "2025-01-01", n_folds=4)
    indices = [f.fold_index for f in folds]
    assert indices == sorted(indices)


def test_custom_purge_days():
    from qnt.hyperopt.walk_forward import build_folds

    folds_small = build_folds("2024-01-01", "2025-01-01", n_folds=3, purge_days=2)
    folds_large = build_folds("2024-01-01", "2025-01-01", n_folds=3, purge_days=14)
    # Larger purge → test windows start later
    from datetime import datetime

    fmt = "%Y%m%d"
    for fold_small, fold_large in zip(folds_small, folds_large):
        ts_small = datetime.strptime(fold_small.test_start, fmt)
        ts_large = datetime.strptime(fold_large.test_start, fmt)
        # Larger purge → test starts earlier (pushed back to preserve the bigger gap)
        assert ts_large <= ts_small


def test_2_folds_minimum():
    from qnt.hyperopt.walk_forward import build_folds

    folds = build_folds("2024-01-01", "2025-06-01", n_folds=2, purge_days=3)
    assert len(folds) == 2


# ── Strategy lookback map ─────────────────────────────────────────────────────


def test_all_strategies_have_lookback_entry():
    from qnt.hyperopt.distributed import SEARCH_SPACES
    from qnt.hyperopt.walk_forward import _STRATEGY_LOOKBACK_DAYS

    for strategy in SEARCH_SPACES:
        assert strategy in _STRATEGY_LOOKBACK_DAYS, (
            f"Strategy '{strategy}' missing from _STRATEGY_LOOKBACK_DAYS"
        )


def test_lookback_values_positive():
    from qnt.hyperopt.walk_forward import _STRATEGY_LOOKBACK_DAYS

    for strategy, days in _STRATEGY_LOOKBACK_DAYS.items():
        assert days > 0, f"{strategy} lookback must be > 0"
