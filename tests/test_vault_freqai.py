"""
Tests for VaultFreqaiModel and VectorVaultV1 FreqAI wiring.

Covers:
  - _VaultEstimator.predict correctness (Rust + NumPy paths)
  - VaultFreqaiModel.fit returns a usable estimator
  - VectorVaultV1 feature_engineering_* produce correctly-named columns
  - VectorVaultV1.set_freqai_targets produces '&-rust_signal' column
  - VectorVaultV1 entry/exit signal logic given synthetic FreqAI output
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import ta

# Make cipher importable without installing
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qnt.freqai.VaultFreqaiModel import VaultFreqaiModel, _VaultEstimator


# ── _VaultEstimator unit tests ───────────────────────────────────────────────

class TestVaultEstimator:
    def test_returns_array_of_correct_length(self, vault_xy):
        X, y = vault_xy
        est = _VaultEstimator(X[:200], y[:200], lookback=200)
        preds = est.predict(X[200:])
        assert preds.shape == (len(X[200:]),)

    def test_exact_match_returns_own_label(self):
        # Use an identity matrix so every row is unique and its own nearest neighbour.
        rng = np.random.default_rng(7)
        X = np.eye(20, dtype=np.float64)          # each row is a distinct unit vector
        y = rng.normal(0, 0.01, 20).astype(np.float64)
        est = _VaultEstimator(X, y, lookback=20)
        pred = est.predict(X[10:11])
        assert float(pred[0]) == pytest.approx(float(y[10]), abs=1e-9)

    def test_lookback_truncates_vault(self, vault_xy):
        X, y = vault_xy
        est_full = _VaultEstimator(X, y, lookback=len(X))
        est_trunc = _VaultEstimator(X, y, lookback=50)
        assert len(est_trunc.X_vault) == 50
        assert len(est_full.X_vault) == len(X)

    def test_numpy_fallback_matches_rust(self, vault_xy, monkeypatch):
        """Both code paths must return the same nearest-neighbour label."""
        X, y = vault_xy
        est = _VaultEstimator(X[:100], y[:100], lookback=100)

        # Force NumPy path
        import qnt.freqai.VaultFreqaiModel as _mod
        with patch.object(_mod, "_RUST_AVAILABLE", False):
            from qnt.freqai.VaultFreqaiModel import _VaultEstimator as _VE2
            est_np = _VE2(X[:100], y[:100], lookback=100)
            preds_np = est_np.predict(X[100:110])

        preds_rust = est.predict(X[100:110])
        np.testing.assert_allclose(preds_rust, preds_np, rtol=0, atol=1e-9)

    def test_predict_accepts_dataframe(self, vault_xy):
        X, y = vault_xy
        est = _VaultEstimator(X[:100], y[:100])
        df = pd.DataFrame(X[100:105], columns=["rsi", "macd", "bb_width"])
        preds = est.predict(df)
        assert preds.shape == (5,)
        assert np.all(np.isfinite(preds))


# ── VaultFreqaiModel.fit ─────────────────────────────────────────────────────

class TestVaultFreqaiModelFit:
    def _make_dk_stub(self, feature_params=None):
        dk = MagicMock()
        dk.freqai_info = {
            "feature_parameters": feature_params or {"vault_lookback": 200}
        }
        return dk

    def test_fit_returns_vault_estimator(self, vault_xy):
        X, y = vault_xy
        model = VaultFreqaiModel.__new__(VaultFreqaiModel)

        train_features = pd.DataFrame(X[:200], columns=["f0", "f1", "f2"])
        train_labels = pd.DataFrame({"&-rust_signal": y[:200]})
        dd = {"train_features": train_features, "train_labels": train_labels}
        dk = self._make_dk_stub({"vault_lookback": 150})

        est = model.fit(dd, dk)
        assert isinstance(est, _VaultEstimator)
        assert len(est.X_vault) == 150

    def test_fit_predict_pipeline(self, vault_xy):
        """fit then predict end-to-end."""
        X, y = vault_xy
        model = VaultFreqaiModel.__new__(VaultFreqaiModel)

        dd = {
            "train_features": pd.DataFrame(X[:200], columns=["f0", "f1", "f2"]),
            "train_labels": pd.DataFrame({"&-rust_signal": y[:200]}),
        }
        dk = self._make_dk_stub({"vault_lookback": 200})
        est = model.fit(dd, dk)

        preds = est.predict(X[200:210])
        assert preds.shape == (10,)
        assert all(np.isfinite(preds))

    def test_fit_uses_default_lookback_when_missing(self, vault_xy):
        X, y = vault_xy
        model = VaultFreqaiModel.__new__(VaultFreqaiModel)
        dd = {
            "train_features": pd.DataFrame(X, columns=["f0", "f1", "f2"]),
            "train_labels": pd.DataFrame({"&-rust_signal": y}),
        }
        # no vault_lookback key → should use default 1000 (capped by data size)
        dk = self._make_dk_stub({})
        est = model.fit(dd, dk)
        assert isinstance(est, _VaultEstimator)


# ── VectorVaultV1 feature engineering ───────────────────────────────────────

class TestVectorVaultV1Features:
    @pytest.fixture()
    def strategy(self):
        """Instantiate VectorVaultV1 without a real bot config."""
        from strategies.active.VectorVaultV1 import VectorVaultV1
        s = VectorVaultV1.__new__(VectorVaultV1)
        s.freqai_info = {
            "feature_parameters": {
                "label_period_candles": 5,
                "vault_lookback": 1000,
            }
        }
        s.dp = MagicMock()
        return s

    def test_feature_engineering_expand_all_produces_pct_columns(self, strategy, ohlcv_df):
        df = ohlcv_df.copy()
        df = strategy.feature_engineering_expand_all(df, period=14, metadata={})
        assert "%-rsi-period_14" in df.columns
        assert "%-macd-period_14" in df.columns
        assert "%-bb_width-period_14" in df.columns

    def test_feature_engineering_standard_produces_time_cols(self, strategy, ohlcv_df):
        df = ohlcv_df.copy()
        df = strategy.feature_engineering_standard(df, metadata={})
        assert "%-day_of_week" in df.columns
        assert "%-hour_of_day" in df.columns
        assert "%-pct_change" in df.columns

    def test_day_of_week_range(self, strategy, ohlcv_df):
        df = ohlcv_df.copy()
        df = strategy.feature_engineering_standard(df, metadata={})
        assert df["%-day_of_week"].between(0, 6).all()

    def test_hour_of_day_range(self, strategy, ohlcv_df):
        df = ohlcv_df.copy()
        df = strategy.feature_engineering_standard(df, metadata={})
        assert df["%-hour_of_day"].between(0, 23).all()

    def test_set_freqai_targets_column_name(self, strategy, ohlcv_df):
        df = ohlcv_df.copy()
        df = strategy.set_freqai_targets(df, metadata={})
        assert "&-rust_signal" in df.columns

    def test_set_freqai_targets_values_are_returns(self, strategy, ohlcv_df):
        df = ohlcv_df.copy()
        df = strategy.set_freqai_targets(df, metadata={})
        # A return should be in (-1, +∞); typical range for 5-candle crypto is small
        non_null = df["&-rust_signal"].dropna()
        assert non_null.abs().max() < 1.0, "Unreasonably large forward return"

    def test_no_lookahead_in_features(self, strategy, ohlcv_df):
        """Confirm feature_engineering_standard doesn't use future close prices."""
        df = ohlcv_df.copy()
        df = strategy.feature_engineering_standard(df, metadata={})
        # pct_change uses only current and previous close — never shifts negatively
        assert "%-pct_change" in df.columns
        # first row should be 0.0 (fillna) not a non-zero value from row 1
        assert df["%-pct_change"].iloc[0] == pytest.approx(0.0, abs=1e-9)


