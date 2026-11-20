"""Resultados de uma matriz executada, recalculados dos registros brutos de cada execução válida.

As latências, a cobertura explicativa, os descartes e a fila de explicações pendentes vêm da tabela por fluxo e da
tabela de explicações, depois da conferência do hash de cada arquivo, e precisam coincidir com o registro do NIDS. Os
recursos vêm do registro do NIDS, e a carga efetiva e o estado da máquina, do registro da reprodução. As repetições de
cada combinação são resumidas pela mediana, com o mínimo e o máximo. O comando só lê os registros."""

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from domains.campaign import figures, results_reporting
from domains.campaign.audit import capture_loss
from domains.campaign.matrix import expand, read_matrix, read_registry
from domains.campaign.service import _queue_trend, _spread
from domains.explanations.service import summarize
from domains.model_training.repository import sha256
from domains.nids.exceptions import NidsError
from domains.nids.repository import NidsRepository
from domains.nids.schemas import CommandResult
from domains.nids.strategies import DROPPED, REQUESTED, pending_series

FLOW_COLUMNS = ["seq", "t0_ns", "t1_ns", "t2_ns", "t3_ns", "error", "selected", "explanation",
                "explanation_requested_ns"]
EXPLANATION_COLUMNS = ["seq", "dequeued_ns", "explanation_start_ns", "explanation_end_ns", "t4_ns"]
RAW_FILES = ("flows.csv", "explanations.csv")
TIMING_STATS = ("mean", "median", "p95", "p99", "min", "max")
# Limites da latência de classificação de uma execução viável (decisão 19).
P95_LIMIT_NS, P99_LIMIT_NS = 1_000_000_000, 2_000_000_000
# A fila de explicações pendentes cresce até o fim quando atinge o maior tamanho pela primeira vez a partir desta
# fração da execução, ou quando está no limite nesse trecho final (decisão 23).
LAST_PART = 0.9
# O NIDS satura numa execução quando um único intervalo com fluxo pendente de classificação cobre mais que esta fração
# do tempo entre o primeiro fluxo emitido e a última classificação (decisão 27).
SATURATION_SHARE = 0.5
OVERHEAD_STATS = ("mean", "p95", "p99")
# Tolerância relativa entre uma estatística recalculada e a registrada pelo NIDS. As duas vêm das mesmas marcações
# inteiras e das mesmas funções, e só a ordem das somas pode mudar o último dígito da média.
RELATIVE_TOLERANCE = 1e-9


