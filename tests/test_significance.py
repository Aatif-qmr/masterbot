"""Tests for qnt/tools/significance.py"""

from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import numpy as np
import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_trades(returns: list[float]) -> list[dict]:
    """Build minimal trade dicts from a list of profit_ratio values."""
    return [
        {
            "profit_ratio": r,
            "open_date": "2024-01-01 00:00:00",
            "close_date": "2024-01-02 00:00:00",
            "pair": "BTC/USDT",
            "exit_reason": "roi",
            "enter_tag": "",
        }
        for r in returns
    ]


def _make_backtest_zip(tmp_path: Path, strategy: str, trades: list[dict]) -> tuple[Path, Path]:
    """Write a minimal .meta.json + .zip pair that load_trades_from_backtest can read."""
    ts = 1700000000
    meta_path = tmp_path / "backtest-result-test.meta.json"
    zip_path = tmp_path / "backtest-result-test.zip"

    meta_path.write_text(json.dumps({strategy: {"backtest_start_time": ts}}))

    payload = {
        "strategy": {
            strategy: {
                "trades": trades,
                "backtest_start": "2024-01-01 00:00:00",
                "backtest_end": "2024-12-31 00:00:00",
                "total_trades": len(trades),
            }
        }
    }
    json_name = "backtest-result-test.json"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr(json_name, json.dumps(payload))

    return meta_path, zip_path


def _make_db(tmp_path: Path, strategy: str, trades: list[dict]) -> Path:
    """Write a minimal SQLite DB inside tmp_path/user_data/ that load_trades_from_db can read."""
    (tmp_path / "user_data").mkdir(exist_ok=True)
    db_path = tmp_path / "user_data" / "test.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE trades "
        "(close_profit REAL, open_date TEXT, close_date TEXT, pair TEXT, "
        " exit_reason TEXT, enter_tag TEXT, strategy TEXT, is_open INTEGER)"
    )
    conn.executemany(
        "INSERT INTO trades VALUES (?,?,?,?,?,?,?,0)",
        [
            (
                t["profit_ratio"],
                t["open_date"],
                t["close_date"],
                t["pair"],
                t["exit_reason"],
                t["enter_tag"],
                strategy,
            )
            for t in trades
        ],
    )
    conn.commit()
    conn.close()
    return db_path


# ── run_significance_test ─────────────────────────────────────────────────────


def test_significant_strategy():
    """Consistently positive returns should give low p-value."""
    from qnt.tools.significance import run_significance_test

    # 100 trades all +1.5%: obviously not random
    trades = _make_trades([0.015] * 100)
    result = run_significance_test(trades, n_simulations=2000, random_seed=42)

    assert result["n_trades"] == 100
    assert result["p_value"] < 0.05
    assert result["significant_5pct"] is True
    assert result["win_rate"] == 1.0
    assert result["observed_mean"] == pytest.approx(0.015)


def test_random_strategy_not_significant():
    """Zero-mean noise returns should fail to reject H₀."""
    from qnt.tools.significance import run_significance_test

    rng = np.random.default_rng(99)
    returns = rng.normal(0.0, 0.01, size=200).tolist()
    trades = _make_trades(returns)
    result = run_significance_test(trades, n_simulations=2000, random_seed=42)

    assert result["p_value"] > 0.05
    assert result["significant_5pct"] is False


def test_negative_strategy_not_significant():
    """Consistently losing strategy has p-value near 1."""
    from qnt.tools.significance import run_significance_test

    trades = _make_trades([-0.01] * 50)
    result = run_significance_test(trades)

    assert result["p_value"] > 0.05


def test_sqn_positive_for_profitable_strategy():
    from qnt.tools.significance import run_significance_test

    trades = _make_trades([0.01] * 50 + [-0.005] * 20)
    result = run_significance_test(trades)

    assert result["sqn"] > 0


def test_profit_factor_calculated():
    from qnt.tools.significance import run_significance_test

    # 5 wins of +0.02, 5 losses of -0.01 → PF = 0.10 / 0.05 = 2.0
    trades = _make_trades([0.02] * 5 + [-0.01] * 5)
    result = run_significance_test(trades)

    assert result["profit_factor"] == pytest.approx(2.0, rel=1e-3)


def test_low_sample_warning_flag():
    from qnt.tools.significance import run_significance_test

    trades = _make_trades([0.01] * 15)  # < 30
    result = run_significance_test(trades)

    assert result["low_sample_warning"] is True


def test_no_warning_above_30_trades():
    from qnt.tools.significance import run_significance_test

    trades = _make_trades([0.005] * 30)
    result = run_significance_test(trades)

    assert result["low_sample_warning"] is False


def test_raises_below_minimum_trades():
    from qnt.tools.significance import MIN_TRADES_ERROR, run_significance_test

    trades = _make_trades([0.01] * (MIN_TRADES_ERROR - 1))
    with pytest.raises(ValueError, match="at least"):
        run_significance_test(trades)


def test_raises_on_empty_trades():
    from qnt.tools.significance import run_significance_test

    with pytest.raises(ValueError):
        run_significance_test([])


def test_null_distribution_percentiles_ordered():
    from qnt.tools.significance import run_significance_test

    trades = _make_trades([0.01] * 40 + [-0.005] * 20)
    result = run_significance_test(trades)

    assert result["null_p5"] < result["null_p50"] < result["null_p95"]


