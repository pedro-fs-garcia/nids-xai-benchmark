"""Análise de uma matriz de ensaios: cobertura da matriz, validação de cada ensaio e resumo das medições."""

import statistics
from pathlib import Path
from typing import Any

from domains.campaign import reporting
from domains.campaign.matrix import expand, read_matrix, read_registry, status
from domains.nids.comparison import fixed_inputs
from domains.nids.exceptions import NidsError
from domains.nids.repository import NidsRepository
from domains.nids.schemas import CommandResult
from domains.nids.service import NidsService

# Entradas fixas que a leitura por arquivo de referência precisa ter iguais às do ensaio. A configuração do NIDS e as
# CPUs ficam de fora, porque a reprodução usa campos que a leitura por arquivo não usa.
REFERENCE_INPUTS = ("model", "traffic", "model_sha256", "tree_shap_config_sha256", "explainer", "extractor_jars",
                    "extractor_options", "classifier_threads", "python", "libraries")


class CampaignService:
    def __init__(self, repo: NidsRepository, nids: NidsService) -> None:
        self.repo = repo
        self.nids = nids

    def analyze(self, matrix_path: Path, acceleration_run: Path | None = None) -> CommandResult:
        """Valida cada ensaio válido da matriz contra a leitura por arquivo e resume as medições de todos."""
        matrix = read_matrix(matrix_path)
        cells = expand(matrix)
        registry_path = self.repo.runs_dir / "matrizes" / matrix["name"] / "registro.jsonl"
        registry = read_registry(registry_path)
        if not registry:
            raise NidsError(f"A matriz {matrix['name']} ainda não tem ensaios registrados em {registry_path}.")
        situation = status(cells, registry, matrix["max_attempts"])
        references = self._references()
        trials = []
        for entry in registry:
            trial = self._trial(entry)
            if entry["validity"]["valid"] and trial["report"] is not None:
                trial["validation"] = self._validate(trial, references)
            trials.append(trial)
        run_dir = self.repo.create_run(f"analise-{matrix['name']}")
        summary = {
            "stage": "matrix analysis", "run_id": run_dir.name, "matrix": matrix["name"],
            "matrix_config": self.repo.relative(matrix_path), "segment": matrix["segment"],
            "cells": len(cells), "done": len(situation["done"]), "exhausted": [cell.id for cell in situation["exhausted"]],
            "pending": [cell.id for cell, _ in situation["pending"]],
            "registry": self.repo.relative(registry_path), "attempts": len(registry),
            "trials": [_compact(trial) for trial in trials],
            "variability": _variability([trial for trial in trials if trial["valid"]]),
            "acceleration_run": None if acceleration_run is None else self.repo.relative(acceleration_run),
            "environment": self.repo.environment(),
        }
        self.repo.write_json(run_dir / "report.json", summary)
        report = self.repo.write_report(f"{matrix['name']}-{run_dir.name}.md", reporting.render_analysis(summary))
        return CommandResult(run_dir, report, summary)

    def _references(self) -> list[tuple[Path, dict[str, Any]]]:
        """Leituras por arquivo aprovadas, que podem servir de referência a um ensaio na rede emulada."""
        found = []
        for path in sorted((self.repo.runs_dir / "nids" / "arquivo").glob("*/report.json")):
            report = self.repo.read_json(path)
            if report.get("passed") and report.get("segment") and "strategy_key" in report:
                found.append((path.parent, report))
        return found

    def _trial(self, entry: dict[str, Any]) -> dict[str, Any]:
        run_dir = entry["result"].get("run_dir")
        folder = Path(run_dir) if run_dir and run_dir != "None" else None
        load = lambda name: (self.repo.read_json(folder / name)  # noqa: E731
                             if folder is not None and (folder / name).is_file() else None)
        return {"cell": entry["cell"], "attempt": entry["attempt"], "valid": entry["validity"]["valid"],
                "reasons": entry["validity"]["reasons"], "run_dir": folder, "report": load("report.json"),
                "replay": load("replay.json"), "validation": None}

    def _validate(self, trial: dict[str, Any], references: list[tuple[Path, dict[str, Any]]]) -> dict[str, Any]:
        report = trial["report"]
        wanted = {key: fixed_inputs(report)[key] for key in REFERENCE_INPUTS}
        matches = [(directory, reference) for directory, reference in references
                   if reference["strategy_key"] == report["strategy_key"]
                   and reference.get("selection") == report.get("selection")
                   and reference["segment"]["name"] == report["segment"]["name"]
                   and {key: fixed_inputs(reference)[key] for key in REFERENCE_INPUTS} == wanted]
        if not matches:
            return {"status": "sem referência"}
        directory = matches[-1][0]
        try:
            result = self.nids.validate(trial["run_dir"], directory)
        except NidsError as error:
            return {"status": "reprovada", "error": str(error), "file_run": self.repo.relative(directory)}
        summary = result.summary
        copies = summary["copies"] or {"1": None}
        rows = [row for row in (summary["copies"] or {}).values()] or [{
            "file_only_inside": summary["flows"]["file_only_inside"],
            "replay_only_inside": summary["flows"]["replay_only_inside"],
            "predictions_differing": summary["predictions"]["differing"],
            "predictions_compared": summary["predictions"]["compared"]}]
        return {"status": "aprovada" if summary["passed"] else "reprovada", "run": self.repo.relative(result.run_dir),
                "report": self.repo.relative(result.report_path), "file_run": self.repo.relative(directory),
                "copies": len(copies), "checks": summary["checks"],
                "file_only_inside": sum(row["file_only_inside"] for row in rows),
                "replay_only_inside": sum(row["replay_only_inside"] for row in rows),
                "predictions_differing": sum(row["predictions_differing"] for row in rows),
                "predictions_compared": sum(row["predictions_compared"] for row in rows),
                "without_copy": summary["flows"]["without_copy"]}


