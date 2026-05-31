import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from pandas import DataFrame

# Resolve project root from this file's location (works on any machine)
_BASE = Path(__file__).resolve().parent.parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))

from freqtrade.persistence import Trade
from freqtrade.strategy import IntParameter, IStrategy, merge_informative_pair

from indicators.macro_merge import merge_macro_data
from qnt.oracle.hmm_regime import detect_regime, get_regime_for_strategy
from qnt.thesis.thesis_reader import read_thesis
from risk.correlation_guard import is_blocked as corr_blocked
from risk.risk_manager import run_all_checks
from risk.stake_sizer import get_stake_multiplier
from sentiment.reader import get_current_sentiment, get_funding_rate, get_sentiment_signal

logger = logging.getLogger(__name__)

_partial_exits_done: set = set()  # trade IDs that already had 50% exit


class ScalpV1(IStrategy):
    """
    5-minute scalping strategy.
    Entry: RSI < 30 + Price < Lower BB + Vol > Avg Vol
    Exit: RSI > 60 or Price > Mid BB
    Includes multi-timeframe confirmation (15m RSI, 1h EMA).
    """

    INTERFACE_VERSION = 3

    timeframe = "5m"
    informative_timeframes = ["15m", "1h"]

    stoploss = -0.02
    trailing_stop = True

    # R:R fixed: first target equals stoploss (1:1), then decreases to exit slow trades
    minimal_roi = {
        "0": 0.02,
        "30": 0.015,
        "60": 0.01,
        "120": 0.005,
    }

    # Hyperoptable / Dynamic parameters
    buy_rsi = IntParameter(20, 40, default=30, space="buy")
    sell_rsi = IntParameter(60, 80, default=60, space="sell")

    def load_dynamic_params(self):
        self.buy_rsi_val = self.buy_rsi.value
        self.sell_rsi_val = self.sell_rsi.value

        try:
            path1 = _BASE / "config/dynamic_params.json"
            path2 = _BASE / "config/dynamic_params.json"
            path = path1 if path1.exists() else path2

            if path.exists():
                with open(path) as f:
                    params = json.load(f)

                strat_name = self.__class__.__name__
                strat_params = params.get(strat_name, params)

                if "buy_rsi" in strat_params:
                    self.buy_rsi_val = int(strat_params["buy_rsi"])
                if "sell_rsi" in strat_params:
                    self.sell_rsi_val = int(strat_params["sell_rsi"])

                logger.info(
                    f"[{strat_name}] Dynamically loaded parameters: buy_rsi={self.buy_rsi_val}, sell_rsi={self.sell_rsi_val}"
                )
        except Exception as e:
            logger.warning(f"Failed to load dynamic parameters, using defaults: {e}")

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        informative_pairs = []
        for timeframe in self.informative_timeframes:
            for pair in pairs:
                informative_pairs.append((pair, timeframe))
        return informative_pairs

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Load dynamic parameters first
        self.load_dynamic_params()

        from qnt.polars_indicators import add_bollinger_bands, add_ema, add_rsi, add_sma
        from qnt.polars_ohlcv import ohlcv_to_pandas, pandas_to_polars

        # Convert to Polars
        df_pl = pandas_to_polars(dataframe)

        # 5m Indicators
        df_pl = add_rsi(df_pl, period=14, alias="rsi")
        df_pl = add_bollinger_bands(df_pl, period=20, std_dev=2.0, prefix="bb")
        df_pl = add_sma(df_pl, period=20, column="volume", alias="volume_avg")
        df_pl = df_pl.rename({"bb_mid": "bb_middle"})

        # Informative timeframes
        if getattr(self, "config", {}).get("runmode", {}).value in ("live", "dry_run"):
            for tf in self.informative_timeframes:
                inf_df_pd = self.dp.get_pair_dataframe(metadata["pair"], tf)
                if inf_df_pd is not None and not inf_df_pd.empty:
                    inf_df_pl = pandas_to_polars(inf_df_pd)

                    if tf == "15m":
                        inf_df_pl = add_rsi(inf_df_pl, period=14, alias="rsi")
                    elif tf == "1h":
                        inf_df_pl = add_ema(inf_df_pl, period=200, alias="ema_200")

                    # Back to Pandas for Freqtrade merge
                    inf_df_pd = ohlcv_to_pandas(inf_df_pl)

                dataframe = merge_informative_pair(
                    ohlcv_to_pandas(df_pl), inf_df_pd, self.timeframe, tf, ffill=True
                )
                df_pl = pandas_to_polars(dataframe)

        # Convert back to Pandas for merge_macro_data
        dataframe = ohlcv_to_pandas(df_pl)
        dataframe = merge_macro_data(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self.load_dynamic_params()

        is_live = self.config.get("runmode", {}).value in ("live", "dry_run")

        # External signals only available in live/dry_run — default to permissive in backtesting
        sentiment_ok = True
        regime_ok = True
        if is_live:
            sentiment = get_current_sentiment()
            sentiment_ok = sentiment["score"] >= -0.3
            regime = detect_regime(dataframe, metadata["pair"])
            regime_ok = get_regime_for_strategy("ScalpV1", regime)

        dataframe.loc[
            (
                (dataframe["rsi"] < self.buy_rsi_val)
                & (dataframe["rsi"] > dataframe["rsi"].shift(1))
                & (dataframe["close"] < dataframe["bb_lower"])
                & (dataframe["volume"] > dataframe["volume_avg"])
                & (dataframe.get("rsi_15m", 50) < 60)
                & (dataframe.get("close", 0) > dataframe.get("ema_200_1h", 0))
                & (sentiment_ok)
                & (regime_ok)
            ),
            "enter_long",
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self.load_dynamic_params()

        raw_exit = (dataframe["rsi"] > self.sell_rsi_val) | (
            dataframe["close"] > dataframe["bb_middle"]
        )
        # Require signal on 2 consecutive candles — kills one-tick RSI spikes that exit trades at a loss
        dataframe.loc[raw_exit & raw_exit.shift(1).fillna(False), "exit_long"] = 1
        return dataframe

    def adjust_trade_position(
        self,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        min_stake,
        max_stake,
        current_entry_rate: float,
        current_exit_rate: float,
        current_entry_profit: float,
        current_exit_profit: float,
        **kwargs,
    ):
        if trade.id in _partial_exits_done:
            return None
        if current_profit >= 0.010:
            _partial_exits_done.add(trade.id)
            logger.info(
                f"[PARTIAL EXIT] ScalpV1 {trade.pair} profit={current_profit:.2%} — exiting 50%"
            )
            return -(trade.stake_amount * 0.5)
        return None

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ):
        hours_open = (current_time - trade.open_date_utc).total_seconds() / 3600

        # Stale scalp: cut if negative after 4 hours
        if hours_open >= 4 and current_profit < -0.003:
            return "time_stop_4h"

        # Dynamic profit target by regime — bear bounces fade fast, take less
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if dataframe is not None and not dataframe.empty:
                regime = detect_regime(dataframe, pair)
                if regime == "BEAR" and current_profit >= 0.008:
                    return "bear_bounce_target"
        except Exception:
            pass

        return None

    def custom_stake_amount(
        self,
        current_time,
        current_rate,
        proposed_stake,
        min_stake,
        max_stake,
        leverage,
        entry_tag,
        side,
        **kwargs,
    ):
        multiplier = get_stake_multiplier("ScalpV1")
        stake = proposed_stake * multiplier
        if min_stake is not None:
            stake = max(stake, min_stake)
        return min(stake, max_stake)

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: str,
        side: str,
        **kwargs,
    ) -> bool:
        if self.config.get("runmode", {}).value not in ("live", "dry_run"):
            return True

        # --- LAYER 0: THESIS GATE ---
        thesis = read_thesis(pair)
        if thesis["bias"] == "SELL":
            logger.info(
                f"[THESIS BLOCK] {pair} bias=SELL confidence={thesis['confidence']:.2f} — {thesis['reasoning']}"
            )
            return False
        stake_modifier = thesis.get("stake_modifier", 1.0)

        # --- LAYER 1: RISK & SENTIMENT CHECKS ---
        try:
            total_balance = self.wallets.get_total("USDT")

            # Fetch recent trades for loss counting
            recent_trades = [
                {
                    "profit_ratio": float(
                        getattr(t, "close_profit", None) or getattr(t, "profit_ratio", None) or 0.0
                    ),
                    "close_date": getattr(t, "close_date", None),
                }
                for t in Trade.get_trades_proxy(is_open=False)
            ][:10]

            # Count trades in the last hour
            one_hour_ago = current_time - timedelta(hours=1)
            trades_last_hour = len(
                [
                    t
                    for t in Trade.get_trades_proxy(is_open=False)
                    if t.close_date and t.close_date >= one_hour_ago
                ]
            )

            # Load balance state for drawdown checks
            state_file = _BASE / "risk/balance_state.json"
            if state_file.exists():
                with open(state_file) as f:
                    state = json.load(f)
                start_of_day = state.get("start_of_day", total_balance)
                start_of_week = state.get("start_of_week", total_balance)
            else:
                start_of_day = total_balance
                start_of_week = total_balance

            # ScalpV1 requires at least NEUTRAL sentiment
            risk_result = run_all_checks(
                current_balance=total_balance,
                start_of_day_balance=start_of_day,
                start_of_week_balance=start_of_week,
                trade_amount_usdt=amount * rate * stake_modifier,
                trades_last_hour=trades_last_hour,
                recent_trades=recent_trades,
                min_sentiment="NEUTRAL",
            )

            if not risk_result["safe_to_trade"]:
                logger.info(
                    f"[RISK/SENTIMENT BLOCK] Scalp blocked for {pair}. Reasons: {risk_result['blocking_reasons']}"
                )
                return False

            # Log sentiment for visibility
            sentiment = get_current_sentiment()
            signal = get_sentiment_signal()
            logger.info(
                f"[Sentiment Check] {pair} | Score: {sentiment['score']:.3f} | Signal: {signal}"
            )

            # --- LAYER 2: SKEPTIC AGENT (final gate) ---
            try:
                import sys

                sys.path.insert(0, str(_BASE / "qnt/agents"))
                from strategist import summarize_signal
                from trade_gate import evaluate_trade

                # Get analyzed dataframe
                dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

                signal_summary = summarize_signal(dataframe, "ScalpV1", pair)

                gate_result = evaluate_trade(
                    {
                        **signal_summary,
                        "sentiment_score": sentiment["score"],
                        "hmm_regime": detect_regime(dataframe),
                        "stake_amount": amount * rate,
                    }
                )

                if gate_result["decision"] == "BLOCK":
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

        base = pair.split("/")[0]
        if corr_blocked(base, side):
            logger.info(f"[CORR BLOCK] ScalpV1 {pair} — too many concurrent longs on {base}")
            return False

        if side == "long":
            funding = get_funding_rate()
            if funding < -0.5:
                logger.info(
                    f"[FUNDING BLOCK] ScalpV1 {pair} funding={funding:.2f} — extreme negative funding"
                )
                return False

        return True
