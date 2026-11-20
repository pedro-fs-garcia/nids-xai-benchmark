"""Auditoria de uma matriz de ensaios executada na rede emulada.

A auditoria confere a matriz prevista contra o registro, a coerência entre cada tentativa registrada e os registros
da execução, o envio de todos os pacotes de cada cópia, o encerramento do extrator a pedido do NIDS, a integridade e a
recontagem dos arquivos brutos de cada execução válida, a validação por cópia feita pela análise mais recente da matriz
e as entradas fixas de todas as execuções válidas. Ela só lê os registros."""

import csv
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from domains.campaign import audit_reporting
from domains.campaign.matrix import Cell, expand, read_matrix, read_registry, status
from domains.model_training.repository import sha256
from domains.nids.comparison import fixed_inputs
from domains.nids.exceptions import NidsError
from domains.nids.repository import NidsRepository
from domains.nids.schemas import CommandResult
from domains.nids.strategies import COMPLETED, DROPPED, REQUESTED

# Entradas fixas que dependem do classificador. As demais são iguais em todas as execuções.
MODEL_INPUTS = ("model", "model_sha256")
# Campos do registro da reprodução iguais em todas as execuções.
REPLAY_INPUTS = ("stage", "segment", "pcap", "segment_packets", "addresses", "topology", "wait_after_replay_s",
                 "tcpreplay_build", "replay_cpus")
# Campos do registro da reprodução que dependem do nível de carga.
LOAD_INPUTS = ("nids_stop_timeout_s",)
# Campos do registro do NIDS iguais em todas as execuções, com a seção onde ficam.
REPORT_INPUTS = {"java_version": "extractor_start", "ring_bytes": "extractor_start", "platform": "environment"}
# Na captura pela interface, o extrator só para quando o NIDS pede. O fim de arquivo vale só para a leitura de arquivo.
STOP_REQUESTED = "stop_requested"
FLOW_MARKS = ("t0_ns", "t1_ns", "t2_ns", "t3_ns")
# Verificações da validação por cópia que reprovam só porque a captura perdeu pacotes.
CAPTURE_LOSS_CHECKS = {"no_capture_drops", "extractor_read_equals_h2_received"}
EXPLAINED_BY_CAPTURE_LOSS = "reprovada por perda na captura"


