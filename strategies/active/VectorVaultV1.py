import logging
import sys
from pathlib import Path
from functools import reduce

import numpy as np
import pandas as pd
import ta
from pandas import DataFrame

_BASE = Path(__file__).resolve().parent.parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))

from freqtrade.strategy import IStrategy

logger = logging.getLogger(__name__)


class VectorVaultV1(IStrategy):
    """
    Institutional-Grade Vector Pattern Matcher — FreqAI edition.

    Feature engineering:
      %rsi, %macd, %bb_width  (expand_all — period-parameterised)
      %day_of_week, %hour_of_day  (standard — time features)

    Target:
      &-rust_signal = forward return over label_period_candles candles

    Prediction:
      VaultFreqaiModel (qnt/freqai/VaultFreqaiModel.py) finds the nearest
      historical feature vector in the training vault (Rust engine) and
      returns its realised forward return as &-rust_signal.

    Entry/exit uses do_predict == 1 to filter low-confidence candles.
    """

    INTERFACE_VERSION = 3
    timeframe = "15m"
    process_only_new_candles = True
    startup_candle_count: int = 40

    minimal_roi = {"0": 0.15, "30": 0.05, "60": 0.02, "120": 0}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    # Signal threshold for entry/exit (fraction of close price)
    ENTRY_THRESHOLD = 0.01
    EXIT_THRESHOLD = -0.01

    # ── FreqAI lifecycle ────────────────────────────────────────────

    def feature_engineering_expand_all(
        self, dataframe: DataFrame, period: int, metadata: dict, **kwargs
    ) -> DataFrame:
        """Period-parameterised features expanded across indicator_periods_candles."""
        dataframe[f"%-rsi-period_{period}"] = ta.momentum.rsi(
            dataframe["close"], window=period
        )
        macd_obj = ta.trend.MACD(dataframe["close"], window_slow=period * 2, window_fast=period)
        dataframe[f"%-macd-period_{period}"] = macd_obj.macd()
        dataframe[f"%-bb_width-period_{period}"] = (
            ta.volatility.bollinger_hband(dataframe["close"], window=period)
            - ta.volatility.bollinger_lband(dataframe["close"], window=period)
        ) / dataframe["close"].replace(0, np.nan)
        return dataframe

    def feature_engineering_standard(
        self, dataframe: DataFrame, metadata: dict, **kwargs
    ) -> DataFrame:
        """Time-of-week features — not period-expanded."""
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        dataframe["%-pct_change"] = dataframe["close"].pct_change().fillna(0.0)
        return dataframe

    def set_freqai_targets(
        self, dataframe: DataFrame, metadata: dict, **kwargs
    ) -> DataFrame:
        """
        Target: forward return over label_period_candles candles.
        Positive → price went up (long signal); negative → down.
        """
        label_len: int = self.freqai_info["feature_parameters"]["label_period_candles"]
        dataframe["&-rust_signal"] = (
            dataframe["close"].shift(-label_len) / dataframe["close"] - 1
        )
        return dataframe

    # ── Freqtrade strategy interface ────────────────────────────────

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self.freqai.start(dataframe, metadata, self)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        enter_conditions = [
            dataframe["do_predict"] == 1,
            dataframe["&-rust_signal"] > self.ENTRY_THRESHOLD,
            dataframe["volume"] > 0,
        ]
        if enter_conditions:
            dataframe.loc[
                reduce(lambda a, b: a & b, enter_conditions),
                ["enter_long", "enter_tag"],
            ] = (1, "vault_long")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_conditions = [
            dataframe["do_predict"] == 1,
            dataframe["&-rust_signal"] < self.EXIT_THRESHOLD,
            dataframe["volume"] > 0,
        ]
        if exit_conditions:
            dataframe.loc[
                reduce(lambda a, b: a & b, exit_conditions),
                "exit_long",
            ] = 1
        return dataframe

    def confirm_trade_entry(
        self, pair, order_type, amount, rate, time_in_force,
        current_time, entry_tag, side, **kwargs,
    ) -> bool:
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = df.iloc[-1].squeeze()
        if side == "long" and rate > last_candle["close"] * 1.0025:
            return False
        return True
