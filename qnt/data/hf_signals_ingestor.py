# qnt/data/hf_signals_ingestor.py
# Pulls supplementary signal datasets from HuggingFace:
#   1. flowfree/crypto-news-headlines  → extends news sentiment history
#   2. darkknight25/trading_dataset_v2 → labeled trading signals for cross-reference
import json
import csv
import os
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
BASE_DIR = HOME / 'cipher'
HF_CACHE_DIR = BASE_DIR / 'qnt/data/hf_cache'
NEWS_OUT = BASE_DIR / 'sentiment/scores/hf_news_history.csv'
SIGNALS_OUT = BASE_DIR / 'qnt/data/hf_trading_signals.csv'


def _ingest_news_headlines():
    """Pull crypto news headlines dataset → extend news sentiment corpus."""
    try:
        from datasets import load_dataset
        print('[hf_signals] Loading flowfree/crypto-news-headlines...')
        ds = load_dataset('flowfree/crypto-news-headlines',
                          cache_dir=str(HF_CACHE_DIR),
                          trust_remote_code=True)

        split = ds.get('train') or ds[list(ds.keys())[0]]
        print(f'[hf_signals] {len(split)} news entries found')

        NEWS_OUT.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with open(NEWS_OUT, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['date', 'headline', 'source', 'url'])
            for row in split:
                date = row.get('date', row.get('published_at', row.get('timestamp', '')))
                headline = row.get('headline', row.get('title', row.get('text', '')))
                source = row.get('source', '')
                url = row.get('url', '')
                writer.writerow([date, headline, source, url])
                written += 1

        print(f'[hf_signals] Wrote {written} headlines → {NEWS_OUT}')
        return written
    except Exception as e:
        print(f'[hf_signals] News headlines failed: {e}')
        return 0


def _ingest_trading_signals():
    """Pull labeled trading dataset → cross-reference with strategy signals."""
    try:
        from datasets import load_dataset
        print('[hf_signals] Loading darkknight25/trading_dataset_v2...')
        ds = load_dataset('darkknight25/trading_dataset_v2',
                          cache_dir=str(HF_CACHE_DIR),
                          trust_remote_code=True)

        split = ds.get('train') or ds[list(ds.keys())[0]]
        sample = split[0]
        print(f'[hf_signals] {len(split)} signal entries | columns: {list(sample.keys())[:8]}')

        SIGNALS_OUT.parent.mkdir(parents=True, exist_ok=True)
        with open(SIGNALS_OUT, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(sample.keys()))
            writer.writeheader()
            for row in split:
                writer.writerow(row)

        print(f'[hf_signals] Wrote {len(split)} signal rows → {SIGNALS_OUT}')
        return len(split)
    except Exception as e:
        print(f'[hf_signals] Trading signals failed: {e}')
        return 0


def run():
    HF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    results = {
        'news_headlines': _ingest_news_headlines(),
        'trading_signals': _ingest_trading_signals(),
    }
    print(f'[hf_signals] Done: {results}')
    return results


if __name__ == '__main__':
    run()
