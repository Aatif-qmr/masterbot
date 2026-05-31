"""
qnt/freqai/VaultFreqaiModel.py
──────────────────────────────
Custom FreqAI model that backs VectorVaultV1 predictions with the Rust
vector-matching engine.

Training: stores the pipeline-normalised feature matrix + target labels
          as the "vault" (historical context).
Prediction: for each incoming candle vector, finds the nearest vault
            neighbour via Euclidean distance and returns that neighbour's
            realised forward return as the predicted signal.

The model inherits BaseRegressionModel so it slots into FreqAI's standard
train/predict lifecycle without modifications to the framework.

Usage in config:
    "freqai": {
        "enabled": true,
        "freqaimodel": "VaultFreqaiModel",
        "freqaimodel_path": "qnt/freqai",
        ...
    }
"""

import logging
from typing import Any

import numpy as np
from pandas import DataFrame

try:
    from freqtrade.freqai.base_models.BaseRegressionModel import BaseRegressionModel
    from freqtrade.freqai.data_kitchen import FreqaiDataKitchen
except Exception:
    BaseRegressionModel = object  # type: ignore[assignment,misc]
    FreqaiDataKitchen = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

try:
    import rust_engine as _rust

    _RUST_AVAILABLE = True
except ImportError:
    _RUST_AVAILABLE = False
    logger.warning("rust_engine not importable — VaultFreqaiModel uses NumPy fallback")


class _VaultEstimator:
    """
    sklearn-compatible estimator wrapping the Rust nearest-neighbour vault.

    predict(X) finds the closest training vector for each row of X
    and returns the corresponding stored label.
    """

    def __init__(self, X_train: np.ndarray, y_train: np.ndarray, lookback: int = 1000):
        n = len(X_train)
        if lookback and lookback < n:
            self.X_vault: np.ndarray = X_train[-lookback:]
            self.y_vault: np.ndarray = y_train[-lookback:]
        else:
            self.X_vault = X_train
            self.y_vault = y_train

    def predict(self, X: "np.ndarray | DataFrame") -> np.ndarray:
        if hasattr(X, "values"):
            X = X.values
        X = np.asarray(X, dtype=np.float64)
        n_pred = len(X)

        if _RUST_AVAILABLE:
            vault_list = self.X_vault.tolist()
            preds = np.empty(n_pred, dtype=np.float64)
            for i, row in enumerate(X.tolist()):
                idx, _ = _rust.find_closest_match(row, vault_list)
                preds[i] = float(self.y_vault[idx])
        else:
            # Pure NumPy fallback: vectorised squared-Euclidean distances
            preds = np.empty(n_pred, dtype=np.float64)
            for i, row in enumerate(X):
                diffs = self.X_vault - row
                dists = (diffs * diffs).sum(axis=1)
                idx = int(np.argmin(dists))
                preds[i] = float(self.y_vault[idx])

        return preds


class VaultFreqaiModel(BaseRegressionModel):
    """
    FreqAI regression model backed by Rust vector-vault nearest-neighbour.

    Fits a _VaultEstimator from the training features and labels supplied
    by FreqAI's data pipeline.  No external dependencies beyond rust_engine
    (with NumPy fallback for environments where the .so is unavailable).
    """

    def fit(self, data_dictionary: dict[str, Any], dk: FreqaiDataKitchen, **kwargs) -> Any:
        X: np.ndarray = data_dictionary["train_features"].values.astype(np.float64)
        y: np.ndarray = data_dictionary["train_labels"].values[:, 0].astype(np.float64)
        lookback: int = dk.freqai_info.get("feature_parameters", {}).get("vault_lookback", 1000)
        model = _VaultEstimator(X, y, lookback)
        logger.info(
            "VaultFreqaiModel fit: vault=%d vectors, features=%d, rust=%s",
            len(model.X_vault),
            X.shape[1],
            _RUST_AVAILABLE,
        )
        return model