class CampaignResults:
    def __init__(self, repo: NidsRepository) -> None:
        self.repo = repo

    def build(self, matrix_path: Path) -> CommandResult:
        matrix = read_matrix(matrix_path)
        registry_path = self.repo.runs_dir / "matrizes" / matrix["name"] / "registro.jsonl"
        entries = valid_entries(expand(matrix), read_registry(registry_path))
        audit_dir, audit = self._latest_audit(matrix["name"])
        if audit is None or not audit.get("passed"):
            raise NidsError(f"A matriz {matrix['name']} não tem auditoria aprovada.")
        executions, series, problems = [], {}, []
        for entry in entries:
            folder = Path(entry["result"]["run_dir"])
            report, replay = (self.repo.read_json(folder / name) for name in ("report.json", "replay.json"))
            damaged = self._damaged(report)
            if damaged:
                problems.append(f"`{entry['cell']['id']}`: arquivos diferentes do registrado: {', '.join(damaged)}")
                continue
            flows = read_flows(folder / "flows.csv")
            explanations = read_explanations(folder / "explanations.csv")
            measured = measure(flows, explanations)
            problems += [f"`{entry['cell']['id']}`: {item}" for item in differences(measured, report)]
            executions.append(execution_row(entry["cell"], self.repo.relative(folder), report, replay, measured))
            series[entry["cell"]["id"]] = measured["series"]
        if problems:
            raise NidsError("Os registros brutos não reproduzem o registro do NIDS:\n" + "\n".join(problems))
        run_dir = self.repo.create_run(f"resultados-{matrix['name']}")
        summary = {
            "stage": "matrix results", "run_id": run_dir.name, "matrix": matrix["name"],
            "matrix_config": self.repo.relative(matrix_path), "segment": matrix["segment"],
            "registry": self.repo.relative(registry_path), "audit": self.repo.relative(audit_dir),
            "audit_report": f"{matrix['name']}-auditoria-{audit_dir.name}.md",
            "executions": executions, "combinations": combinations(executions),
            "loads": load_summary(executions), "environment": self.repo.environment(),
        }
        summary["figures"] = figures.draw_all(summary, series, run_dir / "figuras", self.repo)
        self.repo.write_json(run_dir / "report.json", summary)
        report_path = self.repo.write_report(f"{matrix['name']}-resultados-{run_dir.name}.md",
                                             results_reporting.render_results(summary))
        return CommandResult(run_dir, report_path, summary)

    def _latest_audit(self, name: str) -> tuple[Path | None, dict[str, Any] | None]:
        runs = sorted((self.repo.runs_dir / "nids" / f"auditoria-{name}").glob("*/report.json"))
        return (None, None) if not runs else (runs[-1].parent, self.repo.read_json(runs[-1]))

    def _damaged(self, report: dict[str, Any]) -> list[str]:
        damaged = []
        for name in RAW_FILES:
            info = report["artifacts"].get(name)
            if info is None:
                continue
            path = self.repo.root / info["file"]
            if not path.is_file() or path.stat().st_size != info["bytes"] or sha256(path) != info["sha256"]:
                damaged.append(name)
        return damaged


