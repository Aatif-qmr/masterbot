"""Tests for risk/twap.py"""

from __future__ import annotations

import time

import pytest


@pytest.fixture
def slicer():
    from risk.twap import TwapSlicer
    return TwapSlicer(n_slices=4, interval_secs=0)  # interval=0 → no waiting


# ── TwapSlicer basics ─────────────────────────────────────────────────────────


def test_single_slice_passthrough():
    from risk.twap import TwapSlicer

    s = TwapSlicer(n_slices=1)
    result = s.slice_stake(100.0, min_stake=5.0, max_stake=200.0)
    assert result == pytest.approx(100.0)


def test_first_slice_is_fraction(slicer):
    result = slicer.slice_stake(400.0, min_stake=5.0, max_stake=500.0)
    assert result == pytest.approx(100.0)  # 400/4


def test_four_slices_sum_to_full(slicer):
    total = 0.0
    for _ in range(4):
        total += slicer.slice_stake(400.0, min_stake=5.0, max_stake=500.0)
    assert total == pytest.approx(400.0)


def test_slices_placed_increments(slicer):
    assert slicer.slices_placed == 0
    slicer.slice_stake(400.0, min_stake=5.0, max_stake=500.0)
    assert slicer.slices_placed == 1
    slicer.slice_stake(400.0, min_stake=5.0, max_stake=500.0)
    assert slicer.slices_placed == 2


def test_is_active_after_first_slice(slicer):
    assert not slicer.is_active
    slicer.slice_stake(100.0, min_stake=1.0, max_stake=200.0)
    assert slicer.is_active


def test_not_active_after_completion(slicer):
    for _ in range(4):
        slicer.slice_stake(400.0, min_stake=5.0, max_stake=500.0)
    assert not slicer.is_active


def test_reset_clears_state(slicer):
    slicer.slice_stake(100.0, min_stake=1.0, max_stake=200.0)
    slicer.reset()
    assert slicer.slices_placed == 0
    assert not slicer.is_active


def test_new_sequence_after_completion(slicer):
    """After completing 4 slices, next call starts a new sequence."""
    for _ in range(4):
        slicer.slice_stake(400.0, min_stake=5.0, max_stake=500.0)
    # 5th call restarts
    result = slicer.slice_stake(200.0, min_stake=5.0, max_stake=500.0)
    assert result == pytest.approx(50.0)  # 200/4
    assert slicer.slices_placed == 1


def test_respects_max_stake(slicer):
    result = slicer.slice_stake(400.0, min_stake=5.0, max_stake=50.0)
    assert result <= 50.0


def test_respects_min_stake():
    from risk.twap import TwapSlicer

    # slice_stake = 400/4 = 100 but min_stake = 150
    s = TwapSlicer(n_slices=4, interval_secs=0)
    result = s.slice_stake(400.0, min_stake=150.0, max_stake=500.0)
    assert result >= 150.0


def test_status_returns_dict(slicer):
    status = slicer.status()
    assert "active" in status
    assert status["active"] is False

    slicer.slice_stake(400.0, min_stake=5.0, max_stake=500.0)
    status = slicer.status()
    assert status["active"] is True
    assert status["slices_placed"] == 1
    assert status["n_slices"] == 4
    assert status["full_stake"] == pytest.approx(400.0)


def test_pair_tracked_in_status(slicer):
    slicer.slice_stake(400.0, min_stake=5.0, max_stake=500.0, pair="BTC/USDT")
    assert slicer.status()["pair"] == "BTC/USDT"


def test_invalid_n_slices_raises():
    from risk.twap import TwapSlicer

    with pytest.raises(ValueError, match="n_slices"):
        TwapSlicer(n_slices=0)


def test_interval_respected():
    from risk.twap import TwapSlicer

    s = TwapSlicer(n_slices=2, interval_secs=60)  # 60-second wait
    s.slice_stake(100.0, min_stake=1.0, max_stake=200.0)  # first slice
    # Immediately ask for second slice — interval not elapsed → skip
    result = s.slice_stake(100.0, min_stake=1.0, max_stake=200.0)
    # Still only 1 slice placed (second call was a skip due to interval)
    assert s.slices_placed == 1
    # The returned value is min_stake (skip signal)
    assert result == pytest.approx(1.0)


def test_timeout_resets_state():
    from risk.twap import TwapSlicer

    s = TwapSlicer(n_slices=4, interval_secs=0, timeout_secs=0)
    s.slice_stake(400.0, min_stake=5.0, max_stake=500.0)
    # timeout_secs=0 → immediately expired; next call restarts
    result = s.slice_stake(200.0, min_stake=5.0, max_stake=500.0)
    assert result == pytest.approx(50.0)  # 200/4 — new sequence
    assert s.slices_placed == 1
