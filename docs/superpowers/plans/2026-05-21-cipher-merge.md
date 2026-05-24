# Cipher Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge Cipher + TradingAgents into a single system with a CLI-driven thesis layer (claude + gemini + qnt), upgraded Qdrant vault, CryptoBERT sentiment, and HMM+LSTM regime detection.

**Architecture:** Additive — new `qnt/thesis/` module runs every 4h per pair, producing a BUY/HOLD/SELL bias that strategies check in `confirm_trade_entry`. Three in-place upgrades swap Chroma→Qdrant, FinBERT→CryptoBERT, HMM→HMM+LSTM with identical public interfaces.

**Tech Stack:** Python 3.11, qdrant-client, sentence-transformers, PyTorch (existing), HuggingFace transformers (existing), claude CLI, gemini CLI, qnt CLI tools, unittest

---

## Phase 1 — Qdrant Migration

### Task 1: Install Qdrant and write failing vault tests

**Files:**
- Create: `qnt/vault/test_vault.py`

- [ ] **Step 1: Install qdrant-client**

```bash
cd /Users/aatifquamre/Downloads/Aatif-qmr/cipher
source venv/bin/activate
pip install qdrant-client
```

Expected: `Successfully installed qdrant-client-x.x.x`

- [ ] **Step 2: Write failing tests**

```python
# qnt/vault/test_vault.py
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

class TestVault(unittest.TestCase):

    def test_store_and_recall_lesson(self):
        from qnt.vault.vault import store_lesson, recall_lessons
        ok = store_lesson(
            "test_001",
            "BTC/USDT trade closed at +2.3% profit after RSI divergence",
            {"pair": "BTC/USDT", "profit_ratio": 0.023, "strategy": "MeanReversionV1", "type": "trade_result"}
        )
        self.assertTrue(ok)
        results = recall_lessons("RSI divergence BTC profit")
        self.assertIsNotNone(results)
        self.assertGreater(len(results), 0)

    def test_get_collection_stats(self):
        from qnt.vault.vault import get_collection_stats
        stats = get_collection_stats()
        self.assertIn("entry_count", stats)
        self.assertIsInstance(stats["entry_count"], int)

    def test_add_trade_memory(self):
        from qnt.vault.vault import add_trade_memory
        trade = {"id": 42, "pair": "ETH/USDT", "strategy": "TrendFollowV1"}
        ok = add_trade_memory(trade, "Strong uptrend confirmed by EMA crossover.")
        self.assertTrue(ok)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /Users/aatifquamre/Downloads/Aatif-qmr/cipher
source venv/bin/activate
python -m pytest qnt/vault/test_vault.py -v
```

Expected: FAIL — tests import the old chromadb vault; confirm tests run and fail for the right reason (chromadb import or assertion), not a syntax error.

---

### Task 2: Migrate vault.py to Qdrant

**Files:**
- Modify: `qnt/vault/vault.py`

- [ ] **Step 1: Replace vault.py entirely**

```python
# qnt/vault/vault.py
import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime, timezone

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter
from sentence_transformers import SentenceTransformer

HOME = Path.home()
BASE_DIR = HOME / 'cipher'
sys.path.insert(0, str(BASE_DIR / 'qnt/memory'))

from memory_manager import log_action, get_device_identity

QDRANT_PATH = str(BASE_DIR / 'qnt/vault/qdrant_storage')
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
    client = _client
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def _stable_id(lesson_id: str) -> int:
    """Convert string lesson_id to a stable positive integer for Qdrant."""
    return abs(hash(lesson_id)) % (2 ** 63)


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
        hits = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=n_results,
        )
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
        return {"entry_count": info.points_count, "db_path": QDRANT_PATH}
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
```

- [ ] **Step 2: Run vault tests**

```bash
cd /Users/aatifquamre/Downloads/Aatif-qmr/cipher
source venv/bin/activate
python -m pytest qnt/vault/test_vault.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add qnt/vault/vault.py qnt/vault/test_vault.py
git commit -m "feat: migrate vault from ChromaDB to Qdrant"
```

---

### Task 3: Migrate vault_indexer.py

**Files:**
- Modify: `qnt/vault/vault_indexer.py`

- [ ] **Step 1: Replace `store_lesson` import path (already compatible — vault.py public API unchanged)**

Open `qnt/vault/vault_indexer.py` and verify the import is:
```python
from vault import store_lesson
```
If so, no change needed. Run the existing indexer to confirm it works:

```bash
cd /Users/aatifquamre/Downloads/Aatif-qmr/cipher
source venv/bin/activate
python -c "
import sys; sys.path.insert(0, 'qnt/vault'); sys.path.insert(0, 'qnt/memory')
from vault_indexer import index_new_trades
print('vault_indexer import OK')
"
```

Expected: `vault_indexer import OK` (no errors).

- [ ] **Step 2: Verify recall_lessons format change does not break skeptic.py**

`recall_lessons` now returns `[{"id", "document", "metadata", "score"}]` instead of Chroma's `{"ids": [[...]], "documents": [[...]], "metadatas": [[...]]}`. Check if skeptic uses the old format:

```bash
grep -n "recall_lessons\|vault_recall\|documents\|metadatas" qnt/agents/skeptic.py 2>/dev/null | head -20
```

If skeptic.py accesses `results["documents"][0]` (Chroma format), update those lines to `results[0]["document"]` (new format). If skeptic.py does not use `recall_lessons` directly, no change needed.

- [ ] **Step 2: Commit if any changes were needed, otherwise note no change required**

```bash
git add qnt/vault/vault_indexer.py
git commit -m "chore: verify vault_indexer compatible with Qdrant vault" --allow-empty
```

---

### Task 4: Remove chromadb from requirements

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Remove chromadb and add qdrant-client**

```bash
cd /Users/aatifquamre/Downloads/Aatif-qmr/cipher
source venv/bin/activate
grep -n "chroma" requirements.txt
```

Note the line number, then remove it:

```bash
sed -i '' '/chromadb/d' requirements.txt
```

Then verify `qdrant-client` is listed (add if missing):

```bash
grep "qdrant-client" requirements.txt || echo "qdrant-client" >> requirements.txt
```

- [ ] **Step 2: Confirm vault still works after requirements change**

```bash
python -m pytest qnt/vault/test_vault.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: replace chromadb with qdrant-client in requirements"
```

---

## Phase 2 — CryptoBERT Sentiment Upgrade

### Task 5: Write failing sentiment test

**Files:**
- Create: `sentiment/test_pipeline.py`

- [ ] **Step 1: Write failing test**

