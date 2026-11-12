"""Leitura da estrutura das árvores do Random Forest e do XGBoost."""

import json
import math
from typing import Any

import numpy as np


def features_without_split(estimator: Any) -> list[int]:
    """Índices dos atributos que nenhuma árvore usa em divisão."""
    used: set[int] = set()
    if hasattr(estimator, "estimators_"):
        for tree in estimator.estimators_:
            features = tree.tree_.feature
            used.update(features[features >= 0].tolist())
    elif hasattr(estimator, "get_booster"):
        for tree in _xgboost_trees(estimator.get_booster()):
            internal = np.asarray(tree["left_children"]) != -1
            used.update(np.asarray(tree["split_indices"])[internal].tolist())
    else:
        raise ValueError("Classificador sem estrutura de árvores conhecida.")
    return sorted(set(range(int(estimator.n_features_in_))) - used)


def xgboost_reference_value(booster: Any) -> float:
    """Logit do base_score somado à média das folhas de cada árvore, ponderada pela soma das hessianas."""
    learner = json.loads(booster.save_raw(raw_format="json"))["learner"]
    if learner["objective"]["name"] != "binary:logistic":
        raise ValueError("O cálculo exige o objetivo binary:logistic.")
    parameters = learner["learner_model_param"]
    if parameters["num_target"] != "1" or parameters["num_class"] != "0":
        raise ValueError("O cálculo exige uma única saída.")
    base_scores = [float(value) for value in parameters["base_score"].strip("[]").split(",")]
    if len(base_scores) != 1:
        raise ValueError("O cálculo exige um único base_score.")
    base_score = base_scores[0]
    total = math.log(base_score / (1 - base_score))
    for tree in _xgboost_trees(booster):
        leaves = np.asarray(tree["left_children"]) == -1
        weights = np.asarray(tree["sum_hessian"], dtype=np.float64)
        values = np.asarray(tree["split_conditions"], dtype=np.float64)
        total += float((values[leaves] * weights[leaves]).sum() / weights[0])
    return total


def _xgboost_trees(booster: Any) -> list[dict[str, Any]]:
    model = json.loads(booster.save_raw(raw_format="json"))["learner"]["gradient_booster"]
    if model["name"] != "gbtree" or model["model"]["gbtree_model_param"]["num_parallel_tree"] != "1":
        raise ValueError("O cálculo exige o booster gbtree com uma árvore por iteração.")
    return model["model"]["trees"]
