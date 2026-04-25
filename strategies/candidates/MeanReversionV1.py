import pandas_ta as ta
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from pandas import DataFrame
import numpy as np
import sys
import os

# Import custom regime detector
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from regime_detector import detect_regime

class MeanReversionV1(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '1h'
    
    # Optimized Parameters
    buy_params = {
        "bb_period": 30,
        "bb_std": 1.7,
        "buy_rsi": 30,
    }
    sell_params = {
        "sell_rsi": 67,
    }
    minimal_roi = {
        "0": 0.426,
        "226": 0.13,
        "650": 0.082,
        "1867": 0
    }
    stoploss = -0.27

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Standard Indicators with optimized params
        dataframe['rsi'] = ta.rsi(dataframe['close'], length=14)
        
        bb = ta.bbands(dataframe['close'], length=self.buy_params['bb_period'], std=self.buy_params['bb_std'])
        dataframe['bb_lower'] = bb[f'BBL_{self.buy_params["bb_period"]}_{self.buy_params["bb_std"]}']
        dataframe['bb_middle'] = bb[f'BBM_{self.buy_params["bb_period"]}_{self.buy_params["bb_std"]}']
            
        dataframe = detect_regime(dataframe)
        dataframe['sentiment_score'] = 0.0
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['rsi'] < self.buy_params['buy_rsi']) &
                (dataframe['close'] < dataframe['bb_lower']) &
                (dataframe['regime'] == 'RANGING') &
                (dataframe['sentiment_score'] > -0.3)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['rsi'] > self.sell_params['sell_rsi']) |
                (dataframe['close'] > dataframe['bb_middle'])
            ),
            'exit_long'] = 1
        return dataframe
