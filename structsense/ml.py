"""Machine learning: Isolation Forest anomaly detection on sensor readings.

Idea: the model is trained only on NORMAL readings. Each tree randomly splits the data;
points that are unusual get isolated in very few splits, so they get a low score.
This catches odd combinations or sudden spikes even if no fixed threshold is crossed.
"""
import numpy as np
from sklearn.ensemble import IsolationForest

KEYS = ['vib', 'tilt', 'crack', 'strain', 'temp']


class Detector:
    def __init__(self):
        self.model = None
        self.n_train = 0

    def _features(self, X):
        # Feature engineering: besides the 5 raw values, add "how far from normal" (z-score) summaries.
        # Without them, one extreme sensor among five normal ones is hard for the forest to isolate.
        z = np.abs((X - self.mu) / self.sd)
        return np.hstack([X, z.max(axis=1, keepdims=True), (z ** 2).sum(axis=1, keepdims=True)])

    def train(self, rows):
        X = np.array(rows, dtype=float)
        self.mu, self.sd = X.mean(axis=0), X.std(axis=0) + 1e-9
        # contamination = share of training data we expect to be unusual (2%)
        self.model = IsolationForest(n_estimators=150, contamination=0.02, random_state=42).fit(self._features(X))
        self.n_train = len(X)

    def check(self, values):
        """Return (is_anomaly, score). Lower score = more unusual; below 0 = anomaly."""
        x = self._features(np.array([[values[k] for k in KEYS]], dtype=float))
        return bool(self.model.predict(x)[0] == -1), float(self.model.decision_function(x)[0])
