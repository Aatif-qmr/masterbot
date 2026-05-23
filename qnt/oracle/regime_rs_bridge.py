"""
Drop-in bridge: tries Rust LSTM inference first, falls back to Python/torch.
Import detect_regime_full from here instead of hmm_regime for zero-torch operation.
"""
import numpy as np
import polars as pl
try:
    import pandas as pd
except ImportError:
    pd = None
from pathlib import Path

HOME = Path.home()
BASE_DIR = HOME / "masterbot"
WEIGHTS_PATH = str(BASE_DIR / "qnt/oracle/regime_rs/lstm_weights.bin")

try:
    import sys
    sys.path.insert(0, str(BASE_DIR / "qnt/oracle/regime_rs"))
    import regime_rs
    _HAS_RUST = True
except ImportError:
    _HAS_RUST = False


def detect_regime_full(dataframe, pair: str = "BTC/USDT") -> dict:
    from qnt.oracle.hmm_regime import detect_regime
    current = detect_regime(dataframe, pair)
    default = {"current_regime": current, "next_regime": current, "confidence": 0.5}

    if pd is not None and isinstance(dataframe, pd.DataFrame):
        from qnt.polars_ohlcv import pandas_to_polars
        df_pl = pandas_to_polars(dataframe)
    else:
        df_pl = dataframe

    if len(df_pl) < 20:
        return {"current_regime": "RANGING", "next_regime": "RANGING", "confidence": 0.5}

    if _HAS_RUST and Path(WEIGHTS_PATH).exists():
        try:
            returns = df_pl.select(
                (pl.col("close") / pl.col("close").shift(1)).log().alias("ret")
            ).drop_nulls().tail(20)["ret"].to_numpy().astype("float32").tolist()
            if len(returns) < 20:
                return default
            _, next_regime, confidence = regime_rs.lstm_infer(WEIGHTS_PATH, returns)
            return {
                "current_regime": current,
                "next_regime": next_regime,
                "confidence": round(confidence, 3),
            }
        except Exception as e:
            print(f"[regime_rs] Rust inference failed, falling back: {e}")

    # Fallback: torch-based Python path (lazy-loaded)
    from qnt.oracle.hmm_regime import detect_regime_full as _py_full
    return _py_full(dataframe, pair)