```python
# sentiment/test_pipeline.py
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

class TestSentimentPipeline(unittest.TestCase):

    def test_score_returns_float_in_range(self):
        from sentiment.pipeline import score_with_finbert
        titles = ["Bitcoin surges to new all time high", "Crypto market crashes on Fed news"]
        score = score_with_finbert(titles)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, -1.0)
        self.assertLessEqual(score, 1.0)

    def test_score_bullish_titles_positive(self):
        from sentiment.pipeline import score_with_finbert
        titles = ["BTC moon breakout bullish rally surge", "Crypto bull run gains accelerate"]
        score = score_with_finbert(titles)
        self.assertGreater(score, 0.0)

    def test_score_bearish_titles_negative(self):
        from sentiment.pipeline import score_with_finbert
        titles = ["Bitcoin crash dumps 20% red sell", "Crypto bear market FUD collapse"]
        score = score_with_finbert(titles)
        self.assertLess(score, 0.0)

    def test_empty_titles_returns_zero(self):
        from sentiment.pipeline import score_with_finbert
        self.assertEqual(score_with_finbert([]), 0.0)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify tests pass with current FinBERT (baseline)**

```bash
cd /Users/aatifquamre/Downloads/Aatif-qmr/cipher
source venv/bin/activate
python -m pytest sentiment/test_pipeline.py -v
```

Expected: All tests PASS (baseline with FinBERT). If any fail, note — they must pass after CryptoBERT swap too.

---

### Task 6: Swap FinBERT → CryptoBERT

**Files:**
- Modify: `sentiment/pipeline.py`

- [ ] **Step 1: Update model name and label mapping**

In `sentiment/pipeline.py`, find and replace:

```python
# OLD (around line 28-30)
def load_finbert():
    global finbert_nlp
    if finbert_nlp is None:
        try:
            from transformers import pipeline
            finbert_nlp = pipeline("sentiment-analysis", model="ProsusAI/finbert")
```

Replace with:

```python
def load_finbert():
    global finbert_nlp
    if finbert_nlp is None:
        try:
            from transformers import pipeline
            finbert_nlp = pipeline("sentiment-analysis", model="ElKulako/cryptobert")
```

- [ ] **Step 2: Update label mapping in score_with_finbert**

Find the label comparison block (around line 46-49):

```python
# OLD
        for r in results:
            if r['label'] == 'positive': score += 1.0
            elif r['label'] == 'negative': score -= 1.0
```

Replace with:

```python
        for r in results:
            label = r['label'].lower()
            if label in ('positive', 'bullish'): score += 1.0
            elif label in ('negative', 'bearish'): score -= 1.0
```

- [ ] **Step 3: Run sentiment tests**

```bash
cd /Users/aatifquamre/Downloads/Aatif-qmr/cipher
source venv/bin/activate
python -m pytest sentiment/test_pipeline.py -v
```

Note: First run downloads CryptoBERT (~440MB). Expected: All 4 tests PASS.

- [ ] **Step 4: Run full pipeline manually to confirm output in expected range**

```bash
python -c "
import sys; sys.path.insert(0, '.')
from sentiment.pipeline import score_with_finbert
print(score_with_finbert(['Bitcoin rally continues', 'ETH breaks resistance']))
"
```

Expected: float between -1.0 and 1.0, printed to stdout.

- [ ] **Step 5: Commit**

```bash
git add sentiment/pipeline.py sentiment/test_pipeline.py
git commit -m "feat: upgrade sentiment model from FinBERT to CryptoBERT"
```

---

## Phase 3 — HMM + LSTM Regime Upgrade

### Task 7: Write failing regime tests

**Files:**
- Create: `qnt/oracle/test_hmm_regime.py`

- [ ] **Step 1: Write failing tests**

```python
# qnt/oracle/test_hmm_regime.py
import unittest
import numpy as np
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def _make_dataframe(n=150):
    """Create a minimal OHLCV dataframe for testing."""
    np.random.seed(42)
    close = 50000 + np.cumsum(np.random.randn(n) * 100)
    return pd.DataFrame({
        "open": close * 0.999,
        "high": close * 1.001,
        "low": close * 0.998,
        "close": close,
        "volume": np.random.uniform(100, 500, n),
    })

class TestHMMRegime(unittest.TestCase):

    def test_detect_regime_returns_valid_string(self):
        from qnt.oracle.hmm_regime import detect_regime
        df = _make_dataframe()
        result = detect_regime(df, "BTC/USDT")
        self.assertIn(result, ("BULL", "BEAR", "RANGING"))

    def test_detect_regime_full_returns_dict(self):
        from qnt.oracle.hmm_regime import detect_regime_full
        df = _make_dataframe()
        result = detect_regime_full(df, "BTC/USDT")
        self.assertIn("current_regime", result)
        self.assertIn("next_regime", result)
        self.assertIn("confidence", result)
        self.assertIn(result["current_regime"], ("BULL", "BEAR", "RANGING"))
        self.assertIn(result["next_regime"], ("BULL", "BEAR", "RANGING"))
        self.assertGreaterEqual(result["confidence"], 0.0)
        self.assertLessEqual(result["confidence"], 1.0)

    def test_detect_regime_full_graceful_on_short_data(self):
        from qnt.oracle.hmm_regime import detect_regime_full
        df = _make_dataframe(n=5)
        result = detect_regime_full(df, "BTC/USDT")
        self.assertEqual(result["current_regime"], "RANGING")
        self.assertEqual(result["next_regime"], "RANGING")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to confirm test_detect_regime_full_returns_dict fails**

```bash
cd /Users/aatifquamre/Downloads/Aatif-qmr/cipher
source venv/bin/activate
python -m pytest qnt/oracle/test_hmm_regime.py -v
```

Expected: `test_detect_regime_returns_valid_string` PASS (existing function), `test_detect_regime_full_*` FAIL with `ImportError: cannot import name 'detect_regime_full'`.

---

### Task 8: Add LSTM layer to hmm_regime.py

**Files:**
- Modify: `qnt/oracle/hmm_regime.py`
- Create: `qnt/oracle/train_regime_lstm.py`

- [ ] **Step 1: Add detect_regime_full and LSTM inference to hmm_regime.py**

Add the following to the **end** of `qnt/oracle/hmm_regime.py` (after the existing `get_regime_for_strategy` function):

