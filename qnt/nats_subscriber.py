import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import nats
from dotenv import load_dotenv

# Suppress NATS library's internal traceback logging — connection failures
# are already handled gracefully by the outer retry loop, and the library's
# stderr tracebacks would otherwise trigger the self-healer on every M2 outage.
logging.getLogger("nats").setLevel(logging.CRITICAL)

# Add project root to sys.path
# Script is at cipher/qnt/nats_subscriber.py
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Load .env from project root
load_dotenv(BASE_DIR / ".env")

NATS_URL = os.getenv("NATS_URL")
SCORES_PATH = BASE_DIR / "sentiment/scores/current_score.json"
MACRO_PATH = BASE_DIR / "risk/macro_state.json"
REGIME_PATH = BASE_DIR / "qnt/oracle/current_regime.json"
ORDERFLOW_PATH = BASE_DIR / "qnt/oracle/order_flow_live.json"


async def handle_sentiment(msg):
    """Instantly write new sentiment to disk."""
    data = json.loads(msg.data.decode())
    with open(SCORES_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[NATS] Sentiment updated: {data.get('score', '?'):.3f}")


async def handle_macro(msg):
    """Instantly write macro state to disk."""
    data = json.loads(msg.data.decode())
    with open(MACRO_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[NATS] Macro updated: DXY={data.get('dxy_24h_change', '?')}")


async def handle_regime(msg):
    """Instantly write HMM regime to disk."""
    data = json.loads(msg.data.decode())
    # Save as simple JSON
    with open(REGIME_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[NATS] Regime updated: {data.get('regime', '?')}")


async def handle_orderflow_live(msg):
    """Instantly update live order flow (CVD) data."""
    data = json.loads(msg.data.decode())
    with open(ORDERFLOW_PATH, "w") as f:
        json.dump(data, f, indent=2)
    # Silent for high-frequency updates


async def handle_anomaly(msg):
    """Forward anomaly alerts immediately."""
    data = json.loads(msg.data.decode())
    print(f"[NATS] ANOMALY: {data.get('type', '?')}")
    try:
        sys.path.insert(0, str(BASE_DIR / "qnt/memory"))
        from qnt_notifier import send_notify

        send_notify(f"Anomaly: {data.get('type', '')}", data.get("description", ""), "WARN")
    except Exception as e:
        print(f"Notification error: {e}")


async def subscribe_all():
    """Subscribe to all M2 intelligence subjects with reconnect loop."""
    if not NATS_URL:
        print("Error: NATS_URL not found in environment.")
        return

    from nats_subjects import SUBJECTS

    retry_delay = 10
    while True:
        try:
            print(f"[NATS] Connecting to {NATS_URL}...", flush=True)

            async def _on_error(e):
                print(f"[NATS] Error: {e}", flush=True)

            async def _on_reconnect():
                print("[NATS] Reconnected.", flush=True)

            async def _on_disconnect():
                print("[NATS] Disconnected, waiting for server...", flush=True)

            nc = await nats.connect(
                servers=[NATS_URL],
                max_reconnect_attempts=-1,
                reconnect_time_wait=5,
                connect_timeout=10,
                error_cb=_on_error,
                reconnected_cb=_on_reconnect,
                disconnected_cb=_on_disconnect,
            )
            js = nc.jetstream()
            retry_delay = 10  # reset on successful connect

            subscriptions = [
                (SUBJECTS["SENTIMENT"], handle_sentiment, "m1_sentiment"),
                (SUBJECTS["MACRO"], handle_macro, "m1_macro"),
                (SUBJECTS["HMM"], handle_regime, "m1_regime"),
                (SUBJECTS["ANOMALY"], handle_anomaly, "m1_anomaly"),
                (SUBJECTS["ORDERFLOW_LIVE"], handle_orderflow_live, "m1_orderflow_live"),
            ]

            for subject, callback, durable in subscriptions:
                try:
                    await js.subscribe(subject, cb=callback, durable=durable, stream="qnt")
                    print(f"[NATS] Subscribed to {subject}", flush=True)
                except Exception as e:
                    print(f"[NATS] Subscription error for {subject}: {e}")

            print("[NATS] Waiting for real-time updates...", flush=True)
            while True:
                await asyncio.sleep(1)

        except Exception as e:
            print(f"[NATS] Connection failed: {e}. Retrying in {retry_delay}s...", flush=True)
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 300)


if __name__ == "__main__":
    try:
        asyncio.run(subscribe_all())
    except KeyboardInterrupt:
        pass
