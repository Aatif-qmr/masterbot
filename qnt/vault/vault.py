import os
import sys
import json
import chromadb
from chromadb.utils import embedding_functions
from datetime import datetime, timezone
from pathlib import Path

# Machine-agnostic path setup
HOME = Path.home()
BASE_DIR = HOME / 'masterbot'
sys.path.insert(0, str(BASE_DIR / 'qnt/memory'))

from memory_manager import log_action, get_device_identity

CHROMA_PATH = str(BASE_DIR / 'qnt/vault/chroma_db')

# Ensure path exists
os.makedirs(CHROMA_PATH, exist_ok=True)

# Initialize ChromaDB client
client = chromadb.PersistentClient(path=CHROMA_PATH)

# Use a local embedding model on M2 to avoid API costs/latency
default_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

def get_vault_collection(name="trade_lessons"):
    """Returns or creates a ChromaDB collection."""
    return client.get_or_create_collection(
        name=name,
        embedding_function=default_ef,
        metadata={"hnsw:space": "cosine"}
    )

def store_lesson(lesson_id, text, metadata):
    """Stores a trade lesson or market event in the Vault."""
    try:
        collection = get_vault_collection()
        collection.add(
            documents=[text],
            metadatas=[metadata],
            ids=[str(lesson_id)]
        )
        log_action("vault_store", f"Stored lesson {lesson_id}")
        return True
    except Exception as e:
        print(f"Vault store error: {e}")
        return False

def recall_lessons(query, n_results=3):
    """Searches the Vault for similar past experiences."""
    try:
        collection = get_vault_collection()
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        log_action("vault_recall", f"Queried: {query}")
        return results
    except Exception as e:
        print(f"Vault recall error: {e}")
        return None

def get_collection_stats():
    """Returns stats about the Vault."""
    try:
        collection = get_vault_collection()
        count = collection.count()
        return {
            "entry_count": count,
            "db_path": CHROMA_PATH
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    # Quick test
    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        print(json.dumps(get_collection_stats(), indent=2))