```python
import torch
import torch.nn as nn


class RegimeLSTM(nn.Module):
    def __init__(self, input_size=1, hidden_size=64, num_layers=1, num_classes=3):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, num_classes)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


_REGIME_LABELS = {0: "BEAR", 1: "RANGING", 2: "BULL"}
_lstm_model = None


def _load_lstm_model():
    global _lstm_model
    if _lstm_model is not None:
        return _lstm_model

    local_path = BASE_DIR / "qnt/oracle/lstm_regime_model.pt"
    m2_path = "/Users/azmatsaif/cipher/qnt/oracle/lstm_regime_model.pt"
    m2_ip = "100.74.110.36"

    if not local_path.exists():
        import subprocess
        try:
            subprocess.run(
                ["scp", f"azmatsaif@{m2_ip}:{m2_path}", str(local_path)],
                check=True, timeout=30
            )
        except Exception as e:
            print(f"LSTM model SCP failed: {e}")
            return None

    try:
        model = RegimeLSTM()
        model.load_state_dict(torch.load(local_path, map_location="cpu"))
        model.eval()
        _lstm_model = model
        return _lstm_model
    except Exception as e:
        print(f"LSTM model load failed: {e}")
        return None


def detect_regime_full(dataframe: pd.DataFrame, pair: str = "BTC/USDT") -> dict:
    """
    Returns current + predicted next regime with confidence.
    Falls back to detect_regime() when LSTM model unavailable.
    """
    current = detect_regime(dataframe, pair)
    default = {"current_regime": current, "next_regime": current, "confidence": 0.5}

    if len(dataframe) < 20:
        return {"current_regime": "RANGING", "next_regime": "RANGING", "confidence": 0.5}

    model = _load_lstm_model()
    if model is None:
        return default

    try:
        returns = (
            np.log(dataframe["close"] / dataframe["close"].shift(1))
            .dropna()
            .values[-20:]
            .astype(np.float32)
        )
        if len(returns) < 20:
            return default

        x = torch.tensor(returns).unsqueeze(0).unsqueeze(-1)  # (1, 20, 1)
        with torch.no_grad():
            logits = model(x)
            probs = torch.softmax(logits, dim=-1).squeeze().numpy()

        next_idx = int(np.argmax(probs))
        confidence = float(probs[next_idx])
        return {
            "current_regime": current,
            "next_regime": _REGIME_LABELS[next_idx],
            "confidence": round(confidence, 3),
        }
    except Exception as e:
        print(f"LSTM inference error: {e}")
        return default
```

- [ ] **Step 2: Create LSTM training script (runs on M2)**

```python
# qnt/oracle/train_regime_lstm.py
"""
Run on M2 (Wednesday 2am via cron).
Trains LSTM on HMM-labeled historical returns.
Saves model to qnt/oracle/lstm_regime_model.pt
"""
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from pathlib import Path
import joblib
import sys

HOME = Path.home()
BASE_DIR = HOME / 'cipher'
sys.path.insert(0, str(BASE_DIR / 'qnt/oracle'))

from hmm_regime import load_hmm_model, RegimeLSTM, _REGIME_LABELS

SEQ_LEN = 20
EPOCHS = 30
BATCH = 64
LR = 1e-3
LABEL_MAP = {"BEAR": 0, "RANGING": 1, "BULL": 2}


def load_returns_from_data() -> np.ndarray:
    data_path = BASE_DIR / 'data/BTC_USDT_1h.csv'
    if not data_path.exists():
        raise FileNotFoundError(f"Training data not found: {data_path}")
    df = pd.read_csv(data_path, parse_dates=['date'])
    df = df.sort_values('date').reset_index(drop=True)
    return np.log(df['close'] / df['close'].shift(1)).dropna().values.astype(np.float32)


def label_with_hmm(returns: np.ndarray) -> np.ndarray:
    model_data = load_hmm_model()
    if model_data is None:
        raise RuntimeError("HMM model not available for labeling")
    model = model_data['model'] if isinstance(model_data, dict) else model_data
    state_map = model_data.get('state_map', {0: "BEAR", 1: "RANGING", 2: "BULL"}) if isinstance(model_data, dict) else {0: "BEAR", 1: "RANGING", 2: "BULL"}

    raw_states = model.predict(returns.reshape(-1, 1))

    def map_state(s):
        label = state_map.get(s, "RANGING")
        if label == "TRENDING_UP": label = "BULL"
        elif label in ("TRENDING_DOWN", "VOLATILE"): label = "BEAR"
        return LABEL_MAP.get(label, 1)

    return np.array([map_state(s) for s in raw_states])


def build_sequences(returns: np.ndarray, labels: np.ndarray):
    X, y = [], []
    for i in range(SEQ_LEN, len(returns)):
        X.append(returns[i - SEQ_LEN:i])
        y.append(labels[i])
    return (
        torch.tensor(np.array(X)).unsqueeze(-1),  # (N, SEQ_LEN, 1)
        torch.tensor(np.array(y), dtype=torch.long),
    )


def train():
    print("Loading returns...")
    returns = load_returns_from_data()
    print("Labeling with HMM...")
    labels = label_with_hmm(returns)

    X, y = build_sequences(returns, labels)
    dataset = TensorDataset(X, y)
    loader = DataLoader(dataset, batch_size=BATCH, shuffle=True)

    model = RegimeLSTM()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    criterion = nn.CrossEntropyLoss()

    model.train()
    for epoch in range(EPOCHS):
        total_loss = 0
        for xb, yb in loader:
            optimizer.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        if (epoch + 1) % 5 == 0:
            print(f"Epoch {epoch+1}/{EPOCHS} — loss: {total_loss/len(loader):.4f}")

    out_path = BASE_DIR / 'qnt/oracle/lstm_regime_model.pt'
    torch.save(model.state_dict(), out_path)
    print(f"LSTM model saved to {out_path}")


if __name__ == "__main__":
    train()
```

- [ ] **Step 3: Run regime tests**

```bash
cd /Users/aatifquamre/Downloads/Aatif-qmr/cipher
source venv/bin/activate
python -m pytest qnt/oracle/test_hmm_regime.py -v
```

Expected: All 3 tests PASS. `detect_regime_full` returns default values when no LSTM model is present (graceful fallback).

- [ ] **Step 4: Commit**

```bash
git add qnt/oracle/hmm_regime.py qnt/oracle/train_regime_lstm.py qnt/oracle/test_hmm_regime.py
git commit -m "feat: upgrade regime detection with HMM+LSTM hybrid"
```

---

## Phase 4 — Thesis Pipeline

### Task 9: Build cli_caller.py

**Files:**
- Create: `qnt/thesis/cli_caller.py`
- Create: `qnt/thesis/test_cli_caller.py`

- [ ] **Step 1: Write failing test**