class CampaignAudit:
    def __init__(self, repo: NidsRepository) -> None:
        self.repo = repo

    def audit(self, matrix_path: Path) -> CommandResult:
        matrix = read_matrix(matrix_path)
        cells = expand(matrix)
        registry_path = self.repo.runs_dir / "matrizes" / matrix["name"] / "registro.jsonl"
        registry = read_registry(registry_path)
        if not registry:
            raise NidsError(f"A matriz {matrix['name']} ainda não tem ensaios registrados em {registry_path}.")
        analysis_dir, analysis = self._latest_analysis(matrix["name"])
        validations = {} if analysis is None else {
            str(Path(trial["run_dir"]).resolve()): trial["validation"]
            for trial in analysis["trials"] if trial.get("run_dir")}
        reports = self._validation_reports()
        trials = [self._trial(entry, matrix, validations, reports) for entry in registry]
        valid = [trial for trial in trials if trial["valid"] and trial["report"] is not None
                 and trial["replay"] is not None]
        inputs = input_differences([(trial["cell"], trial["report"], trial["replay"]) for trial in valid])
        registered = {(self.repo.root / trial["run_dir"]).resolve() for trial in trials if trial["run_dir"]}
        situation = coverage(cells, registry, matrix["max_attempts"])
        run_dir = self.repo.create_run(f"auditoria-{matrix['name']}")
        problems = [*situation["issues"], *inputs["issues"],
                    *(f"`{trial['cell']['id']}`, tentativa {trial['attempt']}: {issue}"
                      for trial in trials for issue in trial["issues"])]
        pending_checks = [f"`{trial['cell']['id']}`, tentativa {trial['attempt']}: {item}"
                          for trial in trials for item in trial["pending_checks"]]
        summary = {
            "stage": "matrix audit", "run_id": run_dir.name, "matrix": matrix["name"],
            "matrix_config": self.repo.relative(matrix_path), "segment": matrix["segment"],
            "registry": self.repo.relative(registry_path), "cells": len(cells), "attempts": len(registry),
            "coverage": situation,
            "analysis": None if analysis is None else {"run": self.repo.relative(analysis_dir),
                                                       "attempts": analysis.get("attempts")},
            "trials": [{key: value for key, value in trial.items() if key not in ("report", "replay")}
                       for trial in trials],
            "fixed_inputs": inputs,
            "exclusions": {"invalid": replacements(registry), "orphans": self._orphans(matrix["name"], registered),
                           "exhausted": situation["exhausted"]},
            "capture_loss": [{key: trial[key] for key in ("cell", "attempt", "run_dir", "capture_lost_packets",
                                                         "validation")}
                             for trial in trials if trial["valid"] and trial["capture_lost_packets"]],
            "problems": problems, "pending_checks": pending_checks,
            "closed": not situation["pending"] and not situation["exhausted"],
            "environment": self.repo.environment(),
        }
        summary["passed"] = summary["closed"] and not problems and not pending_checks
        self.repo.write_json(run_dir / "report.json", summary)
        report = self.repo.write_report(f"{matrix['name']}-auditoria-{run_dir.name}.md",
                                        audit_reporting.render_audit(summary))
        return CommandResult(run_dir, report, summary)

    def _latest_analysis(self, name: str) -> tuple[Path | None, dict[str, Any] | None]:
        runs = sorted((self.repo.runs_dir / "nids" / f"analise-{name}").glob("*/report.json"))
        return (None, None) if not runs else (runs[-1].parent, self.repo.read_json(runs[-1]))

    def _trial(self, entry: dict[str, Any], matrix: dict[str, Any], validations: dict[str, dict[str, Any] | None],
               reports: dict[Path, tuple[Path, dict[str, Any]]]) -> dict[str, Any]:
        cell = entry["cell"]
        trial: dict[str, Any] = {"cell": cell, "attempt": entry["attempt"], "valid": entry["validity"]["valid"],
                                 "reasons": entry["validity"]["reasons"],
                                 "started": entry["result"].get("started", True), "run_dir": None, "issues": [],
                                 "pending_checks": [], "recount": None, "validation": None,
                                 "capture_lost_packets": None, "report": None, "replay": None}
        folder = entry["result"].get("run_dir")
        if not trial["started"] or not folder or folder == "None":
            if trial["valid"]:
                trial["issues"].append("execução válida sem pasta registrada")
            return trial
        folder = Path(folder)
        trial["run_dir"] = self.repo.relative(folder)
        load = lambda name: (self.repo.read_json(folder / name)  # noqa: E731
                             if (folder / name).is_file() else None)
        trial["replay"], trial["report"] = load("replay.json"), load("report.json")
        if trial["replay"] is not None:
            trial["issues"] += consistency(cell, entry["attempt"], matrix["name"], matrix["segment"],
                                           trial["replay"], trial["report"])
        if not trial["valid"]:
            return trial
        if trial["replay"] is None or trial["report"] is None:
            trial["issues"].append("execução válida sem o registro da reprodução ou do NIDS")
            return trial
        report = trial["report"]
        trial["capture_lost_packets"] = capture_loss(report, trial["replay"])
        failing = sorted(name for name, passed in report["checks"].items() if passed is not True)
        if not report.get("passed") or failing:
            trial["issues"].append("o NIDS reprovou nas próprias verificações: " + ", ".join(failing))
        trial["issues"] += delivery_issues(trial["replay"], report)
        damaged = self._damaged_artifacts(report)
        if damaged:
            trial["issues"].append("arquivos diferentes do registrado: " + ", ".join(damaged))
        else:
            trial["recount"] = self._recount(folder, cell["strategy"])
            trial["issues"] += count_issues(trial["recount"], report, cell["strategy"])
        trial["validation"] = self._validation(validations.get(str(folder.resolve())), folder, reports)
        if trial["validation"]["status"] not in ("aprovada", EXPLAINED_BY_CAPTURE_LOSS):
            target = trial["issues"] if trial["validation"]["status"] == "reprovada" else trial["pending_checks"]
            target.append(f"validação por cópia {trial['validation']['status']}")
        return trial

    def _damaged_artifacts(self, report: dict[str, Any]) -> list[str]:
        damaged = []
        for name, info in sorted(report["artifacts"].items()):
            path = self.repo.root / info["file"]
            if not path.is_file() or path.stat().st_size != info["bytes"] or sha256(path) != info["sha256"]:
                damaged.append(name)
        return damaged

    def _recount(self, folder: Path, strategy: str) -> dict[str, Any]:
        with (folder / "flows.csv").open(newline="", encoding="utf-8") as flows:
            explanations = folder / "explanations.csv"
            if explanations.is_file():
                with explanations.open(newline="", encoding="utf-8") as stream:
                    counted = recount(csv.DictReader(flows), csv.DictReader(stream), strategy)
            else:
                counted = recount(csv.DictReader(flows), [], strategy)
        counted["classification_records"] = _lines(folder / "classifications.jsonl")
        counted["explanation_records"] = _lines(folder / "explanations.jsonl")
        return counted

    def _validation(self, validation: dict[str, Any] | None, folder: Path,
                    reports: dict[Path, tuple[Path, dict[str, Any]]]) -> dict[str, Any]:
        """Validação por cópia da análise mais recente, conferida no registro da própria validação. Uma validação
        reprovada só pela perda de pacotes na captura fica registrada como explicada por essa perda."""
        if validation is None:
            return {"status": "não feita"}
        if validation["status"] == "reprovada" and folder.resolve() in reports:
            directory, report = reports[folder.resolve()]
            if explained_by_capture_loss(report):
                rows = list((report.get("copies") or {}).values())
                return {"status": EXPLAINED_BY_CAPTURE_LOSS, "run": self.repo.relative(directory),
                        "flows_with_different_inputs": sum(row["matched_inside"]
                                                           - row["flows_with_equal_exact_attributes"] for row in rows),
                        "flows_compared": sum(row["matched_inside"] for row in rows),
                        "predictions_differing": sum(row["predictions_differing"] for row in rows)}
            return {"status": "reprovada", "run": self.repo.relative(directory),
                    "failing_checks": sorted(name for name, passed in report["checks"].items() if passed is not True)}
        if validation["status"] != "aprovada":
            return {"status": validation["status"], "run": validation.get("run")}
        path = self.repo.root / validation["run"] / "report.json"
        if not path.is_file():
            return {"status": "sem registro", "run": validation["run"]}
        report = self.repo.read_json(path)
        if not report.get("passed") or (self.repo.root / report["replay_run"]).resolve() != folder.resolve():
            return {"status": "reprovada", "run": validation["run"]}
        return {"status": "aprovada", "run": validation["run"], "copies": validation.get("copies"),
                "file_only_inside": validation.get("file_only_inside"),
                "replay_only_inside": validation.get("replay_only_inside"),
                "predictions_differing": validation.get("predictions_differing")}

    def _validation_reports(self) -> dict[Path, tuple[Path, dict[str, Any]]]:
        """Registro da validação por cópia mais recente de cada execução na rede emulada."""
        found = {}
        for path in sorted((self.repo.runs_dir / "nids" / "validacao").glob("*/report.json")):
            report = self.repo.read_json(path)
            if report.get("replay_run"):
                found[(self.repo.root / report["replay_run"]).resolve()] = (path.parent, report)
        return found

    def _orphans(self, name: str, registered: set[Path]) -> list[dict[str, Any]]:
        """Execuções da matriz que não estão no registro, como as interrompidas antes do fim."""
        found = []
        for path in sorted((self.repo.runs_dir / "nids" / "interface").glob("*/replay.json")):
            replay = self.repo.read_json(path)
            cell = replay.get("cell") or {}
            if cell.get("matrix") == name and path.parent.resolve() not in registered:
                found.append({"run_dir": self.repo.relative(path.parent), "cell": cell.get("id"),
                              "attempt": cell.get("attempt"), "replay_started_utc": replay.get("replay_started_utc"),
                              "replay_finished": "replay_finished_utc" in replay})
        return found


