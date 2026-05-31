#!/usr/bin/env python3
"""
Real-Time Order Flow Engine (M2)
- aggTrade stream  → CVD (cumulative volume delta)
- depth20@100ms   → L2 book imbalance, spread, mid-price  (bmoscon/order_book, C-backed)
- JSON via orjson  → 3-5x faster parse/serialize than stdlib json
Publishes combined payload to NATS at 5Hz.
"""

import asyncio
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import nats
import orjson
import websockets
from dotenv import load_dotenv
from order_book import OrderBook

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
from qnt.nats_subjects import SUBJECTS

load_dotenv(BASE_DIR / ".env")
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")

AGG_TRADE_URL = "wss://fstream.binance.com/ws/btcusdt@aggTrade"
DEPTH_URL = "wss://stream.binance.com:9443/ws/btcusdt@depth20@100ms"
PUBLISH_HZ = 0.2  # 5 Hz — max NATS publish interval (seconds)
TOP_LEVELS = 5  # levels used for imbalance calculation


class OrderFlowEngine:
    def __init__(self):
        self.nc = None
        self.js = None

        # CVD state (from aggTrade stream)
        self.cvd = 0.0
        self.batch_delta = 0.0
        self.batch_volume = 0.0
        self.last_publish_time = 0.0

        # L2 book state (from depth20 stream, C-backed OrderBook)
        self.ob = OrderBook()
        self.imbalance = 0.5  # 0–1, >0.5 = buy-side heavy
        self.spread = 0.0
        self.mid_price = 0.0

    # ------------------------------------------------------------------ NATS
    async def connect_nats(self):
        self.nc = await nats.connect(NATS_URL)
        self.js = self.nc.jetstream()
        print(f"[orderflow] NATS connected: {NATS_URL}")

    # ------------------------------------------------------------------ CVD stream (aggTrade)
    async def stream_agg_trades(self):
        print(f"[orderflow] aggTrade stream: {AGG_TRADE_URL}")
        async for ws in websockets.connect(AGG_TRADE_URL):
            try:
                async for raw in ws:
                    data = orjson.loads(raw)
                    qty = float(data["q"])
                    delta = -qty if data["m"] else qty  # m=True → taker sell
                    self.cvd += delta
                    self.batch_delta += delta
                    self.batch_volume += qty

                    now = datetime.now(UTC).timestamp()
                    if now - self.last_publish_time >= PUBLISH_HZ:
                        await self._publish()
                        self.last_publish_time = now
                        self.batch_delta = 0.0
                        self.batch_volume = 0.0

            except websockets.ConnectionClosed:
                print("[orderflow] aggTrade WS closed — reconnecting")
            except Exception as e:
                print(f"[orderflow] aggTrade error: {e}")
                await asyncio.sleep(3)

    # ------------------------------------------------------------------ L2 depth stream
    async def stream_depth(self):
        print(f"[orderflow] depth20 stream: {DEPTH_URL}")
        async for ws in websockets.connect(DEPTH_URL):
            try:
                async for raw in ws:
                    data = orjson.loads(raw)
                    self._apply_depth_snapshot(data)

            except websockets.ConnectionClosed:
                print("[orderflow] depth WS closed — reconnecting")
            except Exception as e:
                print(f"[orderflow] depth error: {e}")
                await asyncio.sleep(3)

    def _apply_depth_snapshot(self, data: dict):
        """Apply depth20 full-snapshot update to C-backed OrderBook."""
        try:
            bids_raw = data.get("bids", [])
            asks_raw = data.get("asks", [])

            # Overwrite book sides entirely (depth20 is a full snapshot each tick)
            self.ob.bids = {Decimal(p): float(q) for p, q in bids_raw if float(q) > 0}
            self.ob.asks = {Decimal(p): float(q) for p, q in asks_raw if float(q) > 0}

            # Best bid / ask from C-backed index(0)
            best_bid_price, _ = self.ob.bids.index(0)
            best_ask_price, _ = self.ob.asks.index(0)

            self.spread = float(best_ask_price - best_bid_price)
            self.mid_price = float((best_bid_price + best_ask_price) / 2)

            # Book imbalance: bid_vol / (bid_vol + ask_vol) across top N levels
            bid_vol = sum(q for _, q in self.ob.bids.to_list()[:TOP_LEVELS])
            ask_vol = sum(q for _, q in self.ob.asks.to_list()[:TOP_LEVELS])
            total = bid_vol + ask_vol
            self.imbalance = bid_vol / total if total > 0 else 0.5

        except Exception as e:
            print(f"[orderflow] depth parse error: {e}")

    # ------------------------------------------------------------------ publish
    async def _publish(self):
        if not self.js:
            return
        payload = {
            "symbol": "BTC/USDT",
            "cvd": self.cvd,
            "delta": self.batch_delta,
            "volume": self.batch_volume,
            "imbalance": round(self.imbalance, 4),  # new: L2 buy pressure 0-1
            "spread": round(self.spread, 2),  # new: ask - bid in USD
            "mid_price": round(self.mid_price, 2),  # new: (bid+ask)/2
            "timestamp": datetime.now(UTC).isoformat() + "Z",
        }
        try:
            await self.js.publish(SUBJECTS["ORDERFLOW_LIVE"], orjson.dumps(payload))
        except Exception as e:
            print(f"[orderflow] NATS publish error: {e}")

    # ------------------------------------------------------------------ run
    async def run(self):
        await self.connect_nats()
        # Run both streams concurrently
        await asyncio.gather(
            self.stream_agg_trades(),
            self.stream_depth(),
        )


async def main():
    engine = OrderFlowEngine()
    await engine.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
