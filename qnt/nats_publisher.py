import asyncio
import json
import os
import nats
from pathlib import Path
from dotenv import load_dotenv
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

NATS_URL = os.getenv('NATS_URL', 'nats://localhost:4222')

async def publish(subject: str, data: dict) -> bool:
    """
    Publish a message to a NATS subject.
    M2 calls this after every intelligence update.
    """
    try:
        nc = await nats.connect(NATS_URL)
        js = nc.jetstream()

        payload = json.dumps({
            **data,
            'source': 'M2',
            'published_at': __import__('datetime').datetime.utcnow().isoformat() + 'Z'
        }).encode()

        await js.publish(subject, payload)
        await nc.drain()
        return True
    except Exception as e:
        print(f'NATS publish error: {e}')
        return False

def publish_sync(subject: str, data: dict) -> bool:
    """Synchronous wrapper for publish."""
    return asyncio.run(publish(subject, data))
