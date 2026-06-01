"""
bus/consumers/signal_handler.py
────────────────────────────────
Event bus consumers that react to SignalEvents and RiskAlertEvents.

Each consumer is a coroutine registered with the bus via subscribe().
They are independently testable — inject fake events, assert side effects.
"""

from __future__ import annotations

import logging
from pathlib import Path

from bus.events import BaseEvent, EventType, RiskAlertEvent, SignalEvent

logger = logging.getLogger(__name__)

_BASE = Path(__file__).resolve().parent.parent.parent


async def log_signal(event: BaseEvent) -> None:
    """Write every SignalEvent to the cipher signal log."""
    if not isinstance(event, SignalEvent):
        return
    logger.info(
        "[SIGNAL] strategy=%s pair=%s direction=%s confidence=%.3f tag=%s",
        event.strategy,
        event.pair,
        event.direction,
        event.confidence,
        event.tag,
    )


async def risk_gate_consumer(event: BaseEvent) -> None:
    """
    Check risk gates before a signal is acted on.
    Publishes a RiskAlertEvent back on the bus if a gate is tripped.
    """
    if not isinstance(event, SignalEvent):
        return
    try:
        import sys

        sys.path.insert(0, str(_BASE))
        from bus.channel import get_bus
        from bus.events import RiskAlertEvent
        from risk.risk_manager import run_all_checks

        result = run_all_checks()
        if result and result.get("halt"):
            bus = get_bus()
            await bus.publish(
                RiskAlertEvent(
                    source="risk_gate_consumer",
                    gate=result.get("gate", "unknown"),
                    value=result.get("value", 0.0),
                    threshold=result.get("threshold", 0.0),
                    action="halt",
                )
            )
    except Exception as exc:
        logger.error("risk_gate_consumer error: %s", exc)


async def vault_writer(event: BaseEvent) -> None:
    """
    After a trade closes, write the outcome to VectorVault for future recall.
    Subscribed to EventType.TRADE_CLOSE.
    """
    if event.type != EventType.TRADE_CLOSE:
        return
    try:
        from qnt.tools.vault import store_lesson

        lesson = (
            f"Strategy {event.source} closed {getattr(event, 'pair', '?')} "
            f"profit={getattr(event, 'profit_ratio', 0):.2%}"
        )
        store_lesson(lesson, lesson, metadata={"event_type": "trade_close"})
    except Exception as exc:
        logger.debug("vault_writer skipped: %s", exc)


async def halt_on_risk_alert(event: BaseEvent) -> None:
    """Log hard halts from the risk system."""
    if not isinstance(event, RiskAlertEvent):
        return
    if event.action == "halt":
        logger.critical(
            "[RISK HALT] gate=%s value=%.4f threshold=%.4f — manual review required",
            event.gate,
            event.value,
            event.threshold,
        )
