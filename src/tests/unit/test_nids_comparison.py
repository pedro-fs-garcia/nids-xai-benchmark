import copy

import pytest

from domains.nids.comparison import compare, measurement_points_present

TIMINGS = {key: {"mean": 1.0, "p95": 2.0, "p99": 3.0} for key in (
    "inference_ns", "classification_latency_ns", "wait_before_inference_ns", "selection_ns", "delivery_ns")}
EXPLANATION_TIMINGS = {key: {"mean": 1.0, "p95": 2.0, "p99": 3.0} for key in ("explanation_ns", "explanation_latency_ns")}
PROBABILITY = {1: 0.9, 2: 0.45, 3: 0.1}


def _report(key, criterion=None, threshold=None, completed=3, **changes):
    report = {
        "run_id": f"{key}-{criterion}", "stage": "nids run", "passed": True, "model": "xgboost",
        "strategy": key, "strategy_key": key,
        "selection": None if criterion is None else {"criterion": criterion, "threshold": threshold},
        "source": {"kind": "arquivo", "pcap": "trecho.pcap"}, "segment": {"pcap": {"sha256": "trecho"}},
        "config_sha256": "config", "model_manifest_sha256": "modelo", "tree_shap_config_sha256": "treeshap",
        "explainer": {"feature_perturbation": "tree_path_dependent"}, "extractor_build": {"jars": {"nids": "jar"}},
        "extractor_options": {"snaplen": 65535}, "classifier_threads": 1,
        "environment": {"python": "3.12.3", "libraries": {"shap": "0.54.1"}},
        "checks": {"processes_on_configured_cpus": True},
        "artifacts": {"classifications.jsonl": {"sha256": "classificacoes"}},
        "flows": {"received": 4, "classified": 3, "errors": 1},
        "explanations": {"eligible": 3, "selected": completed, "completed": completed},
        "timings": {**TIMINGS, **(EXPLANATION_TIMINGS if completed else {}),
                    **({"queue_wait_ns": {"mean": 1.0, "p95": 2.0, "p99": 3.0}} if key == "assincrono" else {})},
        "extractor_end": {"flows_dropped": 0},
        "resources": {"cpus": {"configured": {"classifier": [2]}}, "classifier_process": {
            "user_seconds": 1.0, "system_seconds": 0.5, "max_rss_kib": 2048}, "explainer_process": None,
            "extractor_process": {"cpu_ns": 2e9, "max_rss_kib": 4096}},
    }
    report.update(changes)
    return report


def _explanations(seqs, shift=0.0):
    return {seq: {"seq": seq, "flow_id": f"flow-{seq}", "reference_value": -1.0, "contributions": [0.5 + shift, 0.25]}
            for seq in seqs}


FLOWS = [{"seq": str(seq), "error": "", "attack_probability": str(value)} for seq, value in PROBABILITY.items()]


def _set(reports=None, explanations=None):
    reports = reports or [_report("sem-xai", completed=0), _report("sincrono-total"),
                          _report("sincrono-condicional", "probabilidade", 0.5, completed=1),
                          _report("sincrono-condicional", "incerteza", 0.1, completed=1), _report("assincrono")]
    explanations = explanations or [{}, _explanations([1, 2, 3]), _explanations([1]), _explanations([2]),
                                    _explanations([1, 2, 3])]
    return reports, explanations, [FLOWS] * len(reports)


def test_runs_of_the_four_strategies_with_the_same_inputs_are_comparable():
    result = compare(*_set())
    assert result["passed"] and result["file_mode"]
    assert result["checks"]["conditional_probabilidade_explains_the_selected_subset_of_total"]
    assert result["checks"]["conditional_incerteza_explains_the_selected_subset_of_total"]
    assert result["differences"]["total_vs_async"] == {"common": 3, "max_abs_difference": 0.0, "equal": True}
    assert [row["selected"] for row in result["runs"]] == [0, 3, 1, 1, 3]


@pytest.mark.parametrize("position, change, failed", [
    (1, {"config_sha256": "outra"}, "same_fixed_inputs"),
    (4, {"artifacts": {"classifications.jsonl": {"sha256": "outras"}}}, "identical_classifications"),
    (2, {"passed": False}, "every_run_passed"),
    (3, {"checks": {"processes_on_configured_cpus": False}}, "processes_on_configured_cpus"),
    (0, {"flows": {"received": 4, "classified": 2, "errors": 2}}, "same_flows"),
])
def test_a_run_that_differs_breaks_comparability(position, change, failed):
    reports, explanations, flows = _set()
    reports[position] = {**reports[position], **change}
    assert not compare(reports, explanations, flows)["checks"][failed]


def test_explanations_of_the_same_flow_must_match_across_strategies():
    reports, explanations, flows = _set()
    explanations[4] = _explanations([1, 2, 3], shift=1e-9)
    explanations[2] = _explanations([1, 2])
    checks = compare(reports, explanations, flows)["checks"]
    assert not checks["async_explanations_equal_total"]
    assert not checks["conditional_probabilidade_explains_the_selected_subset_of_total"]


def test_a_missing_strategy_or_a_repeated_one_is_refused():
    reports, explanations, flows = _set()
    assert not compare(reports[:-1], explanations[:-1], flows[:-1])["checks"]["four_strategies_once_each"]
    repeated = compare(reports + [copy.deepcopy(reports[0])], explanations + [{}], flows + [FLOWS])
    assert not repeated["checks"]["four_strategies_once_each"]


def test_emulated_runs_are_compared_without_flow_by_flow_checks():
    reports, explanations, flows = _set()
    for report in reports:
        report["source"] = {"kind": "interface", "iface": "h2-eth0"}
        report["artifacts"]["classifications.jsonl"] = {"sha256": report["run_id"]}
    result = compare(reports, [{}] * 5, [[]] * 5)
    assert result["passed"] and not result["file_mode"] and "identical_classifications" not in result["checks"]


def test_each_strategy_records_the_times_it_produces():
    assert measurement_points_present(_report("sem-xai", completed=0))
    assert measurement_points_present(_report("assincrono"))
    without_wait = _report("assincrono")
    del without_wait["timings"]["queue_wait_ns"]
    assert not measurement_points_present(without_wait)
    assert not measurement_points_present({**_report("sem-xai", completed=0),
                                           "timings": {**TIMINGS, **EXPLANATION_TIMINGS}})
