import csv
import io
import itertools
import json
from types import SimpleNamespace

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier

from core.explanation_worker import explanation_record
from core.tree_explainer import TreeShapExplainer, TreeShapResult, explained_output
from domains.nids import service
from domains.nids.exceptions import NidsError
from domains.nids.repository import _checked_resources, _checked_selection
from domains.nids.service import EXPLANATION_TIMING, TIMING, NidsService, Pipeline, processes_on_configured_cpus, warm_up
from domains.nids.strategies import (build_strategy, explanation_checks, pending_series, selection_rule,
                                     selection_table)

MANIFEST = {
    "inputs": ["Protocol", "Flow Bytes/s", "Flow Packets/s"],
    "preprocessing": {"positive_infinity_columns": ["Flow Bytes/s", "Flow Packets/s"],
                      "positive_infinity_replacement": -1.0},
}
VALUES = {"Flow ID": "10.0.0.1-10.0.0.2-1000-80-6", "Src IP": "10.0.0.1", "Src Port": "1000", "Dst IP": "10.0.0.2",
          "Dst Port": "80", "Protocol": "6", "Timestamp": "2017-07-04 12:00:00", "Flow Bytes/s": "120.5",
          "Flow Packets/s": "3"}


class FixedEstimator:
    def __init__(self, probability):
        self.probability = probability

    def predict_proba(self, inputs):
        return np.array([[1 - self.probability, self.probability]])


class FixedExplainer:
    def explain(self, inputs):
        return TreeShapResult(0.25, np.array([[0.5, -0.125, 0.0]]))


@pytest.fixture
def clock(monkeypatch):
    """Relógio que avança 10 ns a cada leitura, para que a ordem das marcações fique visível."""
    ticks = itertools.count(1000, 10)
    monkeypatch.setattr(service, "monotonic_ns", lambda: next(ticks))


def _flow(seq, selected, t3=60):
    return {"seq": seq, "error": None, "attack_probability": 0.9, "selected": selected, "t2_ns": 30,
            "selection_start_ns": 35, "selection_end_ns": 40, "t3_ns": t3, "flow_id": f"flow-{seq}"}


def _explanation(seq, t4=60, flow_id=None):
    return {"seq": seq, "flow_id": flow_id or f"flow-{seq}", "explanation_start_ns": 40, "explanation_end_ns": 50,
            "t4_ns": t4}


class FakeWorker:
    """Fila de explicações pendentes com lugar para um número fixo de solicitações."""

    def __init__(self, room):
        self.room, self.submitted = room, []

    def submit(self, seq, flow_id, vector, block):
        if len(self.submitted) >= self.room and not block:
            return False
        self.submitted.append((seq, flow_id, vector.tolist(), block))
        return True


def _run(strategy_key, probability=0.9, values=VALUES, criterion=None, threshold=None, worker=None, block=False):
    strategy = build_strategy(strategy_key, criterion, threshold)
    streams = {name: io.StringIO() for name in ("channel", "explanations", "explanation_table", "table")}
    synchronous = strategy.explains and strategy.synchronous
    pipeline = Pipeline(MANIFEST, FixedEstimator(probability), strategy,
                        FixedExplainer() if synchronous else None, streams["channel"],
                        streams["explanations"] if synchronous else None,
                        csv.DictWriter(streams["explanation_table"], fieldnames=EXPLANATION_TIMING),
                        csv.DictWriter(streams["table"], fieldnames=TIMING + list(values)),
                        worker=worker, block_on_full_queue=block)
    flow = SimpleNamespace(seq=7, cause="timeout_sweep", first_packet_us=1, last_packet_us=2, capture_clock_us=3,
                           t0_ns=900, values=values)
    record = NidsService._classify(None, flow, pipeline)
    return record, {name: stream.getvalue() for name, stream in streams.items()}


def test_the_reference_strategy_explains_no_flow_and_the_total_one_explains_every_flow():
    assert not build_strategy("sem-xai").select(0.99) and not build_strategy("sem-xai").explains
    total = build_strategy("sincrono-total")
    assert total.select(0.0) and total.select(1.0) and total.synchronous and total.explains
    with pytest.raises(NidsError):
        build_strategy("outra")


def test_without_explanations_the_flow_is_classified_and_only_the_classification_is_delivered(clock):
    record, written = _run("sem-xai")
    assert record["selected"] == 0 and record["explanation"] == "nao_selecionada"
    assert record["t0_ns"] <= record["t1_ns"] < record["t2_ns"] < record["selection_start_ns"]
    assert record["selection_end_ns"] == record["delivery_start_ns"] < record["t3_ns"]
    assert json.loads(written["channel"])["attack_probability"] == 0.9
    assert written["explanations"] == "" and written["explanation_table"] == ""


