"""
risk/twap.py
─────────────
Time-Weighted Average Price (TWAP) order slicer for Freqtrade strategies.

Splits a large entry into N limit orders spread evenly over a time window.
Reduces market impact on orders > ~0.5 BTC equivalent at current AUM.

Design:
  - Freqtrade doesn't natively support multi-slice entries, but
    custom_stake_amount() can return 1/N of the full allocation on the
    first entry, and the strategy can re-enter using bot_loop_start or
    custom_entry_price on subsequent bars.
  - This module handles the state machine: how many slices have been
    placed, when the next slice is due, and whether to abort.

Usage (add to any IStrategy subclass):
    from risk.twap import TwapSlicer

    class MyStrategy(IStrategy):
        _twap = TwapSlicer(n_slices=4, interval_secs=30)

        def custom_stake_amount(self, current_time, current_rate, proposed_stake,
                                min_stake, max_stake, **kwargs):
            return self._twap.slice_stake(proposed_stake, min_stake, max_stake)

        def custom_entry_price(self, current_time, proposed_rate, **kwargs):
            # Use limit orders at proposed price (Freqtrade default)
            return proposed_rate

The first call to slice_stake() records the full intended stake and
returns stake/n_slices. Subsequent calls (if a partial fill triggers
re-entry) return the next slice. After n_slices the slicer resets.

Thread safety: one TwapSlicer instance per strategy. Freqtrade runs
each strategy in a single thread, so no lock needed.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


@dataclass
class _SliceState:
    """In-flight TWAP order state for one active entry."""
    full_stake: float
    n_slices: int
    interval_secs: int
    slices_placed: int = 0
    started_at: float = field(default_factory=time.monotonic)
    pair: str = ""

    @property
    def slice_stake(self) -> float:
        return self.full_stake / self.n_slices

    def next_slice_due_at(self) -> float:
        return self.started_at + self.slices_placed * self.interval_secs

    def is_complete(self) -> bool:
        return self.slices_placed >= self.n_slices

    def is_expired(self, timeout_secs: int) -> bool:
        return time.monotonic() - self.started_at > timeout_secs


class TwapSlicer:
    """
    Stateful TWAP slicer for Freqtrade's custom_stake_amount() callback.

    Args:
        n_slices:       Number of slices to split the entry into.
        interval_secs:  Minimum seconds between slices.
        timeout_secs:   Abort and reset if all slices not placed within
                        this many seconds (default: n_slices × interval × 3).
        min_slice_pct:  Minimum slice as fraction of full stake (guards
                        against Freqtrade's min_stake constraints).
    """

    def __init__(
        self,
        n_slices: int = 4,
        interval_secs: int = 30,
        timeout_secs: int | None = None,
        min_slice_pct: float = 0.10,
    ) -> None:
        if n_slices < 1:
            raise ValueError("n_slices must be >= 1")
        self.n_slices = n_slices
        self.interval_secs = interval_secs
        # Default timeout: at least 60s to avoid expiry on fast test loops.
        self.timeout_secs = timeout_secs if timeout_secs is not None else max(n_slices * interval_secs * 3, 60)
        self.min_slice_pct = min_slice_pct
        self._state: _SliceState | None = None

    def slice_stake(
        self,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        pair: str = "",
    ) -> float:
        """
        Return the stake amount for the current slice.

        First call: starts a new TWAP sequence, returns proposed_stake / n_slices.
        Subsequent calls (same sequence): returns the next slice if interval elapsed.
        Returns full proposed_stake if TWAP is disabled (n_slices == 1).
        """
        if self.n_slices == 1:
            return min(proposed_stake, max_stake)

        # Start a new sequence if none active or previous is complete/expired
        if self._state is None or self._state.is_complete() or self._state.is_expired(self.timeout_secs):
            if self._state is not None and not self._state.is_complete():
                logger.warning(
                    "TWAP timed out for %s after %d/%d slices — resetting",
                    self._state.pair, self._state.slices_placed, self._state.n_slices,
                )
            self._state = _SliceState(
                full_stake=proposed_stake,
                n_slices=self.n_slices,
                interval_secs=self.interval_secs,
                pair=pair,
            )
            logger.info(
                "TWAP start: %s full_stake=%.2f, n_slices=%d, interval=%ds",
                pair, proposed_stake, self.n_slices, self.interval_secs,
            )

        state = self._state
        # Compute now AFTER state init so started_at <= now is guaranteed.
        now = time.monotonic()

        # Check if it's too early for the next slice
        if self.interval_secs > 0 and now < state.next_slice_due_at():
            wait = state.next_slice_due_at() - now
            logger.debug("TWAP: next slice in %.1fs, skipping entry", wait)
            # Return min_stake to allow Freqtrade to proceed with a minimal order
            # (which will be rejected by the exchange as too small, effectively skipping).
            # Alternatively, return 0 — but Freqtrade may raise. Use min_stake floor.
            return float(min_stake) if min_stake else proposed_stake / self.n_slices

        slice_amount = state.slice_stake
        state.slices_placed += 1

        # Respect min_stake from exchange
        if min_stake and slice_amount < min_stake:
            logger.warning(
                "TWAP slice %.2f below min_stake %.2f — using min_stake",
                slice_amount, min_stake,
            )
            slice_amount = float(min_stake)

        result = min(slice_amount, max_stake)
        logger.info(
            "TWAP slice %d/%d: pair=%s stake=%.2f",
            state.slices_placed, state.n_slices, pair, result,
        )
        return result

    def reset(self) -> None:
        """Manually reset the TWAP state (e.g., on trade close)."""
        self._state = None

    @property
    def slices_placed(self) -> int:
        return self._state.slices_placed if self._state else 0

    @property
    def is_active(self) -> bool:
        return self._state is not None and not self._state.is_complete()

    def status(self) -> dict:
        if self._state is None:
            return {"active": False}
        s = self._state
        return {
            "active": not s.is_complete(),
            "pair": s.pair,
            "slices_placed": s.slices_placed,
            "n_slices": s.n_slices,
            "full_stake": s.full_stake,
            "elapsed_secs": time.monotonic() - s.started_at,
        }
