import os
import json
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
import sys
import functools

# Add base dir to path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from qnt.oracle.hmm_regime import detect_regime_full

# Configuration
STRATEGY_MAP = {
    "BEAR": {
        "MeanReversionV1": 0.30,
        "ScalpV1": 0.30,
        "TrendFollowV1": 0.05,
        "DailyTrendV1": 0.05,
        "SwingV1": 0.20,
        "MicroScalpV1": 0.10
    },
    "BULL": {
        "TrendFollowV1": 0.35,
        "DailyTrendV1": 0.35,
        "MeanReversionV1": 0.05,
        "ScalpV1": 0.05,
        "SwingV1": 0.10,
        "MicroScalpV1": 0.10
    },
    "RANGING": {
        "MeanReversionV1": 0.25,
        "ScalpV1": 0.25,
        "SwingV1": 0.25,
        "MicroScalpV1": 0.15,
        "TrendFollowV1": 0.05,
        "DailyTrendV1": 0.05
    }
}

LOG_PATH = BASE_DIR / 'logs' / 'capital_allocator.log'
os.makedirs(LOG_PATH.parent, exist_ok=True)
logging.basicConfig(filename=LOG_PATH, level=logging.INFO, format='%(asctime)s | %(message)s')

@functools.lru_cache(maxsize=1)
def get_hmm_regime():
    """Detects current market regime using the HMM/LSTM engine."""
    try:
        data_path = BASE_DIR / "user_data/data/binance/BTC_USDT-1h.feather"
        if not data_path.exists():
            return "RANGING"
        
        df = pd.read_feather(data_path)
        regime_data = detect_regime_full(df)
        logging.info(f"HMM Detection: {regime_data}")
        return regime_data.get("current_regime", "RANGING")
    except Exception as e:
        logging.error(f"Error detecting HMM regime: {e}")
        return "RANGING"

def calculate_new_weights(regime):
    """Fetches predefined weights for the detected regime."""
    return STRATEGY_MAP.get(regime, STRATEGY_MAP["RANGING"])

def apply_allocation(weights, regime=None):
    """Saves the new allocation to balance_state.json and potentially updates Freqtrade configs."""
    state_path = BASE_DIR / 'risk/balance_state.json'
    try:
        if state_path.exists():
            with open(state_path, 'r') as f:
                state = json.load(f)
        else:
            state = {}
            
        if regime is None:
            regime = get_hmm_regime()

        state['strategy_allocation_weights'] = weights
        state['last_allocation_update'] = datetime.now(timezone.utc).isoformat()
        state['current_regime_hmm'] = regime
        
        # Update actual stake amounts based on a total budget (e.g. $50k)
        total_budget = state.get('total_budget', 50000.0)
        state['strategy_stake_amounts'] = {k: round(v * total_budget, 2) for k, v in weights.items()}
        
        with open(state_path, 'w') as f:
            json.dump(state, f, indent=4)
            
        logging.info(f"New HMM allocation applied: {json.dumps(weights)}")
        print(f"Success: Market is {state['current_regime_hmm']}. Stake parameters updated.")
        
    except Exception as e:
        logging.error(f"Error applying allocation: {e}")

if __name__ == "__main__":
    regime = get_hmm_regime()
    new_weights = calculate_new_weights(regime)
    apply_allocation(new_weights, regime)