def capture_loss(report: dict[str, Any], replay: dict[str, Any]) -> int:
    """Pacotes perdidos antes do extrator: na interface que recebe o tráfego e no buffer de captura."""
    stats = report["extractor_end"].get("pcap_stats") or {}
    interface = (replay.get("interface_counters") or {}).get("h2-eth0") or {}
    return sum(value or 0 for value in (stats.get("dropped"), stats.get("interface_dropped"),
                                        interface.get("rx_dropped")))


def delivery_issues(replay: dict[str, Any], report: dict[str, Any]) -> list[str]:
    """Cada cópia sai do tcpreplay com todos os pacotes do trecho enviados e nenhum com falha, o total fecha com
    pacotes do trecho vezes cópias, e o extrator para a pedido do NIDS."""
    issues = []
    tcpreplay, packets, load = replay.get("tcpreplay") or {}, replay.get("segment_packets"), replay.get("copies")
    copies = tcpreplay.get("copies") or []
    whole = (isinstance(packets, int) and isinstance(load, int) and len(copies) == load
             and all(copy.get("exit_code") == 0 and copy.get("successful") == packets and copy.get("failed") == 0
                     for copy in copies)
             and tcpreplay.get("exit_code") == 0 and tcpreplay.get("successful") == packets * load
             and tcpreplay.get("failed") == 0)
    if not whole:
        issues.append("o tcpreplay não enviou todos os pacotes de cada cópia")
    stop = (report.get("extractor_end") or {}).get("stop_reason")
    if stop != STOP_REQUESTED:
        issues.append(f"o extrator parou por `{stop}`, e não a pedido do NIDS")
    return issues


