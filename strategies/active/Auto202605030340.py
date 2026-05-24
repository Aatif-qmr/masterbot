import sys
import os
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from pandas import DataFrame

from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade

# Add base directory to path for custom imports
BASE_DIR = '/Users/aatifquamre/cipher'
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from risk.risk_manager import run_all_checks
from sentiment.reader import get_current_sentiment, get_sentiment_signal

logger = logging.getLogger(__name__)

class Auto202605030340(IStrategy):
    """
    Hypothesis: Buy BTC when RSI below 30.
    Integrates Cipher Sentiment Gate and Risk Manager.
    """
    # Strategy Interface Version
    INTERFACE_VERSION = 3

    # Timeframe and candle settings
    timeframe = '5m'
    startup_candle_count: int = 50

    # Risk Management Settings
    stoploss = -0.04
    stoploss_on_exchange = True

    # Minimal ROI (Empty as we primarily use stoploss or custom exit)
    minimal_roi = {
        "0": 0.1,  # Exit at 10% profit
        "60": 0.05,
        "120": 0.02
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculate indicators using polars.
        """
        import polars as pl
        from qnt.polars_ohlcv import pandas_to_polars, ohlcv_to_pandas
        from qnt.polars_indicators import add_rsi
        
        df_pl = pandas_to_polars(dataframe)
        
        # RSI calculation (Standard 14 period)
        df_pl = add_rsi(df_pl, period=14, alias="rsi")
        
        dataframe = ohlcv_to_pandas(df_pl)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Define entry conditions: RSI < 30.
        """
        dataframe.loc[
            (
                (dataframe['rsi'] < 30) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
        
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Define exit conditions: RSI > 70 (Standard counter-signal).
        """
        dataframe.loc[
            (
                (dataframe['rsi'] > 70)
            ),
            'exit_long'] = 1
            
        return dataframe

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: str,
                            side: str, **kwargs) -> bool:
        """
        Custom confirmation layer integrating Sentiment and Risk checks.
        """
        
        # --- LAYER 1: RISK CHECKS ---
        try:
            # 1. Gather balance info
            total_balance = self.wallets.get_total_stake_amount()
            
            # 2. Fetch recent trades as list of dicts (Requirement)
            # Trade.get_trades_proxy returns trade objects
            all_recent_trades = Trade.get_trades_proxy(is_open=False)
            recent_trades_data = [
                {
                    'profit_ratio': t.close_profit,
                    'close_date': t.close_date
                } 
                for t in all_recent_trades
            ][:10]  # Take last 10 for analysis
            
            # 3. Count trades in the last hour
            one_hour_ago = current_time - timedelta(hours=1)
            trades_last_hour = len([
                t for t in all_recent_trades
                if t.close_date and t.close_date >= one_hour_ago
            ])
            
            # 4. Load balance baselines from state file
            state_file = Path('/Users/aatifquamre/cipher/risk/balance_state.json')
            if state_file.exists():
                with open(state_file) as f:
                    state = json.load(f)
                start_of_day = state.get('start_of_day', total_balance)
                start_of_week = state.get('start_of_week', total_balance)
            else:
                start_of_day = total_balance
                start_of_week = total_balance
            
            # 5. Execute all Risk Manager checks
            risk_result = run_all_checks(
                current_balance=total_balance,
                start_of_day_balance=start_of_day,
                start_of_week_balance=start_of_week,
                trade_amount_usdt=amount * rate,
                trades_last_hour=trades_last_hour,
                recent_trades=recent_trades_data
            )
            
            if not risk_result['safe_to_trade']:
                logger.warning(f"[RISK BLOCK] {pair} blocked. Reasons: {risk_result['blocking_reasons']}")
                return False
                
        except Exception as e:
            logger.error(f"[RISK ERROR] Failed to perform risk checks: {e}")
            # In case of system error, we fail-safe by blocking entry
            return False

        # --- LAYER 2: SENTIMENT CHECK ---
        sentiment_signal = get_sentiment_signal()
        
        if sentiment_signal == 'BEARISH':
            logger.info(f"[SENTIMENT BLOCK] {pair} entry blocked due to BEARISH market sentiment.")
            return False
            
        # If both layers pass
        logger.info(f"[ENTRY ALLOWED] {pair} passed all risk and sentiment gates.")
        return True
