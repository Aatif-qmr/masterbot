# qnt/learning/constraint_extractor.py
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
BASE_DIR = HOME / 'cipher'
sys.path.insert(0, str(BASE_DIR / 'qnt/vault'))
CONSTRAINTS_PATH = BASE_DIR / 'config/vault_constraints.json'

MIN_SAMPLES    = 5      # need at least 5 data points to extract a rule
LOSS_RATE_GATE = 0.60   # 60%+ loss rate in a condition → becomes a constraint


def _sentiment_bucket(score: float) -> str:
    if score < -0.3:
        return 'very_negative'
    if score < 0.0:
        return 'negative'
    if score < 0.3:
        return 'neutral'
    return 'positive'


def _load_vault_losses() -> list:
    try:
        from vault import _get_client, COLLECTION_NAME
        client = _get_client()
        # Scroll all entries
        entries = []
        offset = None
        while True:
            result, next_offset = client.scroll(
                collection_name=COLLECTION_NAME,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in result:
                payload = point.payload
                try:
                    profit = float(payload.get('profit_ratio', payload.get('close_profit', 0)))
                    if profit < -0.01:
                        entries.append(payload)
                except Exception:
                    pass
            if next_offset is None:
                break
            offset = next_offset
        return entries
    except Exception as e:
        print(f'[constraint_extractor] Vault scroll error: {e}')
        return []


def run() -> dict:
    losses = _load_vault_losses()
    print(f'[constraint_extractor] Found {len(losses)} loss entries in vault')

    # Group by (strategy, pair, regime, sentiment_bucket)
    buckets: dict = defaultdict(lambda: {'losses': 0, 'total': 0})

    for entry in losses:
        strategy = entry.get('strategy', '')
        pair = entry.get('pair', '')
        regime = entry.get('regime', entry.get('hmm_regime', ''))
        try:
            sentiment = float(entry.get('sentiment_score', 0))
        except Exception:
            sentiment = 0.0
        sb = _sentiment_bucket(sentiment)

        if strategy and pair:
            key_regime = (strategy, pair, 'regime', regime) if regime else None
            key_sentiment = (strategy, pair, 'sentiment', sb)

            if key_regime:
                buckets[key_regime]['losses'] += 1
                buckets[key_regime]['total'] += 1
            buckets[key_sentiment]['losses'] += 1
            buckets[key_sentiment]['total'] += 1

    # Extract constraints where loss_rate > threshold with enough samples
    constraints: dict = {}

    for (strategy, pair, ctype, cval), counts in buckets.items():
        total = counts['total']
        if total < MIN_SAMPLES:
            continue
        loss_rate = counts['losses'] / total
        if loss_rate < LOSS_RATE_GATE:
            continue

        if strategy not in constraints:
            constraints[strategy] = {}
        if pair not in constraints[strategy]:
            constraints[strategy][pair] = {}

        if ctype == 'regime':
            blocked = constraints[strategy][pair].get('blocked_regimes', [])
            if cval not in blocked:
                blocked.append(cval)
            constraints[strategy][pair]['blocked_regimes'] = blocked
            print(f'  [constraint] {strategy}/{pair}: block regime={cval} '
                  f'(loss_rate={loss_rate:.0%}, n={total})')

        elif ctype == 'sentiment':
            # Map sentiment bucket → min_sentiment threshold
            bucket_thresholds = {
                'very_negative': -0.3,
                'negative':       0.0,
                'neutral':        0.3,
            }
            threshold = bucket_thresholds.get(cval)
            if threshold is not None:
                existing = constraints[strategy][pair].get('min_sentiment', -999)
                if threshold > existing:
                    constraints[strategy][pair]['min_sentiment'] = threshold
                    print(f'  [constraint] {strategy}/{pair}: min_sentiment={threshold} '
                          f'(loss_rate={loss_rate:.0%}, n={total})')

    output = {
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'constraints': constraints,
    }

    CONSTRAINTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONSTRAINTS_PATH.write_text(json.dumps(output, indent=2))
    print(f'[constraint_extractor] Wrote {sum(len(v) for v in constraints.values())} '
          f'strategy-pair rules → {CONSTRAINTS_PATH}')
    return output


if __name__ == '__main__':
    import pprint
    pprint.pprint(run())
