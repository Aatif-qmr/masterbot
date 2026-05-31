"""Tests for qnt/tools/montecarlo.py"""

from __future__ import annotations

import numpy as np
import pytest


def _trades(returns: list[float]) -> list[dict]:
    return [{"profit_ratio": r} for r in returns]


# ── Core statistical properties ───────────────────────────────────────────────


def test_positive_strategy_mostly_positive_returns():
    from qnt.tools.montecarlo import run_monte_carlo

    trades = _trades([0.02, 0.01, 0.015] * 20)
    result = run_monte_carlo(trades, n_simulations=500, random_seed=42)
    assert result["shuffle"]["return_p50"] > 0
    assert result["resample"]["return_p50"] > 0


def test_losing_strategy_mostly_negative_returns():
    from qnt.tools.montecarlo import run_monte_carlo

    trades = _trades([-0.02] * 30)
    result = run_monte_carlo(trades, n_simulations=200, random_seed=42)
    assert result["shuffle"]["return_p50"] < 0
    assert result["resample"]["return_p50"] < 0


def test_shuffle_percentiles_ordered():
    from qnt.tools.montecarlo import run_monte_carlo

    trades = _trades([0.01, -0.005] * 20)
    result = run_monte_carlo(trades, mode="shuffle", random_seed=42)
    s = result["shuffle"]
    assert s["return_p10"] <= s["return_p50"] <= s["return_p90"]
    assert s["drawdown_p10"] <= s["drawdown_p50"] <= s["drawdown_p90"]


def test_resample_percentiles_ordered():
    from qnt.tools.montecarlo import run_monte_carlo

    trades = _trades([0.01, -0.005] * 20)
    result = run_monte_carlo(trades, mode="resample", random_seed=42)
    r = result["resample"]
    assert r["return_p10"] <= r["return_p50"] <= r["return_p90"]


def test_ruin_probability_zero_for_consistently_positive():
    from qnt.tools.montecarlo import run_monte_carlo

    trades = _trades([0.005] * 50)
    result = run_monte_carlo(trades, n_simulations=500, ruin_threshold=0.20, random_seed=42)
    assert result["shuffle"]["ruin_probability"] == pytest.approx(0.0)
    assert result["resample"]["ruin_probability"] == pytest.approx(0.0)


def test_ruin_probability_high_for_catastrophic_losses():
    from qnt.tools.montecarlo import run_monte_carlo

    # Every trade loses 10 % — always ruined
    trades = _trades([-0.10] * 30)
    result = run_monte_carlo(trades, n_simulations=300, ruin_threshold=0.20, random_seed=1)
    assert result["shuffle"]["ruin_probability"] == pytest.approx(1.0)
    assert result["resample"]["ruin_probability"] == pytest.approx(1.0)


def test_ruin_probability_in_unit_interval():
    from qnt.tools.montecarlo import run_monte_carlo

    rng = np.random.default_rng(5)
    trades = _trades(rng.normal(0.005, 0.02, 40).tolist())
    result = run_monte_carlo(trades, n_simulations=300)
    for mode in ("shuffle", "resample"):
        rp = result[mode]["ruin_probability"]
        assert 0.0 <= rp <= 1.0


def test_observed_metrics_match_historical():
    from qnt.tools.montecarlo import run_monte_carlo

    returns = [0.01, -0.005, 0.02, -0.01] * 3  # 12 trades to pass MIN_TRADES
    trades = _trades(returns)
    result = run_monte_carlo(trades, n_simulations=100)

    # observed_return: product of (1 + r) - 1
    import math
    base = [0.01, -0.005, 0.02, -0.01]
    expected = math.prod(1 + r for r in base * 3) - 1
    assert result["observed_return"] == pytest.approx(expected, rel=1e-6)


def test_both_modes_present():
    from qnt.tools.montecarlo import run_monte_carlo

    trades = _trades([0.01] * 20)
    result = run_monte_carlo(trades, mode="both")
    assert "shuffle" in result
    assert "resample" in result


def test_only_shuffle_mode():
    from qnt.tools.montecarlo import run_monte_carlo

    trades = _trades([0.01] * 20)
    result = run_monte_carlo(trades, mode="shuffle")
    assert "shuffle" in result
    assert "resample" not in result


def test_only_resample_mode():
    from qnt.tools.montecarlo import run_monte_carlo

    trades = _trades([0.01] * 20)
    result = run_monte_carlo(trades, mode="resample")
    assert "resample" in result
    assert "shuffle" not in result


def test_raises_below_min_trades():
    from qnt.tools.montecarlo import MIN_TRADES, run_monte_carlo

    with pytest.raises(ValueError, match="at least"):
        run_monte_carlo(_trades([0.01] * (MIN_TRADES - 1)))


def test_reproducible_with_same_seed():
    from qnt.tools.montecarlo import run_monte_carlo

    trades = _trades([0.01, -0.005] * 25)
    r1 = run_monte_carlo(trades, n_simulations=200, random_seed=77)
    r2 = run_monte_carlo(trades, n_simulations=200, random_seed=77)
    assert r1["shuffle"]["return_p50"] == r2["shuffle"]["return_p50"]
    assert r1["resample"]["ruin_probability"] == r2["resample"]["ruin_probability"]


def test_median_equity_curve_shape():
    from qnt.tools.montecarlo import run_monte_carlo

    n = 30
    trades = _trades([0.005] * n)
    result = run_monte_carlo(trades, n_simulations=100, mode="shuffle")
    curve = result["shuffle"]["median_equity_curve"]
    assert len(curve) == n
    assert curve[0] > 0


def test_drawdown_is_non_negative():
    from qnt.tools.montecarlo import run_monte_carlo

    trades = _trades([0.01, -0.02, 0.03, -0.01] * 10)
    result = run_monte_carlo(trades, n_simulations=100)
    for mode in ("shuffle", "resample"):
        assert result[mode]["drawdown_p10"] >= 0.0
        assert result[mode]["drawdown_p90"] >= 0.0


def test_shuffle_preserves_trade_count():
    """All shuffled paths should have the same number of trades as the input."""
    from qnt.tools.montecarlo import _run_mode_shuffle

    returns = np.array([0.01, -0.005, 0.02] * 10)
    rng = np.random.default_rng(0)
    mode_result = _run_mode_shuffle(returns, len(returns), 50, 10_000, 0.20, rng)
    assert len(mode_result["median_equity_curve"]) == len(returns)
