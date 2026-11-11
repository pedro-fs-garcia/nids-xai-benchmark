"""Adaptador do XGBoost para classificação binária com árvores."""

import json
from typing import Any

import numpy as np
from xgboost import XGBClassifier


class XGBoostAdapter:
    def __init__(self, parameters: dict[str, Any]) -> None:
        self._parameters = dict(parameters)
        self.estimator = XGBClassifier(**parameters)

    def fit(self, inputs: np.ndarray, labels: np.ndarray) -> None:
        self.estimator.fit(inputs, labels)

    def predict(self, inputs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        probability = self.estimator.predict_proba(inputs)[:, 1]
        return (probability > 0.5).astype(np.int8), probability

    def parameters(self) -> dict[str, Any]:
        # Os demais padrões efetivos são salvos em booster-config.json pelo repositório.
        return dict(self._parameters)

    def complexity(self) -> dict[str, Any]:
        trees = self.estimator.get_booster().get_dump(dump_format="json")
        depths, nodes, leaves = [], 0, 0
        for tree in trees:
            stack = [(json.loads(tree), 0)]
            depth_max = 0
            while stack:
                node, depth = stack.pop()
                nodes += 1
                depth_max = max(depth_max, depth)
                if "leaf" in node:
                    leaves += 1
                else:
                    stack.extend((child, depth + 1) for child in node["children"])
            depths.append(depth_max)
        return {
            "trees": len(trees), "nodes_total": nodes, "leaves_total": leaves,
            "depth_min": min(depths), "depth_max": max(depths),
            "depth_mean": float(np.mean(depths)),
        }

    def prediction_example(self, inputs: np.ndarray) -> dict[str, float | int]:
        score = float(self.estimator.predict(inputs[:1], output_margin=True)[0])
        probability = float(self.estimator.predict_proba(inputs[:1])[0, 1])
        logistic = float(1 / (1 + np.exp(-score)))
        return {
            "score": score, "probability": probability,
            "logistic_of_score": logistic, "prediction": int(probability > 0.5),
        }
