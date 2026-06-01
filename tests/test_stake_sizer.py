"""Tests for risk/stake_sizer.py — Decimal precision additions."""

from unittest.mock import patch

import pytest

from risk.stake_sizer import (
    _compute_multiplier,
    get_stake_amount,
    get_stake_multiplier,
    quantize_stake,
)

# ── _compute_multiplier ───────────────────────────────────────────────────────


def test_50pct_wr_returns_1x():
    assert _compute_multiplier(0.50) == pytest.approx(1.0)


def test_65pct_wr_returns_1_3x():
    assert _compute_multiplier(0.65) == pytest.approx(1.30)


def test_75pct_wr_returns_1_5x():
    assert _compute_multiplier(0.75) == pytest.approx(1.50)


def test_35pct_wr_returns_0_7x():
    assert _compute_multiplier(0.35) == pytest.approx(0.70)


def test_floor_clamped_at_0_5():
    assert _compute_multiplier(0.0) == pytest.approx(0.50)


def test_ceiling_clamped_at_2_0():
    assert _compute_multiplier(1.0) == pytest.approx(2.00)


def test_returns_float():
    result = _compute_multiplier(0.60)
    assert isinstance(result, float)


def test_decimal_no_float_accumulation():
    # 0.1 + 0.2 != 0.3 in native float; Decimal avoids this
    # win_rate derived from 4/10 = 0.4 → raw = 1 + (0.4 - 0.5)*2 = 0.8
    result = _compute_multiplier(0.40)
    # Must be exactly 0.8 (Decimal) not 0.7999999... (float)
    assert result == pytest.approx(0.80, abs=1e-10)


def test_multiplier_rounded_to_2dp():
    # win_rate = 0.63 → raw = 1.0 + (0.63 - 0.50)*2 = 1.26
    assert _compute_multiplier(0.63) == pytest.approx(1.26)
    # win_rate = 0.631 → raw = 1.262 → rounds to 1.26
    assert _compute_multiplier(0.631) == pytest.approx(1.26)


# ── quantize_stake ────────────────────────────────────────────────────────────


def test_quantize_basic():
    assert quantize_stake(10.123456789, "0.001") == pytest.approx(10.123)


def test_quantize_rounds_down_not_up():
    # 10.005 with tick 0.01 → floor to 10.00, not round to 10.01
    assert quantize_stake(10.005, "0.01") == pytest.approx(10.0)


def test_quantize_whole_number_tick():
    assert quantize_stake(10.999, "1") == pytest.approx(10.0)


def test_quantize_no_truncation_needed():
    assert quantize_stake(10.5, "0.5") == pytest.approx(10.5)


def test_quantize_zero_amount():
    assert quantize_stake(0.0, "0.01") == pytest.approx(0.0)


def test_quantize_negative_amount_returns_zero():
    assert quantize_stake(-5.0, "0.01") == 0.0


def test_quantize_float_tick_converted_correctly():
    # 0.1 as float has representation error; str(0.1) → "0.1" → exact Decimal
    result = quantize_stake(10.15, 0.1)
    assert result == pytest.approx(10.1)


def test_quantize_satoshi_precision():
    # Bitcoin satoshi tick = 0.00000001
    result = quantize_stake(0.123456789, "0.00000001")
    assert result == pytest.approx(0.12345678)


def test_quantize_invalid_tick_returns_zero():
    assert quantize_stake(100.0, "0") == 0.0
    assert quantize_stake(100.0, "-0.01") == 0.0


def test_quantize_returns_float():
    result = quantize_stake(10.5, "0.01")
    assert isinstance(result, float)


def test_quantize_large_stake():
    # 100000.123456 USDT with 0.01 tick → 100000.12
    assert quantize_stake(100000.123456, "0.01") == pytest.approx(100000.12)


# ── get_stake_amount ──────────────────────────────────────────────────────────


def test_get_stake_amount_no_tick(monkeypatch):
    monkeypatch.setattr("risk.stake_sizer.get_stake_multiplier", lambda s: 1.5)
    result = get_stake_amount("ScalpV1", 100.0)
    assert result == pytest.approx(150.0)


def test_get_stake_amount_with_tick(monkeypatch):
    monkeypatch.setattr("risk.stake_sizer.get_stake_multiplier", lambda s: 1.3)
    # 100 * 1.3 = 130.0 → quantized to 0.01 → 130.0
    result = get_stake_amount("ScalpV1", 100.0, tick_size="0.01")
    assert result == pytest.approx(130.0)


def test_get_stake_amount_tick_truncates(monkeypatch):
    monkeypatch.setattr("risk.stake_sizer.get_stake_multiplier", lambda s: 1.33)
    # 75 * 1.33 = 99.75 → tick 1.0 → 99.0
    result = get_stake_amount("ScalpV1", 75.0, tick_size="1")
    assert result == pytest.approx(99.0)


def test_get_stake_amount_fallback_multiplier(monkeypatch):
    # No DB → multiplier=1.0 → stake unchanged
    monkeypatch.setattr("risk.stake_sizer.get_stake_multiplier", lambda s: 1.0)
    result = get_stake_amount("UnknownStrategy", 200.0)
    assert result == pytest.approx(200.0)


def test_get_stake_amount_returns_float(monkeypatch):
    monkeypatch.setattr("risk.stake_sizer.get_stake_multiplier", lambda s: 1.2)
    result = get_stake_amount("ScalpV1", 100.0, tick_size="0.01")
    assert isinstance(result, float)


# ── get_stake_multiplier fallback ─────────────────────────────────────────────


def test_get_stake_multiplier_returns_1_when_no_db():
    result = get_stake_multiplier("NonExistentStrategy")
    assert result == pytest.approx(1.0)


def test_get_stake_multiplier_returns_1_below_min_trades():
    # Patch SQLite fetch to return fewer than MIN_TRADES rows
    with patch("risk.stake_sizer._fetch_via_sqlite", return_value=[0.01] * 5):
        result = get_stake_multiplier("ScalpV1")
    assert result == pytest.approx(1.0)


def test_get_stake_multiplier_computes_from_trades():
    # 30 wins out of 40 → 75% → multiplier = 1.5
    profits = [0.01] * 30 + [-0.01] * 10
    with patch("risk.stake_sizer._fetch_via_sqlite", return_value=profits):
        result = get_stake_multiplier("ScalpV1_test_isolation_" + str(id(profits)))
    assert result == pytest.approx(1.50)
