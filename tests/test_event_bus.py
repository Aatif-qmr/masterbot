"""Tests for bus/ event channel."""

import asyncio

import pytest

from bus.channel import EventBus, reset_bus
from bus.events import EventType, RiskAlertEvent, SignalEvent


@pytest.fixture(autouse=True)
def clean_bus():
    reset_bus()
    yield
    reset_bus()


def test_subscribe_and_publish():
    received = []

    async def handler(event):
        received.append(event)

    async def run():
        bus = EventBus()
        bus.subscribe(EventType.SIGNAL, handler)
        event = SignalEvent(strategy="ScalpV1", pair="BTC/USDT", direction="long", confidence=0.9)
        await bus.publish(event)

    asyncio.run(run())
    assert len(received) == 1
    assert received[0].strategy == "ScalpV1"


def test_wildcard_subscription():
    received = []

    async def wildcard_handler(event):
        received.append(event.type)

    async def run():
        bus = EventBus()
        bus.subscribe(None, wildcard_handler)
        await bus.publish(SignalEvent())
        await bus.publish(RiskAlertEvent())

    asyncio.run(run())
    assert EventType.SIGNAL in received
    assert EventType.RISK_ALERT in received


def test_handler_exception_goes_to_dlq():
    async def bad_handler(event):
        raise ValueError("intentional test failure")

    async def run():
        bus = EventBus()
        bus.subscribe(EventType.SIGNAL, bad_handler)
        await bus.publish(SignalEvent())
        return bus

    bus = asyncio.run(run())
    assert len(bus.dead_letter_queue) == 1
    assert isinstance(bus.dead_letter_queue[0][1], ValueError)


def test_unsubscribe():
    received = []

    async def handler(event):
        received.append(event)

    async def run():
        bus = EventBus()
        bus.subscribe(EventType.SIGNAL, handler)
        bus.unsubscribe(EventType.SIGNAL, handler)
        await bus.publish(SignalEvent())

    asyncio.run(run())
    assert len(received) == 0


def test_replay_buffer():
    replayed = []

    async def handler(event):
        replayed.append(event)

    async def run():
        bus = EventBus(replay=True)
        bus.subscribe(EventType.SIGNAL, handler)
        await bus.publish(SignalEvent(strategy="A"))
        await bus.publish(SignalEvent(strategy="B"))
        # replay fires handlers again
        await bus.replay(EventType.SIGNAL)

    asyncio.run(run())
    assert len(replayed) == 4  # 2 original + 2 replay


def test_subscriber_count():
    async def h1(e):
        pass

    async def h2(e):
        pass

    bus = EventBus()
    bus.subscribe(EventType.SIGNAL, h1)
    bus.subscribe(EventType.SIGNAL, h2)
    assert bus.subscriber_count(EventType.SIGNAL) == 2
