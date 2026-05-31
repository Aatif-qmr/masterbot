"""
qnt/oracle/onnx_inference.py
─────────────────────────────
ONNX Runtime-based regime inference — replaces PyTorch at runtime.

This module loads the ONNX-exported LSTM regime model and runs
inference using ONNX Runtime, which:
  - Uses ~60% less RAM than PyTorch (no autograd graph, no CUDA context)
  - Runs 2-5x faster on CPU (operator fusion, hardware acceleration)
  - Has no GIL contention (C++ execution engine)

Drop-in replacement for the torch-based detect_regime_full() path.

Usage:
    from qnt.oracle.onnx_inference import detect_regime_onnx

    result = detect_regime_onnx(returns_array)
    # {'next_regime': 'BULL', 'confidence': 0.847, 'probs': [0.05, 0.10, 0.85]}
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

HOME = Path.home()
BASE_DIR = HOME / "cipher"
ONNX_MODEL_PATH = str(BASE_DIR / "qnt/oracle/lstm_regime_model.onnx")
REGIME_LABELS = {0: "BEAR", 1: "RANGING", 2: "BULL"}

# Lazy-loaded session (initialized on first call)
_ort_session = None


def _get_session():
    """Lazy-load the ONNX Runtime session (one-time ~50ms startup)."""
    global _ort_session
    if _ort_session is not None:
        return _ort_session

    if not os.path.exists(ONNX_MODEL_PATH):
        raise FileNotFoundError(
            f"ONNX model not found at {ONNX_MODEL_PATH}. "
            f"Export first with: python3 qnt/oracle/export_lstm_onnx.py"
        )

    try:
        import onnxruntime as ort

        # Configure session for low-latency inference
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 1  # Single thread for minimal latency
        sess_options.inter_op_num_threads = 1
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.enable_cpu_mem_arena = True
        sess_options.enable_mem_pattern = True

        _ort_session = ort.InferenceSession(
            ONNX_MODEL_PATH,
            sess_options=sess_options,
            providers=["CPUExecutionProvider"],
        )
        return _ort_session

    except ImportError:
        raise ImportError("onnxruntime is required. Install with: pip install onnxruntime")


def infer_regime(returns: list[float] | np.ndarray, seq_len: int = 20) -> dict:
    """
    Run LSTM regime inference using ONNX Runtime.

    Args:
        returns: List or array of log returns (most recent last).
                 Must have at least `seq_len` elements.
        seq_len: Expected sequence length (default: 20, must match training)

    Returns:
        {
            'next_regime': 'BULL' | 'BEAR' | 'RANGING',
            'confidence': float (0.0 - 1.0),
            'probs': [bear_prob, ranging_prob, bull_prob],
        }
    """
    session = _get_session()

    # Prepare input
    if isinstance(returns, list):
        returns = np.array(returns, dtype=np.float32)
    else:
        returns = returns.astype(np.float32)

    if len(returns) < seq_len:
        return {
            "next_regime": "RANGING",
            "confidence": 0.5,
            "probs": [0.0, 1.0, 0.0],
        }

    # Take last seq_len returns, reshape to (1, seq_len, 1)
    x = returns[-seq_len:].reshape(1, seq_len, 1)

    # Run inference
    logits = session.run(None, {"returns": x})[0]  # shape: (1, 3)

    # Softmax
    logits = logits[0]
    exp_logits = np.exp(logits - np.max(logits))  # numerical stability
    probs = exp_logits / exp_logits.sum()

    next_idx = int(np.argmax(probs))
    confidence = float(probs[next_idx])

    return {
        "next_regime": REGIME_LABELS[next_idx],
        "confidence": round(confidence, 3),
        "probs": [round(float(p), 4) for p in probs],
    }


def detect_regime_onnx(dataframe, pair: str = "BTC/USDT") -> dict:
    """
    Drop-in replacement for hmm_regime.detect_regime_full().

    Combines HMM-based current regime detection (Python) with
    ONNX-based LSTM next-regime prediction.

    Args:
        dataframe: Pandas or Polars DataFrame with 'close' column
        pair: Trading pair name (used for HMM caching)

    Returns:
        {
            'current_regime': str,
            'next_regime': str,
            'confidence': float,
        }
    """
    from qnt.oracle.hmm_regime import detect_regime

    current = detect_regime(dataframe, pair)

    if len(dataframe) < 20:
        return {"current_regime": "RANGING", "next_regime": "RANGING", "confidence": 0.5}

    try:
        # Compute log returns
        close = (
            dataframe["close"].to_numpy()
            if hasattr(dataframe["close"], "to_numpy")
            else np.array(dataframe["close"])
        )
        returns = np.log(close[1:] / close[:-1]).astype(np.float32)

        if len(returns) < 20:
            return {"current_regime": current, "next_regime": current, "confidence": 0.5}

        result = infer_regime(returns)
        return {
            "current_regime": current,
            "next_regime": result["next_regime"],
            "confidence": result["confidence"],
        }

    except (FileNotFoundError, ImportError):
        # ONNX model not available, fall back gracefully
        return {"current_regime": current, "next_regime": current, "confidence": 0.5}
    except Exception as e:
        print(f"[ONNX] Inference error: {e}")
        return {"current_regime": current, "next_regime": current, "confidence": 0.5}


def benchmark(n_runs: int = 1000) -> dict:
    """
    Benchmark ONNX inference latency.

    Returns timing statistics for n_runs of inference.
    """
    import time

    # Warm up
    dummy = np.random.randn(20).astype(np.float32)
    infer_regime(dummy)

    # Benchmark
    times = []
    for _ in range(n_runs):
        start = time.perf_counter_ns()
        infer_regime(dummy)
        elapsed_us = (time.perf_counter_ns() - start) / 1000.0
        times.append(elapsed_us)

    times = np.array(times)
    return {
        "n_runs": n_runs,
        "mean_us": round(float(np.mean(times)), 1),
        "median_us": round(float(np.median(times)), 1),
        "p99_us": round(float(np.percentile(times, 99)), 1),
        "min_us": round(float(np.min(times)), 1),
        "max_us": round(float(np.max(times)), 1),
    }


if __name__ == "__main__":
    print("=" * 50)
    print("Cipher ONNX Regime Inference Test")
    print("=" * 50)

    try:
        # Test with random data
        test_returns = np.random.randn(100).astype(np.float32) * 0.01
        result = infer_regime(test_returns)
        print(f"  Next regime:  {result['next_regime']}")
        print(f"  Confidence:   {result['confidence']:.1%}")
        print(f"  Probabilities: {result['probs']}")

        print()
        print("Running latency benchmark (1000 runs)...")
        stats = benchmark()
        print(f"  Mean:   {stats['mean_us']:.1f} μs")
        print(f"  Median: {stats['median_us']:.1f} μs")
        print(f"  P99:    {stats['p99_us']:.1f} μs")
        print(f"  Min:    {stats['min_us']:.1f} μs")
        print(f"  Max:    {stats['max_us']:.1f} μs")

    except (FileNotFoundError, ImportError) as e:
        print(f"ERROR: {e}")