def explained_by_capture_loss(validation: dict[str, Any]) -> bool:
    """Uma validação por cópia que só reprovou porque a captura perdeu pacotes. Os pacotes lidos pelo extrator
    somados aos perdidos na captura fecham com os recebidos pela interface, e nenhuma outra verificação falhou."""
    failing = {name for name, passed in validation["checks"].items() if passed is not True}
    counters = validation["counters"]
    lost = (counters.get("pcap_dropped") or 0) + (counters.get("pcap_interface_dropped") or 0)
    return (bool(failing) and failing <= CAPTURE_LOSS_CHECKS and lost > 0
            and counters.get("extractor_read") is not None
            and counters["extractor_read"] + lost == counters.get("h2_received"))


def coverage(cells: list[Cell], registry: list[dict[str, Any]], max_attempts: int) -> dict[str, Any]:
    """Situação de cada célula e os problemas do registro: célula fora da matriz, célula registrada com outra
    definição, tentativas iniciadas fora da sequência 1, 2, ... e mais de uma execução válida na mesma célula."""
    situation = status(cells, registry, max_attempts)
    expected = {cell.id: cell.as_dict() for cell in cells}
    entries: dict[str, list[dict[str, Any]]] = {}
    for entry in registry:
        entries.setdefault(entry["cell"]["id"], []).append(entry)
    issues = [f"célula fora da matriz: `{cell_id}`" for cell_id in situation["unknown_cells"]]
    for cell_id, found in entries.items():
        if cell_id not in expected:
            continue
        if any(entry["cell"] != expected[cell_id] for entry in found):
            issues.append(f"`{cell_id}` registrada com outra definição de célula")
        started = [entry["attempt"] for entry in found if entry["result"].get("started", True)]
        if started != list(range(1, len(started) + 1)):
            issues.append(f"`{cell_id}`: tentativas iniciadas fora de sequência, {started}")
        valid = sum(1 for entry in found if entry["result"].get("started", True) and entry["validity"]["valid"])
        if valid > 1:
            issues.append(f"`{cell_id}`: {valid} execuções válidas")
    return {"done": len(situation["done"]), "exhausted": [cell.id for cell in situation["exhausted"]],
            "pending": [cell.id for cell, _ in situation["pending"]],
            "not_started": sum(1 for entry in registry if not entry["result"].get("started", True)),
            "issues": issues}


