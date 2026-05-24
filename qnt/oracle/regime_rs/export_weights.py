"""
One-time export: converts lstm_regime_model.pt → lstm_weights.bin
Run from cipher root: python qnt/oracle/regime_rs/export_weights.py
Requires torch (only needed once on a machine that has the .pt file).
"""
import struct
import sys
from pathlib import Path

HOME = Path.home()
BASE_DIR = HOME / "cipher"
PT_PATH = BASE_DIR / "qnt/oracle/lstm_regime_model.pt"
BIN_PATH = BASE_DIR / "qnt/oracle/regime_rs/lstm_weights.bin"

if not PT_PATH.exists():
    print(f"Model not found at {PT_PATH}. Fetch from M2 first.")
    sys.exit(1)

import torch

state = torch.load(PT_PATH, map_location="cpu")

# Expected keys (PyTorch LSTM naming convention)
keys = [
    "lstm.weight_ih_l0",  # 4*64 x 1
    "lstm.weight_hh_l0",  # 4*64 x 64
    "lstm.bias_ih_l0",    # 4*64
    "lstm.bias_hh_l0",    # 4*64
    "fc.weight",          # 3 x 64
    "fc.bias",            # 3
]

with open(BIN_PATH, "wb") as f:
    for key in keys:
        tensor = state[key].float().flatten().numpy()
        f.write(struct.pack(f"{len(tensor)}f", *tensor))
        print(f"  {key}: {tensor.shape} → {len(tensor)} floats")

total = BIN_PATH.stat().st_size
print(f"\nExported to {BIN_PATH} ({total} bytes, {total//4} floats)")
