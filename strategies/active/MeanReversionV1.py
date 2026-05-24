import sys, os; home = os.path.expanduser('~'); sys.path.append(os.path.join(home, 'cipher')); sys.path.append(os.path.join(home, 'cipher', 'qnt', 'memory')); sys.path.append(os.path.join(home, 'cipher', 'qnt', 'oracle'));
import logging
import json
import sys
import os
from pathlib import Path
from datetime import timedelta, datetime
from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from freqtrade.persistence import Trade
import pandas as pd

# Add base directory to path for custom imports
sys.path.insert(0, '/Users/aatifquamre/cipher')
from risk.risk_manager import run_all_checks
from risk.stake_sizer import get_stake_multiplier
from risk.correlation_guard import is_blocked as corr_blocked
from sentiment.reader import get_current_sentiment, get_sentiment_signal, get_funding_rate
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

    def load_dynamic_params(self):
        # Default fallback values
        self.buy_rsi_val = self.buy_rsi.value
        self.bb_period_val = self.bb_period.value
        self.bb_std_val = self.bb_std.value
        self.sell_rsi_val = self.sell_rsi.value

        try:
            path1 = Path('/Users/aatifquamre/cipher/config/dynamic_params.json')
            path2 = Path('/Users/aatifquamre/Downloads/Aatif-qmr/cipher/config/dynamic_params.json')
            path = path1 if path1.exists() else path2
            
            if path.exists():
                with open(path, 'r') as f:
                    params = json.load(f)
                
                strat_name = self.__class__.__name__
                strat_params = params.get(strat_name, params)
                
                if 'buy_rsi' in strat_params:
                    self.buy_rsi_val = int(strat_params['buy_rsi'])
                if 'bb_period' in strat_params:
                    self.bb_period_val = int(strat_params['bb_period'])
                if 'bb_std' in strat_params:
                    self.bb_std_val = float(strat_params['bb_std'])
                if 'sell_rsi' in strat_params:
                    self.sell_rsi_val = int(strat_params['sell_rsi'])
                
                logger.info(f"[{strat_name}] Dynamically loaded parameters: buy_rsi={self.buy_rsi_val}, bb_period={self.bb_period_val}, bb_std={self.bb_std_val}, sell_rsi={self.sell_rsi_val}")
        except Exception as e:
            logger.warning(f"Failed to load dynamic parameters, using defaults: {e}")

    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int,
                                     metadata: dict, **kwargs) -> DataFrame:
        # Standard indicators for the model
        dataframe["%-rsi-period"] = ta.rsi(dataframe["close"], length=period) / 100
        dataframe["%-bb_lower-period"] = dataframe["close"] / dataframe["bb_lower"]
        
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
        # Load dynamic parameters first
        self.load_dynamic_params()
        
        import polars as pl
        from qnt.polars_ohlcv import pandas_to_polars, ohlcv_to_pandas
        from qnt.polars_indicators import add_rsi, add_bollinger_bands, add_atr
        
        df_pl = pandas_to_polars(dataframe)

        # Standard Indicators with optimized params
        df_pl = add_rsi(df_pl, period=14, alias="rsi")
        df_pl = add_bollinger_bands(df_pl, period=self.bb_period_val, std_dev=self.bb_std_val, prefix="bb")
        df_pl = df_pl.rename({"bb_mid": "bb_middle"})
        df_pl = add_atr(df_pl, period=14, alias="atr")

        dataframe = ohlcv_to_pandas(df_pl)
        dataframe = merge_macro_data(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self.load_dynamic_params()

        is_live = self.config.get('runmode', {}).value in ('live', 'dry_run')
        regime_ok = True
        if is_live:
            regime = detect_regime(dataframe, metadata['pair'])
            regime_ok = get_regime_for_strategy('MeanReversionV1', regime)

        dataframe.loc[
            (
                (dataframe['rsi'] < self.buy_rsi_val) &
                (dataframe['close'] < dataframe['bb_lower']) &
                (regime_ok)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self.load_dynamic_params()

        raw_exit = (dataframe['rsi'] > self.sell_rsi_val)
        # Require signal on 2 consecutive candles — prevents RSI spikes exiting at a loss
        dataframe.loc[raw_exit & raw_exit.shift(1).fillna(False), 'exit_long'] = 1
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
            logger.info(f"[PARTIAL EXIT] MeanReversionV1 {trade.pair} profit={current_profit:.2%} — exiting 50%")
            return -(trade.stake_amount * 0.5)
        return None

    def custom_stoploss(self, pair: str, trade, current_time: datetime,
                       current_rate: float, current_profit: float, after_fill: bool,
                       **kwargs) -> float:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty or 'atr' not in dataframe.columns:
            return self.stoploss
        atr = dataframe['atr'].iloc[-1]
        if atr and current_rate:
            # 2× ATR below entry, capped at -6% and floored at -2%
            atr_stop = -(2 * atr) / trade.open_rate
            return max(-0.06, min(-0.02, atr_stop))
        return self.stoploss

    def custom_exit(self, pair: str, trade, current_time: datetime,
                   current_rate: float, current_profit: float, **kwargs):
        hours_open = (current_time - trade.open_date_utc).total_seconds() / 3600

        # Cut losses after 48 hours if still negative
        if hours_open >= 48 and current_profit < -0.01:
            return 'time_stop_48h'

        # In BEAR regime, take profits quickly — bounces don't last on 1h
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if dataframe is not None and not dataframe.empty:
                regime = detect_regime(dataframe, pair)
                if regime == 'BEAR' and current_profit >= 0.015 and hours_open >= 2:
                    return 'bear_bounce_target'
        except Exception:
            pass

        return None

    def custom_stake_amount(self, current_time, current_rate, proposed_stake,
                           min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        multiplier = get_stake_multiplier('MeanReversionV1')
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
            
            # MeanReversionV1 requires at least NEUTRAL sentiment
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
                logger.info(f"[RISK/SENTIMENT BLOCK] MeanReversion blocked for {pair}. Reasons: {risk_result['blocking_reasons']}")
                return False

            # Log sentiment for visibility
            sentiment = get_current_sentiment()
            signal = get_sentiment_signal()
            logger.info(f"[Sentiment Check] {pair} | Score: {sentiment['score']:.3f} | Signal: {signal}")

            # --- LAYER 2: SKEPTIC AGENT (final gate) ---
            try:
                import sys
                sys.path.insert(0, '/Users/aatifquamre/cipher/qnt/agents')
                from trade_gate import evaluate_trade
                from strategist import summarize_signal
                
                # Get analyzed dataframe
                dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
                
                signal_summary = summarize_signal(dataframe, 'MeanReversionV1', pair)
                
                gate_result = evaluate_trade({
                    **signal_summary,
                    'sentiment_score': sentiment['score'],
                    'hmm_regime': detect_regime(dataframe),
                    'stake_amount': amount * rate,
                })
                
                if gate_result['decision'] == 'BLOCK':
                    logger.info(
                        f"[SKEPTIC BLOCK] {pair} "
                        f"Confidence: {gate_result['failure_confidence']:.0%} "
                        f"Reason: {gate_result['primary_concern']}"
                    )
                    return False
                else:
                    logger.info(f"[SKEPTIC ALLOW] {pair} | Proceeding with trade.")
            except Exception as e:
                logger.error(f"[SKEPTIC ERROR] {e} — proceeding")

        except Exception as e:
            logger.error(f"[RISK WARNING] Risk check error: {e}")

        base = pair.split('/')[0]
        if corr_blocked(base, side):
            logger.info(f"[CORR BLOCK] MeanReversionV1 {pair} — too many concurrent longs on {base}")
            return False

        if side == 'long':
            funding = get_funding_rate()
            if funding < -0.5:
                logger.info(f"[FUNDING BLOCK] MeanReversionV1 {pair} funding={funding:.2f} — extreme negative funding")
                return False

        return True