def valid_entries(cells: list[Any], registry: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A tentativa válida de cada célula, na ordem da matriz. Cada célula precisa de exatamente uma."""
    found: dict[str, list[dict[str, Any]]] = {}
    for entry in registry:
        if entry["validity"]["valid"] and entry["result"].get("started", True):
            found.setdefault(entry["cell"]["id"], []).append(entry)
    missing = [cell.id for cell in cells if len(found.get(cell.id, [])) != 1]
    if missing:
        raise NidsError("Células sem exatamente uma execução válida: " + ", ".join(missing))
    return [found[cell.id][0] for cell in cells]


def read_flows(path: Path) -> dict[str, Any]:
    """Colunas da tabela por fluxo usadas nas medidas. As marcações ficam só para os fluxos classificados."""
    table = pd.read_csv(path, usecols=FLOW_COLUMNS, dtype=str, keep_default_na=False)
    classified = table[table["error"] == ""]
    columns = {key: classified[key].astype(np.int64).to_numpy() for key in ("seq", "t0_ns", "t1_ns", "t2_ns", "t3_ns")}
    requested = classified[classified["explanation"] == REQUESTED]
    return {**columns, "all_seq": table["seq"].astype(np.int64).to_numpy(), "errors": int((table["error"] != "").sum()),
            "selected": int((classified["selected"] == "1").sum()),
            "dropped_requests": int((classified["explanation"] == DROPPED).sum()),
            "requested_seq": requested["seq"].astype(np.int64).to_numpy(),
            "requested_ns": requested["explanation_requested_ns"].astype(np.int64).to_numpy()}


def read_explanations(path: Path) -> pd.DataFrame | None:
    if not path.is_file():
        return None
    return pd.read_csv(path, usecols=EXPLANATION_COLUMNS, dtype=str, keep_default_na=False)


def measure(flows: dict[str, Any], explanations: pd.DataFrame | None) -> dict[str, Any]:
    """Medidas de uma execução, recalculadas das marcações de cada fluxo e de cada explicação."""
    t0, t1, t2, t3 = flows["t0_ns"], flows["t1_ns"], flows["t2_ns"], flows["t3_ns"]
    origin = int(t0.min())
    timings: dict[str, Any] = {"inference_ns": summarize(t2 - t1), "classification_latency_ns": summarize(t3 - t0),
                               "wait_before_inference_ns": summarize(t1 - t0)}
    span = (int(t3.max()) - origin) / 1e9
    timings["classified_per_second"] = len(t0) / span if span > 0 else None
    t0_by_seq = pd.Series(t0, index=flows["seq"])
    known = None
    if explanations is not None:
        known = explanations[explanations["seq"].astype(np.int64).isin(flows["seq"])]
    completed = 0 if known is None else len(known)
    queue = None
    if completed:
        seq = known["seq"].astype(np.int64).to_numpy()
        start, end, t4 = (known[key].astype(np.int64).to_numpy()
                          for key in ("explanation_start_ns", "explanation_end_ns", "t4_ns"))
        timings["explanation_ns"] = summarize(end - start)
        timings["explanation_latency_ns"] = summarize(t4 - t0_by_seq.loc[seq].to_numpy())
    if len(flows["requested_seq"]) or flows["dropped_requests"]:
        dequeued = known["dequeued_ns"].astype(np.int64).to_numpy() if completed else np.array([], dtype=np.int64)
        requested_by_seq = pd.Series(flows["requested_ns"], index=flows["requested_seq"])
        if completed:
            timings["queue_wait_ns"] = summarize(dequeued - requested_by_seq.loc[seq].to_numpy())
        last_t4 = int(t4.max()) if completed else None
        last_request = int(flows["requested_ns"].max()) if len(flows["requested_ns"]) else None
        queue = {"accepted": len(flows["requested_seq"]), "dropped": flows["dropped_requests"], "completed": completed,
                 "pending": len(flows["requested_seq"]) - completed,
                 "size": pending_series(flows["requested_ns"].tolist(), dequeued.tolist(), origin),
                 "drain_after_last_request_ns": None if last_t4 is None or last_request is None
                 else last_t4 - last_request}
    pending = pending_series(t0.tolist(), t3.tolist(), origin)
    return {
        "flows": {"received": len(flows["all_seq"]), "classified": len(t0), "errors": flows["errors"]},
        "seq_max": int(flows["all_seq"].max()), "distinct_seq": len(np.unique(flows["all_seq"])),
        "timings": timings, "selected": flows["selected"], "completed": completed, "queue": queue,
        "pending_classification": {"max": pending["max"], **busy_periods(t0, t3)},
        "series": {"latency_quantiles_ms": np.quantile((t3 - t0) / 1e6, figures.QUANTILES),
                   "emitted_per_second": np.bincount((t0 - origin) // 1_000_000_000),
                   "pending_classification": pending["max_by_second"],
                   "queue": None if queue is None else queue["size"]["max_by_second"]},
    }


def busy_periods(arrivals: np.ndarray, departures: np.ndarray) -> dict[str, Any]:
    """Intervalos em que pelo menos um fluxo emitido ainda não tem a classificação disponível.

    Cada fluxo entra em `t0` e sai em `t3`. Num mesmo instante, a saída conta antes da entrada. Devolve o intervalo
    mais longo e a fração do tempo, entre a primeira entrada e a última saída, coberta pelos intervalos."""
    times = np.concatenate([arrivals, departures])
    changes = np.concatenate([np.ones(len(arrivals), dtype=np.int64), -np.ones(len(departures), dtype=np.int64)])
    order = np.lexsort((changes, times))
    times, changes = times[order], changes[order]
    size = np.cumsum(changes)
    starts = times[(changes == 1) & (size == 1)]
    ends = times[size == 0]
    lengths = ends - starts
    total = int(times[-1] - times[0])
    return {"longest_ns": int(lengths.max()), "longest_share": float(lengths.max() / total) if total else None,
            "busy_share": float(lengths.sum() / total) if total else None}


def differences(measured: dict[str, Any], report: dict[str, Any]) -> list[str]:
    """Diferenças entre o recalculado dos registros brutos e o registro do NIDS."""
    found = []
    for key in ("received", "classified", "errors"):
        if measured["flows"][key] != report["flows"][key]:
            found.append(f"fluxos {key}: {measured['flows'][key]} contra {report['flows'][key]}")
    end = report["extractor_end"]
    if measured["distinct_seq"] != measured["flows"]["received"] or measured["seq_max"] > end["flows_emitted"]:
        found.append("números de sequência repetidos ou além dos fluxos emitidos")
    if end["flows_emitted"] - measured["flows"]["received"] != end["flows_dropped"]:
        found.append("os fluxos ausentes da tabela não somam os descartados pelo extrator")
    for key, recomputed in measured["timings"].items():
        recorded = report["timings"].get(key)
        if key == "classified_per_second":
            if recorded is None or not math.isclose(recomputed, recorded, rel_tol=RELATIVE_TOLERANCE):
                found.append(f"{key}: {recomputed} contra {recorded}")
            continue
        if recorded is None or recomputed["count"] != recorded["count"] or not all(
                math.isclose(recomputed[stat], recorded[stat], rel_tol=RELATIVE_TOLERANCE) for stat in TIMING_STATS):
            found.append(f"{key} difere do registro do NIDS")
    missing = sorted(key for key in report["timings"] if key not in measured["timings"]
                     and key not in ("selection_ns", "delivery_ns"))
    if missing:
        found.append("estatísticas sem recálculo: " + ", ".join(missing))
    explanations = report.get("explanations") or {}
    if explanations and (measured["selected"], measured["completed"]) != (explanations["selected"],
                                                                          explanations["completed"]):
        found.append("fluxos selecionados ou explicados diferentes do registro do NIDS")
    queue, recorded_queue = measured["queue"], report.get("explanation_queue")
    if (queue is None) != (recorded_queue is None):
        found.append("fila de explicações pendentes só num dos registros")
    elif queue is not None:
        for key in ("accepted", "dropped", "completed", "pending", "size", "drain_after_last_request_ns"):
            if queue[key] != recorded_queue[key]:
                found.append(f"fila de explicações pendentes, {key}, difere do registro do NIDS")
    return found


def execution_row(cell: dict[str, Any], run_dir: str, report: dict[str, Any], replay: dict[str, Any],
                  measured: dict[str, Any]) -> dict[str, Any]:
    """Medidas de uma execução guardadas no resultado."""
    end, resources = report["extractor_end"], report.get("resources") or {}
    machine = replay.get("machine") or {}
    classified = measured["flows"]["classified"]
    queue = measured["queue"]
    if queue is not None:
        queue = {key: queue[key] for key in ("accepted", "dropped", "completed", "pending",
                                             "drain_after_last_request_ns")} | _queue_trend(queue["size"])
        queue.update({"requested": queue["accepted"] + queue["dropped"],
                      "limit": report["explanation_queue"]["limit"]})
    row = {
        "cell": cell, "run_dir": run_dir, "copies": replay["copies"],
        "load": {"flows_emitted": end["flows_emitted"], "flows_per_second": replay["delivered"]["flows_per_second"],
                 "packets_per_second": replay["tcpreplay"]["rated_packets_per_second"]},
        "flows": {**measured["flows"], "dropped": end["flows_dropped"],
                  "dropped_share": end["flows_dropped"] / end["flows_emitted"] if end["flows_emitted"] else None},
        "capture_lost_packets": capture_loss(report, replay),
        "timings": measured["timings"],
        "explanations": {"selected": measured["selected"], "completed": measured["completed"],
                         "selected_share": measured["selected"] / classified if classified else None,
                         "completed_share": measured["completed"] / classified if classified else None},
        "queue": queue, "pending_classification": measured["pending_classification"],
        "resources": {name: _usage(resources.get(f"{name}_process"), classified)
                      for name in ("classifier", "explainer", "extractor")},
        "machine": {"frequency_mhz": {cpu: _median_mhz(machine, cpu) for cpu in ("0", "2")},
                    "busy_share_sibling_cpus_max": max(
                        (((machine.get("busy_share") or {}).get(cpu) or {}).get("max") or 0) for cpu in ("1", "3")),
                    "memory_available_mib_min": ((machine.get("memory_available_kib") or {}).get("min") or 0) / 1024},
    }
    row["viability"] = viability(row)
    share = row["pending_classification"]["longest_share"]
    row["saturated"] = share is not None and share > SATURATION_SHARE
    return row


def queue_grows_to_end(queue: dict[str, Any]) -> bool:
    """A fila cresce até o fim quando atinge o maior tamanho pela primeira vez no último décimo da execução, ou quando
    está no limite no último décimo (decisão 23)."""
    return queue["max_at_share_of_run"] >= LAST_PART or queue["max_in_last_tenth"] >= queue["limit"]


def viability(row: dict[str, Any]) -> dict[str, Any]:
    """Os três critérios de viabilidade de uma execução. O critério da fila só vale no modo assíncrono."""
    latency = row["timings"]["classification_latency_ns"]
    criteria = {"latency": latency["p95"] <= P95_LIMIT_NS and latency["p99"] <= P99_LIMIT_NS,
                "no_dropped_flow": row["flows"]["dropped"] == 0,
                "queue": None if row["queue"] is None else not queue_grows_to_end(row["queue"])}
    return {**criteria, "viable": all(value is not False for value in criteria.values())}


def _usage(process: dict[str, Any] | None, classified: int) -> dict[str, Any] | None:
    if not process:
        return None
    cpu = process["cpu_ns"] / 1e9 if "cpu_ns" in process else process["user_seconds"] + process["system_seconds"]
    return {"cpu_seconds": cpu, "cpu_ms_per_flow": 1000 * cpu / classified if classified else None,
            "max_rss_mib": process["max_rss_kib"] / 1024}


def _median_mhz(machine: dict[str, Any], cpu: str) -> float | None:
    spread = (machine.get("frequency_khz") or {}).get(cpu)
    return None if not spread else spread["median"] / 1000


def measures(row: dict[str, Any]) -> dict[str, float | None]:
    """Medidas de uma execução que entram no resumo das repetições, em milissegundos, segundos, MiB ou fração."""
    timings, queue, resources = row["timings"], row["queue"] or {}, row["resources"]

    def ms(key: str, stat: str) -> float | None:
        return timings[key][stat] / 1e6 if key in timings else None

    def resource(name: str, key: str) -> float | None:
        return None if resources[name] is None else resources[name][key]

    drain = queue.get("drain_after_last_request_ns")
    return {
        "flows_per_second": row["load"]["flows_per_second"], "classified_per_second": timings["classified_per_second"],
        "flows_dropped": row["flows"]["dropped"], "flows_dropped_share": row["flows"]["dropped_share"],
        "capture_lost_packets": row["capture_lost_packets"],
        "inference_mean_ms": ms("inference_ns", "mean"),
        **{f"classification_{stat}_ms": ms("classification_latency_ns", stat) for stat in ("mean", "p95", "p99")},
        "explanation_mean_ms": ms("explanation_ns", "mean"),
        **{f"explanation_latency_{stat}_ms": ms("explanation_latency_ns", stat) for stat in ("mean", "p95", "p99")},
        **{f"queue_wait_{stat}_ms": ms("queue_wait_ns", stat) for stat in ("mean", "p95")},
        "selected_share": row["explanations"]["selected_share"],
        "completed_share": row["explanations"]["completed_share"],
        "requests_dropped": queue.get("dropped"), "requests_pending": queue.get("pending"),
        "queue_max": queue.get("max"), "queue_max_at_share": queue.get("max_at_share_of_run"),
        "queue_max_in_last_tenth": queue.get("max_in_last_tenth"),
        "drain_s": None if drain is None else drain / 1e9,
        "pending_classification_max": row["pending_classification"]["max"],
        "pending_classification_longest_s": row["pending_classification"]["longest_ns"] / 1e9,
        "pending_classification_longest_share": row["pending_classification"]["longest_share"],
        "pending_classification_busy_share": row["pending_classification"]["busy_share"],
        **{f"cpu_{name}_s": resource(name, "cpu_seconds") for name in ("classifier", "explainer", "extractor")},
        **{f"cpu_{name}_ms_per_flow": resource(name, "cpu_ms_per_flow") for name in ("classifier", "explainer")},
        **{f"rss_{name}_mib": resource(name, "max_rss_mib") for name in ("classifier", "explainer", "extractor")},
        "frequency_cpu2_mhz": row["machine"]["frequency_mhz"]["2"],
        "frequency_cpu0_mhz": row["machine"]["frequency_mhz"]["0"],
        "busy_share_sibling_cpus_max": row["machine"]["busy_share_sibling_cpus_max"],
        "memory_available_mib_min": row["machine"]["memory_available_mib_min"],
    }


def combinations(executions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mediana, mínimo e máximo de cada medida entre as execuções de cada combinação de classificador,
    configuração de explicação e nível de carga, na ordem dos classificadores, das configurações e das cargas."""
    groups: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    for row in executions:
        cell = row["cell"]
        groups.setdefault((cell["model"], cell["configuration"], cell["load"]), []).append(row)
    result = []
    for (model, configuration, load), rows in groups.items():
        values = [measures(row) for row in rows]
        result.append({"model": model, "configuration": configuration, "load": load, "executions": len(rows),
                       "measures": {name: _spread([item[name] for item in values if item[name] is not None])
                                    for name in values[0]},
                       "viability": {criterion: sum(1 for row in rows if row["viability"][criterion])
                                     for criterion in ("latency", "no_dropped_flow", "queue", "viable")},
                       "saturated": sum(1 for row in rows if row["saturated"])})
    for item in result:
        item["viable"] = item["viability"]["viable"] == item["executions"]
        baseline = next((other for other in result if (other["model"], other["configuration"], other["load"])
                         == (item["model"], "sem-xai", item["load"])), None)
        item["overhead"] = None if baseline is None or item is baseline else {
            stat: overhead(item["measures"][f"classification_{stat}_ms"],
                           baseline["measures"][f"classification_{stat}_ms"]) for stat in OVERHEAD_STATS}
    order = {key: index for index, key in enumerate(results_reporting.CONFIGURATION_ORDER)}
    return sorted(result, key=lambda item: (item["model"], order[item["configuration"]], item["load"]))


def overhead(strategy: dict[str, float], baseline: dict[str, float]) -> dict[str, Any]:
    """Sobrecarga de latência: diferença entre a mediana das execuções da estratégia e a do Sem XAI (decisão 25). A
    estratégia difere do Sem XAI quando os intervalos do mínimo ao máximo não se sobrepõem (decisão 26)."""
    if strategy["min"] > baseline["max"]:
        comparison = "maior"
    elif strategy["max"] < baseline["min"]:
        comparison = "menor"
    else:
        comparison = "não se distingue"
    return {"ms": strategy["median"] - baseline["median"], "comparison": comparison}


def load_summary(executions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Carga efetiva de cada nível de carga, entre todas as execuções do nível."""
    loads: dict[int, list[dict[str, Any]]] = {}
    for row in executions:
        loads.setdefault(row["cell"]["load"], []).append(row)
    return [{"load": load, "executions": len(rows),
             "flows_per_second": _spread([row["load"]["flows_per_second"] for row in rows]),
             "packets_per_second": _spread([row["load"]["packets_per_second"] for row in rows]),
             "flows_emitted": _spread([row["load"]["flows_emitted"] for row in rows])}
            for load, rows in sorted(loads.items())]
