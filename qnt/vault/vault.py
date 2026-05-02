import os
import sys
import uuid
import json
from datetime import datetime, timezone
import chromadb
from chromadb.config import Settings

# Add paths for dependencies
BASE_DIR = '/Users/aatifquamre/masterbot'
sys.path.insert(0, os.path.join(BASE_DIR, 'qnt/memory'))

from memory_manager import log_action, get_device_identity

CHROMA_PATH = os.path.join(BASE_DIR, 'qnt/vault/chroma_db')

# Ensure path exists with correct permissions
os.makedirs(CHROMA_PATH, exist_ok=True)

# Initialize ChromaDB client
client = chromadb.PersistentClient(
    path=CHROMA_PATH,
    settings=Settings(anonymized_telemetry=False)
)

COLLECTIONS = ["journal", "trade_memory", "strategies", "market_events", "patterns"]

def now_utc():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def get_or_create_collection(name):
    """Returns a ChromaDB collection, creates if not exists."""
    return client.get_or_create_collection(name=name)

def add_entry(collection_name, content, metadata=None, entry_id=None):
    """Add a document to the vault."""
    if not entry_id:
        entry_id = str(uuid.uuid4())
    
    if not metadata:
        metadata = {}
    
    # Ensure all metadata values are strings or basic types allowed by Chroma
    processed_metadata = {}
    for k, v in metadata.items():
        if v is None: continue
        processed_metadata[k] = str(v)

    collection = get_or_create_collection(collection_name)
    collection.add(
        documents=[content],
        metadatas=[processed_metadata],
        ids=[entry_id]
    )
    return entry_id

def search(query, collection_name=None, n_results=5, filters=None):
    """Semantic search across the vault."""
    results_list = []
    
    search_collections = [collection_name] if collection_name else COLLECTIONS
    
    for coll_name in search_collections:
        try:
            collection = client.get_collection(name=coll_name)
            res = collection.query(
                query_texts=[query],
                n_results=n_results,
                where=filters
            )
            
            # Reformat Chroma results into a flat list
            if res['documents']:
                for i in range(len(res['documents'][0])):
                    results_list.append({
                        "content": res['documents'][0][i],
                        "metadata": res['metadatas'][0][i],
                        "distance": res['distances'][0][i] if 'distances' in res and res['distances'] else 0,
                        "collection": coll_name
                    })
        except Exception:
            # Collection might not exist yet
            continue
            
    # Sort by distance (smaller is more similar)
    results_list.sort(key=lambda x: x['distance'])
    return results_list[:n_results]

def format_results(results):
    """Format search results for display."""
    if not results:
        return "No matching records found in the vault."
    
    output = ["🔍 QNT Recall — Semantic Search Results", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    for i, res in enumerate(results, 1):
        meta = res['metadata']
        ts = meta.get('timestamp', 'unknown')
        coll = res['collection']
        content = res['content'].strip()
        tags = meta.get('tags', 'none')
        outcome = meta.get('outcome', 'N/A')
        
        output.append(f"[{i}] [{coll.upper()}] [{ts}]")
        # Truncate content for display
        display_content = (content[:200] + '...') if len(content) > 200 else content
        output.append(display_content)
        output.append(f"Tags: {tags} | Outcome: {outcome}")
        output.append("───────────────────────────────────")
        
    return "\n".join(output)

def journal_entry(note, tags=None):
    """Add a manual journal entry."""
    device_info = get_device_identity()
    metadata = {
        "timestamp": now_utc(),
        "device": device_info['device'],
        "category": "note",
        "tags": tags or "manual",
        "source": "aatif"
    }
    
    entry_id = add_entry("journal", note, metadata)
    log_action('journal_entry_saved', f"ID: {entry_id}", device_info['device'])
    return "Journal entry saved."

def add_trade_memory(trade_dict, analysis):
    """Store trade outcome with AI analysis."""
    content = f"""
Trade: {trade_dict.get('pair', 'unknown')}
Direction: {trade_dict.get('is_short', False) and 'SHORT' or 'LONG'}
Entry: {trade_dict.get('open_rate', '0')}
Exit: {trade_dict.get('close_rate', '0')}
Profit: {trade_dict.get('profit_abs', 0)} USDT ({trade_dict.get('profit_ratio', 0)*100:.2f}%)
Duration: {trade_dict.get('duration', 'unknown')}
Strategy: {trade_dict.get('strategy', 'unknown')}
Analysis: {analysis}
"""
    
    metadata = {
        "timestamp": trade_dict.get('close_date', now_utc()),
        "device": "M1",
        "category": "trade",
        "tags": f"{trade_dict.get('pair', 'unknown')},{trade_dict.get('strategy', 'unknown')}",
        "outcome": "profit" if trade_dict.get('profit_abs', 0) > 0 else "loss",
        "profit_usdt": str(trade_dict.get('profit_abs', 0)),
        "strategy": trade_dict.get('strategy', 'unknown')
    }
    
    add_entry("trade_memory", content, metadata)

def add_pattern(pattern_description, pattern_type, examples=None):
    """Store a discovered pattern in the library."""
    content = f"""
Pattern: {pattern_description}
Type: {pattern_type}
Examples: {examples or 'N/A'}
Discovered: {now_utc()}
"""
    
    device_info = get_device_identity()
    metadata = {
        "timestamp": now_utc(),
        "device": device_info['device'],
        "category": "pattern",
        "tags": pattern_type,
        "pattern_type": pattern_type
    }
    
    add_entry("patterns", content, metadata)

def get_winning_patterns(n=10):
    """Query patterns collection."""
    results = search("winning profitable pattern", collection_name="patterns", n_results=n)
    if not results:
        return "No patterns discovered yet."
    
    output = ["🧬 Discovered Market Patterns", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    for i, res in enumerate(results, 1):
        output.append(f"{i}. {res['content'].strip()}")
    return "\n".join(output)

def get_collection_stats():
    """Return count of entries per collection."""
    output = ["📚 QNT Vault Statistics", "━━━━━━━━━━━━━━━━━━━━━━━"]
    total = 0
    
    for coll_name in COLLECTIONS:
        try:
            coll = client.get_collection(name=coll_name)
            count = coll.count()
            output.append(f"{coll_name.replace('_', ' ').capitalize():<18}: {count}")
            total += count
        except Exception:
            output.append(f"{coll_name.replace('_', ' ').capitalize():<18}: 0")
            
    output.append("━━━━━━━━━━━━━━━━━━━━━━━")
    output.append(f"Total Entries     : {total}")
    
    # Estimate size (very rough)
    try:
        size_bytes = 0
        for root, dirs, files in os.walk(CHROMA_PATH):
            for f in files:
                size_bytes += os.path.getsize(os.path.join(root, f))
        size_mb = size_bytes / (1024 * 1024)
        output.append(f"ChromaDB Size     : {size_mb:.2f} MB")
    except Exception:
        pass
        
    return "\n".join(output)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "stats":
            print(get_collection_stats())
