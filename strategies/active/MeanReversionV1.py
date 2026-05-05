import sys, os; home = os.path.expanduser('~'); sys.path.append(os.path.join(home, 'masterbot')); sys.path.append(os.path.join(home, 'masterbot', 'qnt', 'memory')); sys.path.append(os.path.join(home, 'masterbot', 'qnt', 'oracle'));
import logging
import json
import sys
import os
from pathlib import Path
from datetime import timedelta, datetime
from pandas import DataFrame
import pandas_ta as ta
import numpy as np

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from freqtrade.persistence import Trade
import pandas as pd

# Add base directory to path for custom imports
sys.path.insert(0, '/Users/aatifquamre/masterbot')
from risk.risk_manager import run_all_checks
from sentiment.reader import get_current_sentiment, get_sentiment_signal
from qnt.oracle.hmm_regime import detect_regime, get_regime_for_strategy

logger = logging.getLogger(__name__)

def merge_macro_data(dataframe: DataFrame) -> DataFrame:
    """
    Injects macro covariates (DXY, Funding, OI) into the dataframe.
    Uses timestamp-based merging to prevent look-ahead bias.
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

        # Ensure main dataframe is sorted by date for asof merge
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

class MeanReversionV1(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '1h'
    
    # Hyperoptable Parameters
    buy_rsi = IntParameter(20, 40, default=32, space='buy')
    bb_period = IntParameter(20, 50, default=31, space='buy')
    bb_std = DecimalParameter(1.5, 2.5, default=1.8, space='buy')
    
    sell_rsi = IntParameter(60, 80, default=68, space='sell')
    minimal_roi = {
        "0": 0.426,
        "226": 0.13,
        "650": 0.082,
        "1867": 0
    }
    stoploss = -0.04
    stoploss_on_exchange = True
    stoploss_on_exchange_interval = 60

    # Startup candles
    startup_candle_count: int = 50

    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int,
                                     metadata: dict, **kwargs) -> DataFrame:
        # Standard indicators for the model
        dataframe["%-rsi-period"] = ta.rsi(dataframe["close"], length=period) / 100
        dataframe["%-bb_lower-period"] = dataframe["close"] / dataframe["bb_lower"]
        
        # External signal features
        import json
        try:
            MASTERBOT_PATH = '/Users/aatifquamre/masterbot'
            with open(f'{MASTERBOT_PATH}/sentiment/scores/current_score.json') as f:
                sentiment_data = json.load(f)
            
            dataframe['sentiment_score'] = sentiment_data.get('score', 0.0)
            dataframe['fear_greed_raw'] = sentiment_data.get('component_scores', {}).get('feargreed', 0.0)
            dataframe['funding_rate_raw'] = sentiment_data.get('component_scores', {}).get('funding', 0.0)
            
            # Calendar risk as numeric feature
            from qnt.oracle.oracle_calendar import check_calendar_risk_today
            risk_map = {'LOW': 0, 'MEDIUM': 1, 'HIGH': 2, 'EXTREME': 3}
            dataframe['calendar_risk'] = risk_map.get(check_calendar_risk_today(), 1)
        except Exception:
            dataframe['sentiment_score'] = 0.0
            dataframe['fear_greed_raw'] = 0.0
            dataframe['funding_rate_raw'] = 0.0
            dataframe['calendar_risk'] = 1

        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        return dataframe

    def feature_engineering_standard(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        dataframe["&-s_close"] = dataframe["close"].shift(-self.freqai_info["feature_parameters"]["label_period_candles"]) / dataframe["close"] - 1
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Standard Indicators with optimized params
        dataframe['rsi'] = ta.rsi(dataframe['close'], length=14)
        
        bb = ta.bbands(dataframe['close'], length=self.bb_period.value, std=self.bb_std.value)
        dataframe['bb_lower'] = bb[f'BBL_{self.bb_period.value}_{self.bb_std.value}']
        dataframe['bb_middle'] = bb[f'BBM_{self.bb_period.value}_{self.bb_std.value}']
            
        dataframe = merge_macro_data(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # HMM Regime Check
        regime_data = detect_regime(dataframe)
        regime_ok = get_regime_for_strategy(dataframe, 'mean_reversion')
        confidence_ok = regime_data['confidence'] >= 0.6

        dataframe.loc[
            (
                (dataframe['rsi'] < self.buy_rsi.value) &
                (dataframe['close'] < dataframe['bb_lower']) &
                (regime_ok) &
                (confidence_ok)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['rsi'] > self.sell_rsi.value)
            ),
            'exit_long'] = 1
        return dataframe

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: str,
                            side: str, **kwargs) -> bool:
        
        # --- LAYER 1: RISK & SENTIMENT CHECKS ---
        try:
            total_balance = self.wallets.get_total('USDT')
            
            # Fetch recent trades for loss counting
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
            
            # Load balance state for drawdown checks
            state_file = Path('/Users/aatifquamre/masterbot/risk/balance_state.json')
            if state_file.exists():
                with open(state_file) as f:
                    state = json.load(f)
                start_of_day = state.get('start_of_day', total_balance)
                start_of_week = state.get('start_of_week', total_balance)
            else:
                start_of_day = total_balance
                start_of_week = total_balance
            
            # MeanReversionV1 requires at least NEUTRAL sentiment
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
                logger.info(f"[RISK/SENTIMENT BLOCK] MeanReversion blocked for {pair}. Reasons: {risk_result['blocking_reasons']}")
                return False

            # Log sentiment for visibility
            sentiment = get_current_sentiment()
            signal = get_sentiment_signal()
            logger.info(f"[Sentiment Check] {pair} | Score: {sentiment['score']:.3f} | Signal: {signal}")

        except Exception as e:
            logger.error(f"[RISK WARNING] Risk check error: {e}")

        return True
