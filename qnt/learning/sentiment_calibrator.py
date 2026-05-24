# qnt/learning/sentiment_calibrator.py
import json
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
BASE_DIR = HOME / 'cipher'
SCORES_PATH      = BASE_DIR / 'qnt/learning/scores.json'
WEIGHTS_PATH     = BASE_DIR / 'config/sentiment_weights.json'

DEFAULTS = {
    'reddit':    0.20,
    'news':      0.20,
    'coingecko': 0.20,
    'feargreed': 0.20,
    'funding':   0.20,
}

BLEND_ALPHA = 0.05   # 5% new signal per cycle — slow, stable convergence
FLOOR       = 0.10   # no source below 10% — all voices represented
CEILING     = 0.35   # no source above 35% — no source dominates


def _load_current_weights() -> dict:
    if WEIGHTS_PATH.exists():
        try:
            return json.loads(WEIGHTS_PATH.read_text())
        except Exception:
            pass
    return DEFAULTS.copy()


def _save_weights(weights: dict):
    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    out = {'updated_at': datetime.now(timezone.utc).isoformat(), 'weights': weights}
    WEIGHTS_PATH.write_text(json.dumps(out, indent=2))


def run() -> dict:
    current = _load_current_weights()
    if isinstance(current.get('weights'), dict):
        current = current['weights']

    scores = {}
    if SCORES_PATH.exists():
        try:
            scores = json.loads(SCORES_PATH.read_text())
        except Exception:
            pass

    correlations = scores.get('sentiment_correlations', {})

    if not correlations:
        print('[sentiment_calibrator] No correlation data yet — keeping current weights')
        _save_weights(current)
        return current

    # Clip negatives to 0, then normalise
    clipped = {k: max(0.0, correlations.get(k, 0.0)) for k in DEFAULTS}
    total = sum(clipped.values())

    if total == 0:
        print('[sentiment_calibrator] All correlations zero or negative — keeping current weights')
        _save_weights(current)
        return current

    normalised = {k: v / total for k, v in clipped.items()}

    # Blend: 80% old weight, 20% new signal
    blended = {
        k: (1 - BLEND_ALPHA) * current.get(k, DEFAULTS[k]) + BLEND_ALPHA * normalised[k]
        for k in DEFAULTS
    }

    # Enforce floor and ceiling, then re-normalise to sum=1
    clipped_blended = {k: max(FLOOR, min(CEILING, v)) for k, v in blended.items()}
    total2 = sum(clipped_blended.values())
    final = {k: round(v / total2, 4) for k, v in clipped_blended.items()}

    for k in DEFAULTS:
        old = round(current.get(k, DEFAULTS[k]), 4)
        new = final[k]
        if abs(new - old) > 0.005:
            print(f'  [sentiment_calibrator] {k}: {old:.4f} → {new:.4f}')

    _save_weights(final)
    print(f'[sentiment_calibrator] Weights updated: {final}')
    return final


if __name__ == '__main__':
    import pprint
    pprint.pprint(run())
