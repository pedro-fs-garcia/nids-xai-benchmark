"""Adaptador do TreeSHAP path-dependent sobre a biblioteca shap."""

from dataclasses import dataclass
from typing import Any

import numpy as np
import shap


@dataclass(frozen=True)
class TreeShapResult:
    reference_value: float
    contributions: np.ndarray


class TreeShapExplainer:
    """Explica a classe 1 de um classificador binário de árvores, sem conjunto de referência."""

    def __init__(
        self,
        estimator: Any,
        feature_perturbation: str = "tree_path_dependent",
        model_output: str = "raw",
        approximate: bool = False,
        data: Any = None,
    ) -> None:
        if data is not None:
            raise ValueError("O TreeSHAP path-dependent não usa conjunto de referência.")
        if feature_perturbation != "tree_path_dependent":
            raise ValueError("Somente a perturbação path-dependent é permitida.")
        if model_output != "raw":
            raise ValueError("Somente a saída bruta das árvores é permitida.")
        if approximate is not False:
            raise ValueError("O cálculo aproximado não é permitido.")
        if [int(label) for label in getattr(estimator, "classes_", [])] != [0, 1]:
            raise ValueError("O classificador deve ter as classes 0 e 1, nessa ordem.")
        self.features = int(estimator.n_features_in_)
        self._explainer = shap.TreeExplainer(
            estimator, feature_perturbation="tree_path_dependent", model_output="raw"
        )
        self.construction_reference_value = self._class_one(self._explainer.expected_value)

    def explain(self, inputs: np.ndarray) -> TreeShapResult:
        if inputs.ndim != 2 or inputs.shape[1] != self.features or not np.isfinite(inputs).all():
            raise ValueError(f"As entradas devem formar uma matriz finita com {self.features} colunas.")
        values = np.asarray(
            self._explainer.shap_values(inputs, check_additivity=False, approximate=False)
        )
        if values.ndim == 3:
            if values.shape[2] != 2:
                raise ValueError("A explicação deve ter uma saída por classe.")
            values = values[:, :, 1]
        if values.shape != inputs.shape:
            raise ValueError("A explicação deve ter uma contribuição por atributo e por fluxo.")
        return TreeShapResult(self._class_one(self._explainer.expected_value), values)

    @staticmethod
    def _class_one(expected_value: Any) -> float:
        values = np.atleast_1d(np.asarray(expected_value, dtype=np.float64))
        if values.size == 2:
            return float(values[1])
        if values.size == 1:
            return float(values[0])
        raise ValueError("O valor de referência deve ter uma saída por classe ou uma saída única.")
