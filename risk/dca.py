"""
risk/dca.py
────────────
Dollar-Cost Averaging (DCA) executor for MeanReversionV1.

Pyramids into a losing position across N safety orders, each triggered
when the price drops a configurable step below the previous entry.
Implements Freqtrade's adjust_trade_position() interface.

Design:
  - Safety orders are placed only while the position is open and below
    a loss threshold.  Each order multiplies stake by a volume scale factor.
  - Maximum drawdown exposure is bounded by max_safety_orders and
    max_dca_multiplier (total stake must not exceed this × initial stake).
  - Freqtrade calls adjust_trade_position() every bot loop.  We return
    additional stake (positive float) or None (no action).

Usage (add to MeanReversionV1 or any IStrategy):
    from risk.dca import DcaExecutor

    class MeanReversionV1(IStrategy):
        _dca = DcaExecutor(
            safety_orders=3,
            price_step_pct=0.02,    # add safety order at every 2% drop
            volume_scale=1.5,       # each order 1.5× the previous
            max_dca_multiplier=4.0, # total stake ≤ 4× initial
        )

        def adjust_trade_position(self, trade, current_time, current_rate,
                                  current_profit, min_stake, max_stake, **kwargs):
            return self._dca.adjust(trade, current_rate, min_stake, max_stake)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class _OrderState:
    """In-flight DCA state for one open trade."""
    trade_id: int
    initial_stake: float
    orders_placed: int = 0
    last_dca_rate: float = 0.0  # price at which the most recent safety order was placed
    total_dca_stake: float = 0.0  # cumulative additional stake injected


class DcaExecutor:
    """
    Freqtrade adjust_trade_position() helper — pyramids into losing trades.

    Args:
        safety_orders:      Max extra buy-ins beyond the initial entry.
        price_step_pct:     Minimum price drop (fraction, e.g. 0.02 = 2%)
                            from the last DCA entry before adding a new order.
        volume_scale:       Stake multiplier per safety order (e.g. 1.5 = 50% bigger
                            than the previous DCA order).
        max_dca_multiplier: Hard cap — total injected DCA stake ≤ initial_stake × this.
        min_profit_threshold: Only DCA when current_profit < this value (negative float).
    """

    def __init__(
        self,
        safety_orders: int = 3,
        price_step_pct: float = 0.02,
        volume_scale: float = 1.5,
        max_dca_multiplier: float = 4.0,
        min_profit_threshold: float = -0.01,
    ) -> None:
        if safety_orders < 0:
            raise ValueError("safety_orders must be >= 0")
        if price_step_pct <= 0:
            raise ValueError("price_step_pct must be > 0")
        if volume_scale < 1.0:
            raise ValueError("volume_scale must be >= 1.0")
        if max_dca_multiplier < 1.0:
            raise ValueError("max_dca_multiplier must be >= 1.0")

        self.safety_orders = safety_orders
        self.price_step_pct = price_step_pct
        self.volume_scale = volume_scale
        self.max_dca_multiplier = max_dca_multiplier
        self.min_profit_threshold = min_profit_threshold

        self._states: dict[int, _OrderState] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def adjust(
        self,
        trade,
        current_rate: float,
        min_stake: float | None,
        max_stake: float,
        current_profit: float = 0.0,
    ) -> float | None:
        """
        Called from adjust_trade_position().  Returns additional stake to buy,
        or None if no action should be taken.

        Args:
            trade:          Freqtrade Trade object (duck-typed: needs .id,
                            .open_rate, .stake_amount, .is_open).
            current_rate:   Current market price.
            min_stake:      Exchange minimum order size.
            max_stake:      Maximum stake allowed.
            current_profit: Fractional P&L (e.g. -0.03 = -3%).
        """
        trade_id = _trade_id(trade)
        initial_stake = _initial_stake(trade)

        # Init state on first call for this trade
        if trade_id not in self._states:
            self._states[trade_id] = _OrderState(
                trade_id=trade_id,
                initial_stake=initial_stake,
                last_dca_rate=_open_rate(trade),
            )

        state = self._states[trade_id]

        # Already exhausted all safety orders
        if state.orders_placed >= self.safety_orders:
            return None

        # Only act when position is sufficiently underwater
        if current_profit >= self.min_profit_threshold:
            return None

        # Check price has dropped enough from last DCA entry
        drop_from_last = (state.last_dca_rate - current_rate) / state.last_dca_rate
        if drop_from_last < self.price_step_pct:
            return None

        # Calculate next order size: initial_stake × volume_scale^orders_placed
        next_order_stake = initial_stake * (self.volume_scale ** state.orders_placed)

        # Hard cap: total additional DCA stake must not exceed max_dca_multiplier × initial
        max_allowed_additional = initial_stake * self.max_dca_multiplier - state.total_dca_stake
        next_order_stake = min(next_order_stake, max_allowed_additional)

        if next_order_stake <= 0:
            logger.info(
                "DCA cap reached for trade %d: total_dca=%.2f >= %.2f × initial",
                trade_id, state.total_dca_stake, self.max_dca_multiplier,
            )
            return None

        # Respect exchange min_stake
        if min_stake and next_order_stake < min_stake:
            logger.debug(
                "DCA stake %.2f below min_stake %.2f — skipping",
                next_order_stake, min_stake,
            )
            return None

        next_order_stake = min(next_order_stake, max_stake)

        # Update state
        state.orders_placed += 1
        state.last_dca_rate = current_rate
        state.total_dca_stake += next_order_stake

        logger.info(
            "DCA order %d/%d for trade %d: rate=%.4f stake=%.2f (total_dca=%.2f)",
            state.orders_placed, self.safety_orders, trade_id,
            current_rate, next_order_stake, state.total_dca_stake,
        )
        return next_order_stake

    def on_trade_exit(self, trade_id: int) -> None:
        """Call when a trade closes to free state memory."""
        self._states.pop(trade_id, None)

    def status(self, trade_id: int) -> dict:
        """Return DCA state for a trade, or empty dict if none."""
        state = self._states.get(trade_id)
        if state is None:
            return {"trade_id": trade_id, "active": False}
        return {
            "trade_id": trade_id,
            "active": True,
            "orders_placed": state.orders_placed,
            "safety_orders": self.safety_orders,
            "total_dca_stake": state.total_dca_stake,
            "last_dca_rate": state.last_dca_rate,
        }


# ── Duck-type helpers (work with real Trade and plain dicts for tests) ────────

def _trade_id(trade) -> int:
    return int(getattr(trade, "id", None) or trade.get("id", 0))


def _initial_stake(trade) -> float:
    return float(getattr(trade, "stake_amount", None) or trade.get("stake_amount", 0.0))


def _open_rate(trade) -> float:
    return float(getattr(trade, "open_rate", None) or trade.get("open_rate", 0.0))
