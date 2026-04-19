from __future__ import annotations

import numpy as np


def build_balanced_sample_weight(y: np.ndarray) -> np.ndarray:
    """Return deterministic inverse-frequency sample weights for binary labels.

    GradientBoostingClassifier does not expose class_weight, but it does accept
    sample_weight during fit. This helper keeps the effective class mass balanced
    without introducing stochastic resampling.
    """
    if y.ndim != 1:
        raise ValueError("y must be one-dimensional")
    if y.size == 0:
        return np.asarray([], dtype=float)

    labels, counts = np.unique(y, return_counts=True)
    if labels.size < 2:
        return np.ones_like(y, dtype=float)

    total = float(y.size)
    label_weights = {
        int(label): total / (float(labels.size) * float(count))
        for label, count in zip(labels.tolist(), counts.tolist(), strict=True)
        if count > 0
    }
    return np.asarray([float(label_weights.get(int(label), 1.0)) for label in y.tolist()], dtype=float)
