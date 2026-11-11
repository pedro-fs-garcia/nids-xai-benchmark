import numpy as np
import pytest

from core.classification import binary_metrics
from domains.model_training.exceptions import InvalidPilotConfigError
from domains.model_training.service import sample_training_indices


def test_sample_is_reproducible_without_replacement_and_covers_rare_labels() -> None:
    original = np.repeat([0, 1, 2, 3], [1000, 100, 3, 1])
    first = sample_training_indices(original, size=100, seed=42)
    second = sample_training_indices(original, size=100, seed=42)
    assert len(first) == len(np.unique(first)) == 100
    assert np.array_equal(first, second)
    assert set(original[first]) == {0, 1, 2, 3}
    assert (first >= 0).all() and (first < len(original)).all()
    assert not np.array_equal(first, sample_training_indices(original, size=100, seed=43))


def test_sample_approximates_original_proportions() -> None:
    original = np.repeat([0, 1], [7500, 2500])
    selected = sample_training_indices(original, size=1000, seed=42)
    assert np.mean(original[selected] == 1) == pytest.approx(0.25, abs=0.001)


@pytest.mark.parametrize("size", [2, 101])
def test_sample_rejects_size_that_cannot_preserve_labels_or_requires_duplicates(size: int) -> None:
    with pytest.raises(InvalidPilotConfigError):
        sample_training_indices(np.arange(100) % 3, size=size, seed=42)


def test_sample_can_use_all_training_rows() -> None:
    original = np.array([1, 2, 0])
    assert sample_training_indices(original, size=3, seed=42).tolist() == [0, 1, 2]


def test_binary_metrics_use_attack_as_positive_and_probability_for_roc_auc() -> None:
    metrics = binary_metrics(
        actual=np.array([0, 0, 1, 1]),
        predicted=np.array([0, 1, 0, 1]),
        probability=np.array([0.1, 0.8, 0.4, 0.9]),
    )
    assert metrics["confusion_matrix"] == {"tn": 1, "fp": 1, "fn": 1, "tp": 1}
    assert metrics["precision"] == metrics["recall"] == metrics["f1"] == 0.5
    assert metrics["false_positive_rate"] == 0.5
    assert metrics["roc_auc"] == 0.75