def test_the_synchronous_explanation_is_generated_before_the_classification_is_delivered(clock):
    record, written = _run("sincrono-total")
    marks = dict(zip(EXPLANATION_TIMING, written["explanation_table"].strip().split(",")))
    assert record["selected"] == 1 and record["explanation"] == "concluida"
    # O tempo de explicação fica entre o fim da seleção e o início da escrita nos canais de saída.
    assert int(marks["explanation_start_ns"]) == record["selection_end_ns"]
    assert int(marks["explanation_end_ns"]) == record["delivery_start_ns"] > record["selection_end_ns"]
    assert int(marks["t4_ns"]) == record["t3_ns"] > record["delivery_start_ns"] and marks["dequeued_ns"] == ""
    assert json.loads(written["explanations"]) == {"seq": 7, "flow_id": VALUES["Flow ID"], "reference_value": 0.25,
                                                   "contributions": [0.5, -0.125, 0.0]}


def test_both_strategies_deliver_the_same_classification_record(clock):
    assert _run("sem-xai")[1]["channel"] == _run("sincrono-total")[1]["channel"]


def test_a_flow_that_cannot_be_classified_is_neither_delivered_nor_explained(clock):
    record, written = _run("sincrono-total", values={**VALUES, "Flow Bytes/s": "NaN"})
    assert record["error"] and record["selected"] is None and record["t1_ns"] is None
    assert written["channel"] == "" and written["explanations"] == "" and written["table"].count("\n") == 1


def test_the_asynchronous_strategy_delivers_the_classification_before_requesting_the_explanation(clock):
    worker = FakeWorker(room=1)
    record, written = _run("assincrono", worker=worker)
    assert build_strategy("assincrono").explains and not build_strategy("assincrono").synchronous
    assert record["explanation"] == "solicitada" and record["explanation_requested_ns"] > record["t3_ns"]
    assert worker.submitted == [(7, VALUES["Flow ID"], [[6.0, 120.5, 3.0]], False)]
    assert written["explanations"] == "" and written["explanation_table"] == ""
    assert written["channel"] == _run("sem-xai")[1]["channel"]


def test_a_request_that_finds_the_queue_full_is_dropped_live_and_waits_in_file_mode(clock):
    worker = FakeWorker(room=0)
    dropped, _ = _run("assincrono", worker=worker)
    assert dropped["explanation"] == "descartada" and not worker.submitted
    waited, _ = _run("assincrono", worker=worker, block=True)
    assert waited["explanation"] == "solicitada" and worker.submitted[0][3] is True


def _async_flow(seq, status, requested=70):
    return {**_flow(seq, 1), "explanation": status, "explanation_requested_ns": requested}


def _async_explanation(seq, dequeued=80, t4=100):
    return {**_explanation(seq, t4=t4), "dequeued_ns": dequeued, "explanation_start_ns": 85, "explanation_end_ns": 95}


def test_asynchronous_checks_pass_when_each_request_is_accepted_or_dropped_and_explained_later():
    flows = [_async_flow(1, "solicitada"), _async_flow(2, "descartada", requested=None), _async_flow(3, "solicitada")]
    checks = explanation_checks(build_strategy("assincrono"), flows, [_async_explanation(1)], 0.0, 1e-9)
    assert all(checks.values()) and "explained_equals_selected" not in checks


@pytest.mark.parametrize("flows, explanations, failed", [
    ([_async_flow(1, "descartada")], [_async_explanation(1)], "no_explanation_without_accepted_request"),
    ([_async_flow(1, "solicitada", requested=50)], [_async_explanation(1)], "explanation_marks_ordered"),
    ([_async_flow(1, "solicitada")], [_async_explanation(1, dequeued=60)], "explanation_marks_ordered"),
    ([_async_flow(1, "nao_selecionada")], [], "every_selected_flow_requested_or_dropped"),
])
def test_asynchronous_checks_point_to_what_broke(flows, explanations, failed):
    checks = explanation_checks(build_strategy("assincrono"), flows, explanations, 0.0, 1e-9)
    assert not checks[failed]


def test_pending_size_is_rebuilt_from_request_and_dequeue_instants():
    second = 1_000_000_000
    series = pending_series([10, 20, 30, second + 5], [25, 40, second + 6], origin_ns=0)
    assert (series["max"], series["max_at_ns"]) == (2, 20)
    assert series["max_by_second"] == [[0, 2], [1, 2]]
    assert pending_series([], [], 0) == {"max": 0, "max_at_ns": None, "max_by_second": []}


RESOURCES = {"cpus": {"classifier": [2], "explainer": [0], "extractor": [4, 5], "replay": [8]},
             "extractor_max_heap_mib": 4096, "extractor_jvm_options": []}


