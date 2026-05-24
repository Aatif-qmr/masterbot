# qnt/data/retrain_hmm_extended.py
# Retrains HMM regime model using full extended history (years vs weeks).
# Replaces hmm_model.pkl with a better-calibrated version.
import sys
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
BASE_DIR = HOME / 'cipher'
DATA_DIR = BASE_DIR / 'user_data/data/binance'
MODEL_OUT = BASE_DIR / 'qnt/oracle/hmm_model.pkl'
sys.path.insert(0, str(BASE_DIR))

PAIRS = ['BTC_USDT', 'ETH_USDT', 'SOL_USDT']  # BTC primary, ETH/SOL supplementary
TIMEFRAME = '1h'
N_STATES = 3
MIN_CANDLES = 500


def _load_returns(pair: str, tf: str) -> np.ndarray:
    path = DATA_DIR / f'{pair}-{tf}.feather'
    if not path.exists():
        return np.array([])
    df = pd.read_feather(path)
    df = df.sort_values('date').dropna()
    returns = np.log(df['close'] / df['close'].shift(1)).dropna().values
    return returns.reshape(-1, 1).astype(np.float32)


def _train_hmm(returns: np.ndarray, n_states: int = N_STATES):
    from hmmlearn.hmm import GaussianHMM
    model = GaussianHMM(
        n_components=n_states,
        covariance_type='diag',
        n_iter=200,
        random_state=42,
        tol=1e-4,
    )
    model.fit(returns)
    return model


def _build_state_map(model, returns: np.ndarray) -> dict:
    """Map HMM states to BULL/BEAR/RANGING by mean return."""
    means = model.means_.flatten()
    order = np.argsort(means)  # ascending
    state_map = {}
    state_map[int(order[0])] = 'BEAR'
    state_map[int(order[-1])] = 'BULL'
    # Middle states → RANGING
    for i in range(1, len(order) - 1):
        state_map[int(order[i])] = 'RANGING'
    return state_map


def run():
    all_returns = []
    for pair in PAIRS:
        r = _load_returns(pair, TIMEFRAME)
        if len(r) >= MIN_CANDLES:
            all_returns.append(r)
            print(f'[retrain_hmm] {pair}: {len(r)} candles loaded')
        else:
            print(f'[retrain_hmm] {pair}: only {len(r)} candles, skipping')

    if not all_returns:
        print('[retrain_hmm] No data available, aborting')
        return False

    combined = np.concatenate(all_returns, axis=0)
    print(f'[retrain_hmm] Training on {len(combined)} total returns '
          f'({len(combined)/24:.0f} days equivalent)...')

    model = _train_hmm(combined)
    state_map = _build_state_map(model, combined)

    # Score on training data
    states = model.predict(combined)
    state_counts = np.bincount(states)
    print(f'[retrain_hmm] State distribution: '
          + ' | '.join(f'{state_map[i]}={state_counts[i]/len(states):.1%}'
                       for i in range(N_STATES)))

    payload = {
        'model': model,
        'state_map': state_map,
        'trained_at': datetime.now(timezone.utc).isoformat(),
        'n_candles': len(combined),
        'pairs': PAIRS,
        'timeframe': TIMEFRAME,
    }

    MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, MODEL_OUT)
    print(f'[retrain_hmm] Saved new model → {MODEL_OUT}')
    return True


if __name__ == '__main__':
    run()
