import csv
import json

from domains.campaign.audit import (CampaignAudit, capture_loss, count_issues, coverage, delivery_issues,
                                    explained_by_capture_loss, input_differences, recount, replacements)
from domains.campaign.audit_reporting import render_audit
from domains.campaign.matrix import Cell, expand
from domains.model_training.repository import sha256
from domains.nids.repository import NidsRepository

FLOW_HEADER = ["seq", "t0_ns", "t1_ns", "t2_ns", "t3_ns", "prediction", "attack_probability", "error", "selected",
               "selection_start_ns", "selection_end_ns", "delivery_start_ns", "explanation",
               "explanation_requested_ns"]
EXPLANATION_HEADER = ["seq", "dequeued_ns", "explanation_start_ns", "explanation_end_ns", "t4_ns"]


def _matrix(name="teste", configurations=("sincrono-total",), loads=(1,), repetitions=2):
    return {"name": name, "segment": "curto", "seed": 3,
            "machine": {"require_mains": True, "max_busy_share": 0.25, "min_available_mib": 1, "window_s": 1,
                        "max_wait_s": 1},
            "max_attempts": 2,
            "blocks": [{"label": "b", "models": ["random-forest"], "configurations": list(configurations),
                        "loads": list(loads), "repetitions": repetitions}]}


def _entry(cell, attempt, valid, started=True, run_dir=None):
    return {"cell": cell.as_dict(), "attempt": attempt,
            "result": {"started": started, "run_dir": None if run_dir is None else str(run_dir)},
            "validity": {"valid": valid, "reasons": [] if valid else ["o tcpreplay não enviou todos os pacotes"]}}


def _flow(seq, selected, explanation, requested="", error=""):
    base = seq * 100
    marks = {} if error else {"t0_ns": base, "t1_ns": base + 1, "t2_ns": base + 2, "t3_ns": base + 3}
    return {"seq": str(seq), "t0_ns": str(marks.get("t0_ns", "")), "t1_ns": str(marks.get("t1_ns", "")),
            "t2_ns": str(marks.get("t2_ns", "")), "t3_ns": str(marks.get("t3_ns", "")), "prediction": "0",
            "attack_probability": "0.1", "error": error, "selected": selected, "selection_start_ns": "",
            "selection_end_ns": "", "delivery_start_ns": "", "explanation": explanation,
            "explanation_requested_ns": requested}


def _explained(seq, synchronous=True):
    base = seq * 100
    if synchronous:
        return {"seq": str(seq), "dequeued_ns": "", "explanation_start_ns": str(base + 2),
                "explanation_end_ns": str(base + 3), "t4_ns": str(base + 3)}
    return {"seq": str(seq), "dequeued_ns": str(base + 5), "explanation_start_ns": str(base + 6),
            "explanation_end_ns": str(base + 7), "t4_ns": str(base + 8)}


def test_coverage_flags_unknown_cells_repeated_valid_runs_and_attempts_out_of_sequence():
    cells = expand(_matrix(repetitions=3))
    first, second, third = cells
    outside = Cell("outro", "xgboost", "sem-xai", 1, 1)
    registry = [_entry(first, 1, False), _entry(first, 2, True), _entry(second, 1, True), _entry(second, 2, True),
                _entry(third, 1, False, started=False), _entry(third, 2, False), _entry(outside, 1, True)]
    situation = coverage(cells, registry, 2)
    assert situation["done"] == 2 and situation["pending"] == [third.id] and situation["not_started"] == 1
    issues = " | ".join(situation["issues"])
    assert "fora da matriz" in issues and f"`{second.id}`: 2 execuções válidas" in issues
    assert f"`{third.id}`: tentativas iniciadas fora de sequência, [2]" in issues
    assert f"`{first.id}`" not in issues


def test_each_invalid_attempt_points_to_the_next_attempt_of_the_same_cell():
    first, second = expand(_matrix())
    registry = [_entry(first, 1, False), _entry(second, 1, False, started=False), _entry(second, 1, False),
                _entry(first, 2, True)]
    found = replacements(registry)
    assert [(item["cell"], item["attempt"]) for item in found] == [(first.id, 1), (second.id, 1)]
    assert found[0]["replaced_by"] == {"attempt": 2, "valid": True} and found[1]["replaced_by"] is None


