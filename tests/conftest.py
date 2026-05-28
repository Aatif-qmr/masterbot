"""Shared pytest fixtures for Cipher strategy and model tests."""
import sys
import types
from unittest.mock import MagicMock

# ── Inject minimal freqtrade stubs ────────────────────────────────────────────
# VectorVaultV1 inherits IStrategy at import time. The freqtrade submodule
# exists but has a broken import chain in this environment (no __version__).
# Inject lightweight stubs so the strategy can be imported and its logic
# tested in isolation — without the full bot stack.
#
# This block runs at conftest-load time (before any test fixture executes),
# so the stubs are in sys.modules before VectorVaultV1 is ever imported.


class _IStrategyStub:
    INTERFACE_VERSION = 3
    timeframe = "15m"
    process_only_new_candles = True
    startup_candle_count: int = 0
    minimal_roi: dict = {}
    stoploss: float = -0.10
    trailing_stop: bool = False
    trailing_stop_positive: float = 0.0
    trailing_stop_positive_offset: float = 0.0
    trailing_only_offset_is_reached: bool = False


_ft_iface_mod = types.ModuleType("freqtrade.strategy.interface")
_ft_iface_mod.IStrategy = _IStrategyStub  # type: ignore[attr-defined]

_ft_strategy_mod = types.ModuleType("freqtrade.strategy")
_ft_strategy_mod.IStrategy = _IStrategyStub  # type: ignore[attr-defined]
_ft_strategy_mod.interface = _ft_iface_mod  # type: ignore[attr-defined]

# The BaseRegressionModel stub must be a real module with a real class attribute,
# not a MagicMock — otherwise `from ... import BaseRegressionModel` returns a
# MagicMock instance which VaultFreqaiModel would inherit from, breaking __new__.
_ft_brm_mod = types.ModuleType("freqtrade.freqai.base_models.BaseRegressionModel")
_ft_brm_mod.BaseRegressionModel = object  # type: ignore[attr-defined]

_ft_dk_mod = types.ModuleType("freqtrade.freqai.data_kitchen")
_ft_dk_mod.FreqaiDataKitchen = type("FreqaiDataKitchen", (), {})  # type: ignore[attr-defined]

_FREQTRADE_STUB_MODS = {
    "freqtrade.strategy": _ft_strategy_mod,
    "freqtrade.strategy.interface": _ft_iface_mod,
    "freqtrade.data": MagicMock(),
    "freqtrade.data.dataprovider": MagicMock(),
    "freqtrade.rpc": MagicMock(),
    "freqtrade.rpc.rpc": MagicMock(),
    "freqtrade.freqai": MagicMock(),
    "freqtrade.freqai.base_models": MagicMock(),
    "freqtrade.freqai.base_models.BaseRegressionModel": _ft_brm_mod,
    "freqtrade.freqai.data_kitchen": _ft_dk_mod,
}

for _name, _mod in _FREQTRADE_STUB_MODS.items():
    sys.modules[_name] = _mod

# ─────────────────────────────────────────────────────────────────────────────

import numpy as np
import pandas as pd
import pytest


def _make_ohlcv(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """Return a synthetic OHLCV DataFrame with `date` column."""
    rng = np.random.default_rng(seed)
    price = 30_000.0 + np.cumsum(rng.normal(0, 50, n))
    low = price - rng.uniform(10, 100, n)
    high = price + rng.uniform(10, 100, n)
    close = price + rng.normal(0, 10, n)
    volume = rng.uniform(10, 500, n)
    dates = pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC")
    return pd.DataFrame(
        {
            "date": dates,
            "open": price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


@pytest.fixture()
def ohlcv_df() -> pd.DataFrame:
    """300-row synthetic 15-min OHLCV dataframe."""
    return _make_ohlcv(300)


@pytest.fixture()
def small_ohlcv_df() -> pd.DataFrame:
    """50-row dataframe for edge-case tests."""
    return _make_ohlcv(50, seed=7)


@pytest.fixture()
def vault_xy(ohlcv_df):
    """Pre-computed X/y arrays from synthetic OHLCV (RSI + MACD + BB_width → fwd return)."""
    import ta
    df = ohlcv_df.copy()
    df["rsi"] = ta.momentum.rsi(df["close"], window=14).fillna(50.0)
    df["macd"] = ta.trend.macd(df["close"]).fillna(0.0)
    df["bb_width"] = (
        (ta.volatility.bollinger_hband(df["close"])
         - ta.volatility.bollinger_lband(df["close"]))
        / df["close"]
    ).fillna(0.0)
    df["fwd_return"] = (df["close"].shift(-5) / df["close"] - 1).fillna(0.0)
    X = df[["rsi", "macd", "bb_width"]].values.astype(np.float64)
    y = df["fwd_return"].values.astype(np.float64)
    return X, y
