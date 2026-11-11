"""Adaptador do scikit-learn para treinamento e avaliação binária."""

from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


class RandomForestAdapter:
    def __init__(self, parameters: dict[str, Any]) -> None:
        self.estimator = RandomForestClassifier(**parameters)

    def fit(self, inputs: np.ndarray, labels: np.ndarray) -> None:
        self.estimator.fit(inputs, labels)

    def predict(self, inputs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if self.estimator.classes_.tolist() != [0, 1]:
            raise ValueError("O classificador deve ter as classes 0 (benigno) e 1 (ataque).")
        probability = self.estimator.predict_proba(inputs)[:, 1]
        # O scikit-learn escolhe a primeira classe em empates.
        return (probability > 0.5).astype(np.int8), probability

    def parameters(self) -> dict[str, Any]:
        return self.estimator.get_params(deep=False)

    def complexity(self) -> dict[str, Any]:
        trees = self.estimator.estimators_
        return {
            "trees": len(trees),
            "depth_min": int(min(tree.tree_.max_depth for tree in trees)),
            "depth_max": int(max(tree.tree_.max_depth for tree in trees)),
            "depth_mean": float(np.mean([tree.tree_.max_depth for tree in trees])),
            "nodes_total": int(sum(tree.tree_.node_count for tree in trees)),
            "leaves_total": int(sum(tree.tree_.n_leaves for tree in trees)),
        }


def binary_metrics(
    actual: np.ndarray, predicted: np.ndarray, probability: np.ndarray
) -> dict[str, Any]:
    tn, fp, fn, tp = (int(n) for n in confusion_matrix(actual, predicted, labels=[0, 1]).ravel())
    return {
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "accuracy": float(accuracy_score(actual, predicted)),
        "precision": float(precision_score(actual, predicted, zero_division=0)),
        "recall": float(recall_score(actual, predicted, zero_division=0)),
        "f1": float(f1_score(actual, predicted, zero_division=0)),
        "false_positive_rate": fp / (tn + fp) if tn + fp else None,
        "roc_auc": float(roc_auc_score(actual, probability)),
    }