def _compact(trial: dict[str, Any]) -> dict[str, Any]:
    """Medições de um ensaio usadas na análise do piloto e da campanha."""
    report, replay = trial["report"] or {}, trial["replay"] or {}
    row: dict[str, Any] = {"cell": trial["cell"], "attempt": trial["attempt"], "valid": trial["valid"],
                           "reasons": trial["reasons"], "run_dir": None if trial["run_dir"] is None
                           else str(trial["run_dir"]), "validation": trial["validation"]}
    if not report:
        return row
    timings, end = report["timings"], report["extractor_end"]
    explanations, queue = report.get("explanations") or {}, report.get("explanation_queue") or {}
    stats = end.get("pcap_stats") or {}
    interfaces = replay.get("interface_counters") or {}
    emitted = end.get("flows_emitted") or 0
    dropped = end.get("flows_dropped") or 0
    replay_seconds = replay.get("replay_seconds")
    machine = replay.get("machine") or {}
    resources = report.get("resources") or {}
    row.update({
        "copies": replay.get("copies", 1),
        "load": {"flows_emitted": emitted, "flows_per_second": emitted / replay_seconds if replay_seconds else None,
                 "packets_per_second": (replay.get("tcpreplay") or {}).get("rated_packets_per_second"),
                 "mbps": (replay.get("tcpreplay") or {}).get("rated_mbps")},
        "drops": {"h2_interface": (interfaces.get("h2-eth0") or {}).get("rx_dropped"),
                  "libpcap": stats.get("dropped"), "libpcap_interface": stats.get("interface_dropped"),
                  "packets_received": stats.get("received"), "extractor_queue_flows": dropped,
                  "extractor_queue_share": dropped / emitted if emitted else None,
                  "extractor_queue_max": end.get("output_queue_max")},
        "timings": {key: {stat: timings[key][stat] for stat in ("mean", "median", "p95", "p99", "max")}
                    for key in ("inference_ns", "classification_latency_ns", "wait_before_inference_ns",
                                "explanation_ns", "explanation_latency_ns", "queue_wait_ns") if key in timings},
        "classified_per_second": timings.get("classified_per_second"),
        "flows": report["flows"]["received"], "classified": report["flows"]["classified"],
        "explanations": {key: explanations.get(key) for key in ("eligible", "selected", "completed",
                                                                "selected_share", "completed_share")},
        "queue": {key: queue.get(key) for key in ("requested", "accepted", "dropped", "completed", "pending",
                                                  "drain_after_end_of_capture_ns", "killed_after_drain_timeout")}
        | _queue_trend(queue.get("size")),
        "resources": {name: _usage(resources.get(f"{name}_process")) for name in ("classifier", "explainer",
                                                                                   "extractor")},
        "machine": {"mains_online_in_every_sample": machine.get("mains_online_in_every_sample"),
                    "frequency_mhz": {cpu: _median_mhz(machine, cpu) for cpu in ("0", "2")},
                    "throttle_events": machine.get("throttle_events"),
                    "busy_share_sibling_cpus": {cpu: ((machine.get("busy_share") or {}).get(cpu) or {}).get("max")
                                                for cpu in ("1", "3")},
                    "memory_available_mib_min": ((machine.get("memory_available_kib") or {}).get("min") or 0) / 1024},
    })
    return row


def _queue_trend(size: dict[str, Any] | None) -> dict[str, Any]:
    """Onde o maior tamanho da fila ocorre e quanto a fila tem no último décimo da execução.

    Uma fila que só cresce tem o maior tamanho no fim. Uma fila que se estabiliza ou esvazia tem, no último décimo,
    um tamanho menor que o maior."""
    if not size or not size.get("max_by_second"):
        return {"max": None}
    series = size["max_by_second"]
    last = series[-1][0] or 1
    tail = [value for second, value in series if second >= 0.9 * last]
    peak_second = max(series, key=lambda item: item[1])[0]
    return {"max": size["max"], "max_at_share_of_run": peak_second / last, "max_in_last_tenth": max(tail)}


def _usage(process: dict[str, Any] | None) -> dict[str, Any] | None:
    if not process:
        return None
    cpu = process["cpu_ns"] / 1e9 if "cpu_ns" in process else process["user_seconds"] + process["system_seconds"]
    return {"cpu_seconds": cpu, "max_rss_mib": process["max_rss_kib"] / 1024}


def _median_mhz(machine: dict[str, Any], cpu: str) -> float | None:
    spread = (machine.get("frequency_khz") or {}).get(cpu)
    return None if not spread else spread["median"] / 1000


def _variability(trials: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Variação entre ensaios válidos da mesma combinação, nos blocos de repetição e fora deles."""
    groups: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    for trial in trials:
        report = trial["report"]
        if not report:
            continue
        cell = trial["cell"]
        groups.setdefault((cell["model"], cell["configuration"], cell["load"]), []).append(report)
    result = []
    for (model, configuration, load), reports in sorted(groups.items()):
        if len(reports) < 2:
            continue
        measures = (("inference_ns", "mean"), ("classification_latency_ns", "p95"),
                    ("classification_latency_ns", "p99"))
        result.append({"model": model, "configuration": configuration, "load": load, "trials": len(reports),
                       **{f"{key}_{stat}": _spread([report["timings"][key][stat] / 1e6 for report in reports
                                                    if key in report["timings"]]) for key, stat in measures}})
    return result


def _spread(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    median = statistics.median(values)
    return {"min": min(values), "median": median, "max": max(values),
            "relative_range": (max(values) - min(values)) / median if median else None}
