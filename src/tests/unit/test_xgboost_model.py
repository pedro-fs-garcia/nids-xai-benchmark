import numpy as np
import pytest

from core.xgboost_model import XGBoostAdapter


def test_xgboost_probability_is_the_logistic_transform_of_the_ensemble_score() -> None:
    rng = np.random.default_rng(42)
    inputs = rng.normal(size=(100, 3))
    labels = (inputs[:, 0] > 0).astype(np.int8)
    parameters = {
        "objective": "binary:logistic", "tree_method": "hist", "device": "cpu",
        "n_estimators": 5, "max_depth": 2, "learning_rate": 0.1, "n_jobs": 1,
    }
    model = XGBoostAdapter(parameters)
    model.fit(inputs, labels)
    example = model.prediction_example(inputs)
    assert example["probability"] == pytest.approx(example["logistic_of_score"], abs=1e-7)
    predictions, probabilities = model.predict(inputs)
    assert np.array_equal(predictions, (probabilities > 0.5).astype(np.int8))
    complexity = model.complexity()
    assert complexity["trees"] == 5
    assert complexity["depth_max"] <= 2
    assert complexity["nodes_total"] == 2 * complexity["leaves_total"] - complexity["trees"]
    assert model.parameters() == parameters