def test_verdict_contains_significant_for_strong_edge():
    from qnt.tools.significance import run_significance_test

    trades = _make_trades([0.02] * 150)
    result = run_significance_test(trades)

    assert "SIGNIFICANT" in result["verdict"]


def test_verdict_not_significant_for_random():
    from qnt.tools.significance import run_significance_test

    rng = np.random.default_rng(7)
    trades = _make_trades(rng.normal(0, 0.01, 100).tolist())
    result = run_significance_test(trades, n_simulations=2000, random_seed=0)

    assert "NOT SIGNIFICANT" in result["verdict"] or result["p_value"] > 0.05


def test_reproducible_with_same_seed():
    from qnt.tools.significance import run_significance_test

    trades = _make_trades([0.008, -0.003] * 50)
    r1 = run_significance_test(trades, random_seed=123)
    r2 = run_significance_test(trades, random_seed=123)

    assert r1["p_value"] == r2["p_value"]


def test_different_seeds_produce_close_but_not_identical_p_values():
    from qnt.tools.significance import run_significance_test

    trades = _make_trades([0.008, -0.003] * 50)
    r1 = run_significance_test(trades, n_simulations=5000, random_seed=1)
    r2 = run_significance_test(trades, n_simulations=5000, random_seed=2)

    # Both converge to same truth; should be within 0.05 of each other
    assert abs(r1["p_value"] - r2["p_value"]) < 0.05


# ── Trade loaders ─────────────────────────────────────────────────────────────


def test_load_trades_from_backtest(tmp_path, monkeypatch):
    from qnt.tools import significance as sig_mod

    strategy = "TestStrat"
    trades = _make_trades([0.01, -0.005, 0.02] * 5)
    _make_backtest_zip(tmp_path, strategy, trades)

    monkeypatch.setattr(sig_mod, "_RESULTS_DIR", tmp_path)

    loaded, meta = sig_mod.load_trades_from_backtest(strategy)
    assert len(loaded) == 15
    assert meta["source"] == "backtest"
    assert meta["strategy"] == strategy


def test_load_trades_from_backtest_not_found(tmp_path, monkeypatch):
    from qnt.tools import significance as sig_mod

    monkeypatch.setattr(sig_mod, "_RESULTS_DIR", tmp_path)

    with pytest.raises(FileNotFoundError, match="No backtest result"):
        sig_mod.load_trades_from_backtest("NoSuchStrategy")


def test_load_trades_from_db(tmp_path, monkeypatch):
    from qnt.tools import significance as sig_mod

    strategy = "ScalpV1"
    trades = _make_trades([0.01, -0.005] * 10)
    db_path = _make_db(tmp_path, strategy, trades)

    # Patch _STRATEGY_DB to point at our temp db
    monkeypatch.setattr(sig_mod, "_STRATEGY_DB", {strategy: db_path.name})
    monkeypatch.setattr(sig_mod, "_BASE", tmp_path)

    loaded, meta = sig_mod.load_trades_from_db(strategy)
    assert len(loaded) == 20
    assert meta["source"] == "live_db"
    assert all(isinstance(t["profit_ratio"], float) for t in loaded)


def test_load_trades_from_db_not_found(tmp_path, monkeypatch):
    from qnt.tools import significance as sig_mod

    monkeypatch.setattr(sig_mod, "_BASE", tmp_path)
    monkeypatch.setattr(sig_mod, "_STRATEGY_DB", {"Ghost": "ghost.sqlite"})

    with pytest.raises(FileNotFoundError, match="not found"):
        sig_mod.load_trades_from_db("Ghost")


def test_load_trades_prefers_backtest(tmp_path, monkeypatch):
    from qnt.tools import significance as sig_mod

    strategy = "ScalpV1"
    bt_trades = _make_trades([0.01] * 30)
    db_trades = _make_trades([-0.01] * 10)

    _make_backtest_zip(tmp_path, strategy, bt_trades)
    db_path = _make_db(tmp_path, strategy, db_trades)

    monkeypatch.setattr(sig_mod, "_RESULTS_DIR", tmp_path)
    monkeypatch.setattr(sig_mod, "_STRATEGY_DB", {strategy: db_path.name})
    monkeypatch.setattr(sig_mod, "_BASE", tmp_path)

    loaded, meta = sig_mod.load_trades(strategy, prefer="backtest")
    assert meta["source"] == "backtest"
    assert len(loaded) == 30


def test_load_trades_prefers_live(tmp_path, monkeypatch):
    from qnt.tools import significance as sig_mod

    strategy = "ScalpV1"
    bt_trades = _make_trades([0.01] * 30)
    db_trades = _make_trades([-0.01] * 10)

    _make_backtest_zip(tmp_path, strategy, bt_trades)
    db_path = _make_db(tmp_path, strategy, db_trades)

    monkeypatch.setattr(sig_mod, "_RESULTS_DIR", tmp_path)
    monkeypatch.setattr(sig_mod, "_STRATEGY_DB", {strategy: db_path.name})
    monkeypatch.setattr(sig_mod, "_BASE", tmp_path)

    loaded, meta = sig_mod.load_trades(strategy, prefer="live")
    assert meta["source"] == "live_db"
    assert len(loaded) == 10
