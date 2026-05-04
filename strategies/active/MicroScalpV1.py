import sys, os; home = os.path.expanduser('~'); sys.path.append(os.path.join(home, 'masterbot')); sys.path.append(os.path.join(home, 'masterbot', 'qnt', 'memory')); sys.path.append(os.path.join(home, 'masterbot', 'qnt', 'oracle'));
import logging
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from pandas import DataFrame
import pandas_ta as ta
import numpy as np
import pandas as pd

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, merge_informative_pair
from freqtrade.persistence import Trade

# Add base directory to path for custom imports
home = os.path.expanduser("~")
sys.path.append(os.path.join(home, 'masterbot'))
from risk.risk_manager import run_all_checks
from sentiment.reader import get_current_sentiment, get_sentiment_signal

logger = logging.getLogger(__name__)

def merge_macro_data(dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Injects macro covariates (DXY, Funding, OI) into the dataframe.
    """
    try:
        history_file = Path('/Users/aatifquamre/masterbot/risk/macro_history.json')
        if not history_file.exists():
            dataframe['dxy_24h_change'] = 0.0
            dataframe['btc_funding_rate'] = 0.0
            dataframe['btc_open_interest'] = 0.0
            return dataframe

        with open(history_file, 'r') as f:
            history = json.load(f)

        macro_df = pd.DataFrame(history)
        macro_df['date'] = pd.to_datetime(macro_df['timestamp'])
        macro_df = macro_df.sort_values('date')

        dataframe = dataframe.sort_values('date')
        dataframe = pd.merge_asof(
            dataframe,
            macro_df[['date', 'dxy_24h_change', 'btc_funding_rate', 'btc_open_interest']],
            on='date',
            direction='backward'
        )

        dataframe[['dxy_24h_change', 'btc_funding_rate', 'btc_open_interest']] = \
            dataframe[['dxy_24h_change', 'btc_funding_rate', 'btc_open_interest']].fillna(0.0)

        return dataframe
    except Exception as e:
        return dataframe

class MicroScalpV1(IStrategy):
    """
    Highest frequency 1-minute micro-scalping strategy.
    Optimized for maximum trade generation to accelerate FreqAI learning.
    """
    INTERFACE_VERSION = 3
    
    timeframe = '1m'
    informative_timeframes = ['5m', '15m']
    
    # Strategy parameters
    buy_rsi = IntParameter(15, 30, default=25, space='buy')
    sell_rsi = IntParameter(70, 85, default=75, space='sell')
    
    # Tight scalping targets
    minimal_roi = {
        "0": 0.003,    # 0.3% immediate
        "5": 0.005,    # 0.5% after 5 mins
        "15": 0.008,   # 0.8% after 15 mins
        "30": 0.010    # 1.0% after 30 mins
    }
    
    stoploss = -0.015  # 1.5% hard stop
    
    trailing_stop = True
    trailing_stop_positive = 0.003
    trailing_stop_positive_offset = 0.005
    stoploss_on_exchange = True

    def informative_pairs(self):
        # We need BTC for trend and sentiment context
        pairs = self.dp.current_whitelist()
        informative_pairs = []
        for tf in self.informative_timeframes:
            for pair in pairs:
                informative_pairs.append((pair, tf))
            # Always track BTC/USDT for market-wide filters
            if "BTC/USDT" not in pairs:
                informative_pairs.append(("BTC/USDT", tf))
        return informative_pairs

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- 1m Indicators ---
        dataframe['rsi'] = ta.rsi(dataframe['close'], length=7)
        bb = ta.bbands(dataframe['close'], length=15, std=1.8)
        dataframe['bb_lower'] = bb['BBL_15_1.8']
        dataframe['bb_middle'] = bb['BBM_15_1.8']
        dataframe['volume_avg'] = ta.sma(dataframe['volume'], length=20)

        # --- Informative Timeframes ---
        # 5m Trend confirmation
        inf_5m = self.dp.get_pair_dataframe(metadata['pair'], '5m')
        inf_5m['ema_20'] = ta.ema(inf_5m['close'], length=20)
        dataframe = merge_informative_pair(dataframe, inf_5m, self.timeframe, '5m', ffill=True)

        # 15m RSI Context
        inf_15m = self.dp.get_pair_dataframe(metadata['pair'], '15m')
        inf_15m['rsi'] = ta.rsi(inf_15m['close'], length=14)
        dataframe = merge_informative_pair(dataframe, inf_15m, self.timeframe, '15m', ffill=True)

        # --- Macro Data ---
        dataframe = merge_macro_data(dataframe)
        
        # --- FreqAI Features ---
        # This will be used by FreqAI to expand features
        dataframe['sentiment_score'] = get_current_sentiment()['score']
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        sentiment = get_current_sentiment()
        
        dataframe.loc[
            (
                # Rule 1: Fast RSI Oversold
                (dataframe['rsi'] < self.buy_rsi.value) &
                # Rule 2: Bollinger Band breakout
                (dataframe['close'] < dataframe['bb_lower']) &
                # Rule 3: Volume spike
                (dataframe['volume'] > dataframe['volume_avg'] * 1.5) &
                # Rule 4: 5m Trend Filter (Not strongly bearish)
                (dataframe['close'] >= dataframe['ema_20_5m'] * 0.995) &
                # Rule 5: Sentiment Gate
                (sentiment['score'] >= -0.3)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # Exit Rule 1: RSI Overbought
                (dataframe['rsi'] > self.sell_rsi.value)
            ),
            'exit_long'] = 1
        return dataframe

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                           time_in_force: str, current_time: datetime, entry_tag: str,
                           side: str, **kwargs) -> bool:
        """
        Final check before execution - Risk Manager Audit.
        """
        try:
            total_balance = self.wallets.get_total('USDT')
            
            # Fetch recent trades
            recent_trades = [
                {'profit_ratio': t.profit_ratio, 'close_date': t.close_date} 
                for t in Trade.get_trades_proxy(is_open=False)
            ][:10]
            
            # Count trades in the last hour
            one_hour_ago = current_time - timedelta(hours=1)
            trades_last_hour = len([
                t for t in Trade.get_trades_proxy(is_open=False)
                if t.close_date and t.close_date >= one_hour_ago
            ])
            
            # Load balance state
            state_file = Path('/Users/aatifquamre/masterbot/risk/balance_state.json')
            if state_file.exists():
                with open(state_file) as f:
                    state = json.load(f)
                start_of_day = state.get('start_of_day', total_balance)
                start_of_week = state.get('start_of_week', total_balance)
            else:
                start_of_day = total_balance
                start_of_week = total_balance
            
            risk_result = run_all_checks(
                current_balance=total_balance,
                start_of_day_balance=start_of_day,
                start_of_week_balance=start_of_week,
                trade_amount_usdt=amount * rate,
                trades_last_hour=trades_last_hour,
                recent_trades=recent_trades,
                min_sentiment='NEUTRAL'
            )
            
            if not risk_result['safe_to_trade']:
                logger.info(f"[MicroScalp BLOCK] Risk audit failed for {pair}. Reasons: {risk_result['blocking_reasons']}")
                return False

        except Exception as e:
            logger.error(f"Risk check error in MicroScalp: {e}")
            
        return True

    # FreqAI Integration
    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int,
                                    metadata: dict, **kwargs) -> DataFrame:
        """
        Expand features for FreqAI.
        """
        dataframe["%-rsi-period"] = ta.rsi(dataframe["close"], length=period)
        dataframe["%-mfi-period"] = ta.mfi(dataframe["high"], dataframe["low"], dataframe["close"], dataframe["volume"], length=period)
        dataframe["%-adx-period"] = ta.adx(dataframe["high"], dataframe["low"], dataframe["close"], length=period)["ADX_" + str(period)]
        
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        """
        Define the targets for the FreqAI model.
        """
        dataframe["&-s_close_price"] = (
            dataframe["close"].shift(-self.freqai_info["feature_parameters"]["label_period_candles"])
            / dataframe["close"]
            - 1
        )
        return dataframe
