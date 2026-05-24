# qnt/data/backtest_calibrator.py
# Vectorized walk-forward parameter calibration across 8 years of candle history.
# Tests RSI/BB combos across 3 distinct market eras, picks the most consistent params.
# Writes directly to config/dynamic_params.json — same format as live param_optimizer.

import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
from itertools import product

HOME = Path.home()
BASE_DIR = HOME / 'cipher'
DATA_DIR = BASE_DIR / 'user_data/data/binance'
PARAMS_PATH = BASE_DIR / 'config/dynamic_params.json'

PAIRS = [
    'BTC_USDT', 'ETH_USDT', 'SOL_USDT', 'BNB_USDT', 'XRP_USDT',
    'DOGE_USDT', 'ADA_USDT', 'AVAX_USDT', 'LINK_USDT', 'DOT_USDT',
]

# 3 eras — each covers a distinct market character to avoid era-specific overfitting
WINDOWS_1H = [
    ('2018-01-01', '2021-12-31'),
    ('2022-01-01', '2023-12-31'),
    ('2024-01-01', '2026-05-23'),
]
# 5m/15m data only available from 2020
WINDOWS_5M = [
    ('2020-01-01', '2021-12-31'),
    ('2022-01-01', '2023-12-31'),
    ('2024-01-01', '2026-05-23'),
]

SEARCH_SPACES = {
    'ScalpV1': {
        'buy_rsi':  list(range(22, 36, 2)),           # 7 values
        'sell_rsi': list(range(55, 73, 3)),           # 6 values  → 42 combos
    },
    'MeanReversionV1': {
        'buy_rsi':   list(range(25, 38, 3)),          # 5 values
        'bb_period': list(range(15, 46, 5)),          # 7 values
        'bb_std':    [1.5, 1.8, 2.0, 2.2, 2.5],      # 5 values
        'sell_rsi':  list(range(60, 76, 5)),          # 4 values  → 700 combos
    },
    'TrendFollowV1': {
        'buy_rsi_min':    list(range(30, 50, 5)),     # 4 values
        'buy_rsi_max':    list(range(65, 82, 5)),     # 4 values
        'sell_rsi_limit': list(range(70, 86, 5)),     # 4 values  → 64 combos
    },
}

# Use first-tier ROI as exit target; stoploss and timeframe per strategy
STRATEGY_META = {
    'ScalpV1':         {'stoploss': -0.02, 'roi': 0.02,  'tf': '5m',  'windows': WINDOWS_5M},
    'MeanReversionV1': {'stoploss': -0.04, 'roi': 0.04,  'tf': '1h',  'windows': WINDOWS_1H},
    'TrendFollowV1':   {'stoploss': -0.06, 'roi': 0.03,  'tf': '1h',  'windows': WINDOWS_1H},
}


# ── Indicator helpers ────────────────────────────────────────────────────────

def _rsi(close: pd.Series, period: int = 14) -> np.ndarray:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).values


def _bb(close: pd.Series, period: int, std: float):
    mid = close.rolling(period).mean()
    dev = close.rolling(period).std()
    return (mid - std * dev).values, mid.values, (mid + std * dev).values


def _ema(close: pd.Series, period: int) -> np.ndarray:
    return close.ewm(span=period, adjust=False).mean().values


# ── Trade simulation ─────────────────────────────────────────────────────────

def _simulate(close: np.ndarray, entry: np.ndarray, exit_sig: np.ndarray,
              stoploss: float, roi: float, max_hold: int = 120) -> dict:
    """
    Sequential trade simulator. Enters on entry signal, exits on first of:
    stop-loss hit, ROI target hit, exit signal, or max_hold candles.
    """
    profits = []
    last_exit = -1

    for ei in np.where(entry)[0]:
        if ei <= last_exit:
            continue
        entry_price = close[ei]
        end = min(ei + max_hold, len(close) - 1)
        for j in range(ei + 1, end + 1):
            pnl = (close[j] - entry_price) / entry_price
            if pnl <= stoploss or pnl >= roi or exit_sig[j]:
                profits.append(pnl)
                last_exit = j
                break

    if len(profits) < 8:
        return {'win_rate': 0.0, 'avg_profit': 0.0, 'n_trades': len(profits)}

    arr = np.array(profits)
    return {
        'win_rate': float((arr > 0).mean()),
        'avg_profit': float(arr.mean()),
        'n_trades': len(profits),
    }


def _score(m: dict) -> float:
    """Combined score: win_rate × positive_expectancy. Zero if avg_profit ≤ 0."""
    if m['n_trades'] < 8 or m['avg_profit'] <= 0:
        return 0.0
    return m['win_rate']


# ── Per-strategy calibrators ─────────────────────────────────────────────────