def test_recount_closes_the_synchronous_and_asynchronous_accounts():
    flows = [_flow(1, "1", "concluida"), _flow(2, "1", "concluida"), _flow(3, "", "", error="Valor não finito")]
    counted = recount(flows, [_explained(1), _explained(2)], "sincrono-total")
    assert (counted["received"], counted["classified"], counted["errors"], counted["selected"],
            counted["completed"]) == (3, 2, 1, 2, 2)
    assert counted["flow_marks_ordered"] and counted["explanation_marks_ordered"]
    late = dict(_explained(2), t4_ns="999")
    assert not recount(flows, [_explained(1), late], "sincrono-total")["explanation_marks_ordered"]
    asynchronous = [_flow(1, "1", "solicitada", requested="104"), _flow(2, "1", "descartada"),
                    _flow(3, "1", "solicitada", requested="304")]
    counted = recount(asynchronous, [_explained(1, synchronous=False)], "assincrono")
    assert counted["states"] == {"solicitada": 2, "descartada": 1} and counted["explanation_marks_ordered"]
    early = dict(_explained(1, synchronous=False), dequeued_ns="103")
    assert not recount(asynchronous, [early], "assincrono")["explanation_marks_ordered"]
    disordered = [dict(_flow(1, "0", "nao_selecionada"), t2_ns="50")]
    assert not recount(disordered, [], "sem-xai")["flow_marks_ordered"]


def _report(received=3, classified=2, errors=1, selected=2, completed=2, queue=None):
    return {"extractor_end": {"flows_emitted": received, "flows_dropped": 0},
            "flows": {"received": received, "classified": classified, "errors": errors},
            "explanations": {"selected": selected, "completed": completed}, "explanation_queue": queue}


def test_count_issues_compare_the_recount_with_the_report_of_the_run():
    flows = [_flow(1, "1", "concluida"), _flow(2, "1", "concluida"), _flow(3, "", "", error="Valor não finito")]
    counted = recount(flows, [_explained(1), _explained(2)], "sincrono-total")
    counted.update(classification_records=2, explanation_records=2)
    assert count_issues(counted, _report(), "sincrono-total") == []
    issues = count_issues(counted, _report(completed=1), "sincrono-total")
    assert issues == ["explicações concluídas: 2 nos arquivos contra 1"]
    asynchronous = [_flow(1, "1", "solicitada", requested="104"), _flow(2, "1", "descartada")]
    counted = recount(asynchronous, [], "assincrono")
    counted.update(classification_records=2, explanation_records=0)
    queue = {"requested": 2, "accepted": 1, "dropped": 1, "completed": 0, "pending": 1}
    report = _report(received=2, classified=2, errors=0, selected=2, completed=0, queue=queue)
    assert count_issues(counted, report, "assincrono") == []
    wrong = _report(received=2, classified=2, errors=0, selected=2, completed=0, queue={**queue, "pending": 0})
    assert count_issues(counted, wrong, "assincrono") == [
        "a fila de explicações difere da recontagem em pending",
        "solicitações diferentes de concluídas mais descartadas mais pendentes"]


def _fixed_report(model, libraries=None, java="17.0.21"):
    return {"model": model, "source": {"kind": "interface"}, "segment": {"pcap": {"sha256": "trecho"}},
            "config_sha256": "config", "model_manifest_sha256": f"manifesto-{model}", "tree_shap_config_sha256": "shap",
            "explainer": {"feature_perturbation": "tree_path_dependent"}, "extractor_build": {"jars": ["a.jar"]},
            "extractor_options": {"timeout": 120}, "classifier_threads": 1,
            "resources": {"cpus": {"configured": {"classifier": [2]}}},
            "extractor_start": {"java_version": java, "ring_bytes": 268435456},
            "environment": {"python": "3.12", "libraries": libraries or {"shap": "0.54.1"}, "platform": "Linux-7.0"}}