```python
# qnt/thesis/test_cli_caller.py
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

class TestCliCaller(unittest.TestCase):

    def test_extract_json_from_plain_output(self):
        from qnt.thesis.cli_caller import extract_json
        output = 'Some preamble text\n{"bias": "BUY", "confidence": 0.8}\ntrailing text'
        result = extract_json(output)
        self.assertEqual(result["bias"], "BUY")
        self.assertAlmostEqual(result["confidence"], 0.8)

    def test_extract_json_raises_on_no_json(self):
        from qnt.thesis.cli_caller import extract_json
        with self.assertRaises(ValueError):
            extract_json("This output has no JSON in it at all")

    def test_call_cli_timeout_returns_none(self):
        from qnt.thesis.cli_caller import call_cli
        # Use a command that sleeps longer than timeout
        result = call_cli("sleep", "5", timeout=1)
        self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/aatifquamre/Downloads/Aatif-qmr/cipher
source venv/bin/activate
python -m pytest qnt/thesis/test_cli_caller.py -v 2>&1 | head -20
```

Expected: FAIL — `ModuleNotFoundError: No module named 'qnt.thesis'`

- [ ] **Step 3: Create qnt/thesis/__init__.py**

```bash
mkdir -p /Users/aatifquamre/Downloads/Aatif-qmr/cipher/qnt/thesis
touch /Users/aatifquamre/Downloads/Aatif-qmr/cipher/qnt/thesis/__init__.py
```

- [ ] **Step 4: Implement cli_caller.py**

```python
# qnt/thesis/cli_caller.py
import json
import re
import subprocess
from typing import Optional


def extract_json(text: str) -> dict:
    """Extract first JSON object from CLI output text."""
    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}', text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in output: {text[:300]}")
    return json.loads(match.group())


def call_cli(cli_name: str, prompt: str, timeout: int = 60) -> Optional[dict]:
    """
    Call claude or gemini CLI with -p flag.
    Returns parsed JSON dict or None on failure/timeout.
    """
    try:
        result = subprocess.run(
            [cli_name, "-p", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout.strip()
        if not output:
            print(f"[cli_caller] {cli_name} returned empty output (stderr: {result.stderr[:200]})")
            return None
        return extract_json(output)
    except subprocess.TimeoutExpired:
        print(f"[cli_caller] {cli_name} timed out after {timeout}s")
        return None
    except json.JSONDecodeError as e:
        print(f"[cli_caller] JSON parse error from {cli_name}: {e}")
        return None
    except Exception as e:
        print(f"[cli_caller] Unexpected error calling {cli_name}: {e}")
        return None
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest qnt/thesis/test_cli_caller.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add qnt/thesis/__init__.py qnt/thesis/cli_caller.py qnt/thesis/test_cli_caller.py
git commit -m "feat: add cli_caller subprocess wrapper for thesis pipeline"
```

---

### Task 10: Build context_builder.py

**Files:**
- Create: `qnt/thesis/context_builder.py`
- Create: `qnt/thesis/test_context_builder.py`

- [ ] **Step 1: Write failing test**

```python
# qnt/thesis/test_context_builder.py
import unittest
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

class TestContextBuilder(unittest.TestCase):

    def test_build_context_returns_string(self):
        from qnt.thesis.context_builder import build_context
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "score: 0.42"
            mock_run.return_value.returncode = 0
            ctx = build_context("BTC/USDT")
        self.assertIsInstance(ctx, str)
        self.assertIn("BTC/USDT", ctx)

    def test_build_context_includes_all_sections(self):
        from qnt.thesis.context_builder import build_context
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "mock output"
            mock_run.return_value.returncode = 0
            ctx = build_context("ETH/USDT")
        for section in ("Sentiment", "Shield", "Balance", "Anomaly", "Calendar"):
            self.assertIn(section, ctx)

    def test_build_context_handles_cli_failure_gracefully(self):
        from qnt.thesis.context_builder import build_context
        with patch("subprocess.run", side_effect=Exception("tool not found")):
            ctx = build_context("SOL/USDT")
        self.assertIsInstance(ctx, str)
        self.assertIn("unavailable", ctx)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest qnt/thesis/test_context_builder.py -v 2>&1 | head -10
```

Expected: FAIL — `cannot import name 'build_context'`

- [ ] **Step 3: Implement context_builder.py**

```python
# qnt/thesis/context_builder.py
import subprocess
from pathlib import Path

HOME = Path.home()
BASE_DIR = HOME / 'cipher'
QNT_BIN = str(BASE_DIR / 'qnt/bin')

_QNT_TOOLS = {
    "Sentiment": "qnt-sentiment",
    "Shield": "qnt-risk-check",
    "Balance": "qnt-balance",
    "Anomaly": "qnt-anomaly",
    "Calendar": "qnt-calendar",
}


def _run_qnt_tool(tool_name: str, timeout: int = 15) -> str:
    try:
        result = subprocess.run(
            [f"{QNT_BIN}/{tool_name}"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout.strip()
        return output if output else "no output"
    except subprocess.TimeoutExpired:
        return "unavailable: timeout"
    except Exception as e:
        return f"unavailable: {e}"


def build_context(pair: str) -> str:
    """Run qnt CLI tools and assemble context block for thesis pipeline."""
    sections = {name: _run_qnt_tool(tool) for name, tool in _QNT_TOOLS.items()}
    lines = [f"LIVE MARKET CONTEXT for {pair} (UTC):"]
    for name, output in sections.items():
        lines.append(f"\n[{name}]\n{output}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest qnt/thesis/test_context_builder.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add qnt/thesis/context_builder.py qnt/thesis/test_context_builder.py
git commit -m "feat: add context_builder for thesis pipeline qnt CLI reads"
```

---

### Task 11: Build prompts.py

**Files:**
- Create: `qnt/thesis/prompts.py`

- [ ] **Step 1: Implement prompts.py**

