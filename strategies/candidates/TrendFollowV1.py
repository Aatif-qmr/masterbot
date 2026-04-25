import pandas_ta as ta
from freqtrade.strategy import IStrategy, IntParameter
from pandas import DataFrame
import numpy as np
import sys
import os
import freqtrade.vendor.qtpylib.indicators as qtpylib

# Import custom regime detector
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from regime_detector import detect_regime

class TrendFollowV1(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '4h'
    
    # Parameters
    buy_rsi_min = IntParameter(30, 50, default=40, space='buy')
    buy_rsi_max = IntParameter(60, 80, default=80, space='buy')
    sell_rsi_limit = IntParameter(70, 90, default=75, space='sell')
    
    minimal_roi = {"0": 0.03}
    stoploss = -0.08
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if 'ema_fast' not in dataframe.columns:
            dataframe['ema_fast'] = ta.ema(dataframe['close'], length=20)
            dataframe['ema_slow'] = ta.ema(dataframe['close'], length=50)
            macd = ta.macd(dataframe['close'], fast=12, slow=26, signal=9)
            dataframe['macd_hist'] = macd['MACDh_12_26_9']
            dataframe['rsi'] = ta.rsi(dataframe['close'], length=14)
            dataframe = detect_regime(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Handle both Hyperopt object and raw value
        rsi_min = self.buy_rsi_min.value if hasattr(self.buy_rsi_min, 'value') else self.buy_rsi_min
        rsi_max = self.buy_rsi_max.value if hasattr(self.buy_rsi_max, 'value') else self.buy_rsi_max
        
        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe['ema_fast'], dataframe['ema_slow'])) &
                (dataframe['macd_hist'] > 0) &
                (dataframe['regime'] == 'TRENDING_UP') &
                (dataframe['rsi'] > rsi_min) & 
                (dataframe['rsi'] < rsi_max)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi_limit = self.sell_rsi_limit.value if hasattr(self.sell_rsi_limit, 'value') else self.sell_rsi_limit
        
        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe['ema_fast'], dataframe['ema_slow'])) |
                (dataframe['rsi'] > rsi_limit)
            ),
            'exit_long'] = 1
        return dataframe
