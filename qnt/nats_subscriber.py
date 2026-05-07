import asyncio
import json
import os
import sys
import nats
from pathlib import Path
from dotenv import load_dotenv

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

load_dotenv(BASE_DIR / '.env')

NATS_URL = os.getenv('NATS_URL')
SCORES_PATH = Path('/Users/aatifquamre/masterbot/sentiment/scores/current_score.json')
MACRO_PATH = Path('/Users/aatifquamre/masterbot/risk/macro_state.json')
REGIME_PATH = Path('/Users/aatifquamre/masterbot/qnt/oracle/current_regime.json')

async def handle_sentiment(msg):
    """Instantly write new sentiment to disk."""
    data = json.loads(msg.data.decode())
    with open(SCORES_PATH, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"[NATS] Sentiment updated: {data.get('score', '?'):.3f}")

async def handle_macro(msg):
    """Instantly write macro state to disk."""
    data = json.loads(msg.data.decode())
    with open(MACRO_PATH, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"[NATS] Macro updated: DXY={data.get('dxy_change_24h','?')}")

async def handle_regime(msg):
    """Instantly write HMM regime to disk."""
    data = json.loads(msg.data.decode())
    with open(REGIME_PATH, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"[NATS] Regime updated: {data.get('regime','?')} ({data.get('confidence',0):.0%})")

async def handle_anomaly(msg):
    """Forward anomaly alerts immediately."""
    data = json.loads(msg.data.decode())
    print(f"[NATS] ANOMALY: {data.get('type','?')}")
    # Import and call send_notify
    import sys
    sys.path.insert(0, '/Users/aatifquamre/masterbot/qnt/memory')
    from qnt_notifier import send_notify
    send_notify(
        f"Anomaly: {data.get('type','')}",
        data.get('description',''),
        'WARN'
    )

async def subscribe_all():
    """Subscribe to all M2 intelligence subjects."""
    from qnt.nats_subjects import SUBJECTS
    
    nc = await nats.connect(NATS_URL)
    js = nc.jetstream()

    # Create durable subscriptions
    await js.subscribe(
        SUBJECTS['SENTIMENT'],
        cb=handle_sentiment,
        durable='m1_sentiment',
        stream='qnt'
    )
    await js.subscribe(
        SUBJECTS['MACRO'],
        cb=handle_macro,
        durable='m1_macro',
        stream='qnt'
    )
    await js.subscribe(
        SUBJECTS['HMM'],
        cb=handle_regime,
        durable='m1_regime',
        stream='qnt'
    )
    await js.subscribe(
        SUBJECTS['ANOMALY'],
        cb=handle_anomaly,
        durable='m1_anomaly',
        stream='qnt'
    )

    print("[NATS] M1 subscribed to all M2 subjects")
    print("[NATS] Waiting for real-time updates...")

    # Keep running forever
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await nc.drain()

if __name__ == '__main__':
    asyncio.run(subscribe_all())
