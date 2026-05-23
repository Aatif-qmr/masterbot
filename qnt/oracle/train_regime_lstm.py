"""
Run on M2 (Wednesday 2am via cron).
Trains LSTM on HMM-labeled historical returns.
Saves model to qnt/oracle/lstm_regime_model.pt
"""
import numpy as np
import polars as pl
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from pathlib import Path
import joblib
import sys

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / 'qnt/oracle'))

from hmm_regime import load_hmm_model, _REGIME_LABELS, RegimeLSTM

SEQ_LEN = 20
EPOCHS = 30
BATCH = 64
LR = 1e-3
LABEL_MAP = {"BEAR": 0, "RANGING": 1, "BULL": 2}


def load_returns_from_data() -> np.ndarray:
    data_path = BASE_DIR / 'data/BTC_USDT_1h.csv'
    if not data_path.exists():
        raise FileNotFoundError(f"Training data not found: {data_path}")
    
    # Fast lazy evaluation with polars
    df = pl.scan_csv(data_path).sort('date').collect()
    
    returns = df.select(
        (pl.col("close") / pl.col("close").shift(1)).log().alias("ret")
    ).drop_nulls()["ret"].to_numpy().astype(np.float32)
    
    return returns


def label_with_hmm(returns: np.ndarray) -> np.ndarray:
    model_data = load_hmm_model()
    if model_data is None:
        raise RuntimeError("HMM model not available for labeling")
    model = model_data['model'] if isinstance(model_data, dict) else model_data
    state_map = model_data.get('state_map', {0: "BEAR", 1: "RANGING", 2: "BULL"}) if isinstance(model_data, dict) else {0: "BEAR", 1: "RANGING", 2: "BULL"}

    raw_states = model.predict(returns.reshape(-1, 1))

    def map_state(s):
        label = state_map.get(s, "RANGING")
        if label == "TRENDING_UP": label = "BULL"
        elif label in ("TRENDING_DOWN", "VOLATILE"): label = "BEAR"
        return LABEL_MAP.get(label, 1)

    return np.array([map_state(s) for s in raw_states])


def build_sequences(returns: np.ndarray, labels: np.ndarray):
    X, y = [], []
    for i in range(SEQ_LEN, len(returns)):
        X.append(returns[i - SEQ_LEN:i])
        y.append(labels[i])
    return (
        torch.tensor(np.array(X)).unsqueeze(-1),
        torch.tensor(np.array(y), dtype=torch.long),
    )


def train():
    print("Loading returns...")
    returns = load_returns_from_data()
    print("Labeling with HMM...")
    labels = label_with_hmm(returns)

    X, y = build_sequences(returns, labels)
    dataset = TensorDataset(X, y)
    loader = DataLoader(dataset, batch_size=BATCH, shuffle=True)

    model = RegimeLSTM()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    criterion = nn.CrossEntropyLoss()

    model.train()
    for epoch in range(EPOCHS):
        total_loss = 0
        for xb, yb in loader:
            optimizer.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        if (epoch + 1) % 5 == 0:
            print(f"Epoch {epoch+1}/{EPOCHS} — loss: {total_loss/len(loader):.4f}")

    out_path = BASE_DIR / 'qnt/oracle/lstm_regime_model.pt'
    torch.save(model.state_dict(), out_path)
    print(f"LSTM model saved to {out_path}")


if __name__ == "__main__":
    train()
