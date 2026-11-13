"""Inferência binária com os parâmetros aprendidos de um modelo salvo."""

from typing import Any

import numpy as np


class FrozenPredictor:
    def __init__(self, estimator: Any) -> None:
        if list(estimator.classes_) != [0, 1]:
            raise ValueError("O modelo deve usar as classes 0 e 1, nessa ordem.")
        self.estimator = estimator

    def predict(self, inputs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if inputs.ndim != 2 or not np.isfinite(inputs).all():
            raise ValueError("As entradas devem formar uma matriz de valores finitos.")
        probability = self.estimator.predict_proba(inputs)[:, 1]
        return self.classify(probability), probability

    @staticmethod
    def classify(probability: np.ndarray) -> np.ndarray:
        """Ataque quando a probabilidade é maior que 0,5; o empate é benigno."""
        if not np.isfinite(probability).all() or ((probability < 0) | (probability > 1)).any():
            raise ValueError("O classificador produziu probabilidades inválidas.")
        return (probability > 0.5).astype(np.int8)
