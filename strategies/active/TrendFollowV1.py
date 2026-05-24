import sys, os; home = os.path.expanduser('~'); sys.path.append(os.path.join(home, 'cipher')); sys.path.append(os.path.join(home, 'cipher', 'qnt', 'memory')); sys.path.append(os.path.join(home, 'cipher', 'qnt', 'oracle'));
import logging
import json
import sys
import os
from pathlib import Path
from datetime import timedelta, datetime
from pandas import DataFrame
import freqtrade.vendor.qtpylib.indicators as qtpylib

from freqtrade.strategy import IStrategy, IntParameter
from freqtrade.persistence import Trade

# Add base directory to path for custom imports
sys.path.insert(0, '/Users/aatifquamre/cipher')
from risk.risk_manager import run_all_checks
from risk.stake_sizer import get_stake_multiplier
from risk.correlation_guard import is_blocked as corr_blocked
from sentiment.reader import get_current_sentiment, get_sentiment_signal, get_funding_rate
import pandas as pd
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

class TrendFollowV1(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '4h'
    
    # Parameters
    buy_rsi_min = IntParameter(30, 50, default=40, space='buy')
    buy_rsi_max = IntParameter(60, 80, default=80, space='buy')
    sell_rsi_limit = IntParameter(70, 90, default=75, space='sell')

    minimal_roi = {"0": 0.03}
    stoploss = -0.06

    def load_dynamic_params(self):
        self.buy_rsi_min_val = self.buy_rsi_min.value if hasattr(self.buy_rsi_min, 'value') else self.buy_rsi_min
        self.buy_rsi_max_val = self.buy_rsi_max.value if hasattr(self.buy_rsi_max, 'value') else self.buy_rsi_max
        self.sell_rsi_limit_val = self.sell_rsi_limit.value if hasattr(self.sell_rsi_limit, 'value') else self.sell_rsi_limit
        try:
            import json
            from pathlib import Path
            p = Path('/Users/aatifquamre/cipher/config/dynamic_params.json')
            if p.exists():
                sp = json.loads(p.read_text()).get('TrendFollowV1', {})
                if 'buy_rsi_min' in sp:
                    self.buy_rsi_min_val = int(sp['buy_rsi_min'])
                if 'buy_rsi_max' in sp:
                    self.buy_rsi_max_val = int(sp['buy_rsi_max'])
                if 'sell_rsi_limit' in sp:
                    self.sell_rsi_limit_val = int(sp['sell_rsi_limit'])
        except Exception:
            pass
    stoploss_on_exchange = True
    stoploss_on_exchange_interval = 60

    # Startup candles
    startup_candle_count: int = 50

    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int,
                                     metadata: dict, **kwargs) -> DataFrame:
        # Standard indicators for the model
        dataframe["%-rsi-period"] = ta.rsi(dataframe["close"], length=period) / 100
        dataframe["%-ema_9-period"] = ta.ema(dataframe["close"], length=9) / dataframe["close"]
        
        # External signal features
        import json
        try:
            CIPHER_PATH = '/Users/aatifquamre/cipher'
            with open(f'{CIPHER_PATH}/sentiment/scores/current_score.json') as f:
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
        import polars as pl
        from qnt.polars_ohlcv import pandas_to_polars, ohlcv_to_pandas
        from qnt.polars_indicators import add_ema, add_macd, add_rsi
        
        if 'ema_fast' not in dataframe.columns:
            df_pl = pandas_to_polars(dataframe)
            
            df_pl = add_ema(df_pl, period=20, alias="ema_fast")
            df_pl = add_ema(df_pl, period=50, alias="ema_slow")
            df_pl = add_macd(df_pl, fast=12, slow=26, signal=9, prefix="macd")
            df_pl = add_rsi(df_pl, period=14, alias="rsi")
            
            dataframe = ohlcv_to_pandas(df_pl)
            
        dataframe = merge_macro_data(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self.load_dynamic_params()
        regime = detect_regime(dataframe, metadata['pair'])
        regime_ok = get_regime_for_strategy('TrendFollowV1', regime)

        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe['ema_fast'], dataframe['ema_slow'])) &
                (dataframe['macd_hist'] > 0) &
                (regime_ok) &
                (dataframe['rsi'] > self.buy_rsi_min_val) &
                (dataframe['rsi'] < self.buy_rsi_max_val)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self.load_dynamic_params()
        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe['ema_fast'], dataframe['ema_slow'])) |
                (dataframe['rsi'] > self.sell_rsi_limit_val)
            ),
            'exit_long'] = 1
        return dataframe

    def adjust_trade_position(self, trade, current_time: datetime, current_rate: float,
                             current_profit: float, min_stake, max_stake,
                             current_entry_rate: float, current_exit_rate: float,
                             current_entry_profit: float, current_exit_profit: float,
                             **kwargs):
        if trade.id in _partial_exits_done:
            return None
        if current_profit >= 0.015:
            _partial_exits_done.add(trade.id)
            logger.info(f"[PARTIAL EXIT] TrendFollowV1 {trade.pair} profit={current_profit:.2%} — exiting 50%")
            return -(trade.stake_amount * 0.5)
        return None

    def custom_stake_amount(self, current_time, current_rate, proposed_stake,
                           min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        multiplier = get_stake_multiplier('TrendFollowV1')
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
            
            # Fetch recent trades
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
            
            # Load balance state
            state_file = Path('/Users/aatifquamre/cipher/risk/balance_state.json')
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
                trade_amount_usdt=amount * rate * stake_modifier,
                trades_last_hour=trades_last_hour,
                recent_trades=recent_trades,
                min_sentiment='NEUTRAL'
            )
            
            if not risk_result['safe_to_trade']:
                logger.info(f"[RISK/SENTIMENT BLOCK] TrendFollow blocked for {pair}. Reasons: {risk_result['blocking_reasons']}")
                return False

            # Log sentiment for visibility
            sentiment = get_current_sentiment()
            signal = get_sentiment_signal()
            logger.info(f"[Sentiment Check] {pair} | Score: {sentiment['score']:.3f} | Signal: {signal}")

        except Exception as e:
            logger.error(f"[RISK WARNING] Risk check error: {e}")

        base = pair.split('/')[0]
        if corr_blocked(base, side):
            logger.info(f"[CORR BLOCK] TrendFollowV1 {pair} — too many concurrent longs on {base}")
            return False

        if side == 'long':
            funding = get_funding_rate()
            if funding < -0.5:
                logger.info(f"[FUNDING BLOCK] TrendFollowV1 {pair} funding={funding:.2f} — extreme negative funding")
                return False

        return True
