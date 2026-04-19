from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Iterable

import numpy as np


@dataclass
class GradientBoostingClassifier:
    random_state: int | None = None

    def fit(self, X: Iterable[Iterable[float]], y: Iterable[int]):
        X_array = np.asarray(list(X), dtype=float)
        y_array = np.asarray(list(y), dtype=float)
        if X_array.ndim != 2:
            raise ValueError("X must be a 2D array-like")
        if X_array.size == 0:
            raise ValueError("X must contain at least one row")

        positive = X_array[y_array >= 0.5]
        negative = X_array[y_array < 0.5]
        pos_mean = positive.mean(axis=0) if len(positive) else X_array.mean(axis=0)
        neg_mean = negative.mean(axis=0) if len(negative) else X_array.mean(axis=0)
        weights = pos_mean - neg_mean
        if not np.any(weights):
            weights = np.ones(X_array.shape[1], dtype=float)

        self.coef_ = weights.astype(float)
        importances = np.abs(self.coef_)
        total = float(importances.sum()) or 1.0
        self.feature_importances_ = importances / total
        self.classes_ = np.asarray([0, 1])
        self.n_features_in_ = X_array.shape[1]
        return self

    def predict_proba(self, X: Iterable[Iterable[float]]):
        X_array = np.asarray(list(X), dtype=float)
        scores = X_array @ self.coef_
        probabilities = np.asarray([1.0 / (1.0 + exp(-float(score))) for score in scores], dtype=float)
        return np.column_stack([1.0 - probabilities, probabilities])
