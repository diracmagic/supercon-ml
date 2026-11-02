"""Label-free, train-only prototype features. Similarity is not SC probability."""
from __future__ import annotations

import hashlib
import json
import warnings
from pathlib import Path

import numpy as np

VERSION = "train-only-rbf-prototypes-v1"


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


class TrainOnlyPrototypes:
    """Fit X alone; retain a fixed output width with explicit inactive padding.

    Nonfinite physical inputs remain unknown and are imputed by training medians.
    A zero in an inactive output column is a missing basis function, not a physical
    value. No labels, family annotations or held-out rows are accepted by fit.
    """
    def __init__(self, n_clusters=16, seed=7):
        if isinstance(n_clusters, bool) or not isinstance(n_clusters, int) or n_clusters < 1:
            raise ValueError("n_clusters must be a positive integer")
        self.n_clusters, self.seed = n_clusters, int(seed)

    @staticmethod
    def _matrix(X):
        X = np.asarray(X, dtype=float)
        if X.ndim != 2:
            raise ValueError("A two-dimensional physical feature matrix is required")
        return np.where(np.isfinite(X), X, np.nan)

    def fit(self, X):
        from sklearn.cluster import KMeans
        X = self._matrix(X)
        if not len(X):
            raise ValueError("Training rows must be nonempty")
        self.fit_rows, self.input_columns = X.shape
        finite = np.isfinite(X)
        self.training_sha256 = _hash({"shape": list(X.shape), "finite": finite.tolist(),
                                      "values": np.where(finite, X, 0.).tolist()})
        observed = finite.any(axis=0)
        indices = np.flatnonzero(observed)
        medians = np.array([np.median(X[finite[:, j], j]) for j in indices])
        filled = np.where(finite[:, indices], X[:, indices], medians)
        means, stds = filled.mean(axis=0), filled.std(axis=0)
        if not np.isfinite(means).all() or not np.isfinite(stds).all():
            raise ValueError("Training scale overflow")
        variable = stds > 1e-12
        self.selected_columns = indices[variable]
        self.all_missing_columns = np.flatnonzero(~observed)
        self.constant_columns = indices[~variable]
        self.medians, self.means, self.stds = medians[variable], means[variable], stds[variable]
        self.centers = np.empty((0, len(self.selected_columns)))
        self.active_prototypes, self.bandwidth = 0, 1.
        self.bandwidth_status = "inactive_no_informative_columns"
        self.degenerate = []
        self.cluster_sizes, self.inertia, self.iterations = [], 0., 0
        self.fit_warnings = []
        self.distinct_training_rows = 0
        if not len(self.selected_columns):
            self.degenerate.append("no_informative_columns")
            return self
        Z = self._scale(X)
        self.distinct_training_rows = len(np.unique(Z, axis=0))
        self.active_prototypes = min(self.n_clusters, self.distinct_training_rows)
        if self.active_prototypes < self.n_clusters:
            self.degenerate.append("fewer_distinct_rows_than_requested_prototypes")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            fitted = KMeans(n_clusters=self.active_prototypes, random_state=self.seed,
                            n_init=10, init="k-means++", algorithm="lloyd",
                            max_iter=300, tol=1e-4).fit(Z)
        self.fit_warnings = [f"{type(w.message).__name__}: {w.message}" for w in caught]
        used, sizes = np.unique(fitted.labels_, return_counts=True)
        if len(used) != self.active_prototypes:
            self.degenerate.append("kmeans_returned_fewer_occupied_clusters")
        self.active_prototypes = len(used)
        self.centers = fitted.cluster_centers_[used]
        distances = np.linalg.norm(Z[:, None, :] - self.centers[None, :, :], axis=2)
        nearest = distances.min(axis=1)
        positive = nearest[nearest > 1e-12]
        if len(positive):
            self.bandwidth = float(np.median(positive))
            self.bandwidth_status = "median_positive_training_nearest_distance"
        else:
            self.bandwidth_status = "unit_scaled_fallback_all_training_nearest_distances_zero"
            self.degenerate.append("zero_training_nearest_distances")
        self.cluster_sizes = sizes.tolist()
        self.inertia, self.iterations = float(fitted.inertia_), int(fitted.n_iter_)
        return self

    def _scale(self, X):
        chosen = X[:, self.selected_columns]
        filled = np.where(np.isfinite(chosen), chosen, self.medians)
        return np.clip((filled - self.means) / self.stds, -5., 5.)

    def transform(self, X):
        if not hasattr(self, "fit_rows"):
            raise ValueError("Representation is not fitted")
        X = self._matrix(X)
        if X.shape[1] != self.input_columns:
            raise ValueError("Feature column count changed")
        result = np.zeros((len(X), self.n_clusters))
        if self.active_prototypes:
            delta = self._scale(X)[:, None, :] - self.centers[None, :, :]
            d2 = np.sum(delta * delta, axis=2)
            result[:, :self.active_prototypes] = np.exp(-d2 / (2 * self.bandwidth ** 2))
        return result

    def identity(self):
        if not hasattr(self, "fit_rows"):
            raise ValueError("Representation is not fitted")
        state = {"version": VERSION, "fit_rows": self.fit_rows, "input_columns": self.input_columns,
                 "requested_prototypes": self.n_clusters, "active_prototypes": self.active_prototypes,
                 "seed": self.seed, "n_init": 10, "selected_columns": self.selected_columns.tolist(),
                 "all_missing_columns": self.all_missing_columns.tolist(),
                 "constant_columns": self.constant_columns.tolist(),
                 "medians": self.medians.tolist(), "means": self.means.tolist(), "stds": self.stds.tolist(),
                 "z_clip": 5., "centers": self.centers.tolist(), "bandwidth": self.bandwidth,
                 "bandwidth_status": self.bandwidth_status, "degenerate": list(self.degenerate),
                 "distinct_training_rows": self.distinct_training_rows, "cluster_sizes": self.cluster_sizes,
                 "inertia": self.inertia, "iterations": self.iterations,
                 "max_iter_reached": self.iterations >= 300,
                 "fit_warnings": self.fit_warnings,
                 "training_sha256": self.training_sha256,
                 "source_sha256": hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                 "semantics": "Uncalibrated similarity features; no target/probability interpretation"}
        return {**state, "state_sha256": _hash(state)}
