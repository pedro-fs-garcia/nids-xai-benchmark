import time

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier

from core.explanation_worker import ExplanationWorker, ExplanationWorkerError, read_explanations
from core.tree_explainer import TreeShapExplainer, explained_output


def _model():
    rng = np.random.default_rng(0)
    inputs = rng.integers(0, 10, size=(200, 4)).astype(np.float64)
    labels = ((inputs[:, 0] + inputs[:, 1] + rng.normal(0, 1, 200)) > 9).astype(np.int64)
    return inputs, RandomForestClassifier(n_estimators=3, max_depth=3, random_state=0, n_jobs=1).fit(inputs, labels)


def synthetic_explainer(delay_s):
    """Fábrica do processo explicador nos testes: um Random Forest sintético e um atraso fixo por explicação."""
    _, model = _model()
    explainer = TreeShapExplainer(model)

    def explain(vector):
        time.sleep(delay_s)
        result = explainer.explain(vector)
        return result.reference_value, result.contributions[0]

    return explain, {"model_sha256": "sintetico", "load_ns": 0, "explainer_construction_ns": 1, "explanation_ns": 1}


def failing_explainer(delay_s):
    raise ValueError("modelo indisponível")


def _submit(worker, inputs, count, block=False):
    return [worker.submit(seq, f"flow-{seq}", inputs[seq:seq + 1], block) for seq in range(count)]


def test_the_explainer_process_explains_every_accepted_request_and_records_its_marks(tmp_path):
    inputs, model = _model()
    worker = ExplanationWorker(synthetic_explainer, (0.0,), tmp_path, limit=100, cpus=None, threads=1)
    assert all(_submit(worker, inputs, 30))
    end = worker.finish(drain_timeout_s=60)
    explanations, unmarked = read_explanations(tmp_path)
    assert (end["accepted"], end["dropped"], end["worker"]["received"], end["exit_code"]) == (30, 0, 30, 0)
    assert not end["killed_after_drain_timeout"] and unmarked == 0
    assert [item["seq"] for item in explanations] == list(range(30))
    assert all(item["dequeued_ns"] <= item["explanation_start_ns"] <= item["explanation_end_ns"] <= item["t4_ns"]
               for item in explanations)
    explained = np.array([item["reference_value"] + sum(item["contributions"]) for item in explanations])
    assert np.max(np.abs(explained - explained_output(model, inputs[:30]))) <= 1e-9
    assert end["worker"]["process"]["max_rss_kib"] > 0


def test_requests_that_find_the_queue_full_are_dropped_and_counted(tmp_path):
    inputs, _ = _model()
    worker = ExplanationWorker(synthetic_explainer, (0.2,), tmp_path, limit=3, cpus=None, threads=1)
    accepted = _submit(worker, inputs, 12)
    end = worker.finish(drain_timeout_s=60)
    explanations, _ = read_explanations(tmp_path)
    assert end["dropped"] >= 5 and end["accepted"] + end["dropped"] == 12
    assert sum(accepted) == end["accepted"] == end["worker"]["received"] == len(explanations)
    assert {item["seq"] for item in explanations} == {seq for seq, ok in enumerate(accepted) if ok}


def test_in_file_mode_a_request_waits_for_room_instead_of_being_dropped(tmp_path):
    inputs, _ = _model()
    worker = ExplanationWorker(synthetic_explainer, (0.05,), tmp_path, limit=2, cpus=None, threads=1)
    assert all(_submit(worker, inputs, 8, block=True))
    end = worker.finish(drain_timeout_s=60)
    assert (end["accepted"], end["dropped"], len(read_explanations(tmp_path)[0])) == (8, 0, 8)


def test_the_explainer_is_stopped_after_the_drain_timeout_and_what_is_left_stays_pending(tmp_path):
    inputs, _ = _model()
    worker = ExplanationWorker(synthetic_explainer, (0.5,), tmp_path, limit=20, cpus=None, threads=1)
    _submit(worker, inputs, 10)
    end = worker.finish(drain_timeout_s=1.2)
    explanations, _ = read_explanations(tmp_path)
    assert end["killed_after_drain_timeout"] and end["worker"] is None and not worker.process.is_alive()
    assert end["accepted"] == 10 and len(explanations) < 10


def test_an_explainer_that_cannot_start_fails_the_run(tmp_path):
    with pytest.raises(ExplanationWorkerError, match="modelo indisponível"):
        ExplanationWorker(failing_explainer, (0.0,), tmp_path, limit=10, cpus=None, threads=1)