```python
# qnt/thesis/prompts.py

BULL_PROMPT = """\
You are a crypto bull researcher at a professional trading firm.

{context}

Your task: Make the strongest possible case FOR entering a LONG position on {pair} RIGHT NOW.
- Be specific about price levels, indicators, and signals in the context above.
- Identify the 3 most compelling bullish signals.
- Ignore sentiment you cannot verify from the data provided.

Respond ONLY with valid JSON — no preamble, no trailing text:
{{"case": "<your bullish argument in 2-3 sentences>", "key_signals": ["<signal1>", "<signal2>", "<signal3>"], "confidence": <float 0.0-1.0>}}
"""

BEAR_PROMPT = """\
You are a crypto bear researcher at a professional trading firm.

{context}

Bull researcher's case:
{bull_case}

Your task: Argue AGAINST entering a long position on {pair} RIGHT NOW.
- Directly rebut the bull case with counter-evidence from the context.
- Identify the 3 biggest risks or red flags.
- Do not agree with the bull unless the data absolutely demands it.

Respond ONLY with valid JSON — no preamble, no trailing text:
{{"case": "<your bearish argument in 2-3 sentences>", "key_signals": ["<risk1>", "<risk2>", "<risk3>"], "confidence": <float 0.0-1.0>}}
"""

SYNTHESIS_PROMPT = """\
You are a senior portfolio manager reviewing a bull vs bear debate.

{context}

Bull case (confidence {bull_confidence}):
{bull_case}

Bear case (confidence {bear_confidence}):
{bear_case}

Your task: Make a final trading bias decision for {pair}.
Rules:
- If shield status is RED, output bias: SELL regardless of the debate.
- If anomaly_active is true, reduce confidence by 0.15.
- BUY: stake_modifier 1.5 if confidence > 0.75, else 1.0
- HOLD: stake_modifier 0.5
- SELL: stake_modifier 0.0

Respond ONLY with valid JSON — no preamble, no trailing text:
{{"bias": "<BUY|HOLD|SELL>", "confidence": <float 0.0-1.0>, "reasoning": "<1-2 sentence explanation>", "stake_modifier": <0.0|0.5|1.0|1.5>, "key_risks": ["<risk1>", "<risk2>"]}}
"""
```

- [ ] **Step 2: Verify import works**

```bash
cd /Users/aatifquamre/Downloads/Aatif-qmr/cipher
source venv/bin/activate
python -c "from qnt.thesis.prompts import BULL_PROMPT, BEAR_PROMPT, SYNTHESIS_PROMPT; print('prompts OK')"
```

Expected: `prompts OK`

- [ ] **Step 3: Commit**

```bash
git add qnt/thesis/prompts.py
git commit -m "feat: add thesis pipeline prompt templates"
```

---

### Task 12: Build thesis_runner.py

**Files:**
- Create: `qnt/thesis/thesis_runner.py`
- Create: `qnt/thesis/test_thesis_runner.py`

- [ ] **Step 1: Write failing test**

```python
# qnt/thesis/test_thesis_runner.py
import unittest
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

MOCK_BULL = {"case": "Strong RSI divergence", "key_signals": ["RSI", "volume", "funding"], "confidence": 0.8}
MOCK_BEAR = {"case": "OI too high risk", "key_signals": ["OI spike", "fear", "macro"], "confidence": 0.4}
MOCK_SYNTHESIS = {"bias": "BUY", "confidence": 0.75, "reasoning": "Bull wins", "stake_modifier": 1.0, "key_risks": ["macro"]}

class TestThesisRunner(unittest.TestCase):

    def test_run_thesis_writes_valid_json(self):
        from qnt.thesis.thesis_runner import run_thesis
        with patch("qnt.thesis.thesis_runner.build_context", return_value="mock context"), \
             patch("qnt.thesis.thesis_runner.call_cli", side_effect=[MOCK_BULL, MOCK_BEAR, MOCK_SYNTHESIS]), \
             tempfile.TemporaryDirectory() as tmpdir:
            thesis = run_thesis("BTC/USDT", output_dir=Path(tmpdir))

        self.assertEqual(thesis["bias"], "BUY")
        self.assertEqual(thesis["pair"], "BTC/USDT")
        self.assertIn("generated_at", thesis)
        self.assertIn("valid_until", thesis)
        self.assertIn("context_snapshot", thesis)

    def test_run_thesis_falls_back_on_cli_failure(self):
        from qnt.thesis.thesis_runner import run_thesis
        with patch("qnt.thesis.thesis_runner.build_context", return_value="ctx"), \
             patch("qnt.thesis.thesis_runner.call_cli", return_value=None), \
             tempfile.TemporaryDirectory() as tmpdir:
            thesis = run_thesis("ETH/USDT", output_dir=Path(tmpdir))

        self.assertIn(thesis["bias"], ("BUY", "HOLD", "SELL"))
        self.assertLess(thesis["confidence"], 0.5)

    def test_run_thesis_writes_file(self):
        from qnt.thesis.thesis_runner import run_thesis
        with patch("qnt.thesis.thesis_runner.build_context", return_value="ctx"), \
             patch("qnt.thesis.thesis_runner.call_cli", side_effect=[MOCK_BULL, MOCK_BEAR, MOCK_SYNTHESIS]), \
             tempfile.TemporaryDirectory() as tmpdir:
            run_thesis("SOL/USDT", output_dir=Path(tmpdir))
            out_file = Path(tmpdir) / "SOL_USDT.json"
            self.assertTrue(out_file.exists())
            data = json.loads(out_file.read_text())
            self.assertEqual(data["pair"], "SOL/USDT")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest qnt/thesis/test_thesis_runner.py -v 2>&1 | head -10
```

Expected: FAIL — `cannot import name 'run_thesis'`

- [ ] **Step 3: Implement thesis_runner.py**

