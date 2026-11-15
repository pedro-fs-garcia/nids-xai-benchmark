"""Comparabilidade das quatro estratégias de explicação.

As execuções comparadas usam as mesmas entradas fixas. Na leitura de arquivo, os fluxos são os mesmos em todas
as execuções, então as previsões devem ser idênticas, e as explicações do mesmo fluxo também."""

from typing import Any

from domains.nids.schemas import STRATEGIES
from domains.nids.strategies import selection_rule

# Tempos que cada execução precisa registrar, conforme a estratégia e a existência de fluxos explicados.
BASE_TIMINGS = ("inference_ns", "classification_latency_ns", "wait_before_inference_ns", "selection_ns", "delivery_ns")
EXPLANATION_TIMINGS = ("explanation_ns", "explanation_latency_ns")


def fixed_inputs(report: dict[str, Any]) -> dict[str, Any]:
    """Entradas que não podem variar entre as execuções comparadas."""
    segment = report["segment"] or {}
    return {
        "model": report["model"], "source_kind": report["source"]["kind"],
        "traffic": segment.get("pcap", {}).get("sha256") or report["source"].get("pcap"),
        "config_sha256": report["config_sha256"], "model_sha256": report["model_manifest_sha256"],
        "tree_shap_config_sha256": report["tree_shap_config_sha256"], "explainer": report["explainer"],
        "extractor_jars": report["extractor_build"]["jars"], "extractor_options": report["extractor_options"],
        "classifier_threads": report["classifier_threads"], "cpus": report["resources"]["cpus"]["configured"],
        "python": report["environment"]["python"], "libraries": report["environment"]["libraries"],
    }


def run_key(report: dict[str, Any]) -> tuple[str, str | None]:
    return report["strategy_key"], (report.get("selection") or {}).get("criterion")


def measurement_points_present(report: dict[str, Any]) -> bool:
    timings, completed = report["timings"], report["explanations"]["completed"]
    expected = list(BASE_TIMINGS)
    if completed:
        expected += EXPLANATION_TIMINGS
    if completed and report["strategy_key"] == "assincrono":
        expected.append("queue_wait_ns")
    return all(key in timings for key in expected) and (completed > 0 or "explanation_ns" not in timings)


def compare(reports: list[dict[str, Any]], explanations: list[dict[int, dict[str, Any]]],
            flows: list[list[dict[str, str]]]) -> dict[str, Any]:
    """Confere que as execuções formam um conjunto comparável das quatro estratégias.

    `explanations` e `flows` seguem a ordem de `reports`. Os registros de explicação vêm do canal de saída das
    explicações, e os fluxos, da tabela por fluxo de cada execução."""
    keys = [run_key(report) for report in reports]
    strategies = {key for key, _ in keys}
    inputs = [fixed_inputs(report) for report in reports]
    file_mode = all(report["source"]["kind"] == "arquivo" for report in reports)
    checks: dict[str, bool] = {
        "four_strategies_once_each": strategies == set(STRATEGIES) and len(keys) == len(set(keys)),
        "same_fixed_inputs": all(item == inputs[0] for item in inputs),
        "every_run_passed": all(report["passed"] for report in reports),
        "measurement_points_present": all(measurement_points_present(report) for report in reports),
        "processes_on_configured_cpus": all(report["checks"].get("processes_on_configured_cpus") is True
                                            for report in reports),
    }
    differences: dict[str, Any] = {}
    if file_mode and checks["four_strategies_once_each"]:
        hashes = {report["artifacts"]["classifications.jsonl"]["sha256"] for report in reports}
        checks["identical_classifications"] = len(hashes) == 1
        checks["same_flows"] = len({(report["flows"]["received"], report["flows"]["classified"],
                                     report["flows"]["errors"]) for report in reports}) == 1
        index = {key: position for position, key in enumerate(keys)}
        total = explanations[index[("sincrono-total", None)]]
        asynchronous = explanations[index[("assincrono", None)]]
        differences["total_vs_async"] = _difference(total, asynchronous)
        checks["async_explanations_equal_total"] = (set(total) == set(asynchronous)
                                                    and differences["total_vs_async"]["equal"])
        probability = {int(row["seq"]): float(row["attack_probability"])
                       for row in flows[index[("sincrono-total", None)]] if not row["error"]}
        for position, (key, criterion) in enumerate(keys):
            if key != "sincrono-condicional":
                continue
            report = reports[position]
            rule = selection_rule(criterion, report["selection"]["threshold"])
            expected = {seq for seq, value in probability.items() if rule(value)}
            conditional = explanations[position]
            differences[f"total_vs_conditional_{criterion}"] = _difference(total, conditional)
            checks[f"conditional_{criterion}_explains_the_selected_subset_of_total"] = (
                set(conditional) == expected and differences[f"total_vs_conditional_{criterion}"]["equal"])
    return {"passed": all(checks.values()), "checks": checks, "file_mode": file_mode, "differences": differences,
            "runs": [_row(report) for report in reports]}


def _difference(reference: dict[int, dict[str, Any]], other: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """Maior diferença entre as explicações do mesmo fluxo nas duas execuções."""
    common = set(reference) & set(other)
    largest = 0.0
    same_flow = True
    for seq in common:
        left, right = reference[seq], other[seq]
        same_flow = same_flow and left["flow_id"] == right["flow_id"]
        largest = max(largest, abs(left["reference_value"] - right["reference_value"]),
                      *(abs(a - b) for a, b in zip(left["contributions"], right["contributions"])))
    return {"common": len(common), "max_abs_difference": largest, "equal": same_flow and largest == 0.0}


def _row(report: dict[str, Any]) -> dict[str, Any]:
    explanations, queue = report["explanations"], report.get("explanation_queue") or {}
    timings, resources = report["timings"], report["resources"]
    return {
        "run_id": report["run_id"], "source_kind": report["source"]["kind"], "strategy": report["strategy"],
        "criterion": (report.get("selection") or {}).get("criterion"),
        "threshold": (report.get("selection") or {}).get("threshold"),
        "classified": explanations["eligible"], "selected": explanations["selected"],
        "completed": explanations["completed"], "dropped": queue.get("dropped", 0), "pending": queue.get("pending", 0),
        "queue_max": (queue.get("size") or {}).get("max"),
        "flows_dropped_in_extractor": report["extractor_end"].get("flows_dropped") or 0,
        "timings": {key: {stat: timings[key][stat] for stat in ("mean", "p95", "p99")}
                    for key in ("inference_ns", "explanation_ns", "classification_latency_ns",
                                "explanation_latency_ns", "queue_wait_ns") if key in timings},
        "cpu_seconds": {name: _cpu_seconds(resources.get(f"{name}_process"))
                        for name in ("classifier", "explainer", "extractor")},
        "max_rss_mib": {name: None if not resources.get(f"{name}_process")
                        else resources[f"{name}_process"]["max_rss_kib"] / 1024
                        for name in ("classifier", "explainer", "extractor")},
    }


def _cpu_seconds(process: dict[str, Any] | None) -> float | None:
    if not process:
        return None
    if "cpu_ns" in process:
        return process["cpu_ns"] / 1e9
    return process["user_seconds"] + process["system_seconds"]
