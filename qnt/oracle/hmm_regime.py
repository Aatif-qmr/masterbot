import joblib
import numpy as np
import polars as pl

try:
    import pandas as pd
except ImportError:
    pd = None
import os
from pathlib import Path

from dotenv import load_dotenv

# Machine-agnostic path setup
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def load_hmm_model():
    """Load HMM model from M2 via SCP if not cached locally."""
    local_path = BASE_DIR / "qnt/oracle/hmm_model.pkl"

    m2_ip = os.getenv("M2_TAILSCALE_IP")
    m2_user = os.getenv("M2_SSH_USER")
    if not m2_ip or not m2_user:
        raise ValueError(
            "Missing critical configuration: M2_TAILSCALE_IP and M2_SSH_USER must be set in .env"
        )

    m2_path = os.getenv("M2_HMM_PATH", f"/Users/{m2_user}/cipher/qnt/oracle/hmm_model.pkl")

    if not local_path.exists():
        import subprocess

        try:
            # Try to fetch from M2
            subprocess.run(
                ["scp", f"{m2_user}@{m2_ip}:{m2_path}", str(local_path)], check=True, timeout=30
            )
        except Exception as e:
            print(f"Error loading HMM model from M2: {e}")
            return None
    try:
        return joblib.load(local_path)
    except Exception:
        # Fallback to pickle if joblib fails (since the other machine might use pickle)
        import pickle

        try:
            with open(local_path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None


_regime_cache: dict = {}  # pair → (regime, expires_at)
_REGIME_CACHE_TTL = 300  # 5 minutes per pair


def detect_regime(dataframe, pair: str = "BTC/USDT") -> str:
    """
    Returns: 'BULL', 'BEAR', or 'RANGING'
    Uses last 100 candles of the pair's own data. Cached per-pair for 5 min.
    """
    import time

    cached = _regime_cache.get(pair)
    if cached and time.time() < cached[1]:
        return cached[0]

    model_data = load_hmm_model()
    if model_data is None:
        return "RANGING"  # Safe default

    # Handle both raw model and payload dict
    if isinstance(model_data, dict):
        model = model_data.get("model")
        state_map = model_data.get("state_map")
    else:
        model = model_data
        state_map = {0: "BEAR", 1: "RANGING", 2: "BULL"}  # Default map for 3-state

    if model is None:
        return "RANGING"

    try:
        # Transparent pandas bridge
        if pd is not None and isinstance(dataframe, pd.DataFrame):
            from qnt.polars_ohlcv import pandas_to_polars

            df_pl = pandas_to_polars(dataframe)
        else:
            df_pl = dataframe

        if len(df_pl) < 10:
            return "RANGING"

        # Fast vectorized polars log returns
        returns = (
            df_pl.select((pl.col("close") / pl.col("close").shift(1)).log().alias("ret"))
            .drop_nulls()
            .tail(100)["ret"]
            .to_numpy()
            .reshape(-1, 1)
        )

        if len(returns) < 10:
            return "RANGING"

        # Predict most likely state
        states = model.predict(returns)
        state_counts = np.bincount(states)
        dominant_state = np.argmax(state_counts)

        # Map HMM state to regime label
        if state_map:
            res = state_map.get(dominant_state, "RANGING")
            if res == "TRENDING_UP":
                result = "BULL"
            elif res == "TRENDING_DOWN":
                result = "BEAR"
            elif res == "VOLATILE":
                result = "BEAR"
            else:
                result = "RANGING"
        else:
            regime_map = {0: "BEAR", 1: "RANGING", 2: "BULL"}
            result = regime_map.get(dominant_state, "RANGING")

        import time

        _regime_cache[pair] = (result, time.time() + _REGIME_CACHE_TTL)
        return result
    except Exception as e:
        print(f"HMM Detection Error: {e}")
        return "RANGING"


def get_regime_for_strategy(strategy_name: str, current_regime: str) -> bool:
    """
    Returns True if strategy should trade in current regime.
    MicroScalpV1: trades in all regimes but reduces size in BEAR
    """
    if strategy_name == "MicroScalpV1":
        return True  # Always allowed, size adjusted elsewhere
    if strategy_name in ["MeanReversionV1", "ScalpV1"]:
        return current_regime != "BULL"  # Mean-rev underperforms in strong trends
    if strategy_name in ["TrendFollowV1", "DailyTrendV1"]:
        return current_regime != "RANGING"  # Trend strategies need direction
    if strategy_name == "SwingV1":
        return current_regime == "BULL"  # EMA crossovers need a trending bull market
    if strategy_name == "BearScalpV1":
        return current_regime == "BEAR"  # Short-only strategy
    return True


_REGIME_LABELS = {0: "BEAR", 1: "RANGING", 2: "BULL"}


def detect_regime_full(dataframe, pair: str = "BTC/USDT") -> dict:
    """
    Returns current + predicted next regime with confidence.
    Routes to the high-performance ONNX Runtime implementation.
    """
    try:
        from qnt.oracle.onnx_inference import detect_regime_onnx

        return detect_regime_onnx(dataframe, pair)
    except Exception as e:
        print(f"Error routing to ONNX regime inference: {e}")
        current = detect_regime(dataframe, pair)
        return {"current_regime": current, "next_regime": current, "confidence": 0.5}


try:
    import torch  # noqa: F401
    import torch.nn as nn

    class RegimeLSTM(nn.Module):
        """LSTM architecture for regime detection (mirrored in train_regime_lstm.py)."""

        def __init__(self, input_size=1, hidden_size=64, num_layers=1, num_classes=3):
            super().__init__()
            self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
            self.fc = nn.Linear(hidden_size, num_classes)

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.fc(out[:, -1, :])
except ImportError:

    class RegimeLSTM:
        """Fallback placeholder when PyTorch is not installed."""

        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch is required to use RegimeLSTM. Please install torch.")