```python
# qnt/thesis/thesis_runner.py
import json
import sys
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

HOME = Path.home()
BASE_DIR = HOME / 'cipher'
DEFAULT_OUTPUT_DIR = BASE_DIR / 'thesis'

sys.path.insert(0, str(BASE_DIR))

from qnt.thesis.context_builder import build_context
from qnt.thesis.cli_caller import call_cli
from qnt.thesis.prompts import BULL_PROMPT, BEAR_PROMPT, SYNTHESIS_PROMPT


def _default_thesis(pair: str, reason: str = "cli_unavailable") -> dict:
    now = datetime.now(timezone.utc)
    return {
        "pair": pair,
        "bias": "HOLD",
        "confidence": 0.1,
        "stake_modifier": 0.5,
        "reasoning": f"Default thesis — {reason}",
        "key_risks": ["thesis_pipeline_failure"],
        "bull_confidence": 0.0,
        "bear_confidence": 0.0,
        "valid_until": (now + timedelta(hours=4)).isoformat(),
        "generated_at": now.isoformat(),
        "context_snapshot": {},
    }


def _extract_snapshot(context: str) -> dict:
    """Pull key values from context block for storage."""
    snapshot = {}
    for line in context.splitlines():
        if "score:" in line.lower():
            try:
                snapshot["sentiment_score"] = float(line.split(":")[-1].strip().split()[0])
            except Exception:
                pass
        if "GREEN" in line:
            snapshot["shield_status"] = "GREEN"
        elif "YELLOW" in line:
            snapshot["shield_status"] = "YELLOW"
        elif "RED" in line:
            snapshot["shield_status"] = "RED"
    snapshot.setdefault("shield_status", "UNKNOWN")
    return snapshot


def run_thesis(pair: str, output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    history_dir = output_dir / "history"
    history_dir.mkdir(exist_ok=True)

    now = datetime.now(timezone.utc)
    context = build_context(pair)
    snapshot = _extract_snapshot(context)

    # Hard-bail if shield is RED — no need to run LLMs
    if snapshot.get("shield_status") == "RED":
        thesis = _default_thesis(pair, "shield_RED")
        thesis["bias"] = "SELL"
        thesis["confidence"] = 1.0
        thesis["reasoning"] = "Shield status RED — all entries blocked."
        thesis["context_snapshot"] = snapshot
    else:
        bull = call_cli(
            "gemini",
            BULL_PROMPT.format(context=context, pair=pair),
            timeout=60,
        )
        bear = call_cli(
            "gemini",
            BEAR_PROMPT.format(
                context=context,
                pair=pair,
                bull_case=json.dumps(bull) if bull else "unavailable",
            ),
            timeout=60,
        )

        if bull is None and bear is None:
            return _default_thesis(pair, "gemini_unavailable")

        synthesis = call_cli(
            "claude",
            SYNTHESIS_PROMPT.format(
                context=context,
                pair=pair,
                bull_case=json.dumps(bull) if bull else "no bull case",
                bear_case=json.dumps(bear) if bear else "no bear case",
                bull_confidence=bull.get("confidence", 0.0) if bull else 0.0,
                bear_confidence=bear.get("confidence", 0.0) if bear else 0.0,
            ),
            timeout=60,
        )

        if synthesis is None:
            synthesis = {
                "bias": "HOLD",
                "confidence": 0.3,
                "reasoning": "Synthesis unavailable — defaulting to HOLD.",
                "stake_modifier": 0.5,
                "key_risks": ["claude_unavailable"],
            }

        thesis = {
            "pair": pair,
            "bias": synthesis.get("bias", "HOLD"),
            "confidence": synthesis.get("confidence", 0.3),
            "stake_modifier": synthesis.get("stake_modifier", 0.5),
            "reasoning": synthesis.get("reasoning", ""),
            "key_risks": synthesis.get("key_risks", []),
            "bull_confidence": bull.get("confidence", 0.0) if bull else 0.0,
            "bear_confidence": bear.get("confidence", 0.0) if bear else 0.0,
            "valid_until": (now + timedelta(hours=4)).isoformat(),
            "generated_at": now.isoformat(),
            "context_snapshot": snapshot,
        }

    # Atomic write: write to tmp, rename
    pair_slug = pair.replace("/", "_")
    out_path = output_dir / f"{pair_slug}.json"
    tmp_path = output_dir / f"{pair_slug}.json.tmp"
    tmp_path.write_text(json.dumps(thesis, indent=2))
    tmp_path.rename(out_path)

    # Archive
    ts = now.strftime("%Y-%m-%dT%H-%M")
    archive_path = history_dir / f"{pair_slug}_{ts}.json"
    archive_path.write_text(json.dumps(thesis, indent=2))

    print(f"[thesis] {pair} → {thesis['bias']} (confidence={thesis['confidence']:.2f})")
    return thesis


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pairs", nargs="+", help="Trading pairs e.g. BTC/USDT ETH/USDT")
    args = parser.parse_args()
    for pair in args.pairs:
        run_thesis(pair)
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest qnt/thesis/test_thesis_runner.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add qnt/thesis/thesis_runner.py qnt/thesis/test_thesis_runner.py
git commit -m "feat: add thesis_runner orchestrating bull/bear/synthesis pipeline"
```

---

### Task 13: Build thesis_reader.py

**Files:**
- Create: `qnt/thesis/thesis_reader.py`
- Create: `qnt/thesis/test_thesis_reader.py`

- [ ] **Step 1: Write failing test**

```python
# qnt/thesis/test_thesis_reader.py
import unittest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def _write_thesis(tmpdir: Path, pair: str, bias: str, confidence: float, minutes_old: int = 30) -> Path:
    slug = pair.replace("/", "_")
    now = datetime.now(timezone.utc)
    thesis = {
        "pair": pair, "bias": bias, "confidence": confidence,
        "stake_modifier": 1.0, "reasoning": "test",
        "key_risks": [], "bull_confidence": 0.7, "bear_confidence": 0.3,
        "valid_until": (now + timedelta(hours=4)).isoformat(),
        "generated_at": (now - timedelta(minutes=minutes_old)).isoformat(),
        "context_snapshot": {"shield_status": "GREEN"},
    }
    path = tmpdir / f"{slug}.json"
    path.write_text(json.dumps(thesis))
    return path

class TestThesisReader(unittest.TestCase):

    def test_read_valid_thesis(self):
        from qnt.thesis.thesis_reader import read_thesis
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_thesis(Path(tmpdir), "BTC/USDT", "BUY", 0.8)
            result = read_thesis("BTC/USDT", thesis_dir=Path(tmpdir))
        self.assertEqual(result["bias"], "BUY")
        self.assertAlmostEqual(result["confidence"], 0.8)

    def test_read_missing_returns_hold(self):
        from qnt.thesis.thesis_reader import read_thesis
        with tempfile.TemporaryDirectory() as tmpdir:
            result = read_thesis("XRP/USDT", thesis_dir=Path(tmpdir))
        self.assertEqual(result["bias"], "HOLD")
        self.assertLess(result["confidence"], 0.5)

    def test_read_stale_returns_hold(self):
        from qnt.thesis.thesis_reader import read_thesis
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_thesis(Path(tmpdir), "ETH/USDT", "BUY", 0.9, minutes_old=400)
            result = read_thesis("ETH/USDT", thesis_dir=Path(tmpdir))
        self.assertEqual(result["bias"], "HOLD")

    def test_low_confidence_returns_hold(self):
        from qnt.thesis.thesis_reader import read_thesis
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_thesis(Path(tmpdir), "SOL/USDT", "BUY", 0.3)
            result = read_thesis("SOL/USDT", thesis_dir=Path(tmpdir))
        self.assertEqual(result["bias"], "HOLD")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest qnt/thesis/test_thesis_reader.py -v 2>&1 | head -10
```

Expected: FAIL — `cannot import name 'read_thesis'`

- [ ] **Step 3: Implement thesis_reader.py**