def _replay(load, modified=(), commit="abc", timeout=None):
    return {"stage": "segment replay", "segment": "curto", "pcap": {"sha256": "trecho"}, "segment_packets": 10,
            "addresses": {"sha256": "enderecos"}, "topology": {"hosts": ["h1", "h2"]}, "wait_after_replay_s": 137.0,
            "tcpreplay_build": {"version": "4.6.2"}, "replay_cpus": [8, 9],
            "nids_stop_timeout_s": timeout or 100 * load,
            "interfaces": {"h1-eth0": {"offloads": ["rx-checksumming: off"], "link": f"índice {load}"}},
            "git": {"commit": commit, "modified_tracked_files": list(modified)}}


def test_fixed_inputs_vary_only_with_the_model_and_the_load():
    trials = [({"model": model, "load": load}, _fixed_report(model), _replay(load, modified=["M docs/decisoes.md"]))
              for model in ("random-forest", "xgboost") for load in (1, 2)]
    result = input_differences(trials)
    assert result["issues"] == [] and all(row["equal"] for row in result["rows"])
    assert result["git"] == {"commits": ["abc"], "modified_tracked_files": ["docs/decisoes.md"]}
    changed = [*trials[:3], ({"model": "xgboost", "load": 2}, _fixed_report("xgboost", {"shap": "0.55"}, java="21"),
                             _replay(2, modified=[" M src/main.py"], commit="def", timeout=7))]
    issues = input_differences(changed)["issues"]
    assert issues == ["a entrada `libraries` difere entre execuções (todas)",
                      "a entrada `java_version` difere entre execuções (todas)",
                      "a entrada `nids_stop_timeout_s` difere entre execuções (por carga)",
                      "a entrada `git_commit` difere entre execuções (todas)",
                      "arquivos de código alterados durante a matriz: src/main.py"]


def _tcpreplay(packets, load, failed=0):
    copies = [{"copy": number, "exit_code": 0, "successful": packets - (failed if number == 1 else 0),
               "failed": failed if number == 1 else 0} for number in range(1, load + 1)]
    return {"exit_code": 0, "successful": sum(copy["successful"] for copy in copies), "failed": failed,
            "copies": copies}


def test_delivery_requires_every_packet_of_every_copy_and_a_requested_stop():
    stopped = {"extractor_end": {"stop_reason": "stop_requested"}}
    replay = {"segment_packets": 10, "copies": 2, "tcpreplay": _tcpreplay(10, 2)}
    assert delivery_issues(replay, stopped) == []
    assert delivery_issues({**replay, "tcpreplay": _tcpreplay(10, 2, failed=1)}, stopped) == [
        "o tcpreplay não enviou todos os pacotes de cada cópia"]
    assert delivery_issues({**replay, "copies": 3}, stopped) == [
        "o tcpreplay não enviou todos os pacotes de cada cópia"]
    unknown = {**replay, "tcpreplay": {**_tcpreplay(10, 2), "failed": None}}
    assert delivery_issues(unknown, stopped) == ["o tcpreplay não enviou todos os pacotes de cada cópia"]
    assert delivery_issues(replay, {"extractor_end": {"stop_reason": "end_of_file"}}) == [
        "o extrator parou por `end_of_file`, e não a pedido do NIDS"]


