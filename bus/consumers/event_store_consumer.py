"""
bus/consumers/event_store_consumer.py
──────────────────────────────────────
Wildcard bus subscriber — persists every bus event to the append-only event store.

Failures are swallowed so a store write error never crashes the bus or a strategy.

Wire-up (call once at bot startup, e.g. in start_bot.sh or a bot_loop_start hook):

    from bus.channel import get_bus
    from bus.consumers.event_store_consumer import register_event_store_consumer

    register_event_store_consumer(get_bus())
"""

from __future__ import annotations

import logging

from bus.channel import EventBus
from bus.events import BaseEvent

logger = logging.getLogger(__name__)


async def _persist_to_store(event: BaseEvent) -> None:
    try:
        from qnt.event_store import get_event_store

        get_event_store().append(event)
    except Exception as exc:
        logger.warning("event_store_consumer: failed to persist %s: %s", event.type, exc)


def register_event_store_consumer(bus: EventBus) -> None:
    """Subscribe the event store writer to ALL bus events (wildcard)."""
    bus.subscribe(None, _persist_to_store)
    logger.info("EventStore consumer registered (wildcard subscriber)")
