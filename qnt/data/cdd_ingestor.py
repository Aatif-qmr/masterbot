# qnt/data/cdd_ingestor.py
# Downloads extended OHLCV + funding rate history from CryptoDataDownload.
# Merges with existing feather files — fills the gap before 2026-03-06.
import io
import csv
import pandas as pd
import requests
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
BASE_DIR = HOME / 'cipher'
DATA_DIR = BASE_DIR / 'user_data/data/binance'
FUNDING_OUT = BASE_DIR / 'qnt/data/cdd_funding_history.csv'

# CryptoDataDownload URL patterns (no auth required)
CDD_BASE = 'https://www.cryptodatadownload.com/cdd'

PAIR_MAP = {
    'BTC/USDT': 'Binance_BTCUSDT',
    'ETH/USDT': 'Binance_ETHUSDT',
    'SOL/USDT': 'Binance_SOLUSDT',
    'BNB/USDT': 'Binance_BNBUSDT',
    'XRP/USDT': 'Binance_XRPUSDT',
}

TF_MAP = {'1h': '1h', '4h': '4h', '1d': 'd'}

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; cipher-data-ingestor/1.0)'}


def _fetch_csv(url: str) -> pd.DataFrame | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            return None
        # CDD CSVs have a junk first line, skip it
        lines = resp.text.splitlines()
        start = next((i for i, l in enumerate(lines) if l.lower().startswith('unix')), 1)
        content = '\n'.join(lines[start:])
        df = pd.read_csv(io.StringIO(content))
        return df
    except Exception as e:
        print(f'  [cdd] fetch error {url}: {e}')
        return None


def _to_ft_format(df: pd.DataFrame) -> pd.DataFrame | None:
    """Convert CDD dataframe to freqtrade feather format."""
    try:
        col_map = {}
        for c in df.columns:
            lc = c.lower()
            if 'unix' in lc or 'timestamp' in lc:
                col_map[c] = 'ts'
            elif lc == 'open':
                col_map[c] = 'open'
            elif lc == 'high':
                col_map[c] = 'high'
            elif lc == 'low':
                col_map[c] = 'low'
            elif lc == 'close':
                col_map[c] = 'close'
            elif 'volume' in lc and 'usdt' not in lc and col_map.get(c) is None:
                col_map[c] = 'volume'

        df = df.rename(columns=col_map)
        if 'ts' not in df.columns:
            return None

        # CDD mixes ms and μs timestamps: normalize μs (>2e13) → ms
        df['ts'] = df['ts'].where(df['ts'] <= 2e13, df['ts'] / 1000).astype('int64')
        df['date'] = pd.to_datetime(df['ts'], unit='ms', utc=True)
        df = df[['date', 'open', 'high', 'low', 'close', 'volume']].dropna()
        df = df.sort_values('date').reset_index(drop=True)
        return df
    except Exception as e:
        print(f'  [cdd] format error: {e}')
        return None


def _merge_and_save(new_df: pd.DataFrame, feather_path: Path):
    """Prepend new data to existing feather, deduplicate by date."""
    if feather_path.exists():
        existing = pd.read_feather(feather_path)
        combined = pd.concat([new_df, existing], ignore_index=True)
    else:
        combined = new_df

    combined = combined.drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)
    combined.to_feather(feather_path)
    return len(combined)


def ingest_ohlcv(pairs: list = None, timeframes: list = None):
    """Download extended OHLCV from CDD and merge into feather files."""
    pairs = pairs or list(PAIR_MAP.keys())
    timeframes = timeframes or ['1h', '4h']
    results = {}

    for pair in pairs:
        slug = PAIR_MAP.get(pair)
        if not slug:
            continue
        for tf in timeframes:
            tf_slug = TF_MAP.get(tf, tf)
            url = f'{CDD_BASE}/{slug}_{tf_slug}.csv'
            print(f'[cdd] Fetching {pair} {tf} from CDD...')
            raw = _fetch_csv(url)
            if raw is None:
                print(f'  [cdd] No data for {pair} {tf}')
                continue

            ft_df = _to_ft_format(raw)
            if ft_df is None or len(ft_df) == 0:
                continue

            feather_path = DATA_DIR / f'{pair.replace("/", "_")}-{tf}.feather'
            total = _merge_and_save(ft_df, feather_path)
            print(f'  [cdd] {pair} {tf}: {len(ft_df)} new rows → {total} total')
            results[f'{pair}_{tf}'] = total

    return results


def ingest_funding_history():
    """Download extended funding rate history from CDD."""
    # CDD funding data endpoint
    url = f'{CDD_BASE}/Binance_BTCUSDT_funding.csv'
    print('[cdd] Fetching BTC funding rate history...')
    df = _fetch_csv(url)
    if df is None:
        print('[cdd] Funding rate data unavailable')
        return 0

    FUNDING_OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(FUNDING_OUT, index=False)
    print(f'[cdd] Wrote {len(df)} funding rows → {FUNDING_OUT}')
    return len(df)


def run():
    ohlcv_results = ingest_ohlcv()
    funding_count = ingest_funding_history()
    return {'ohlcv': ohlcv_results, 'funding_rows': funding_count}


if __name__ == '__main__':
    run()