def _run(repo, cell, attempt, matrix_name, synchronous_flows):
    folder = repo.create_run("interface")
    with (folder / "flows.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FLOW_HEADER)
        writer.writeheader()
        writer.writerows(synchronous_flows)
    with (folder / "explanations.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=EXPLANATION_HEADER)
        writer.writeheader()
        writer.writerows([_explained(1), _explained(2)])
    (folder / "classifications.jsonl").write_text('{"seq": 1}\n{"seq": 2}\n', encoding="utf-8")
    (folder / "explanations.jsonl").write_text('{"seq": 1}\n{"seq": 2}\n', encoding="utf-8")
    report = {**_fixed_report("random-forest"), **_report(), "passed": True, "checks": {"timestamps_ordered": True},
              "strategy_key": "sincrono-total", "selection": None, "segment": {"name": "curto",
                                                                                "pcap": {"sha256": "trecho"}},
              "artifacts": {name: repo.artifact(folder / name) for name in
                            ("flows.csv", "explanations.csv", "classifications.jsonl", "explanations.jsonl")}}
    replay = {**_replay(cell.load), "model": cell.model, "strategy": cell.strategy, "criterion": cell.criterion,
              "copies": cell.load, "segment": "curto", "tcpreplay": _tcpreplay(10, cell.load),
              "cell": {**cell.as_dict(), "attempt": attempt, "matrix": matrix_name}}
    report["extractor_end"]["stop_reason"] = "stop_requested"
    repo.write_json(folder / "report.json", report)
    repo.write_json(folder / "replay.json", replay)
    return folder


def test_the_audit_closes_a_matrix_and_lists_the_exclusions(tmp_path):
    repo = NidsRepository(tmp_path, tmp_path / "derived-data", tmp_path / "training-runs", tmp_path / "relatorios")
    repo.environment = lambda: {}
    matrix = _matrix()
    matrix_path = tmp_path / "matriz.json"
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
    first, second = expand(matrix)
    flows = [_flow(1, "1", "concluida"), _flow(2, "1", "concluida"), _flow(3, "", "", error="Valor não finito")]
    failed = _run(repo, first, 1, "teste", flows)
    retried = _run(repo, first, 2, "teste", flows)
    other = _run(repo, second, 1, "teste", flows)
    interrupted = _run(repo, second, 1, "teste", flows)
    registry = [_entry(first, 1, False, run_dir=failed), _entry(first, 2, True, run_dir=retried),
                _entry(second, 1, True, run_dir=other)]
    folder = repo.runs_dir / "matrizes" / "teste"
    folder.mkdir(parents=True)
    (folder / "registro.jsonl").write_text("".join(json.dumps(entry) + "\n" for entry in registry), encoding="utf-8")
    trials = []
    for run in (retried, other):
        validation = repo.create_run("validacao")
        repo.write_json(validation / "report.json", {"passed": True, "replay_run": repo.relative(run)})
        trials.append({"run_dir": str(run), "validation": {"status": "aprovada", "run": repo.relative(validation),
                                                           "copies": 1, "file_only_inside": 0,
                                                           "replay_only_inside": 0, "predictions_differing": 0}})
    analysis = repo.create_run("analise-teste")
    repo.write_json(analysis / "report.json", {"attempts": 3, "trials": trials})

    summary = CampaignAudit(repo).audit(matrix_path).summary
    assert summary["closed"] and summary["passed"], summary["problems"] + summary["pending_checks"]
    assert summary["exclusions"]["invalid"][0]["replaced_by"] == {"attempt": 2, "valid": True}
    assert [item["run_dir"] for item in summary["exclusions"]["orphans"]] == [repo.relative(interrupted)]
    assert "A auditoria aprovou a matriz." in render_audit(summary)

    (other / "flows.csv").write_text((other / "flows.csv").read_text(encoding="utf-8") + "4,,,,,,,x,,,,,,\n",
                                     encoding="utf-8")
    assert sha256(other / "flows.csv") != repo.read_json(other / "report.json")["artifacts"]["flows.csv"]["sha256"]
    summary = CampaignAudit(repo).audit(matrix_path).summary
    assert not summary["passed"]
    assert summary["problems"] == [f"`{second.id}`, tentativa 1: arquivos diferentes do registrado: flows.csv"]


def test_a_validation_that_failed_only_by_capture_loss_is_explained_by_it():
    counters = {"h2_received": 100, "h2_dropped": 0, "pcap_dropped": 7, "pcap_interface_dropped": 0,
                "extractor_read": 93}
    checks = {"no_capture_drops": False, "extractor_read_equals_h2_received": False,
              "tcpreplay_sent_whole_segment": True}
    assert explained_by_capture_loss({"checks": checks, "counters": counters})
    assert not explained_by_capture_loss({"checks": {**checks, "tcpreplay_sent_whole_segment": False},
                                          "counters": counters})
    assert not explained_by_capture_loss({"checks": checks, "counters": {**counters, "extractor_read": 90}})
    assert not explained_by_capture_loss({"checks": {name: True for name in checks},
                                          "counters": {**counters, "pcap_dropped": 0, "extractor_read": 100}})
    report = {"extractor_end": {"pcap_stats": {"dropped": 7, "interface_dropped": 1}}}
    assert capture_loss(report, {"interface_counters": {"h2-eth0": {"rx_dropped": 2}}}) == 10
    assert capture_loss({"extractor_end": {}}, {}) == 0
