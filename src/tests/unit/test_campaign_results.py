import csv
import math

import numpy as np
import pytest

from domains.campaign import figures
from domains.campaign.matrix import expand
from domains.campaign.results import (busy_periods, combinations, differences, execution_row, measure, overhead,
                                      queue_grows_to_end, read_explanations, read_flows, valid_entries, viability)
from domains.campaign.results_reporting import render_results
from domains.nids.exceptions import NidsError
from domains.nids.repository import NidsRepository
from tests.unit.test_campaign_audit import EXPLANATION_HEADER, FLOW_HEADER, _entry, _matrix

MODELS = ("random-forest", "xgboost")
CONFIGURATIONS = ("sem-xai", "sincrono-total", "sincrono-condicional-probabilidade", "sincrono-condicional-incerteza",
                  "assincrono")


def _write(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    return path


SECOND = 1_000_000_000


def _flow(seq, explanation, scale=1, error=""):
    base = seq * SECOND
    marks = {} if error else {"t0_ns": base, "t1_ns": base + 10 * scale, "t2_ns": base + 20 * scale,
                              "t3_ns": base + 30 * scale}
    requested = str(base + 30 * scale + 1) if explanation in ("solicitada", "descartada") else ""
    selected = "" if error else ("0" if explanation == "nao_selecionada" else "1")
    return {"seq": str(seq), **{key: str(marks.get(key, "")) for key in ("t0_ns", "t1_ns", "t2_ns", "t3_ns")},
            "prediction": "" if error else "0", "attack_probability": "", "error": error, "selected": selected,
            "selection_start_ns": "", "selection_end_ns": "", "delivery_start_ns": "",
            "explanation": "" if error else explanation, "explanation_requested_ns": requested}


def _asynchronous(tmp_path, scale=1):
    """Quatro fluxos classificados, um por segundo, e um não classificável. Três solicitações aceitas, uma descartada, duas
    explicações concluídas e uma pendente. O fluxo 6 foi descartado pelo extrator."""
    flows = [_flow(1, "solicitada", scale), _flow(2, "solicitada", scale), _flow(3, "solicitada", scale),
             _flow(4, "descartada", scale), _flow(5, "", error="nan")]
    explained = [{"seq": str(seq), "dequeued_ns": str(seq * SECOND + 30 * scale + 6),
                  "explanation_start_ns": str(seq * SECOND + 30 * scale + 7),
                  "explanation_end_ns": str(seq * SECOND + 30 * scale + 8),
                  "t4_ns": str(seq * SECOND + 30 * scale + 9)}
                 for seq in (1, 2)]
    flows_path = _write(tmp_path / f"flows-{scale}.csv", FLOW_HEADER, flows)
    explanations_path = _write(tmp_path / f"explanations-{scale}.csv", EXPLANATION_HEADER, explained)
    return measure(read_flows(flows_path), read_explanations(explanations_path))


def _report(measured, emitted=6, dropped=1):
    return {"flows": dict(measured["flows"]), "extractor_end": {"flows_emitted": emitted, "flows_dropped": dropped},
            "timings": {key: (dict(value) if isinstance(value, dict) else value)
                        for key, value in measured["timings"].items()},
            "explanations": {"selected": measured["selected"], "completed": measured["completed"]},
            "explanation_queue": None if measured["queue"] is None else {**measured["queue"], "limit": 10}}


def _replay(load):
    return {"copies": load, "delivered": {"flows_per_second": 20.0 * load},
            "tcpreplay": {"rated_packets_per_second": 3000.0 * load}, "interface_counters": {},
            "machine": {"frequency_khz": {"0": {"median": 3_000_000}, "2": {"median": 400_000}},
                        "busy_share": {"1": {"max": 0.5}, "3": {"max": 0.7}},
                        "memory_available_kib": {"min": 8 * 1024 * 1024}}}


def test_busy_periods_join_overlapping_flows_and_count_departures_first_at_the_same_instant():
    periods = busy_periods(*(np.array(values) for values in ([0, 5, 12, 20], [10, 12, 15, 25])))
    # De 0 a 12 há sempre um fluxo pendente; em 12 o segundo sai antes de o terceiro entrar, e um novo intervalo
    # vai de 12 a 15. O último vai de 20 a 25.
    assert periods["longest_ns"] == 12
    assert math.isclose(periods["busy_share"], (12 + 3 + 5) / 25)
    assert math.isclose(periods["longest_share"], 12 / 25)


def test_measure_recomputes_latencies_coverage_and_queue_from_the_raw_tables(tmp_path):
    measured = _asynchronous(tmp_path)
    assert measured["flows"] == {"received": 5, "classified": 4, "errors": 1}
    assert measured["timings"]["classification_latency_ns"]["mean"] == 30
    assert measured["timings"]["wait_before_inference_ns"]["max"] == 10
    assert measured["timings"]["queue_wait_ns"]["mean"] == 5
    assert measured["timings"]["explanation_latency_ns"]["mean"] == 39
    assert (measured["selected"], measured["completed"]) == (4, 2)
    queue = measured["queue"]
    assert (queue["accepted"], queue["dropped"], queue["completed"], queue["pending"]) == (3, 1, 2, 1)
    assert queue["size"]["max"] == 1
    assert measured["pending_classification"]["max"] == 1
    assert measured["pending_classification"]["longest_ns"] == 30
    assert list(measured["series"]["emitted_per_second"]) == [1, 1, 1, 1]


def test_differences_flag_a_statistic_or_a_count_that_does_not_match_the_nids_record(tmp_path):
    measured = _asynchronous(tmp_path)
    report = _report(measured)
    assert differences(measured, report) == []
    report["timings"]["classification_latency_ns"]["p95"] += 1
    report["explanation_queue"]["dropped"] = 0
    report["extractor_end"]["flows_dropped"] = 2
    found = " | ".join(differences(measured, report))
    assert "classification_latency_ns difere" in found and "dropped" in found and "não somam" in found


def test_valid_entries_need_exactly_one_valid_execution_per_cell():
    cells = expand(_matrix(repetitions=2))
    first, second = cells
    assert [entry["cell"]["id"] for entry in valid_entries(cells, [_entry(second, 1, True), _entry(first, 1, False),
                                                                  _entry(first, 2, True)])] == [first.id, second.id]
    with pytest.raises(NidsError, match=second.id):
        valid_entries(cells, [_entry(first, 1, True)])
    with pytest.raises(NidsError, match=first.id):
        valid_entries(cells, [_entry(first, 1, True), _entry(first, 2, True), _entry(second, 1, True)])


def _executions(tmp_path):
    rows, series = [], {}
    for model in MODELS:
        for configuration in CONFIGURATIONS:
            for repetition, scale in enumerate((1, 2, 3), start=1):
                measured = _asynchronous(tmp_path, scale)
                cell = {"model": model, "configuration": configuration, "load": 1, "repetition": repetition,
                        "id": f"b/{model}/{configuration}/carga-1/rep-{repetition}"}
                report = {**_report(measured), "extractor_end": {"flows_emitted": 6, "flows_dropped": 1},
                          "resources": {"classifier_process": {"user_seconds": 1.5 * scale, "system_seconds": 0.5,
                                                               "max_rss_kib": 2048}}}
                rows.append(execution_row(cell, f"runs/{repetition}", report, _replay(1), measured))
                series[cell["id"]] = measured["series"]
    return rows, series


def test_combinations_summarize_the_repetitions_by_median_minimum_and_maximum(tmp_path):
    rows, _ = _executions(tmp_path)
    summary = combinations(rows)
    assert [(item["model"], item["configuration"]) for item in summary[:5]] == [
        ("random-forest", configuration) for configuration in CONFIGURATIONS]
    latency = summary[0]["measures"]["classification_mean_ms"]
    assert (latency["min"], latency["median"], latency["max"]) == (30e-6, 60e-6, 90e-6)
    cpu = summary[0]["measures"]["cpu_classifier_s"]
    assert (cpu["min"], cpu["median"], cpu["max"]) == (2.0, 3.5, 5.0)
    assert summary[0]["measures"]["cpu_explainer_s"] is None
    assert summary[0]["measures"]["flows_dropped_share"]["median"] == 1 / 6
    # O fluxo descartado pelo extrator reprova todas as execuções, que não saturam.
    assert summary[0]["viability"] == {"latency": 3, "no_dropped_flow": 0, "queue": 3, "viable": 0}
    assert not summary[0]["viable"] and summary[0]["saturated"] == 0
    assert summary[0]["overhead"] is None
    assert summary[1]["overhead"]["p95"] == {"ms": 0.0, "comparison": "não se distingue"}


def test_the_queue_grows_to_the_end_only_with_a_first_peak_in_the_last_tenth_or_a_full_queue_there():
    queue = {"max": 15, "max_at_share_of_run": 0.33, "max_in_last_tenth": 15, "limit": 10_000}
    assert not queue_grows_to_end(queue)
    assert queue_grows_to_end({**queue, "max_at_share_of_run": 0.95})
    assert queue_grows_to_end({**queue, "max": 10_001, "max_in_last_tenth": 10_001})


def test_an_execution_is_viable_only_within_the_latency_limits_without_drops_and_with_a_bounded_queue():
    row = {"timings": {"classification_latency_ns": {"p95": 1_000_000_000, "p99": 2_000_000_000}},
           "flows": {"dropped": 0}, "queue": None}
    assert viability(row) == {"latency": True, "no_dropped_flow": True, "queue": None, "viable": True}
    assert not viability({**row, "flows": {"dropped": 1}})["viable"]
    slow = {"classification_latency_ns": {"p95": 900_000_000, "p99": 2_000_000_001}}
    assert not viability({**row, "timings": slow})["viable"]
    growing = {"max": 30, "max_at_share_of_run": 0.97, "max_in_last_tenth": 30, "limit": 10_000}
    assert viability({**row, "queue": growing}) == {"latency": True, "no_dropped_flow": True, "queue": False,
                                                   "viable": False}


def test_overhead_is_the_difference_of_medians_and_overlapping_ranges_do_not_distinguish_a_strategy():
    baseline = {"min": 9.0, "median": 9.2, "max": 10.0}
    assert overhead({"min": 17.0, "median": 18.0, "max": 19.0}, baseline) == {"ms": 18.0 - 9.2, "comparison": "maior"}
    assert overhead({"min": 8.0, "median": 9.0, "max": 9.5}, baseline)["comparison"] == "não se distingue"
    assert overhead({"min": 5.0, "median": 6.0, "max": 8.9}, baseline)["comparison"] == "menor"


def test_report_and_figures_are_written_for_every_combination(tmp_path):
    rows, series = _executions(tmp_path)
    repo = NidsRepository(tmp_path, tmp_path, tmp_path / "runs", tmp_path / "reports")
    summary = {"matrix": "teste", "segment": "curto", "matrix_config": "configs/teste.json",
               "registry": "runs/registro.jsonl", "audit_report": "teste-auditoria-1.md", "run_id": "1",
               "executions": rows, "combinations": combinations(rows),
               "loads": [{"load": 1, "executions": len(rows), "flows_per_second": None, "packets_per_second": None,
                          "flows_emitted": None}]}
    summary["figures"] = figures.draw_all(summary, series, tmp_path / "figuras", repo)
    assert all((tmp_path / path).is_file() for path in summary["figures"].values())
    text = render_results(summary)
    assert "RF, Assíncrono, 1×" in text and "XGB, Sem XAI, 1×" in text
    assert all(f"](../{path})" in text for path in summary["figures"].values())