def test_each_process_needs_its_own_cpus():
    _checked_resources(RESOURCES)
    for cpus in ({**RESOURCES["cpus"], "explainer": [2]}, {**RESOURCES["cpus"], "replay": []},
                 {**RESOURCES["cpus"], "replay": [4096]}):
        with pytest.raises(ValueError):
            _checked_resources({**RESOURCES, "cpus": cpus})


def test_extractor_jvm_options_are_jvm_flags_without_the_heap_limit():
    _checked_resources({**RESOURCES, "extractor_jvm_options": ["-Dnio.mx=1073741824", "-XX:+ExplicitGCInvokesConcurrent"]})
    for options in ("-Dnio.mx=1073741824", ["nio.mx=1073741824"], ["-Xmx8g"], [1]):
        with pytest.raises(ValueError):
            _checked_resources({**RESOURCES, "extractor_jvm_options": options})


def test_processes_are_on_the_configured_cpus_only_when_every_thread_is():
    observed = {"configured": RESOURCES["cpus"], "classifier": [[2]], "explainer": [[0]], "extractor": [4, 5]}
    assert processes_on_configured_cpus(observed)
    assert not processes_on_configured_cpus({**observed, "classifier": [[2], [0, 1, 2, 3]]})
    assert not processes_on_configured_cpus({**observed, "extractor": [4, 5, 6]})
    assert processes_on_configured_cpus({**observed, "explainer": None})


def test_the_probability_criterion_selects_alerts_and_the_uncertainty_criterion_selects_doubtful_flows():
    by_probability, by_uncertainty = selection_rule("probabilidade", 0.3), selection_rule("incerteza", 0.2)
    assert [by_probability(value) for value in (0.0, 0.29, 0.3, 0.5, 1.0)] == [False, False, True, True, True]
    assert [by_uncertainty(value) for value in (0.0, 0.29, 0.3, 0.5, 0.7, 0.71, 1.0)] == [
        False, False, True, True, True, False, False]
    assert by_probability(np.array([0.1, 0.9])).tolist() == [False, True]
    assert by_uncertainty(np.array([0.1, 0.45, 0.9])).tolist() == [False, True, False]
    with pytest.raises(NidsError):
        selection_rule("outro", 0.5)


def test_the_conditional_strategy_needs_a_criterion_and_the_other_strategies_refuse_one():
    conditional = build_strategy("sincrono-condicional", "probabilidade", 0.3)
    assert conditional.synchronous and conditional.select(0.3) and not conditional.select(0.2)
    assert (conditional.criterion, conditional.threshold) == ("probabilidade", 0.3)
    for arguments in (("sincrono-condicional",), ("sincrono-condicional", "incerteza", None),
                      ("sincrono-total", "probabilidade", 0.3), ("sem-xai", "incerteza", 0.1)):
        with pytest.raises(NidsError):
            build_strategy(*arguments)


def test_the_conditional_strategy_explains_only_the_selected_flows(clock):
    selected, written = _run("sincrono-condicional", probability=0.9, criterion="probabilidade", threshold=0.3)
    assert selected["explanation"] == "concluida" and written["explanations"].count("\n") == 1
    skipped, written = _run("sincrono-condicional", probability=0.2, criterion="probabilidade", threshold=0.3)
    assert skipped["selected"] == 0 and skipped["explanation"] == "nao_selecionada"
    assert written["explanations"] == "" and written["explanation_table"] == ""
    # O fluxo não selecionado é entregue como na estratégia Sem XAI.
    assert written["channel"] == _run("sem-xai", probability=0.2)[1]["channel"]
    assert skipped["selection_end_ns"] == skipped["delivery_start_ns"]


def test_selection_table_counts_what_each_threshold_selects_among_attacks_benign_and_errors():
    probability = np.array([0.05, 0.2, 0.45, 0.55, 0.8, 0.95])
    labels = np.array([0, 0, 1, 0, 1, 1])
    predictions = (probability > 0.5).astype(np.int8)
    low, high = selection_table("probabilidade", [0.4, 0.9], probability, labels, predictions)
    assert (low["selected"], low["attacks_selected"], low["benign_selected"], low["errors_selected"]) == (4, 3, 1, 2)
    assert (high["selected"], high["attacks_selected"], high["benign_selected"], high["errors_selected"]) == (1, 1, 0, 0)
    assert low["attacks_selected_share"] == 1.0 and high["errors_selected_share"] == 0.0
    doubtful, = selection_table("incerteza", [0.1], probability, labels, predictions)
    assert (doubtful["selected"], doubtful["errors_selected"], doubtful["selected_share"]) == (2, 2, 2 / 6)


SELECTION = {"calibration_grid": {"probabilidade": [0.1, 0.5], "incerteza": [0.1, 0.4]}, "calibration_run": None,
             "thresholds": {"probabilidade": {"random-forest": None, "xgboost": None},
                            "incerteza": {"random-forest": None, "xgboost": None}}}