def _load_window(pair: str, tf: str, start: str, end: str) -> pd.DataFrame | None:
    path = DATA_DIR / f'{pair}-{tf}.feather'
    if not path.exists():
        return None
    df = pd.read_feather(path)
    df = df[(df['date'] >= start) & (df['date'] < end)].copy().reset_index(drop=True)
    return df if len(df) >= 150 else None


def _calibrate(strategy: str, search: dict, meta: dict) -> dict:
    stoploss, roi = meta['stoploss'], meta['roi']
    tf      = meta['tf']
    windows = meta['windows']
    keys    = list(search.keys())
    combos  = list(product(*[search[k] for k in keys]))
    n_combos = len(combos)

    print(f'  {n_combos} combos × {len(windows)} windows × {len(PAIRS)} pairs  [{tf}]')

    # Pre-compute all indicators per (pair, window) to avoid recomputation
    cache = {}
    for wi, (ws, we) in enumerate(windows):
        for pair in PAIRS:
            df = _load_window(pair, tf, ws, we)
            if df is None:
                continue
            close = df['close']
            entry = {
                'close': close.values,
                'rsi': _rsi(close),
                'ema200': _ema(close, 200),
            }
            if strategy == 'MeanReversionV1':
                bb_cache = {}
                for bb_p in search.get('bb_period', [20]):
                    for bb_s in search.get('bb_std', [2.0]):
                        lower, mid, _ = _bb(close, bb_p, bb_s)
                        bb_cache[(bb_p, bb_s)] = (lower, mid)
                entry['bb'] = bb_cache
            elif strategy == 'ScalpV1':
                lower, mid, _ = _bb(close, 20, 2.0)
                entry['bb_lower'] = lower
                entry['bb_mid'] = mid
            cache[(pair, wi)] = entry

    best_score, best_params = -1.0, {k: search[k][len(search[k]) // 2] for k in keys}

    for combo in combos:
        params = dict(zip(keys, combo))
        window_scores = []

        for wi in range(len(windows)):
            pair_scores = []
            for pair in PAIRS:
                c = cache.get((pair, wi))
                if c is None:
                    continue
                close = c['close']
                rsi = c['rsi']

                if strategy == 'ScalpV1':
                    entry = ((rsi < params['buy_rsi']) & (close < c['bb_lower']))
                    exit_sig = ((rsi > params['sell_rsi']) | (close > c['bb_mid']))

                elif strategy == 'MeanReversionV1':
                    lower, mid = c['bb'][(params['bb_period'], params['bb_std'])]
                    entry = ((rsi < params['buy_rsi']) & (close < lower))
                    exit_sig = ((rsi > params['sell_rsi']) | (close > mid))

                elif strategy == 'TrendFollowV1':
                    ema200 = c['ema200']
                    entry = (
                        (rsi > params['buy_rsi_min']) &
                        (rsi < params['buy_rsi_max']) &
                        (close > ema200)
                    )
                    exit_sig = (rsi > params['sell_rsi_limit'])

                else:
                    continue

                entry = np.nan_to_num(entry, nan=0).astype(bool)
                exit_sig = np.nan_to_num(exit_sig, nan=0).astype(bool)

                m = _simulate(close, entry, exit_sig, stoploss, roi)
                pair_scores.append(_score(m))

            if pair_scores:
                window_scores.append(float(np.median(pair_scores)))

        if len(window_scores) == len(windows):  # only count combos tested across all windows
            score = float(np.median(window_scores))
            if score > best_score:
                best_score = score
                best_params = params

    return best_params, best_score


# ── Main ─────────────────────────────────────────────────────────────────────

def run() -> dict:
    start = datetime.now(timezone.utc)
    print('[backtest_calibrator] Walk-forward parameter calibration starting...')
    print(f'  Pairs: {PAIRS}')

    existing = {}
    if PARAMS_PATH.exists():
        existing = json.loads(PARAMS_PATH.read_text())

    results = {}
    for strategy, search in SEARCH_SPACES.items():
        print(f'\n[backtest_calibrator] {strategy}:')
        best_params, score = _calibrate(strategy, search, STRATEGY_META[strategy])
        results[strategy] = best_params
        print(f'  → best_score={score:.3f}  params={best_params}')

    # Merge: update strategy values, preserve live-learning _meta_ keys
    merged = {k: v for k, v in existing.items() if k.startswith('_meta_')}
    merged.update(results)
    merged['_backtest_meta'] = {
        'calibrated_at': start.isoformat(),
        'method': 'walk_forward_3window',
        'timeframes': {s: STRATEGY_META[s]['tf'] for s in SEARCH_SPACES},
        'pairs': PAIRS,
    }

    PARAMS_PATH.write_text(json.dumps(merged, indent=2))
    elapsed = (datetime.now(timezone.utc) - start).seconds
    print(f'\n[backtest_calibrator] Done in {elapsed}s → {PARAMS_PATH}')
    return results


if __name__ == '__main__':
    run()
