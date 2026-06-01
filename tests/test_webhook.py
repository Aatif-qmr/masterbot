"""Tests for mcp/webhook.py"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Patch secret before importing app so _SECRET is set at module load
os.environ["TV_WEBHOOK_SECRET"] = "test-secret"

from mcp.webhook import WebhookPayload, app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


# ── /health ───────────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── WebhookPayload validation ─────────────────────────────────────────────────

def test_payload_valid():
    p = WebhookPayload(secret="x", strategy="ScalpV1", pair="BTC/USDT", side="buy")
    assert p.side == "buy"
    assert p.pair == "BTC/USDT"


def test_payload_side_normalised():
    p = WebhookPayload(secret="x", strategy="ScalpV1", pair="BTC/USDT", side="BUY")
    assert p.side == "buy"


def test_payload_invalid_side():
    with pytest.raises(Exception, match="side"):
        WebhookPayload(secret="x", strategy="ScalpV1", pair="BTC/USDT", side="HODL")


def test_payload_invalid_pair():
    with pytest.raises(Exception, match="pair"):
        WebhookPayload(secret="x", strategy="ScalpV1", pair="BTCUSDT", side="buy")


def test_payload_empty_strategy():
    with pytest.raises(Exception, match="strategy"):
        WebhookPayload(secret="x", strategy="  ", pair="BTC/USDT", side="buy")


def test_payload_pair_uppercased():
    p = WebhookPayload(secret="x", strategy="ScalpV1", pair="btc/usdt", side="sell")
    assert p.pair == "BTC/USDT"


# ── /webhook/tradingview ──────────────────────────────────────────────────────

def _post(payload: dict):
    return client.post("/webhook/tradingview", json=payload)


def test_valid_buy_signal():
    with patch("mcp.webhook._emit_signal", return_value={"event_type": "signal"}):
        r = _post({"secret": "test-secret", "strategy": "ScalpV1", "pair": "BTC/USDT", "side": "buy"})
    assert r.status_code == 202
    assert r.json()["status"] == "accepted"


def test_wrong_secret_returns_403():
    r = _post({"secret": "wrong", "strategy": "ScalpV1", "pair": "BTC/USDT", "side": "buy"})
    assert r.status_code == 403


def test_missing_secret_field_returns_422():
    r = _post({"strategy": "ScalpV1", "pair": "BTC/USDT", "side": "buy"})
    assert r.status_code == 422


def test_invalid_side_returns_422():
    r = _post({"secret": "test-secret", "strategy": "ScalpV1", "pair": "BTC/USDT", "side": "MOON"})
    assert r.status_code == 422


def test_non_json_body_returns_400():
    r = client.post(
        "/webhook/tradingview",
        content=b"not json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 400


def test_sell_signal_accepted():
    with patch("mcp.webhook._emit_signal", return_value={}):
        r = _post({"secret": "test-secret", "strategy": "TrendFollowV1", "pair": "ETH/USDT", "side": "sell"})
    assert r.status_code == 202


def test_close_signal_accepted():
    with patch("mcp.webhook._emit_signal", return_value={}):
        r = _post({"secret": "test-secret", "strategy": "ScalpV1", "pair": "SOL/USDT", "side": "close"})
    assert r.status_code == 202


def test_optional_price_field():
    with patch("mcp.webhook._emit_signal", return_value={}):
        r = _post({
            "secret": "test-secret", "strategy": "ScalpV1", "pair": "BTC/USDT",
            "side": "buy", "price": 42000.0, "reason": "RSI oversold",
        })
    assert r.status_code == 202


# ── /webhook/tradingview/batch ────────────────────────────────────────────────

def _batch(payload: list):
    return client.post("/webhook/tradingview/batch", json=payload)


def test_batch_two_valid_signals():
    alerts = [
        {"secret": "test-secret", "strategy": "ScalpV1", "pair": "BTC/USDT", "side": "buy"},
        {"secret": "test-secret", "strategy": "TrendFollowV1", "pair": "ETH/USDT", "side": "sell"},
    ]
    with patch("mcp.webhook._emit_signal", return_value={}):
        r = _batch(alerts)
    assert r.status_code == 202
    assert r.json()["accepted"] == 2
    assert r.json()["errors"] == []


def test_batch_partial_failure():
    alerts = [
        {"secret": "test-secret", "strategy": "ScalpV1", "pair": "BTC/USDT", "side": "buy"},
        {"secret": "WRONG", "strategy": "ScalpV1", "pair": "BTC/USDT", "side": "buy"},
    ]
    with patch("mcp.webhook._emit_signal", return_value={}):
        r = _batch(alerts)
    data = r.json()
    assert data["accepted"] == 1
    assert len(data["errors"]) == 1


def test_batch_not_array_returns_400():
    r = _batch({"not": "a list"})
    assert r.status_code == 400


def test_batch_empty_array():
    r = _batch([])
    assert r.status_code == 400


# ── _emit_signal bus integration ──────────────────────────────────────────────

def test_emit_signal_falls_back_when_bus_unavailable():
    from mcp.webhook import _emit_signal

    payload = WebhookPayload(
        secret="test-secret", strategy="ScalpV1", pair="BTC/USDT", side="buy"
    )
    with patch("mcp.webhook.get_bus" if False else "builtins.__import__", side_effect=ImportError):
        # Should not raise — bus failure is a warning only
        event = _emit_signal(payload)
    assert event["event_type"] == "signal"
    assert event["pair"] == "BTC/USDT"
