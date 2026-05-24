import sys, os; home = os.path.expanduser('~'); sys.path.append(os.path.join(home, 'cipher')); sys.path.append(os.path.join(home, 'cipher', 'qnt', 'memory')); sys.path.append(os.path.join(home, 'cipher', 'qnt', 'oracle'));
import logging
import json
import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from pandas import DataFrame

from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade
import pandas as pd

# Add base directory to path for custom imports
home = os.path.expanduser("~")
sys.path.append(os.path.join(home, 'cipher'))
sys.path.append(os.path.join(home, 'cipher', 'qnt', 'memory'))
from risk.risk_manager import run_all_checks
from sentiment.reader import get_current_sentiment
from qnt.oracle.oracle_calendar import is_safe_to_trade_today
from qnt.oracle.hmm_regime import detect_regime, get_regime_for_strategy
from qnt.thesis.thesis_reader import read_thesis

logger = logging.getLogger(__name__)

def merge_macro_data(dataframe: DataFrame) -> DataFrame:
    """
    Injects macro covariates (DXY, Funding, OI) into the dataframe.
    Uses timestamp-based merging to prevent look-ahead bias.
    """
    try:
        history_file = Path('/Users/aatifquamre/cipher/risk/macro_history.json')
        if not history_file.exists():
            dataframe['dxy_24h_change'] = 0.0
            dataframe['btc_funding_rate'] = 0.0
            dataframe['btc_open_interest'] = 0.0
            return dataframe

        with open(history_file, 'r') as f:
            history = json.load(f)

        macro_df = pd.DataFrame(history)
        macro_df['date'] = pd.to_datetime(macro_df['timestamp'], format='ISO8601')
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

class DailyTrendV1(IStrategy):
    """
    Daily trend following strategy.
    Entry: Price > 50-day EMA + RSI cross above 45 + Vol expansion
    Exit: RSI > 70 or Price < 50-day EMA
    """
    INTERFACE_VERSION = 3
    
    timeframe = '1d'
    
    stoploss = -0.08
    
    minimal_roi = {
        "0": 0.08,
        "7": 0.05,
        "3": 0.03
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        import polars as pl
        from qnt.polars_ohlcv import pandas_to_polars, ohlcv_to_pandas
        from qnt.polars_indicators import add_ema, add_rsi, add_sma
        
        df_pl = pandas_to_polars(dataframe)
        
        df_pl = add_ema(df_pl, period=50, alias="ema_50")
        df_pl = add_rsi(df_pl, period=14, alias="rsi")
        df_pl = add_sma(df_pl, period=10, column="volume", alias="volume_avg")
        
        dataframe = ohlcv_to_pandas(df_pl)
        dataframe = merge_macro_data(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        sentiment = get_current_sentiment()
        
        # HMM Regime Check
        regime = detect_regime(dataframe, metadata['pair'])
        regime_ok = get_regime_for_strategy('DailyTrendV1', regime)

        dataframe.loc[
            (
                (dataframe['close'] > dataframe['ema_50']) &
                (dataframe['rsi'] > 45) & (dataframe['rsi'].shift(1) <= 45) &
                (dataframe['volume'] > dataframe['volume_avg']) &
                (sentiment['score'] >= -0.3) & # Not BEARISH
                (is_safe_to_trade_today()) &   # Calendar Gate
                (regime_ok)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['rsi'] > 70) |
                (dataframe['close'] < dataframe['ema_50'])
            ),
            'exit_long'] = 1
        return dataframe

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                           time_in_force: str, current_time: datetime, entry_tag: str,
                           side: str, **kwargs) -> bool:
        # --- LAYER 0: THESIS GATE ---
        thesis = read_thesis(pair)
        if thesis["bias"] == "SELL":
            logger.info(f"[THESIS BLOCK] {pair} bias=SELL confidence={thesis['confidence']:.2f} — {thesis['reasoning']}")
            return False
        stake_modifier = thesis.get("stake_modifier", 1.0)

        # --- LAYER 1: RISK & SENTIMENT CHECKS ---
        try:
            total_balance = self.wallets.get_total('USDT')
            
            # Fetch recent trades for loss counting
            recent_trades = [
                {
                    'profit_ratio': float(getattr(t, 'close_profit', None) or
                                         getattr(t, 'profit_ratio', None) or 0.0),
                    'close_date': getattr(t, 'close_date', None)
                }
                for t in Trade.get_trades_proxy(is_open=False)
            ][:10]
            
            # Count trades in the last hour
            one_hour_ago = current_time - timedelta(hours=1)
            trades_last_hour = len([
                t for t in Trade.get_trades_proxy(is_open=False)
                if t.close_date and t.close_date >= one_hour_ago
            ])
            
            # Load balance state for drawdown checks
            state_file = Path('/Users/aatifquamre/cipher/risk/balance_state.json')
            if state_file.exists():
                with open(state_file) as f:
                    state = json.load(f)
                start_of_day = state.get('start_of_day', total_balance)
                start_of_week = state.get('start_of_week', total_balance)
            else:
                start_of_day = total_balance
                start_of_week = total_balance
            
            # DailyTrendV1 requires at least NEUTRAL sentiment
            risk_result = run_all_checks(
                current_balance=total_balance,
                start_of_day_balance=start_of_day,
                start_of_week_balance=start_of_week,
                trade_amount_usdt=amount * rate * stake_modifier,
                trades_last_hour=trades_last_hour,
                recent_trades=recent_trades,
                min_sentiment='NEUTRAL'
            )
            
            if not risk_result['safe_to_trade']:
                logger.info(f"[RISK/SENTIMENT BLOCK] DailyTrend blocked for {pair}. Reasons: {risk_result['blocking_reasons']}")
                return False

            # Log sentiment for visibility
            sentiment = get_current_sentiment()
            logger.info(f"[Sentiment Check] {pair} | Score: {sentiment['score']:.3f}")

        except Exception as e:
            logger.error(f"[RISK WARNING] Risk check error: {e}")
            
        return True