```python
# qnt/thesis/thesis_reader.py
import json
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
DEFAULT_THESIS_DIR = HOME / 'cipher' / 'thesis'
STALE_HOURS = 6
MIN_CONFIDENCE = 0.5

_FALLBACK = {
    "bias": "HOLD",
    "confidence": 0.0,
    "stake_modifier": 0.5,
    "reasoning": "Thesis unavailable — oracle-only mode",
    "key_risks": ["no_thesis"],
}


def read_thesis(pair: str, thesis_dir: Path = DEFAULT_THESIS_DIR) -> dict:
    """
    Read and validate thesis JSON for a pair.
    Returns fallback HOLD if missing, stale, or low confidence.
    """
    slug = pair.replace("/", "_")
    path = thesis_dir / f"{slug}.json"

    if not path.exists():
        return {**_FALLBACK, "reasoning": f"No thesis file for {pair}"}

    try:
        thesis = json.loads(path.read_text())
    except Exception:
        return {**_FALLBACK, "reasoning": "Thesis file unreadable"}

    # Staleness check
    generated_at = thesis.get("generated_at", "")
    try:
        ts = datetime.fromisoformat(generated_at)
        age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
        if age_hours > STALE_HOURS:
            return {**_FALLBACK, "reasoning": f"Thesis stale ({age_hours:.1f}h old)"}
    except Exception:
        return {**_FALLBACK, "reasoning": "Thesis timestamp invalid"}

    # Confidence gate
    if thesis.get("confidence", 0.0) < MIN_CONFIDENCE:
        return {**_FALLBACK, "reasoning": f"Thesis confidence too low ({thesis.get('confidence', 0):.2f})"}

    return thesis
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest qnt/thesis/test_thesis_reader.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add qnt/thesis/thesis_reader.py qnt/thesis/test_thesis_reader.py
git commit -m "feat: add thesis_reader with stale/confidence validation"
```

---

## Phase 5 — Strategy Integration

### Task 14: Add thesis check to MeanReversionV1

**Files:**
- Modify: `strategies/active/MeanReversionV1.py`

- [ ] **Step 1: Add import at top of MeanReversionV1.py**

Find the imports block (around line 19-20 where `detect_regime` is imported) and add:

```python
from qnt.thesis.thesis_reader import read_thesis
```

- [ ] **Step 2: Add thesis gate in confirm_trade_entry — LAYER 0 before existing checks**

Find `confirm_trade_entry` (line 156). Add a new block **before** the `# --- LAYER 1: RISK & SENTIMENT CHECKS ---` comment:

```python
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: str,
                            side: str, **kwargs) -> bool:

        # --- LAYER 0: THESIS GATE ---
        thesis = read_thesis(pair)
        if thesis["bias"] == "SELL":
            logger.info(f"[THESIS BLOCK] {pair} bias=SELL confidence={thesis['confidence']:.2f} — {thesis['reasoning']}")
            return False
        stake_modifier = thesis.get("stake_modifier", 1.0)

        # --- LAYER 1: RISK & SENTIMENT CHECKS ---
        # (existing code unchanged below)
```

- [ ] **Step 3: Apply stake_modifier to amount before risk check**

Find the line `trade_amount_usdt=amount * rate,` inside the `run_all_checks()` call and update to:

```python
            trade_amount_usdt=amount * rate * stake_modifier,
```

- [ ] **Step 4: Test manually with paper trading — observe-only**

```bash
cd /Users/aatifquamre/Downloads/Aatif-qmr/cipher
source venv/bin/activate
python -c "
import sys; sys.path.insert(0, '.')
from qnt.thesis.thesis_reader import read_thesis
print(read_thesis('BTC/USDT'))
"
```

Expected: Returns HOLD with low confidence (no thesis file yet) — strategy will allow trades but at 0.5 stake. This is correct observe-only behaviour.

- [ ] **Step 5: Commit**

```bash
git add strategies/active/MeanReversionV1.py
git commit -m "feat: add thesis gate to MeanReversionV1 confirm_trade_entry"
```

---

### Task 15: Roll out thesis check to remaining 5 strategies

**Files:**
- Modify: `strategies/active/TrendFollowV1.py`
- Modify: `strategies/active/ScalpV1.py`
- Modify: `strategies/active/DailyTrendV1.py`
- Modify: `strategies/active/SwingV1.py`
- Modify: `strategies/active/MicroScalpV1.py`

- [ ] **Step 1: For each remaining strategy, find confirm_trade_entry and add the same LAYER 0 block**

For each file, add at the top of the imports:
```python
from qnt.thesis.thesis_reader import read_thesis
```

And at the start of `confirm_trade_entry` (before any existing checks):
```python
        # --- LAYER 0: THESIS GATE ---
        thesis = read_thesis(pair)
        if thesis["bias"] == "SELL":
            logger.info(f"[THESIS BLOCK] {pair} bias=SELL confidence={thesis['confidence']:.2f} — {thesis['reasoning']}")
            return False
        stake_modifier = thesis.get("stake_modifier", 1.0)
```

And update the `trade_amount_usdt` arg in `run_all_checks()` to `amount * rate * stake_modifier`.

Note: If a strategy does not have `confirm_trade_entry`, add it:
```python
    def confirm_trade_entry(self, pair, order_type, amount, rate,
                            time_in_force, current_time, entry_tag, side, **kwargs):
        thesis = read_thesis(pair)
        if thesis["bias"] == "SELL":
            return False
        return True
```

- [ ] **Step 2: Verify imports work for all strategies**

```bash
cd /Users/aatifquamre/Downloads/Aatif-qmr/cipher
source venv/bin/activate
python -c "
import sys; sys.path.insert(0, '.')
for s in ['TrendFollowV1','ScalpV1','DailyTrendV1','SwingV1','MicroScalpV1']:
    try:
        __import__(f'strategies.active.{s}')
        print(f'{s}: OK')
    except Exception as e:
        print(f'{s}: ERROR {e}')
"
```

Expected: All 5 print `OK`.

- [ ] **Step 3: Commit**

```bash
git add strategies/active/TrendFollowV1.py strategies/active/ScalpV1.py \
        strategies/active/DailyTrendV1.py strategies/active/SwingV1.py \
        strategies/active/MicroScalpV1.py
git commit -m "feat: add thesis gate to all 5 remaining strategies"
```

---

### Task 16: Add thesis_runner to cron and create thesis output directory

**Files:**
- Modify: `config/crontab_m1.txt`

- [ ] **Step 1: Create thesis output directory and add to .gitignore**

```bash
mkdir -p /Users/aatifquamre/Downloads/Aatif-qmr/cipher/thesis/history
echo "thesis/" >> /Users/aatifquamre/Downloads/Aatif-qmr/cipher/.gitignore
```

- [ ] **Step 2: Add cron entry to config/crontab_m1.txt**

```bash
cat /Users/aatifquamre/Downloads/Aatif-qmr/cipher/config/crontab_m1.txt
```