def replacements(registry: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tentativas inválidas, com o motivo e a tentativa seguinte da mesma célula, se houver."""
    result = []
    for position, entry in enumerate(registry):
        if not entry["result"].get("started", True) or entry["validity"]["valid"]:
            continue
        following = next((later for later in registry[position + 1:] if later["cell"]["id"] == entry["cell"]["id"]
                          and later["result"].get("started", True)), None)
        result.append({"cell": entry["cell"]["id"], "attempt": entry["attempt"],
                       "reasons": entry["validity"]["reasons"],
                       "replaced_by": None if following is None else {"attempt": following["attempt"],
                                                                      "valid": following["validity"]["valid"]}})
    return result


def consistency(cell: dict[str, Any], attempt: int, matrix_name: str, segment: str, replay: dict[str, Any],
                report: dict[str, Any] | None) -> list[str]:
    """Diferenças entre a célula registrada e o que os registros da execução dizem que ela foi."""
    issues = []
    recorded = replay.get("cell") or {}
    if (recorded.get("id"), recorded.get("attempt"), recorded.get("matrix")) != (cell["id"], attempt, matrix_name):
        issues.append("o registro da reprodução aponta outra célula, tentativa ou matriz")
    expected = {"model": cell["model"], "strategy": cell["strategy"], "criterion": cell["criterion"],
                "copies": cell["load"], "segment": segment}
    differing = [key for key, value in expected.items() if replay.get(key) != value]
    if differing:
        issues.append("a reprodução difere da célula em " + ", ".join(differing))
    if report is not None:
        actual = {"model": report["model"], "strategy": report["strategy_key"],
                  "criterion": (report.get("selection") or {}).get("criterion"),
                  "segment": (report.get("segment") or {}).get("name"), "source": report["source"]["kind"]}
        expected = {**{key: expected[key] for key in ("model", "strategy", "criterion", "segment")},
                    "source": "interface"}
        differing = [key for key, value in expected.items() if actual[key] != value]
        if differing:
            issues.append("o registro do NIDS difere da célula em " + ", ".join(differing))
    return issues


def recount(flows: Iterable[dict[str, str]], explanations: Iterable[dict[str, str]], strategy: str) -> dict[str, Any]:
    """Contagens e ordem das marcações refeitas da tabela por fluxo e da tabela de explicações de uma execução.

    Nas estratégias síncronas, uma única leitura do relógio vale por `t3` e `t4`. No Assíncrono, a explicação sai da
    fila depois da solicitação e fica disponível depois da classificação."""
    received = errors = 0
    sequences: set[int] = set()
    repeated = False
    ordered = True
    t3: dict[int, int] = {}
    requested: dict[int, int] = {}
    selected: set[int] = set()
    states: dict[str, int] = {}
    for row in flows:
        received += 1
        seq = int(row["seq"])
        repeated = repeated or seq in sequences
        sequences.add(seq)
        if row["error"]:
            errors += 1
            continue
        marks = [int(row[name]) for name in FLOW_MARKS]
        ordered = ordered and marks == sorted(marks)
        t3[seq] = marks[-1]
        if row["selected"] == "1":
            selected.add(seq)
        states[row["explanation"]] = states.get(row["explanation"], 0) + 1
        if row["explanation_requested_ns"]:
            requested[seq] = int(row["explanation_requested_ns"])
    completed = 0
    explained: set[int] = set()
    marks_ordered = True
    for row in explanations:
        completed += 1
        seq = int(row["seq"])
        repeated = repeated or seq in explained
        explained.add(seq)
        if seq not in t3:
            continue
        start, end, t4 = (int(row[name]) for name in ("explanation_start_ns", "explanation_end_ns", "t4_ns"))
        ordered_row = start <= end <= t4
        if strategy == "assincrono":
            ordered_row = (ordered_row and seq in requested and bool(row["dequeued_ns"])
                           and requested[seq] <= int(row["dequeued_ns"]) <= start and t4 >= t3[seq])
        else:
            ordered_row = ordered_row and t4 == t3[seq]
        marks_ordered = marks_ordered and ordered_row
    return {"received": received, "classified": len(t3), "errors": errors,
            "max_seq": max(sequences, default=0), "unique_sequences": not repeated, "flow_marks_ordered": ordered,
            "selected": len(selected), "states": states, "completed": completed,
            "explanation_marks_ordered": marks_ordered, "explained_without_flow": len(explained - set(t3)),
            "explained_not_selected": len(explained - selected)}


def count_issues(counted: dict[str, Any], report: dict[str, Any], strategy: str) -> list[str]:
    """Diferenças entre a recontagem dos arquivos brutos e o que o registro do NIDS informa, e as contas que cada
    estratégia precisa fechar."""
    issues = []
    end, flows, explanations = report["extractor_end"], report["flows"], report["explanations"]
    emitted, dropped = end.get("flows_emitted") or 0, end.get("flows_dropped") or 0
    pairs = {"fluxos recebidos": (counted["received"], flows["received"]),
             "fluxos classificados": (counted["classified"], flows["classified"]),
             "fluxos com erro": (counted["errors"], flows["errors"]),
             "registros de classificação": (counted["classification_records"], counted["classified"]),
             "fluxos selecionados": (counted["selected"], explanations["selected"]),
             "explicações concluídas": (counted["completed"], explanations["completed"]),
             "registros de explicação": (counted["explanation_records"], counted["completed"])}
    issues += [f"{name}: {found} nos arquivos contra {expected}" for name, (found, expected) in pairs.items()
               if found != expected]
    if emitted != counted["received"] + dropped or counted["max_seq"] > emitted or not counted["unique_sequences"]:
        issues.append("os fluxos emitidos não fecham com os recebidos e os descartados")
    if not counted["flow_marks_ordered"]:
        issues.append("marcações t0 a t3 fora de ordem")
    if not counted["explanation_marks_ordered"]:
        issues.append("marcações da explicação fora de ordem")
    if counted["explained_without_flow"] or counted["explained_not_selected"]:
        issues.append("explicação de fluxo não classificado ou não selecionado")
    states, selected, completed = counted["states"], counted["selected"], counted["completed"]
    if strategy == "sem-xai" and (selected or completed):
        issues.append("o Sem XAI selecionou ou explicou fluxos")
    if strategy == "sincrono-total" and selected != counted["classified"]:
        issues.append("o Síncrono total não selecionou todos os fluxos classificados")
    if strategy in ("sincrono-total", "sincrono-condicional") and (
            completed != selected or states.get(COMPLETED, 0) != selected):
        issues.append("um fluxo selecionado ficou sem explicação na estratégia síncrona")
    if strategy == "assincrono":
        accepted, refused = states.get(REQUESTED, 0), states.get(DROPPED, 0)
        pending = accepted - completed
        queue = report.get("explanation_queue") or {}
        found = {"requested": selected, "accepted": accepted, "dropped": refused, "completed": completed,
                 "pending": pending}
        if selected != counted["classified"] or accepted + refused != selected or pending < 0:
            issues.append("as solicitações do Assíncrono não cobrem os fluxos classificados")
        differing = [key for key, value in found.items() if queue.get(key) != value]
        if differing:
            issues.append("a fila de explicações difere da recontagem em " + ", ".join(differing))
        if queue.get("requested") != sum(queue.get(key) or 0 for key in ("completed", "dropped", "pending")):
            issues.append("solicitações diferentes de concluídas mais descartadas mais pendentes")
    return issues


def input_differences(trials: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    """Entradas fixas das execuções válidas. O classificador e o seu manifesto variam com o modelo, o tempo máximo de
    encerramento do NIDS varia com a carga, e todo o resto é igual em todas as execuções. O código é o mesmo commit,
    e só arquivos de documentação podem estar alterados."""
    rows, issues = [], []

    def compare(name: str, scope: str, values: list[tuple[Any, Any]]) -> None:
        groups: dict[Any, set[str]] = {}
        for group, value in values:
            groups.setdefault(group, set()).add(json.dumps(value, sort_keys=True, ensure_ascii=False))
        distinct = max((len(found) for found in groups.values()), default=0)
        rows.append({"input": name, "scope": scope, "distinct": distinct, "equal": distinct <= 1})
        if distinct > 1:
            issues.append(f"a entrada `{name}` difere entre execuções ({scope})")

    reports = [(cell, fixed_inputs(report)) for cell, report, _ in trials]
    for key in (reports[0][1] if reports else {}):
        if key in MODEL_INPUTS:
            compare(key, "por classificador", [(cell["model"], inputs[key]) for cell, inputs in reports])
        else:
            compare(key, "todas", [(None, inputs[key]) for _, inputs in reports])
    for key, section in REPORT_INPUTS.items():
        compare(key, "todas", [(None, (report.get(section) or {}).get(key)) for _, report, _ in trials])
    for key in REPLAY_INPUTS:
        compare(key, "todas", [(None, replay.get(key)) for _, _, replay in trials])
    for key in LOAD_INPUTS:
        compare(key, "por carga", [(cell["load"], replay.get(key)) for cell, _, replay in trials])
    compare("interface_offloads", "todas",
            [(None, {name: data.get("offloads") for name, data in (replay.get("interfaces") or {}).items()})
             for _, _, replay in trials])
    commits = sorted({(replay.get("git") or {}).get("commit") for _, _, replay in trials}, key=str)
    compare("git_commit", "todas", [(None, commit) for commit in commits])
    modified = sorted({_path(line) for _, _, replay in trials
                       for line in (replay.get("git") or {}).get("modified_tracked_files", [])})
    code = [path for path in modified if not _documentation(path)]
    if code:
        issues.append("arquivos de código alterados durante a matriz: " + ", ".join(code))
    return {"rows": rows, "issues": issues, "git": {"commits": commits, "modified_tracked_files": modified}}


def _path(line: str) -> str:
    """Caminho de uma linha do `git status --porcelain`, inclusive de um arquivo renomeado."""
    path = line.strip().split(maxsplit=1)[-1]
    return path.split(" -> ")[-1]


def _documentation(path: str) -> bool:
    return path.startswith("docs/") or path.endswith(".md")


def _lines(path: Path) -> int:
    """Número de linhas de um canal de saída. Um canal que a execução não abriu tem zero linhas."""
    if not path.is_file():
        return 0
    with path.open("rb") as stream:
        return sum(chunk.count(b"\n") for chunk in iter(lambda: stream.read(1 << 20), b""))
