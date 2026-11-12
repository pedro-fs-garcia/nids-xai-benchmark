import numpy as np
import pytest

from domains.explanations.exceptions import ExplanationError
from domains.explanations.repository import ExplanationRepository
from domains.explanations.service import measurement_flows, select_example, stratified_sample


def test_repository_refuses_the_test_split(tmp_path):
    repository = ExplanationRepository(tmp_path, tmp_path, tmp_path, tmp_path)
    for name in ("test", "train"):
        with pytest.raises(ExplanationError, match="não permitido"):
            repository.load_split(name)


def test_stratified_sample_has_exact_size_minimum_per_label_and_is_reproducible():
    labels = np.repeat([0, 1, 2, 3], [9000, 500, 15, 3])
    sample = stratified_sample(labels, 1000, 42, 20)
    assert sample.size == 1000 and np.unique(sample).size == 1000
    counts = dict(zip(*np.unique(labels[sample], return_counts=True)))
    assert counts[2] == 15 and counts[3] == 3
    assert counts[0] + counts[1] == 982 and counts[1] >= 20
    assert np.array_equal(sample, stratified_sample(labels, 1000, 42, 20))
    assert not np.array_equal(sample, stratified_sample(labels, 1000, 7, 20))


def test_stratified_sample_rejects_impossible_sizes():
    labels = np.repeat([0, 1], [10, 10])
    with pytest.raises(ExplanationError):
        stratified_sample(labels, 30, 0, 1)
    with pytest.raises(ExplanationError):
        stratified_sample(labels, 5, 0, 5)


def test_example_is_the_lower_median_with_ties_broken_by_index():
    labels = np.array([5, 5, 5, 5, 0, 5, 5])
    predictions = np.array([1, 1, 1, 1, 1, 0, 1])
    probabilities = np.array([0.9, 0.7, 0.7, 0.6, 0.8, 0.75, 0.95])
    # Candidatos 0, 1, 2, 3 e 6, ordenados por probabilidade e índice: 3, 1, 2, 0, 6.
    assert select_example(labels, predictions, probabilities, 5, 1) == (2, 5)
    # Sem o registro 6, sobram quatro candidatos; vale o menor dos dois centrais, o registro 1.
    predictions[6] = 0
    assert select_example(labels, predictions, probabilities, 5, 1) == (1, 4)
    with pytest.raises(ExplanationError):
        select_example(labels, predictions, probabilities, 9, 1)


def test_measurement_flows_are_a_sorted_subset_of_the_sample():
    sample = np.arange(0, 20000, 2)
    flows = measurement_flows(sample, 1000, 42)
    assert flows.size == 1000 and np.all(np.diff(flows) > 0) and np.isin(flows, sample).all()
    assert np.array_equal(flows, measurement_flows(sample, 1000, 42))
