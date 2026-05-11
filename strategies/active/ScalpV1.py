import sys, os; home = os.path.expanduser('~'); sys.path.append(os.path.join(home, 'masterbot')); sys.path.append(os.path.join(home, 'masterbot', 'qnt', 'memory')); sys.path.append(os.path.join(home, 'masterbot', 'qnt', 'oracle'));
import logging
import json
import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from pandas import DataFrame
import pandas_ta as ta
import numpy as np

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, merge_informative_pair
from freqtrade.persistence import Trade
import pandas as pd

# Add base directory to path for custom imports
home = os.path.expanduser("~")
sys.path.append(os.path.join(home, 'masterbot'))
from risk.risk_manager import run_all_checks
from sentiment.reader import get_current_sentiment, get_sentiment_signal
from qnt.oracle.hmm_regime import detect_regime, get_regime_for_strategy

logger = logging.getLogger(__name__)

def merge_macro_data(dataframe: pd.DataFrame) -> pd.DataFrame:
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

        import json
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

class ScalpV1(IStrategy):
    """
    5-minute scalping strategy.
    Entry: RSI < 30 + Price < Lower BB + Vol > Avg Vol
    Exit: RSI > 60 or Price > Mid BB
    Includes multi-timeframe confirmation (15m RSI, 1h EMA).
    """
    INTERFACE_VERSION = 3
    
    timeframe = '5m'
    informative_timeframes = ['15m', '1h']
    
    stoploss = -0.02
    trailing_stop = True
    
    minimal_roi = {
        "0": 0.015,
        "30": 0.01,
        "15": 0.005
    }

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        informative_pairs = []
        for timeframe in self.informative_timeframes:
            for pair in pairs:
                informative_pairs.append((pair, timeframe))
        return informative_pairs

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 5m Indicators
        dataframe['rsi'] = ta.rsi(dataframe['close'], length=14)
        bb = ta.bbands(dataframe['close'], length=20, std=2)
        dataframe['bb_lower'] = bb['BBL_20_2.0']
        dataframe['bb_middle'] = bb['BBM_20_2.0']
        dataframe['volume_avg'] = ta.sma(dataframe['volume'], length=20)

        # Informative timeframes
        if self.config['runmode'].value in ('live', 'dry_run'):
            for tf in self.informative_timeframes:
                inf_df = self.dp.get_pair_dataframe(metadata['pair'], tf)
                
                if tf == '15m':
                    inf_df['rsi'] = ta.rsi(inf_df['close'], length=14)
                elif tf == '1h':
                    inf_df['ema_200'] = ta.ema(inf_df['close'], length=200)
                
                dataframe = merge_informative_pair(dataframe, inf_df, self.timeframe, tf, ffill=True)

        dataframe = merge_macro_data(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Sentiment Gate (Current)
        sentiment = get_current_sentiment()
        
        # HMM Regime Check
        regime_data = detect_regime(dataframe)
        regime_ok = get_regime_for_strategy(dataframe, 'scalp')
        confidence_ok = regime_data['confidence'] >= 0.6

        dataframe.loc[
            (
                (dataframe['rsi'] < 30) &
                (dataframe['close'] < dataframe['bb_lower']) &
                (dataframe['volume'] > dataframe['volume_avg']) &
                # HTF Context (if available)
                (dataframe.get('rsi_15m', 50) < 60) & # Not overbought on 15m
                (dataframe.get('close', 0) > dataframe.get('ema_200_1h', 0)) & # Above 200 EMA on 1h
                (sentiment['score'] >= -0.3) & # Global Gate
                (regime_ok) &
                (confidence_ok)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['rsi'] > 60) |
                (dataframe['close'] > dataframe['bb_middle'])
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
            
            # ScalpV1 requires at least NEUTRAL sentiment
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
                logger.info(f"[RISK/SENTIMENT BLOCK] Scalp blocked for {pair}. Reasons: {risk_result['blocking_reasons']}")
                return False

            # Log sentiment for visibility
            sentiment = get_current_sentiment()
            signal = get_sentiment_signal()
            logger.info(f"[Sentiment Check] {pair} | Score: {sentiment['score']:.3f} | Signal: {signal}")

            # --- LAYER 2: SKEPTIC AGENT (final gate) ---
            try:
                import sys
                sys.path.insert(0, '/Users/aatifquamre/masterbot/qnt/agents')
                from trade_gate import evaluate_trade
                from strategist import summarize_signal
                
                # Get analyzed dataframe
                dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
                
                signal_summary = summarize_signal(dataframe, 'ScalpV1', pair)
                
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
            
        return True
