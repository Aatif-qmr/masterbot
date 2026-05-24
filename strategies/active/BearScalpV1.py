import sys, os; home = os.path.expanduser('~'); sys.path.append(os.path.join(home, 'cipher')); sys.path.append(os.path.join(home, 'cipher', 'qnt', 'memory')); sys.path.append(os.path.join(home, 'cipher', 'qnt', 'oracle'))
import logging
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from pandas import DataFrame
import pandas as pd

from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade

home = os.path.expanduser("~")
sys.path.append(os.path.join(home, 'cipher'))
from risk.risk_manager import run_all_checks
from risk.stake_sizer import get_stake_multiplier
from sentiment.reader import get_current_sentiment
from qnt.oracle.hmm_regime import detect_regime
from qnt.thesis.thesis_reader import read_thesis

logger = logging.getLogger(__name__)


class BearScalpV1(IStrategy):
    """
    Short-only scalp strategy. Activates exclusively when HMM detects BEAR regime.
    Entry: RSI > 70 + close > BB_upper + BEAR regime confirmed.
    Exit: RSI < 50 OR close < BB_middle (2-candle persistence).
    Complements ScalpV1 (long) to exploit both sides of the market.
    """
    INTERFACE_VERSION = 3
    can_short = True

    timeframe = '5m'
    stoploss = -0.02
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.015

    minimal_roi = {
        "0":   0.02,
        "30":  0.015,
        "60":  0.01,
        "120": 0.005,
    }

    startup_candle_count: int = 30

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        import polars as pl
        from qnt.polars_ohlcv import pandas_to_polars, ohlcv_to_pandas
        from qnt.polars_indicators import add_rsi, add_bollinger_bands, add_sma
        
        df_pl = pandas_to_polars(dataframe)
        
        df_pl = add_rsi(df_pl, period=14, alias="rsi")
        df_pl = add_bollinger_bands(df_pl, period=20, std_dev=2.0, prefix="bb")
        df_pl = df_pl.rename({"bb_mid": "bb_middle"})
        df_pl = add_sma(df_pl, period=20, column="volume", alias="volume_avg")
        
        dataframe = ohlcv_to_pandas(df_pl)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        sentiment = get_current_sentiment()
        regime    = detect_regime(dataframe, metadata['pair'])

        # Only short in confirmed BEAR regime
        bear_confirmed = (regime == 'BEAR')

        dataframe.loc[
            (
                bear_confirmed &
                (dataframe['rsi'] > 70) &
                (dataframe['close'] > dataframe['bb_upper']) &
                (dataframe['volume'] > dataframe['volume_avg']) &
                (sentiment['score'] <= 0.3)  # not strongly bullish
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        raw_exit = (
            (dataframe['rsi'] < 50) |
            (dataframe['close'] < dataframe['bb_middle'])
        )
        # 2-candle persistence — same whipsaw protection as long strategies
        dataframe.loc[raw_exit & raw_exit.shift(1).fillna(False), 'exit_short'] = 1
        return dataframe

    def custom_stake_amount(self, current_time, current_rate, proposed_stake,
                           min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        multiplier = get_stake_multiplier('BearScalpV1')
        stake = proposed_stake * multiplier
        if min_stake is not None:
            stake = max(stake, min_stake)
        return min(stake, max_stake)

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                           time_in_force: str, current_time: datetime, entry_tag: str,
                           side: str, **kwargs) -> bool:
        # Block longs — this strategy is short-only
        if side != 'short':
            return False

        thesis = read_thesis(pair)
        if thesis.get('bias') == 'BUY':
            logger.info(f"[BEAR_SCALP BLOCK] {pair} thesis=BUY — not shorting into bullish thesis")
            return False

        try:
            total_balance = self.wallets.get_total('USDT')
            state_file = Path(f'{home}/cipher/risk/balance_state.json')
            state = json.loads(state_file.read_text()) if state_file.exists() else {}
            risk_result = run_all_checks(
                current_balance=total_balance,
                start_of_day_balance=state.get('start_of_day', total_balance),
                start_of_week_balance=state.get('start_of_week', total_balance),
                trade_amount_usdt=amount * rate,
                trades_last_hour=0,
                recent_trades=[],
                min_sentiment='NEUTRAL',
            )
            if not risk_result['safe_to_trade']:
                return False
        except Exception as e:
            logger.warning(f"[BEAR_SCALP] Risk check error: {e}")

        return True
