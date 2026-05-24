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
    """Read and validate thesis JSON. Returns fallback HOLD if missing, stale, or low confidence."""
    slug = pair.replace("/", "_")
    path = thesis_dir / f"{slug}.json"

    if not path.exists():
        return {**_FALLBACK, "reasoning": f"No thesis file for {pair}"}

    try:
        thesis = json.loads(path.read_text())
    except Exception:
        return {**_FALLBACK, "reasoning": "Thesis file unreadable"}

    generated_at = thesis.get("generated_at", "")
    try:
        ts = datetime.fromisoformat(generated_at)
        age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
        if age_hours > STALE_HOURS:
            return {**_FALLBACK, "reasoning": f"Thesis stale ({age_hours:.1f}h old)"}
    except Exception:
        return {**_FALLBACK, "reasoning": "Thesis timestamp invalid"}

    if thesis.get("confidence", 0.0) < MIN_CONFIDENCE:
        return {**_FALLBACK, "reasoning": f"Thesis confidence too low ({thesis.get('confidence', 0):.2f})"}

    return thesis
