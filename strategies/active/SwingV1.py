import sys, os; home = os.path.expanduser('~'); sys.path.append(os.path.join(home, 'cipher')); sys.path.append(os.path.join(home, 'cipher', 'qnt', 'memory')); sys.path.append(os.path.join(home, 'cipher', 'qnt', 'oracle'));
import logging
import json
import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from pandas import DataFrame

from freqtrade.strategy import IStrategy, merge_informative_pair
from freqtrade.persistence import Trade
import pandas as pd

# Add base directory to path for custom imports
home = os.path.expanduser("~")
sys.path.append(os.path.join(home, 'cipher'))
from risk.risk_manager import run_all_checks
from risk.stake_sizer import get_stake_multiplier
from risk.correlation_guard import is_blocked as corr_blocked
from sentiment.reader import get_current_sentiment, get_funding_rate
from qnt.oracle.hmm_regime import detect_regime, get_regime_for_strategy
from qnt.thesis.thesis_reader import read_thesis

logger = logging.getLogger(__name__)

_partial_exits_done: set = set()

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

class SwingV1(IStrategy):
    """
    15-minute swing strategy.
    Entry: EMA 9 > EMA 21 + RSI 40-60
    Exit: EMA 9 < EMA 21 or Trailing Stop
    """
    INTERFACE_VERSION = 3
    
    timeframe = '15m'
    informative_timeframes = ['1h']
    
    stoploss = -0.03
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.02   # activate trailing only after 2% profit locked

    # R:R fixed: target 5% → 3% → 2% — never smaller than the 3% stoploss risk
    minimal_roi = {
        "0":   0.05,
        "120": 0.03,
        "300": 0.02,
        "600": 0.01,
    }

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [(pair, '1h') for pair in pairs]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        import polars as pl
        from qnt.polars_ohlcv import pandas_to_polars, ohlcv_to_pandas
        from qnt.polars_indicators import add_ema, add_rsi, add_sma
        
        df_pl = pandas_to_polars(dataframe)

        # 15m Indicators
        df_pl = add_ema(df_pl, period=9, alias="ema_9")
        df_pl = add_ema(df_pl, period=21, alias="ema_21")
        df_pl = add_rsi(df_pl, period=14, alias="rsi")
        df_pl = add_sma(df_pl, period=20, column="volume", alias="volume_ma")

        # 1h Informative
        if getattr(self, 'config', {}).get('runmode', {}).value in ('live', 'dry_run'):
            inf_df_pd = self.dp.get_pair_dataframe(metadata['pair'], '1h')
            if inf_df_pd is not None and not inf_df_pd.empty:
                inf_df_pl = pandas_to_polars(inf_df_pd)
                inf_df_pl = add_ema(inf_df_pl, period=50, alias="ema_50")
                inf_df_pd = ohlcv_to_pandas(inf_df_pl)
                
            dataframe = merge_informative_pair(ohlcv_to_pandas(df_pl), inf_df_pd, self.timeframe, '1h', ffill=True)
            df_pl = pandas_to_polars(dataframe)

        dataframe = ohlcv_to_pandas(df_pl)
        dataframe = merge_macro_data(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        is_live = self.config.get('runmode', {}).value in ('live', 'dry_run')

        sentiment_ok = True
        regime_ok = True
        if is_live:
            sentiment = get_current_sentiment()
            sentiment_ok = sentiment['score'] >= -0.3
            regime = detect_regime(dataframe, metadata['pair'])
            regime_ok = get_regime_for_strategy('SwingV1', regime)

        ema_50_1h = dataframe.get('ema_50_1h', dataframe['close'])

        dataframe.loc[
            (
                (dataframe['ema_9'] > dataframe['ema_21']) &
                (dataframe['ema_9'].shift(1) > dataframe['ema_21'].shift(1)) &
                (dataframe['ema_9'].shift(2) <= dataframe['ema_21'].shift(2)) &
                (dataframe['rsi'] >= 45) & (dataframe['rsi'] <= 65) &
                (dataframe['rsi'] > dataframe['rsi'].shift(1)) &
                (dataframe['volume'] > dataframe['volume_ma'] * 1.1) &
                (dataframe['close'] > ema_50_1h) &
                (sentiment_ok) &
                (regime_ok)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Require EMA9 < EMA21 for 2 consecutive candles — sustained reversal, not a single-candle wick
        dataframe.loc[
            (dataframe['ema_9'] < dataframe['ema_21']) &
            (dataframe['ema_9'].shift(1) < dataframe['ema_21'].shift(1)),
            'exit_long'] = 1
        return dataframe

    def adjust_trade_position(self, trade, current_time: datetime, current_rate: float,
                             current_profit: float, min_stake, max_stake,
                             current_entry_rate: float, current_exit_rate: float,
                             current_entry_profit: float, current_exit_profit: float,
                             **kwargs):
        if trade.id in _partial_exits_done:
            return None
        if current_profit >= 0.025:
            _partial_exits_done.add(trade.id)
            logger.info(f"[PARTIAL EXIT] SwingV1 {trade.pair} profit={current_profit:.2%} — exiting 50%")
            return -(trade.stake_amount * 0.5)
        return None

    def custom_exit(self, pair: str, trade, current_time: datetime,
                   current_rate: float, current_profit: float, **kwargs):
        # Cut losses after 24 hours if still negative — prevents week-long trapped positions
        hours_open = (current_time - trade.open_date_utc).total_seconds() / 3600
        if hours_open >= 24 and current_profit < -0.005:
            return 'time_stop_24h'
        return None

    def custom_stake_amount(self, current_time, current_rate, proposed_stake,
                           min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        multiplier = get_stake_multiplier('SwingV1')
        stake = proposed_stake * multiplier
        if min_stake is not None:
            stake = max(stake, min_stake)
        return min(stake, max_stake)

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                           time_in_force: str, current_time: datetime, entry_tag: str,
                           side: str, **kwargs) -> bool:
        if self.config.get('runmode', {}).value not in ('live', 'dry_run'):
            return True

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
            
            # SwingV1 requires at least NEUTRAL sentiment
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
                logger.info(f"[RISK/SENTIMENT BLOCK] Swing blocked for {pair}. Reasons: {risk_result['blocking_reasons']}")
                return False

            # Log sentiment for visibility
            sentiment = get_current_sentiment()
            logger.info(f"[Sentiment Check] {pair} | Score: {sentiment['score']:.3f}")

        except Exception as e:
            logger.error(f"[RISK WARNING] Risk check error: {e}")

        base = pair.split('/')[0]
        if corr_blocked(base, side):
            logger.info(f"[CORR BLOCK] SwingV1 {pair} — too many concurrent longs on {base}")
            return False

        if side == 'long':
            funding = get_funding_rate()
            if funding < -0.5:
                logger.info(f"[FUNDING BLOCK] SwingV1 {pair} funding={funding:.2f} — extreme negative funding")
                return False

        return True
