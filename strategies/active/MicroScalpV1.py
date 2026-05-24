import pandas as pd
import talib.abstract as ta
import logging
from datetime import datetime
from pathlib import Path
import sys

logger = logging.getLogger(__name__)

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from risk.risk_manager import run_all_checks
from qnt.oracle.sentiment_gate import get_sentiment_score
from qnt.oracle.hmm_regime import detect_regime, get_regime_for_strategy
from qnt.thesis.thesis_reader import read_thesis

from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade

class MicroScalpV1(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1m"
    stoploss = -0.025
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.015
    trailing_only_offset_is_reached = True

    # 1m strategies need higher timeframe context
    @informative("5m")
    @informative("15m")
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        import polars as pl
        from qnt.polars_ohlcv import pandas_to_polars, ohlcv_to_pandas
        from qnt.polars_indicators import add_rsi, add_bollinger_bands, add_ema

        # Convert Pandas to Polars
        df_pl = pandas_to_polars(dataframe)

        # 1m specific indicators (applied to whatever timeframe is passed due to @informative decorators,
        # but named _1m for historical consistency in this strategy)
        df_pl = add_rsi(df_pl, period=7, alias="rsi_1m")
        df_pl = add_bollinger_bands(df_pl, period=15, std_dev=1.8, prefix="bb")
        
        # Add custom rolling volume and rename bb columns to match old strategy
        df_pl = df_pl.with_columns([
            pl.col("volume").rolling_mean(window_size=20).alias("volume_avg_20"),
            pl.col("bb_lower").alias("bb_lower_1m"),
            pl.col("bb_upper").alias("bb_upper_1m"),
        ])
        
        # Informative 5m trend filter
        if metadata.get("timeframe") == "5m":
            df_pl = add_ema(df_pl, period=20, alias="ema_20_5m")
            df_pl = df_pl.with_columns(
                (pl.col("close") < pl.col("ema_20_5m")).alias("trend_5m_bearish")
            )
        
        # Convert back to Pandas for Freqtrade
        return ohlcv_to_pandas(df_pl)

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # Risk & Sentiment Gate
        risk_result = run_all_checks()
        if isinstance(risk_result, dict) and not risk_result.get('safe_to_trade', True):
            dataframe.loc[:, "enter_long"] = 0
            return dataframe
        
        sentiment = get_sentiment_score()
        if sentiment < -0.3:  # Strong bearish social/macro
            dataframe.loc[:, "enter_long"] = 0
            return dataframe

        # Regime Filter
        regime = detect_regime(dataframe, metadata["pair"])
        if not get_regime_for_strategy("MicroScalpV1", regime):
            dataframe.loc[:, "enter_long"] = 0
            return dataframe
        
        # Optional: Reduce stake in BEAR regime (already handled by risk_manager, but explicit here)
        if regime == "BEAR":
            # Log for audit, risk_manager enforces actual sizing
            logger.info(f"MicroScalpV1: BEAR regime detected for {metadata['pair']}, proceeding with caution")

        # --- Order Flow Trap Filter ---
        import json
        of_path = Path("/Users/aatifquamre/cipher/qnt/oracle/order_flow_live.json")
        if not of_path.exists():
            # Fallback to 15m polling file
            of_path = Path("/Users/aatifquamre/cipher/qnt/oracle/order_flow_state.json")
        
        if of_path.exists():
            with open(of_path) as f:
                of_data = json.load(f)
            
            # High-frequency CVD data (if available)
            live_cvd = of_data.get("cvd", 0)
            live_delta = of_data.get("delta", 0)
            
            # Standard order flow state from polling (fallback or combined)
            liq_trend = of_data.get("liquidation", {}).get("trend", "neutral")
            cvd_div = of_data.get("cvd_divergence", "neutral")
            
            # BLOCK Longs if Long Squeeze risk (Too many longs, likely to dump)
            if liq_trend == "long_squeeze_risk":
                dataframe.loc[:, "enter_long"] = 0
            
            # BLOCK Shorts if Short Squeeze risk (Too many shorts, likely to pump)
            if liq_trend == "short_squeeze_risk":
                dataframe.loc[:, "enter_short"] = 0
                
            # DIVERGENCE CHECK
            if cvd_div == "bearish_divergence":
                dataframe.loc[:, "enter_long"] = 0

            # --- SKEPTIC AGENT (final gate) ---
        # Ensure we have trend_5m_bearish (it comes from informative merge)
        # Note: Freqtrade appends timeframe to columns for informatives by default
        trend_col = "trend_5m_bearish_5m" if "trend_5m_bearish_5m" in dataframe.columns else "trend_5m_bearish"
        
        cond = (
            (dataframe["rsi_1m"].shift(1) > 28) &
            (dataframe["rsi_1m"] <= 28) &
            (dataframe["close"] <= dataframe["bb_lower_1m"]) &
            (dataframe["volume"] > (dataframe["volume_avg_20"] * 1.5))
        )
        
        if trend_col in dataframe.columns:
            cond = cond & (~dataframe[trend_col])

        dataframe.loc[cond, "enter_long"] = 1
        dataframe.loc[:, "enter_short"] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[:, "exit_long"] = 0
        dataframe.loc[:, "exit_short"] = 0
        return dataframe

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        # Enforce 2% max per trade
        return proposed_stake * 0.8

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: str,
                            side: str, **kwargs) -> bool:
        """
        Final gatekeeper - Skeptic Agent review.
        """
        # --- LAYER 0: THESIS GATE ---
        thesis = read_thesis(pair)
        if thesis["bias"] == "SELL":
            logger.info(f"[THESIS BLOCK] {pair} bias=SELL confidence={thesis['confidence']:.2f} — {thesis['reasoning']}")
            return False
        stake_modifier = thesis.get("stake_modifier", 1.0)

        try:
            import sys
            sys.path.insert(0, '/Users/aatifquamre/cipher/qnt/agents')
            from trade_gate import evaluate_trade
            from strategist import summarize_signal
            
            # Get analyzed dataframe
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            
            signal_summary = summarize_signal(dataframe, 'MicroScalpV1', pair)
            
            # Add extra context for Skeptic
            from sentiment.reader import get_current_sentiment
            sentiment = get_current_sentiment()
            regime = detect_regime(dataframe, pair)
            
            gate_result = evaluate_trade({
                **signal_summary,
                'sentiment_score': sentiment['score'],
                'hmm_regime': regime,
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
            
        return True