def _selection(**changes):
    selection = json.loads(json.dumps(SELECTION))
    for path, value in changes.items():
        target, *keys = path.split("__")
        node = selection
        for key in [target, *keys][:-1]:
            node = node[key]
        node[[target, *keys][-1]] = value
    return selection


def test_selection_settings_accept_thresholds_still_to_be_fixed_and_fixed_ones_with_their_calibration():
    assert _checked_selection(_selection()) == SELECTION
    fixed = _selection(calibration_run="training-runs/nids/calibracao/x",
                       **{"thresholds__probabilidade__xgboost": 0.5, "thresholds__incerteza__random-forest": 0.4})
    assert _checked_selection(fixed)["thresholds"]["probabilidade"]["xgboost"] == 0.5


@pytest.mark.parametrize("changes", [
    {"thresholds__probabilidade__xgboost": 0.5},
    {"calibration_run": "x", "thresholds__incerteza__xgboost": 0.6},
    {"calibration_run": "x", "thresholds__probabilidade__xgboost": 0},
    {"calibration_grid__incerteza": []},
    {"calibration_grid__probabilidade": [0.5, 1.5]},
    {"thresholds__incerteza": {"random-forest": None}},
])
def test_selection_settings_reject_thresholds_out_of_range_or_without_calibration(changes):
    with pytest.raises(ValueError):
        _checked_selection(_selection(**changes))


def test_explanation_checks_pass_when_every_selected_flow_has_its_explanation_at_delivery():
    flows = [_flow(1, 1), _flow(2, 1), {"seq": 3, "error": "Valor não finito em Flow Bytes/s."}]
    checks = explanation_checks(build_strategy("sincrono-total"), flows, [_explanation(1), _explanation(2)], 1e-12, 1e-9)
    assert all(checks.values())
    assert all(explanation_checks(build_strategy("sem-xai"), [_flow(1, 0)], [], None, 1e-9).values())


@pytest.mark.parametrize("flows, explanations, residual, failed", [
    ([_flow(1, 1), _flow(2, 1)], [_explanation(1)], 0.0, {"explained_equals_selected"}),
    ([_flow(1, 1)], [_explanation(1, t4=61)], 0.0, {"explanation_marks_ordered"}),
    ([_flow(1, 1)], [_explanation(1, flow_id="outro")], 0.0, {"explanations_match_classifications"}),
    ([_flow(1, 1)], [_explanation(1), _explanation(1)], 0.0, {"explanations_match_classifications"}),
    ([_flow(1, 1)], [_explanation(1)], 1e-6, {"sum_identity"}),
    ([_flow(1, 0)], [], None, {"selection_follows_strategy"}),
])
def test_explanation_checks_point_to_what_broke(flows, explanations, residual, failed):
    checks = explanation_checks(build_strategy("sincrono-total"), flows, explanations, residual, 1e-9)
    assert {name for name, passed in checks.items() if not passed} >= failed


@pytest.fixture(scope="module")
def models():
    rng = np.random.default_rng(0)
    inputs = rng.integers(0, 10, size=(300, 5)).astype(np.float64)
    labels = ((inputs[:, 0] + inputs[:, 1] * (inputs[:, 2] > 4) + rng.normal(0, 1, 300)) > 7).astype(np.int64)
    forest = RandomForestClassifier(n_estimators=4, max_depth=3, random_state=0, n_jobs=1).fit(inputs, labels)
    booster = XGBClassifier(n_estimators=4, max_depth=3, learning_rate=0.5, tree_method="hist", n_jobs=1,
                            random_state=0).fit(inputs, labels)
    return inputs, {"random-forest": (forest, 1e-9), "xgboost": (booster, 1e-4)}


@pytest.mark.parametrize("name", ["random-forest", "xgboost"])
def test_the_delivered_record_keeps_the_identity_between_contributions_and_explained_output(models, name):
    inputs, estimators = models
    estimator, tolerance = estimators[name]
    explainer = TreeShapExplainer(estimator)
    for row in inputs[:20]:
        vector = row.reshape(1, -1)
        result = explainer.explain(vector)
        record = json.loads(json.dumps(explanation_record(1, "flow", result.reference_value, result.contributions[0])))
        explained = record["reference_value"] + float(np.sum(record["contributions"]))
        assert abs(explained - explained_output(estimator, vector)[0]) <= tolerance


def test_warm_up_builds_the_explainer_only_for_strategies_that_explain(models):
    forest = models[1]["random-forest"][0]
    explainer, record = warm_up(forest, build_strategy("sem-xai"), 5)
    assert explainer is None and record["explainer_construction_ns"] is None and record["inference_ns"] > 0
    explainer, record = warm_up(forest, build_strategy("sincrono-total"), 5)
    assert isinstance(explainer, TreeShapExplainer) and record["explainer_construction_ns"] > 0
    assert record["explanation_ns"] > 0
