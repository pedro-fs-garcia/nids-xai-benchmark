import json
import math
from itertools import combinations

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier

from core.tree_explainer import TreeShapExplainer
from core.tree_structure import features_without_split, xgboost_reference_value

CONSTANT_FEATURE = 4


@pytest.fixture(scope="module")
def data():
    rng = np.random.default_rng(0)
    inputs = rng.integers(0, 10, size=(400, 5)).astype(np.float64)
    inputs[:, CONSTANT_FEATURE] = 3.0
    labels = ((inputs[:, 0] + inputs[:, 1] * (inputs[:, 2] > 4) + rng.normal(0, 1, 400)) > 7).astype(np.int64)
    return inputs, labels


@pytest.fixture(scope="module")
def forest(data):
    return RandomForestClassifier(n_estimators=4, max_depth=3, random_state=0, n_jobs=1).fit(*data)


@pytest.fixture(scope="module")
def booster(data):
    return XGBClassifier(n_estimators=4, max_depth=3, learning_rate=0.5, tree_method="hist", n_jobs=1,
                         random_state=0).fit(*data)


def _forest_trees(model):
    for estimator in model.estimators_:
        tree = estimator.tree_
        values = tree.value[:, 0, :]
        yield {"left": tree.children_left, "right": tree.children_right, "feature": tree.feature,
               "threshold": tree.threshold, "cover": tree.weighted_n_node_samples,
               "value": values[:, 1] / values.sum(1) / len(model.estimators_),
               "goes_left": lambda value, threshold: value <= threshold}


def _booster_trees(model):
    trees = json.loads(model.get_booster().save_raw(raw_format="json"))["learner"]["gradient_booster"]["model"]["trees"]
    for tree in trees:
        yield {"left": np.asarray(tree["left_children"]), "right": np.asarray(tree["right_children"]),
               "feature": np.asarray(tree["split_indices"]),
               "threshold": np.asarray(tree["split_conditions"], dtype=np.float32),
               "cover": np.asarray(tree["sum_hessian"], dtype=np.float64),
               "value": np.asarray(tree["split_conditions"], dtype=np.float64),
               "goes_left": lambda value, threshold: np.float32(value) < threshold}


def _expected_value(inputs, known, tree, node=0):
    """Algorithm 1 de Lundberg et al. (2020): expectativa path-dependent dado o conjunto de atributos conhecidos."""
    left, right = tree["left"][node], tree["right"][node]
    if left == -1:
        return tree["value"][node]
    feature = tree["feature"][node]
    if feature in known:
        child = left if tree["goes_left"](inputs[feature], tree["threshold"][node]) else right
        return _expected_value(inputs, known, tree, child)
    return (_expected_value(inputs, known, tree, left) * tree["cover"][left]
            + _expected_value(inputs, known, tree, right) * tree["cover"][right]) / tree["cover"][node]


def _brute_force(inputs, trees):
    """Valor de Shapley exato pela soma sobre todos os subconjuntos de atributos."""
    features = len(inputs)

    def value(known):
        return sum(_expected_value(inputs, known, tree) for tree in trees)

    contributions = np.zeros(features)
    for feature in range(features):
        others = [other for other in range(features) if other != feature]
        for size in range(features):
            weight = math.factorial(size) * math.factorial(features - size - 1) / math.factorial(features)
            for subset in combinations(others, size):
                contributions[feature] += weight * (value(set(subset) | {feature}) - value(set(subset)))
    return value(set()), contributions


def _base_margin(model):
    learner = json.loads(model.get_booster().save_raw(raw_format="json"))["learner"]
    base_score = float(learner["learner_model_param"]["base_score"].strip("[]"))
    return math.log(base_score / (1 - base_score))


def test_random_forest_identity_holds_in_probability_scale_for_class_one(forest, data):
    inputs = data[0][:50]
    result = TreeShapExplainer(forest).explain(inputs)
    probabilities = forest.predict_proba(inputs)
    explained = result.reference_value + result.contributions.sum(1)
    np.testing.assert_allclose(explained, probabilities[:, 1], atol=1e-12, rtol=0)
    assert not np.allclose(explained, probabilities[:, 0], atol=1e-6)


def test_xgboost_identity_holds_in_log_odds_scale(booster, data):
    inputs = data[0][:50]
    result = TreeShapExplainer(booster).explain(inputs)
    margin = booster.predict(inputs, output_margin=True)
    np.testing.assert_allclose(result.reference_value + result.contributions.sum(1), margin, atol=1e-5, rtol=0)


@pytest.mark.parametrize("model_name,trees,tolerance", [
    ("forest", _forest_trees, 1e-12),
    ("booster", _booster_trees, 1e-5),
])
def test_contributions_match_brute_force_shapley_values(request, data, model_name, trees, tolerance):
    model = request.getfixturevalue(model_name)
    inputs = data[0][:5]
    result = TreeShapExplainer(model).explain(inputs)
    offset = _base_margin(model) if model_name == "booster" else 0.0
    for row, contributions in zip(inputs, result.contributions):
        reference, expected = _brute_force(row, list(trees(model)))
        np.testing.assert_allclose(contributions, expected, atol=tolerance, rtol=0)
        assert result.reference_value == pytest.approx(reference + offset, abs=tolerance)


@pytest.mark.parametrize("model_name", ["forest", "booster"])
def test_features_without_split_receive_exactly_zero(request, data, model_name):
    model = request.getfixturevalue(model_name)
    unused = features_without_split(model)
    assert CONSTANT_FEATURE in unused and len(unused) < data[0].shape[1]
    contributions = TreeShapExplainer(model).explain(data[0][:50]).contributions
    assert np.all(contributions[:, unused] == 0)
    used = [feature for feature in range(data[0].shape[1]) if feature not in unused]
    assert np.all(np.any(contributions[:, used] != 0, axis=0))


def test_xgboost_reference_value_matches_hessian_weighted_leaves(booster, data):
    result = TreeShapExplainer(booster).explain(data[0][:1])
    assert xgboost_reference_value(booster.get_booster()) == pytest.approx(result.reference_value, abs=1e-5)


@pytest.mark.parametrize("arguments", [
    {"data": np.zeros((2, 5))},
    {"feature_perturbation": "interventional"},
    {"approximate": True},
    {"model_output": "probability"},
])
def test_explainer_refuses_reference_set_interventional_and_approximation(forest, arguments):
    with pytest.raises(ValueError):
        TreeShapExplainer(forest, **arguments)


def test_explainer_refuses_classes_other_than_zero_and_one(data):
    inputs, labels = data
    model = RandomForestClassifier(n_estimators=2, max_depth=2, random_state=0).fit(inputs, labels + 1)
    with pytest.raises(ValueError, match="classes 0 e 1"):
        TreeShapExplainer(model)


def test_explainer_refuses_inputs_with_wrong_shape_or_non_finite_values(forest):
    explainer = TreeShapExplainer(forest)
    with pytest.raises(ValueError):
        explainer.explain(np.zeros((2, 4)))
    with pytest.raises(ValueError):
        explainer.explain(np.full((1, 5), np.inf))
