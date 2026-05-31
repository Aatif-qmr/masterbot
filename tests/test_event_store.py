"""Tests for qnt/event_store.py and bus/consumers/event_store_consumer.py"""

from __future__ import annotations

import asyncio
import os

import pytest

# Use a fixed test key so HMAC is deterministic across runs.
os.environ.setdefault("CIPHER_HMAC_KEY", "test-key-do-not-use-in-prod-32ch")


@pytest.fixture
def store(tmp_path):
    from qnt.event_store import EventStore

    return EventStore(db_path=tmp_path / "test_events.duckdb")


# ── append_raw + query ────────────────────────────────────────────────────────


def test_append_raw_creates_row(store):
    store.append_raw(
        "trade_open",
        strategy="ScalpV1",
        pair="BTC/USDT",
        side="long",
        price=67000.0,
        qty=0.001,
        source="confirm_trade_entry",
    )
    df = store.query(strategy="ScalpV1")
    assert len(df) == 1
    assert df["pair"][0] == "BTC/USDT"
    assert df["event_type"][0] == "trade_open"


def test_multiple_appends_counted(store):
    for i in range(5):
        store.append_raw("signal", strategy="SwingV1", pair=f"PAIR{i}/USDT")
    assert store.count() == 5


def test_filter_by_event_type(store):
    store.append_raw("trade_open", strategy="ScalpV1", pair="BTC/USDT")
    store.append_raw("signal", strategy="ScalpV1", pair="BTC/USDT")
    df = store.query(event_type="trade_open")
    assert len(df) == 1
    assert df["event_type"][0] == "trade_open"


def test_filter_by_pair(store):
    store.append_raw("signal", pair="BTC/USDT")
    store.append_raw("signal", pair="ETH/USDT")
    df = store.query(pair="ETH/USDT")
    assert len(df) == 1
    assert df["pair"][0] == "ETH/USDT"


def test_query_empty_returns_dataframe(store):
    import polars as pl

    df = store.query(strategy="NonExistent")
    assert isinstance(df, pl.DataFrame)
    assert len(df) == 0


def test_ids_are_monotonically_increasing(store):
    for _ in range(3):
        store.append_raw("candle", pair="BTC/USDT")
    df = store.query(limit=10)
    ids = df["id"].to_list()
    assert ids == sorted(ids, reverse=True)  # query returns newest first


# ── HMAC integrity ────────────────────────────────────────────────────────────


def test_verify_integrity_clean(store):
    store.append_raw("trade_open", strategy="ScalpV1", pair="ETH/USDT", price=3000.0)
    store.append_raw("signal", strategy="SwingV1", pair="BTC/USDT")
    result = store.verify_integrity()
    assert result["tampered"] == []
    assert result["total"] == 2
    assert result["ok"] == 2


def test_verify_detects_tampered_row(store):
    store.append_raw("trade_open", strategy="ScalpV1", pair="BTC/USDT", price=50000.0)
    # Simulate an attacker directly modifying the price field.
    store._conn.execute("UPDATE events SET price = 1.0 WHERE id = 1")
    result = store.verify_integrity()
    assert 1 in result["tampered"]
    assert result["ok"] == 0


def test_verify_detects_bad_hmac(store):
    store.append_raw("trade_open", strategy="ScalpV1", pair="BTC/USDT")
    store._conn.execute("UPDATE events SET hmac = 'forged' WHERE id = 1")
    result = store.verify_integrity()
    assert 1 in result["tampered"]


def test_verify_mixed_tampered_and_clean(store):
    store.append_raw("trade_open", pair="BTC/USDT")  # id 1 — will be tampered
    store.append_raw("signal", pair="ETH/USDT")      # id 2 — clean
    store._conn.execute("UPDATE events SET pair = 'HACKED/USDT' WHERE id = 1")
    result = store.verify_integrity()
    assert 1 in result["tampered"]
    assert 2 not in result["tampered"]
    assert result["ok"] == 1


# ── Bus consumer integration ──────────────────────────────────────────────────


def test_bus_consumer_persists_signal_event(tmp_path):
    import qnt.event_store as es_mod
    from bus.channel import EventBus
    from bus.consumers.event_store_consumer import register_event_store_consumer
    from bus.events import SignalEvent
    from qnt.event_store import EventStore

    store = EventStore(db_path=tmp_path / "bus_test.duckdb")
    original = es_mod._store
    es_mod._store = store

    try:
        bus = EventBus()
        register_event_store_consumer(bus)

        asyncio.run(
            bus.publish(
                SignalEvent(
                    strategy="TrendFollowV1",
                    pair="BTC/USDT",
                    direction="long",
                    confidence=0.85,
                    source="test",
                )
            )
        )

        df = store.query(event_type="signal")
        assert len(df) == 1
        assert df["strategy"][0] == "TrendFollowV1"
        assert df["side"][0] == "long"
    finally:
        es_mod._store = original


def test_bus_consumer_persists_risk_alert(tmp_path):
    import qnt.event_store as es_mod
    from bus.channel import EventBus
    from bus.consumers.event_store_consumer import register_event_store_consumer
    from bus.events import RiskAlertEvent
    from qnt.event_store import EventStore

    store = EventStore(db_path=tmp_path / "bus_risk_test.duckdb")
    original = es_mod._store
    es_mod._store = store

    try:
        bus = EventBus()
        register_event_store_consumer(bus)

        asyncio.run(
            bus.publish(
                RiskAlertEvent(
                    source="risk_manager",
                    gate="max_drawdown",
                    value=0.055,
                    threshold=0.05,
                    action="halt",
                )
            )
        )

        df = store.query(event_type="risk_alert")
        assert len(df) == 1
        assert df["reason"][0] == "max_drawdown"
    finally:
        es_mod._store = original


def test_consumer_failure_doesnt_crash_bus(tmp_path):
    """Store write failure must not propagate to bus callers."""
    import qnt.event_store as es_mod
    from bus.channel import EventBus
    from bus.consumers.event_store_consumer import register_event_store_consumer
    from bus.events import SignalEvent
    from qnt.event_store import EventStore

    store = EventStore(db_path=tmp_path / "crash_test.duckdb")
    original = es_mod._store

    # Make _write raise to simulate a locked/corrupt DB.
    def boom(row):
        raise RuntimeError("simulated DB failure")

    store._write = boom
    es_mod._store = store

    try:
        bus = EventBus()
        register_event_store_consumer(bus)
        # Should not raise — failure goes to bus DLQ.
        asyncio.run(bus.publish(SignalEvent(strategy="X", pair="BTC/USDT")))
        # Consumer swallows the exception (logs warning); DLQ stays empty.
        # The point: no exception propagates out of bus.publish().
        assert len(bus.dead_letter_queue) == 0
    finally:
        es_mod._store = original
