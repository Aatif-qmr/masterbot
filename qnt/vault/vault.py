# qnt/vault/vault.py
import hashlib
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

_BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_BASE / 'qnt/memory'))

try:
    from memory_manager import log_action
except Exception:
    def log_action(action, msg):
        pass

QDRANT_PATH = str(_BASE / 'qnt/vault/qdrant_storage')
COLLECTION_NAME = "trade_lessons"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
VECTOR_SIZE = 384

os.makedirs(QDRANT_PATH, exist_ok=True)

_client = None
_encoder = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(path=QDRANT_PATH)
        _ensure_collection()
    return _client


def _get_encoder() -> SentenceTransformer:
    global _encoder
    if _encoder is None:
        _encoder = SentenceTransformer(EMBEDDING_MODEL)
    return _encoder


def _ensure_collection():
    existing = [c.name for c in _client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        _client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def _stable_id(lesson_id: str) -> int:
    return int(hashlib.md5(lesson_id.encode()).hexdigest(), 16) % (2 ** 63)


def store_lesson(lesson_id: str, text: str, metadata: dict) -> bool:
    """Stores a trade lesson in the Vault."""
    try:
        client = _get_client()
        encoder = _get_encoder()
        vector = encoder.encode(text).tolist()
        point = PointStruct(
            id=_stable_id(lesson_id),
            vector=vector,
            payload={"lesson_id": lesson_id, "text": text, **metadata},
        )
        client.upsert(collection_name=COLLECTION_NAME, points=[point])
        log_action("vault_store", f"Stored lesson {lesson_id}")
        return True
    except Exception as e:
        print(f"Vault store error: {e}")
        return False


def recall_lessons(query: str, n_results: int = 3) -> list:
    """Searches the Vault for similar past experiences."""
    try:
        client = _get_client()
        encoder = _get_encoder()
        query_vector = encoder.encode(query).tolist()
        response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=n_results,
        )
        hits = response.points
        log_action("vault_recall", f"Queried: {query}")
        return [
            {
                "id": h.payload.get("lesson_id"),
                "document": h.payload.get("text"),
                "metadata": {k: v for k, v in h.payload.items() if k not in ("lesson_id", "text")},
                "score": h.score,
            }
            for h in hits
        ]
    except Exception as e:
        print(f"Vault recall error: {e}")
        return []


def get_collection_stats() -> dict:
    """Returns stats about the Vault."""
    try:
        client = _get_client()
        info = client.get_collection(COLLECTION_NAME)
        return {"entry_count": info.points_count or 0, "db_path": QDRANT_PATH}
    except Exception as e:
        return {"error": str(e), "entry_count": 0}


def add_trade_memory(trade_dict: dict, analysis: str) -> bool:
    """Specific wrapper for trade post-mortems."""
    lesson_id = (
        f"postmortem_{trade_dict.get('trade_id', trade_dict.get('id', 'unk'))}"
        f"_{int(time.time())}"
    )
    text = f"ANALYSIS OF TRADE {trade_dict.get('pair')}:\n{analysis}"
    metadata = {
        "pair": trade_dict.get("pair", ""),
        "strategy": trade_dict.get("strategy", ""),
        "type": "trade_postmortem",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return store_lesson(lesson_id, text, metadata)


def add_entry(category: str, text: str, metadata: dict) -> bool:
    """Generic entry addition for the Vault."""
    entry_id = f"{category}_{int(time.time())}"
    meta = metadata.copy() if metadata else {}
    meta['category'] = category
    return store_lesson(entry_id, text, meta)