# ── VectorVaultV1 entry / exit signal logic ──────────────────────────────────

class TestVectorVaultV1Signals:
    @pytest.fixture()
    def strategy(self):
        from strategies.active.VectorVaultV1 import VectorVaultV1
        s = VectorVaultV1.__new__(VectorVaultV1)
        s.freqai_info = {"feature_parameters": {"label_period_candles": 5, "vault_lookback": 1000}}
        s.dp = MagicMock()
        s.ENTRY_THRESHOLD = 0.01
        s.EXIT_THRESHOLD = -0.01
        return s

    def _signal_df(self, n=50, rust_signal_val=0.05, do_predict_val=1) -> pd.DataFrame:
        rng = np.random.default_rng(0)
        df = pd.DataFrame({
            "close": 30000.0 + rng.normal(0, 50, n),
            "volume": rng.uniform(10, 100, n),
            "do_predict": do_predict_val,
            "&-rust_signal": rust_signal_val,
            "enter_long": 0,
            "exit_long": 0,
        })
        return df

    def test_entry_fires_when_signal_positive(self, strategy):
        df = self._signal_df(rust_signal_val=0.03, do_predict_val=1)
        out = strategy.populate_entry_trend(df.copy(), {})
        assert out["enter_long"].sum() > 0

    def test_entry_blocked_when_do_predict_zero(self, strategy):
        df = self._signal_df(rust_signal_val=0.03, do_predict_val=0)
        out = strategy.populate_entry_trend(df.copy(), {})
        assert out["enter_long"].sum() == 0

    def test_entry_blocked_when_signal_below_threshold(self, strategy):
        df = self._signal_df(rust_signal_val=0.005, do_predict_val=1)
        out = strategy.populate_entry_trend(df.copy(), {})
        assert out["enter_long"].sum() == 0

    def test_exit_fires_when_signal_negative(self, strategy):
        df = self._signal_df(rust_signal_val=-0.03, do_predict_val=1)
        out = strategy.populate_exit_trend(df.copy(), {})
        assert out["exit_long"].sum() > 0

    def test_exit_blocked_when_do_predict_zero(self, strategy):
        df = self._signal_df(rust_signal_val=-0.03, do_predict_val=0)
        out = strategy.populate_exit_trend(df.copy(), {})
        assert out["exit_long"].sum() == 0

    def test_no_entry_and_no_exit_at_neutral_signal(self, strategy):
        df = self._signal_df(rust_signal_val=0.0, do_predict_val=1)
        out = strategy.populate_entry_trend(df.copy(), {})
        out = strategy.populate_exit_trend(out, {})
        assert out["enter_long"].sum() == 0
        assert out["exit_long"].sum() == 0

    def test_entry_tag_set(self, strategy):
        df = self._signal_df(rust_signal_val=0.05, do_predict_val=1)
        df["enter_tag"] = ""
        out = strategy.populate_entry_trend(df.copy(), {})
        entered = out[out["enter_long"] == 1]
        assert (entered["enter_tag"] == "vault_long").all()
