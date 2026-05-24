"""
qnt/oracle/export_lstm_onnx.py
──────────────────────────────
Export the PyTorch LSTM Regime model to ONNX format.

This script loads the trained LSTM model from lstm_regime_model.pt
and exports it as an ONNX file for use with ONNX Runtime (Python or
Rust/C++ bindings), eliminating the need for PyTorch at inference time.

Usage:
    python3 qnt/oracle/export_lstm_onnx.py
    # Output: qnt/oracle/lstm_regime_model.onnx

Benefits:
    - No PyTorch dependency at runtime (saves ~2GB RAM)
    - ONNX Runtime inference is 2-5x faster than PyTorch eager mode
    - Compatible with Rust (ort crate), C++ (ONNX Runtime C++ API), and Mojo
"""

import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "qnt/oracle"))

import torch
import torch.nn as nn
import numpy as np

from hmm_regime import RegimeLSTM


def export_to_onnx(
    pt_path: str | None = None,
    onnx_path: str | None = None,
    seq_len: int = 20,
    opset_version: int = 17,
) -> str:
    """
    Export the PyTorch LSTM regime model to ONNX format.

    Args:
        pt_path: Path to the .pt model file (default: qnt/oracle/lstm_regime_model.pt)
        onnx_path: Output path for the .onnx file
        seq_len: Sequence length the model expects (default: 20)
        opset_version: ONNX opset version (17 recommended for LSTM support)

    Returns:
        Path to the exported ONNX file
    """
    if pt_path is None:
        pt_path = str(BASE_DIR / "qnt/oracle/lstm_regime_model.pt")
    if onnx_path is None:
        onnx_path = str(BASE_DIR / "qnt/oracle/lstm_regime_model.onnx")

    if not os.path.exists(pt_path):
        raise FileNotFoundError(
            f"PyTorch model not found at {pt_path}. "
            f"Train first with: python3 qnt/oracle/train_regime_lstm.py"
        )

    # Load model
    model = RegimeLSTM()
    model.load_state_dict(torch.load(pt_path, map_location="cpu", weights_only=True))
    model.eval()

    # Create dummy input: (batch=1, seq_len=20, features=1)
    dummy_input = torch.randn(1, seq_len, 1)

    # Export
    torch.onnx.export(
        model,
        dummy_input,
        onnx_path,
        export_params=True,
        opset_version=opset_version,
        do_constant_folding=True,
        input_names=["returns"],
        output_names=["logits"],
        dynamic_axes={
            "returns": {0: "batch_size"},
            "logits": {0: "batch_size"},
        },
    )

    # Verify the exported model
    import onnx

    onnx_model = onnx.load(onnx_path)
    onnx.checker.check_model(onnx_model)

    # File size comparison
    pt_size = os.path.getsize(pt_path) / 1024
    onnx_size = os.path.getsize(onnx_path) / 1024

    print(f"✓ ONNX export successful!")
    print(f"  PyTorch model: {pt_size:.1f} KB")
    print(f"  ONNX model:    {onnx_size:.1f} KB")
    print(f"  Output:        {onnx_path}")

    return onnx_path


def verify_onnx_output(
    pt_path: str | None = None,
    onnx_path: str | None = None,
    seq_len: int = 20,
) -> bool:
    """
    Verify that the ONNX model produces identical outputs to PyTorch.

    Returns True if outputs match within tolerance.
    """
    if pt_path is None:
        pt_path = str(BASE_DIR / "qnt/oracle/lstm_regime_model.pt")
    if onnx_path is None:
        onnx_path = str(BASE_DIR / "qnt/oracle/lstm_regime_model.onnx")

    import onnxruntime as ort

    # PyTorch inference
    model = RegimeLSTM()
    model.load_state_dict(torch.load(pt_path, map_location="cpu", weights_only=True))
    model.eval()

    test_input = torch.randn(1, seq_len, 1)
    with torch.no_grad():
        pt_output = model(test_input).numpy()

    # ONNX Runtime inference
    session = ort.InferenceSession(onnx_path)
    ort_output = session.run(None, {"returns": test_input.numpy()})[0]

    # Compare
    max_diff = np.max(np.abs(pt_output - ort_output))
    match = max_diff < 1e-5

    print(f"  PyTorch output:      {pt_output.flatten()}")
    print(f"  ONNX Runtime output: {ort_output.flatten()}")
    print(f"  Max difference:      {max_diff:.2e}")
    print(f"  Match: {'✓ YES' if match else '✗ NO'}")

    return match


if __name__ == "__main__":
    print("=" * 50)
    print("Cipher LSTM → ONNX Export")
    print("=" * 50)

    try:
        path = export_to_onnx()
        print()
        print("Verifying ONNX output parity...")
        verify_onnx_output()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    except ImportError as e:
        print(f"ERROR: Missing dependency — {e}")
        print("Install with: pip install onnx onnxruntime")
        sys.exit(1)
