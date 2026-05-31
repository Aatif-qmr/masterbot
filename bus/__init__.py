"""
bus/ — Cipher async event bus.

Quick start:
    from bus.channel import get_bus
    from bus.events import EventType, SignalEvent
    from bus.consumers.signal_handler import log_signal, risk_gate_consumer
    from bus.consumers.event_store_consumer import register_event_store_consumer

    bus = get_bus()
    register_event_store_consumer(bus)          # persist all events to DuckDB
    bus.subscribe(EventType.SIGNAL, log_signal)
    bus.subscribe(EventType.SIGNAL, risk_gate_consumer)

    await bus.publish(SignalEvent(strategy="ScalpV1", pair="BTC/USDT", direction="long"))
"""

from bus.channel import EventBus, get_bus, reset_bus
from bus.consumers.event_store_consumer import register_event_store_consumer
from bus.events import (
    CandleEvent,
    EventType,
    HyperoptResultEvent,
    MacroEvent,
    RiskAlertEvent,
    SentimentEvent,
    SignalEvent,
    SystemHealthEvent,
    TradeEvent,
)

__all__ = [
    "EventBus",
    "get_bus",
    "reset_bus",
    "register_event_store_consumer",
    "EventType",
    "CandleEvent",
    "SignalEvent",
    "TradeEvent",
    "RiskAlertEvent",
    "SentimentEvent",
    "MacroEvent",
    "HyperoptResultEvent",
    "SystemHealthEvent",
]
