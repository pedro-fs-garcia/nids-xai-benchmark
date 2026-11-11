import numpy as np
import pytest

from core.frozen_prediction import FrozenPredictor
from domains.model_artifacts.service import prepare_flow


@pytest.fixture
def manifest():
    return {
        "inputs": ["Flow Bytes/s", "Flow Packets/s", "Protocol"],
        "preprocessing": {"positive_infinity_columns": ["Flow Bytes/s", "Flow Packets/s"],
                          "positive_infinity_replacement": -1.0},
    }


def test_flow_uses_feature_order_and_training_infinity_rule(manifest):
    flow = {"Protocol": 6, "Flow Packets/s": "inf", "Flow Bytes/s": float("inf")}
    assert np.array_equal(prepare_flow(flow, manifest), [[-1, -1, 6]])
    assert flow["Flow Packets/s"] == "inf"


@pytest.mark.parametrize("field,value", [
    ("Protocol", float("inf")), ("Flow Bytes/s", float("-inf")),
    ("Flow Packets/s", float("nan")), ("Protocol", True), ("Protocol", "6"),
])
def test_flow_rejects_invalid_values(manifest, field, value):
    flow = dict.fromkeys(manifest["inputs"], 0)
    flow[field] = value
    with pytest.raises(ValueError):
        prepare_flow(flow, manifest)


@pytest.mark.parametrize("change", ["missing", "extra"])
def test_flow_rejects_wrong_feature_set(manifest, change):
    flow = dict.fromkeys(manifest["inputs"], 0)
    if change == "missing":
        del flow["Protocol"]
    else:
        flow["Label"] = 1
    with pytest.raises(ValueError, match="Atributos ausentes"):
        prepare_flow(flow, manifest)


def test_prediction_threshold_preserves_benign_ties():
    class Estimator:
        classes_ = [0, 1]

        def predict_proba(self, inputs):
            return np.array([[0.5, 0.5], [0.49, 0.51]])

    labels, _ = FrozenPredictor(Estimator()).predict(np.zeros((2, 3)))
    assert labels.tolist() == [0, 1]
