"""Vault tools: semantic recall, store, and stats from Qdrant."""

import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_BASE / "qnt/vault"))


def recall_lessons(query: str, n_results: int = 5) -> list[dict]:
    """Semantic search through historical trade lessons in the Vault."""
    try:
        from vault import recall_lessons as _recall
        return _recall(query, n_results=n_results)
    except Exception as e:
        return [{"error": str(e)}]


def get_vault_stats() -> dict:
    """Return Vault collection statistics (entry count, DB path)."""
    try:
        from vault import get_collection_stats
        return get_collection_stats()
    except Exception as e:
        return {"error": str(e), "entry_count": 0}


def store_lesson(lesson_id: str, text: str, metadata: dict) -> bool:
    """Store a new lesson in the Vault."""
    try:
        from vault import store_lesson as _store
        return _store(lesson_id, text, metadata)
    except Exception as e:
        print(f"Vault store error: {e}")
        return False


def add_journal_entry(text: str, tags: list[str] | None = None) -> bool:
    """Add a manual journal note to the Vault."""
    try:
        from vault import add_entry
        metadata = {"type": "journal", "tags": tags or []}
        return add_entry("journal", text, metadata)
    except Exception as e:
        print(f"Journal store error: {e}")
        return False