Add this line to the file (after existing entries):

```
# Thesis pipeline — every 4h
0 */4 * * * cd /Users/aatifquamre/cipher && source venv/bin/activate && python qnt/thesis/thesis_runner.py BTC/USDT ETH/USDT SOL/USDT BNB/USDT XRP/USDT >> logs/thesis.log 2>&1
```

- [ ] **Step 3: Run thesis_runner manually for one pair to verify end-to-end**

```bash
cd /Users/aatifquamre/Downloads/Aatif-qmr/cipher
source venv/bin/activate
python qnt/thesis/thesis_runner.py BTC/USDT
cat thesis/BTC_USDT.json
```

Expected: JSON file created with valid `bias`, `confidence`, `generated_at` fields. `bias` will be HOLD with low confidence until 48h observation period confirms quality.

- [ ] **Step 4: Commit**

```bash
git add config/crontab_m1.txt .gitignore
git commit -m "feat: add thesis_runner cron schedule and output directory"
```

---

### Task 17: Add thesis staleness check to health_check.py

**Files:**
- Modify: `automation/health_check.py`

- [ ] **Step 1: Add thesis check function to health_check.py**

Find the section where health checks are defined (look for functions that return `{"name": ..., "status": ..., "message": ...}` dicts). Add a new check function:

```python
def check_thesis_freshness() -> dict:
    """Verify thesis files are not stale for all trading pairs."""
    pairs = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "BNB_USDT", "XRP_USDT"]
    thesis_dir = BASE_DIR / "thesis"
    stale = []
    missing = []

    for slug in pairs:
        path = thesis_dir / f"{slug}.json"
        if not path.exists():
            missing.append(slug)
            continue
        try:
            import json as _json
            from datetime import datetime, timezone
            data = _json.loads(path.read_text())
            ts = datetime.fromisoformat(data["generated_at"])
            age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            if age_h > 6:
                stale.append(f"{slug}({age_h:.1f}h)")
        except Exception as e:
            stale.append(f"{slug}(unreadable)")

    if missing:
        return {"name": "Thesis Files", "status": "WARN",
                "message": f"Missing thesis for: {', '.join(missing)}", "critical": False}
    if stale:
        return {"name": "Thesis Files", "status": "WARN",
                "message": f"Stale thesis: {', '.join(stale)}", "critical": False}
    return {"name": "Thesis Files", "status": "PASS", "message": "All thesis files fresh"}
```

- [ ] **Step 2: Add check_thesis_freshness to the checks list**

Find where the list of checks is assembled (look for a list like `checks = [check_freqtrade_processes(), check_sentiment_freshness(), ...]`) and add:

```python
        check_thesis_freshness(),
```

- [ ] **Step 3: Verify health_check runs without error**

```bash
cd /Users/aatifquamre/Downloads/Aatif-qmr/cipher
source venv/bin/activate
python -c "
import sys; sys.path.insert(0, '.')
from automation.health_check import check_thesis_freshness
print(check_thesis_freshness())
"
```

Expected: `{"name": "Thesis Files", "status": "WARN", "message": "Missing thesis for: ..."}` — correct, since thesis files don't exist yet.

- [ ] **Step 4: Commit**

```bash
git add automation/health_check.py
git commit -m "feat: add thesis staleness check to health diagnostics"
```

---

## Phase 6 — Cleanup

### Task 18: Delete TradingAgents-0.2.5

**Files:**
- Delete: `TradingAgents-0.2.5/` (entire directory)

- [ ] **Step 1: Confirm no cipher code imports from TradingAgents**

```bash
cd /Users/aatifquamre/Downloads/Aatif-qmr/cipher
grep -r "TradingAgents\|tradingagents\|from tradingagents" \
  --include="*.py" \
  --exclude-dir=TradingAgents-0.2.5 .
```

Expected: No matches. If any matches found, remove those imports before proceeding.

- [ ] **Step 2: Delete directory**

```bash
rm -rf /Users/aatifquamre/Downloads/Aatif-qmr/cipher/TradingAgents-0.2.5
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove TradingAgents-0.2.5 (concepts absorbed into qnt/thesis)"
```

---

### Task 19: Clean requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Remove TradingAgents-only dependencies**

```bash
cd /Users/aatifquamre/Downloads/Aatif-qmr/cipher
for pkg in langchain-core langchain-anthropic langchain-google-genai langchain-openai \
           langchain-experimental langgraph langgraph-checkpoint-sqlite \
           yfinance backtrader stockstats parsel questionary; do
  sed -i '' "/${pkg}/d" requirements.txt
done
```

- [ ] **Step 2: Verify nothing in the active codebase needs these packages**

```bash
grep -r "import langchain\|import langgraph\|import yfinance\|import backtrader\|import stockstats\|import parsel\|import questionary" \
  --include="*.py" \
  --exclude-dir=venv .
```

Expected: No matches.

- [ ] **Step 3: Verify the project still imports cleanly**

```bash
source venv/bin/activate
python -c "
import sys; sys.path.insert(0, '.')
from qnt.thesis.thesis_runner import run_thesis
from qnt.thesis.thesis_reader import read_thesis
from qnt.vault.vault import store_lesson, recall_lessons
from sentiment.pipeline import score_with_finbert
from qnt.oracle.hmm_regime import detect_regime, detect_regime_full
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest qnt/vault/test_vault.py sentiment/test_pipeline.py \
  qnt/oracle/test_hmm_regime.py qnt/thesis/test_cli_caller.py \
  qnt/thesis/test_context_builder.py qnt/thesis/test_thesis_runner.py \
  qnt/thesis/test_thesis_reader.py risk/test_risk_manager.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Final commit**

```bash
git add requirements.txt
git commit -m "chore: remove unused TradingAgents dependencies from requirements.txt"
```

---

## Summary

| Phase | Tasks | Risk | Impact |
|-------|-------|------|--------|
| 1 — Qdrant Migration | 1–4 | Low | vault.py, vault_indexer.py |
| 2 — CryptoBERT | 5–6 | Low | sentiment/pipeline.py (1 line) |
| 3 — HMM+LSTM | 7–8 | Medium | hmm_regime.py (additive) |
| 4 — Thesis Pipeline | 9–13 | Low (new code) | qnt/thesis/ (all new) |
| 5 — Strategy Integration | 14–17 | Medium | all 6 strategies + health_check |
| 6 — Cleanup | 18–19 | Low | delete + requirements |

**Rollback:** Remove 3-line thesis check from any strategy to instantly restore pre-merge behaviour. Each phase is independently reversible.
