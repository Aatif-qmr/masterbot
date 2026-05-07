import numpy as np
import pandas as pd
from hmmlearn import hmm
import pickle
import os
import time
from pathlib import Path
from sklearn.preprocessing import StandardScaler
import logging

logger = logging.getLogger(__name__)

# Machine-agnostic path setup
HOME = Path.home()
BASE_DIR = HOME / 'masterbot'
MODEL_PATH = BASE_DIR / 'qnt/oracle/hmm_model.pkl'

# Regime Labels (4 states)
# 0 = TRENDING_UP
# 1 = TRENDING_DOWN
# 2 = RANGING
# 3 = VOLATILE

REGIME_NAMES = ["TRENDING_UP", "TRENDING_DOWN", "RANGING", "VOLATILE"]

def prepare_features(dataframe: pd.DataFrame) -\u003e pd.DataFrame:
    """Calculates features for HMM training/prediction."""
    df = dataframe.copy()
    
    # 1. Returns: log returns
    df['returns'] = np.log(df['close'] / df['close'].shift(1))
    
    # 2. Volatility: rolling std of returns (window=20)
    df['volatility'] = df['returns'].rolling(window=20).std()
    
    # 3. Volume ratio: volume / volume.rolling(20).mean()
    df['volume_ratio'] = df['volume'] / df['volume'].rolling(window=20).mean()
    
    # 4. Price position: (close - low) / (high - low)
    df['price_pos'] = (df['close'] - df['low']) / (df['high'] - df['low'])
    
    # 5. Range: (high - low) / close
    df['range'] = (df['high'] - df['low']) / df['close']
    
    # Drop NaN rows
    return df[['returns', 'volatility', 'volume_ratio', 'price_pos', 'range']].dropna()

def train_hmm_model(dataframe: pd.DataFrame, n_states=4):
    """Trains a GaussianHMM and maps states to regimes."""
    features_df = prepare_features(dataframe)
    
    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(features_df)
    
    model = hmm.GaussianHMM(
        n_components=n_states,
        covariance_type='full',
        n_iter=200,
        random_state=42
    )
    
    model.fit(scaled_features)
    
    # Map states to regimes based on means
    means = model.means_
    
    vol_indices = np.argsort(means[:, 1])
    ranging_state = vol_indices[0]
    volatile_state = vol_indices[-1]
    
    remaining = [i for i in range(n_states) if i not in [ranging_state, volatile_state]]
    if means[remaining[0], 0] \u003e means[remaining[1], 0]:
        trending_up = remaining[0]
        trending_down = remaining[1]
    else:
        trending_up = remaining[1]
        trending_down = remaining[0]
        
    state_map = {
        trending_up: "TRENDING_UP",
        trending_down: "TRENDING_DOWN",
        ranging_state: "RANGING",
        volatile_state: "VOLATILE"
    }
    
    payload = {
        "model": model,
        "state_map": state_map,
        "scaler": scaler,
        "timestamp": time.time()
    }
    
    os.makedirs(MODEL_PATH.parent, exist_ok=True)
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(payload, f)
        
    return model, state_map

def load_or_train_model(dataframe: pd.DataFrame):
    """Loads model from disk or trains if missing/old."""
    if MODEL_PATH.exists():
        with open(MODEL_PATH, 'rb') as f:
            payload = pickle.load(f)
            
        if time.time() - payload.get('timestamp', 0) \u003c 7 * 86400:
            return payload
            
    train_hmm_model(dataframe)
    with open(MODEL_PATH, 'rb') as f:
        return pickle.load(f)

def detect_regime(dataframe: pd.DataFrame) -\u003e dict:
    """Detects current market regime using HMM."""
    try:
        payload = load_or_train_model(dataframe)
        model = payload['model']
        state_map = payload['state_map']
        scaler = payload['scaler']
        
        features_df = prepare_features(dataframe.tail(120))
        scaled_features = scaler.transform(features_df)
        
        hidden_states = model.predict(scaled_features)
        probs = model.predict_proba(scaled_features)[-1]
        
        curr_state = hidden_states[-1]
        regime = state_map[curr_state]
        
        prev_state = hidden_states[-2] if len(hidden_states) \u003e 1 else curr_state
        prev_regime = state_map[prev_state]
        
        prob_dict = {}
        for state_idx, name in state_map.items():
            prob_dict[name] = float(probs[state_idx])
            
        result = {
            "regime": regime,
            "confidence": float(probs[curr_state]),
            "probabilities": prob_dict,
            "previous_regime": prev_regime,
            "regime_changed": regime != prev_regime,
            "timestamp": datetime.fromtimestamp(time.time(), timezone.utc).isoformat() + 'Z'
        }

        # Publish to NATS
        try:
            import sys
            sys.path.insert(0, '/Users/azmatsaif/masterbot/qnt')
            from nats_publisher import publish_sync
            from nats_subjects import SUBJECTS
            publish_sync(SUBJECTS['HMM'], result)
            print("[NATS] Regime published to M1")
        except Exception as e:
            print(f"[NATS] Regime publish error: {e}")

        return result
    except Exception as e:
        logger.error(f"HMM Detection Error: {e}")
        return {
            "regime": "RANGING",
            "confidence": 0.0,
            "probabilities": {},
            "previous_regime": "RANGING",
            "regime_changed": False
        }

def get_regime_for_strategy(dataframe: pd.DataFrame, strategy_type: str) -\u003e bool:
    regime_data = detect_regime(dataframe)
    regime = regime_data['regime']
    
    if strategy_type == "mean_reversion":
        return regime == "RANGING"
    elif strategy_type == "trend_follow":
        return regime == "TRENDING_UP"
    elif strategy_type == "scalp":
        return regime in ["RANGING", "TRENDING_UP"]
    elif strategy_type == "swing":
        return regime == "TRENDING_UP"
    elif strategy_type == "micro_scalp":
        return regime in ["RANGING", "TRENDING_UP"]
    elif strategy_type == "daily_trend":
        return regime == "TRENDING_UP"
    
    return False

if __name__ == "__main__":
    from datetime import datetime, timezone
    import sys
    if len(sys.argv) \u003e 1 and sys.argv[1] == "--retrain":
        print("Retraining HMM model...")
        # Need to fix the data loading path if running on M2
        import freqtrade.data.history as history
        # This is a bit complex as it depends on freqtrade being installed
        # and data being present. 
        # For now, just a placeholder or minimal logic.
