"""Tests for risk/dca.py"""

from __future__ import annotations

import pytest
from risk.dca import DcaExecutor


def _trade(id=1, stake=100.0, open_rate=1.0):
    """Minimal trade stub."""
    return {"id": id, "stake_amount": stake, "open_rate": open_rate}


@pytest.fixture
def dca():
    return DcaExecutor(
        safety_orders=3,
        price_step_pct=0.02,
        volume_scale=1.5,
        max_dca_multiplier=4.0,
        min_profit_threshold=-0.01,
    )


# ── Constructor validation ─────────────────────────────────────────────────────

def test_invalid_safety_orders():
    with pytest.raises(ValueError, match="safety_orders"):
        DcaExecutor(safety_orders=-1)


def test_invalid_price_step():
    with pytest.raises(ValueError, match="price_step_pct"):
        DcaExecutor(price_step_pct=0)


def test_invalid_volume_scale():
    with pytest.raises(ValueError, match="volume_scale"):
        DcaExecutor(volume_scale=0.5)


def test_invalid_max_multiplier():
    with pytest.raises(ValueError, match="max_dca_multiplier"):
        DcaExecutor(max_dca_multiplier=0.5)


# ── No action when position not underwater ────────────────────────────────────

def test_no_dca_above_threshold(dca):
    trade = _trade(open_rate=1.0)
    result = dca.adjust(trade, current_rate=0.985, min_stake=5.0, max_stake=500.0, current_profit=0.0)
    assert result is None


# ── No action when price hasn't dropped enough ────────────────────────────────

def test_no_dca_price_drop_too_small(dca):
    trade = _trade(open_rate=1.0)
    # First: trigger an initial DCA (2% drop)
    dca.adjust(trade, current_rate=0.979, min_stake=5.0, max_stake=500.0, current_profit=-0.02)
    # Second: only 0.5% further drop — below price_step_pct=0.02
    result = dca.adjust(trade, current_rate=0.974, min_stake=5.0, max_stake=500.0, current_profit=-0.026)
    assert result is None


# ── First DCA order ───────────────────────────────────────────────────────────

def test_first_dca_order_amount(dca):
    trade = _trade(stake=100.0, open_rate=1.0)
    result = dca.adjust(trade, current_rate=0.97, min_stake=5.0, max_stake=500.0, current_profit=-0.03)
    # First order = initial_stake * volume_scale^0 = 100 * 1 = 100
    assert result == pytest.approx(100.0)


def test_state_tracks_orders_placed(dca):
    trade = _trade(stake=100.0, open_rate=1.0)
    dca.adjust(trade, current_rate=0.97, min_stake=5.0, max_stake=500.0, current_profit=-0.03)
    assert dca.status(1)["orders_placed"] == 1


# ── Volume scale progression ──────────────────────────────────────────────────

def test_second_dca_order_scaled(dca):
    trade = _trade(stake=100.0, open_rate=1.0)
    # Order 1: 2% drop
    dca.adjust(trade, current_rate=0.97, min_stake=5.0, max_stake=500.0, current_profit=-0.03)
    # Order 2: another 2% drop from 0.97
    r2 = dca.adjust(trade, current_rate=0.97 * 0.978, min_stake=5.0, max_stake=500.0, current_profit=-0.05)
    # Second order = 100 * 1.5^1 = 150
    assert r2 == pytest.approx(150.0)


def test_third_dca_order_scaled(dca):
    trade = _trade(stake=100.0, open_rate=1.0)
    rates = [0.97, 0.97 * 0.978, 0.97 * 0.978 * 0.978]
    profits = [-0.03, -0.05, -0.08]
    for rate, profit in zip(rates, profits):
        dca.adjust(trade, current_rate=rate, min_stake=5.0, max_stake=500.0, current_profit=profit)
    assert dca.status(1)["orders_placed"] == 3


# ── Safety order cap ──────────────────────────────────────────────────────────

def test_no_dca_after_max_safety_orders(dca):
    trade = _trade(stake=100.0, open_rate=1.0)
    rate = 0.97
    for i in range(3):
        dca.adjust(trade, current_rate=rate, min_stake=5.0, max_stake=500.0, current_profit=-0.05)
        rate *= 0.97
    # 4th attempt — exhausted
    result = dca.adjust(trade, current_rate=rate * 0.97, min_stake=5.0, max_stake=500.0, current_profit=-0.15)
    assert result is None


# ── Max DCA multiplier cap ────────────────────────────────────────────────────

def test_max_dca_multiplier_caps_total(dca):
    # max_dca_multiplier=4.0, initial=100 → max additional = 400
    # volume_scale=1.5 → orders: 100, 150, 225 = 475 total
    # After first two (250), third should be capped to 150 (400 - 250 = 150)
    trade = _trade(stake=100.0, open_rate=1.0)
    rate = 0.97
    results = []
    for _ in range(3):
        r = dca.adjust(trade, current_rate=rate, min_stake=5.0, max_stake=500.0, current_profit=-0.05)
        results.append(r)
        rate *= 0.97
    assert sum(r for r in results if r) <= 400.0 + 1e-6


# ── min_stake respect ─────────────────────────────────────────────────────────

def test_skip_if_below_min_stake():
    dca = DcaExecutor(safety_orders=3, price_step_pct=0.02, volume_scale=1.0, max_dca_multiplier=4.0)
    trade = _trade(stake=1.0, open_rate=1.0)  # tiny stake → slice < min_stake
    result = dca.adjust(trade, current_rate=0.97, min_stake=50.0, max_stake=500.0, current_profit=-0.03)
    assert result is None


# ── max_stake cap ─────────────────────────────────────────────────────────────

def test_respects_max_stake(dca):
    trade = _trade(stake=100.0, open_rate=1.0)
    result = dca.adjust(trade, current_rate=0.97, min_stake=5.0, max_stake=80.0, current_profit=-0.03)
    assert result <= 80.0


# ── on_trade_exit clears state ────────────────────────────────────────────────

def test_on_trade_exit_clears_state(dca):
    trade = _trade(id=42, stake=100.0, open_rate=1.0)
    dca.adjust(trade, current_rate=0.97, min_stake=5.0, max_stake=500.0, current_profit=-0.03)
    assert dca.status(42)["active"] is True
    dca.on_trade_exit(42)
    assert dca.status(42)["active"] is False


# ── status ────────────────────────────────────────────────────────────────────

def test_status_no_trade():
    dca = DcaExecutor()
    assert dca.status(999) == {"trade_id": 999, "active": False}


def test_status_after_first_order(dca):
    trade = _trade(id=7, stake=200.0, open_rate=2.0)
    dca.adjust(trade, current_rate=1.94, min_stake=5.0, max_stake=500.0, current_profit=-0.03)
    st = dca.status(7)
    assert st["active"] is True
    assert st["orders_placed"] == 1
    assert st["total_dca_stake"] == pytest.approx(200.0)
