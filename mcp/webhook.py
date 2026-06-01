"""
mcp/webhook.py
───────────────
TradingView webhook bridge — receives TV alerts and forwards them to the
Cipher event bus as standardised SignalEvent objects.

Usage:
    python -m mcp.webhook --port 9011 --secret $TV_WEBHOOK_SECRET

TradingView alert payload (JSON body):
    {
        "secret":   "your-shared-secret",
        "strategy": "ScalpV1",
        "pair":     "BTC/USDT",
        "side":     "buy" | "sell",
        "price":    42000.0,          # optional — current price
        "reason":   "RSI oversold"    # optional — alert message
    }

Design:
  - FastAPI app on a separate port so the MCP server (9010) is unaffected.
  - HMAC-SHA256 secret check on every request (constant-time compare).
  - Validated payload → SignalEvent on the async event bus.
  - /health endpoint for uptime checks.
  - Runs standalone; can also be imported for testing.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

# ── Secret ────────────────────────────────────────────────────────────────────

_SECRET = os.getenv("TV_WEBHOOK_SECRET", "")

VALID_SIDES = {"buy", "sell", "long", "short", "close"}


# ── Payload schema ────────────────────────────────────────────────────────────

class WebhookPayload(BaseModel):
    secret: str
    strategy: str
    pair: str
    side: str
    price: float | None = None
    reason: str = ""
    extra: dict[str, Any] = {}

    @field_validator("side")
    @classmethod
    def _validate_side(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in VALID_SIDES:
            raise ValueError(f"side must be one of {VALID_SIDES}, got '{v}'")
        return v

    @field_validator("strategy")
    @classmethod
    def _validate_strategy(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("strategy must not be empty")
        return v.strip()

    @field_validator("pair")
    @classmethod
    def _validate_pair(cls, v: str) -> str:
        if "/" not in v:
            raise ValueError("pair must be in BASE/QUOTE format, e.g. BTC/USDT")
        return v.upper().strip()


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Cipher TradingView Webhook",
    description="Receives TradingView alerts and emits them as Cipher SignalEvents.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)


def _check_secret(provided: str) -> None:
    """Constant-time HMAC compare against TV_WEBHOOK_SECRET env var."""
    if not _SECRET:
        logger.warning("TV_WEBHOOK_SECRET not set — webhook is open (dev mode only)")
        return
    if not hmac.compare_digest(provided.encode(), _SECRET.encode()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook secret.",
        )


def _emit_signal(payload: WebhookPayload) -> dict[str, Any]:
    """
    Publish to the async event bus if available; fall back to logging only.
    Returns a dict describing what was emitted.
    """
    event: dict[str, Any] = {
        "event_type": "signal",
        "strategy": payload.strategy,
        "pair": payload.pair,
        "side": payload.side,
        "price": payload.price,
        "reason": payload.reason or f"TV alert: {payload.side} {payload.pair}",
        "source": "tradingview_webhook",
    }

    try:
        from bus.event_bus import get_bus
        bus = get_bus()
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(bus.publish("signal", event))
        else:
            loop.run_until_complete(bus.publish("signal", event))
        logger.info("Signal emitted to bus: %s %s %s", payload.strategy, payload.side, payload.pair)
    except Exception as exc:
        logger.warning("Bus unavailable (%s) — signal logged only", exc)

    return event


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "cipher-tv-webhook"})


@app.post("/webhook/tradingview")
async def tradingview_webhook(request: Request) -> JSONResponse:
    """
    Receive a TradingView alert.

    Expected body: JSON with fields: secret, strategy, pair, side,
    optionally price and reason.
    """
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body must be valid JSON.",
        )

    try:
        payload = WebhookPayload(**raw)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    _check_secret(payload.secret)
    event = _emit_signal(payload)

    return JSONResponse(
        {"status": "accepted", "event": event},
        status_code=status.HTTP_202_ACCEPTED,
    )


@app.post("/webhook/tradingview/batch")
async def tradingview_webhook_batch(request: Request) -> JSONResponse:
    """
    Accept a list of alerts in one request.
    Each alert must include the secret field.
    """
    try:
        raw_list = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body must be a JSON array.")

    if not isinstance(raw_list, list):
        raise HTTPException(status_code=400, detail="Body must be a JSON array.")

    accepted = []
    errors = []
    for i, raw in enumerate(raw_list):
        try:
            payload = WebhookPayload(**raw)
            _check_secret(payload.secret)
            event = _emit_signal(payload)
            accepted.append(event)
        except HTTPException as exc:
            errors.append({"index": i, "error": exc.detail})
        except Exception as exc:
            errors.append({"index": i, "error": str(exc)})

    return JSONResponse(
        {"accepted": len(accepted), "errors": errors, "events": accepted},
        status_code=status.HTTP_202_ACCEPTED if accepted else status.HTTP_400_BAD_REQUEST,
    )


# ── Entrypoint ────────────────────────────────────────────────────────────────

def run(host: str = "0.0.0.0", port: int = 9011) -> None:
    import uvicorn
    logger.info("TradingView webhook bridge starting at http://%s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Cipher TradingView Webhook Bridge")
    p.add_argument("--port", type=int, default=9011)
    p.add_argument("--host", type=str, default="0.0.0.0")
    args = p.parse_args()
    run(host=args.host, port=args.port)
