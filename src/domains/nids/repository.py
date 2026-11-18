"""Arquivos do NIDS: configuração, modelos congelados, trechos preparados, canal de saída e registros."""

import csv
import json
import os
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any

from domains.explanations.repository import ExplanationRepository
from domains.explanations.schemas import SplitData, TreeShapConfig
from domains.model_artifacts.repository import ModelArtifactRepository
from domains.model_artifacts.schemas import LoadedModel
from domains.model_training.repository import sha256
from domains.nids.exceptions import NidsError
from domains.nids.schemas import CRITERIA, MODELS, NidsConfig

csv.field_size_limit(1 << 20)


PROCESSES = ("classifier", "explainer", "extractor", "replay")


def _checked_resources(resources: dict[str, Any]) -> None:
    """CPUs de cada processo do experimento, heap máximo e opções da JVM do extrator. Nenhuma CPU é dividida entre
    processos."""
    if (set(resources) != {"cpus", "extractor_max_heap_mib", "extractor_jvm_options"}
            or set(resources["cpus"]) != set(PROCESSES)):
        raise ValueError(f"resources deve ter cpus de {list(PROCESSES)}, extractor_max_heap_mib e "
                         "extractor_jvm_options")
    cpus = [cpu for name in PROCESSES for cpu in resources["cpus"][name]]
    available = set(range(os.cpu_count() or 0))
    if not all(type(cpu) is int for cpu in cpus) or len(cpus) != len(set(cpus)) or not set(cpus) <= available:
        raise ValueError("cada processo precisa de CPUs próprias, existentes na máquina")
    if any(not resources["cpus"][name] for name in PROCESSES):
        raise ValueError("cada processo precisa de ao menos uma CPU")
    if type(resources["extractor_max_heap_mib"]) is not int or resources["extractor_max_heap_mib"] < 256:
        raise ValueError("extractor_max_heap_mib deve ser um inteiro de pelo menos 256")
    options = resources["extractor_jvm_options"]
    # O heap máximo fica só em extractor_max_heap_mib.
    if (type(options) is not list or not all(type(option) is str and option.startswith("-") for option in options)
            or any(option.startswith("-Xmx") for option in options)):
        raise ValueError("extractor_jvm_options deve ser uma lista de opções da JVM, sem -Xmx")


def _checked_selection(selection: dict[str, Any]) -> dict[str, Any]:
    """Grade de calibração e limiares do Síncrono condicional. Um limiar nulo ainda não foi fixado."""
    if set(selection) != {"calibration_grid", "calibration_run", "thresholds"}:
        raise ValueError("selection deve ter calibration_grid, calibration_run e thresholds")
    grid, thresholds = selection["calibration_grid"], selection["thresholds"]
    if set(grid) != set(CRITERIA) or set(thresholds) != set(CRITERIA):
        raise ValueError(f"a grade e os limiares devem cobrir os critérios {sorted(CRITERIA)}")
    for criterion, limit in CRITERIA.items():
        if set(thresholds[criterion]) != set(MODELS):
            raise ValueError(f"os limiares de {criterion} devem cobrir os dois classificadores")
        fixed = [value for value in thresholds[criterion].values() if value is not None]
        if not grid[criterion] or not all(type(value) in (int, float) and 0 < value <= limit
                                          for value in [*grid[criterion], *fixed]):
            raise ValueError(f"os limiares de {criterion} devem ser maiores que 0 e de no máximo {limit}")
        if fixed and selection["calibration_run"] is None:
            raise ValueError("limiares fixados exigem a execução de calibração que os sustenta")
    return selection


class NidsRepository:
    def __init__(self, root: Path, data_dir: Path, runs_dir: Path, reports_dir: Path) -> None:
        self.root = root
        self.data_dir = data_dir
        self.runs_dir = runs_dir
        self.reports_dir = reports_dir

    def read_config(self, path: Path) -> NidsConfig:
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
            if set(content) != {"frozen_run", "preparation_manifests", "tree_shap_config", "selection",
                                "explanation_queue", "resources", "extractor", "classifier_threads",
                                "shared_clock_tolerance_ns"}:
                raise ValueError("campos inesperados ou ausentes")
            if set(content["extractor"]) != {"snaplen", "read-timeout-ms", "idle-margin-us", "buffer-bytes",
                                             "flow-queue-limit"}:
                raise ValueError("extractor deve ter snaplen, read-timeout-ms, idle-margin-us, buffer-bytes e "
                                 "flow-queue-limit")
            queue_settings = content["explanation_queue"]
            if (set(queue_settings) != {"limit", "drain_timeout_s"} or type(queue_settings["limit"]) is not int
                    or queue_settings["limit"] < 1 or not queue_settings["drain_timeout_s"] > 0):
                raise ValueError("explanation_queue deve ter limit e drain_timeout_s positivos")
            _checked_resources(content["resources"])
            if type(content["classifier_threads"]) is not int or content["classifier_threads"] < 1:
                raise ValueError("classifier_threads deve ser um inteiro positivo")
            manifests = content["preparation_manifests"]
            if not manifests or not all(type(item) is str for item in manifests):
                raise ValueError("preparation_manifests deve listar ao menos um manifesto")
            return NidsConfig(path, sha256(path), content, self.root / content["frozen_run"],
                              tuple(self.root / item for item in manifests), self.root / content["tree_shap_config"],
                              _checked_selection(content["selection"]), dict(content["explanation_queue"]),
                              content["resources"], dict(content["extractor"]), content["classifier_threads"],
                              int(content["shared_clock_tolerance_ns"]))
        except (OSError, KeyError, ValueError, TypeError) as error:
            raise NidsError(f"Configuração inválida em {path}: {error}") from error

    def validation_split(self) -> SplitData:
        """Conjunto de validação, o único que a calibração do critério de seleção pode usar."""
        return ExplanationRepository(self.root, self.data_dir, self.runs_dir, self.reports_dir).load_split("validation")

    def tree_shap(self, path: Path, frozen_run: Path) -> TreeShapConfig:
        """Configuração validada do TreeSHAP, que deve se referir aos mesmos modelos congelados do NIDS."""
        config = ExplanationRepository(self.root, self.data_dir, self.runs_dir, self.reports_dir).read_config(path)
        if config.frozen_run.resolve() != frozen_run.resolve():
            raise NidsError("A configuração do TreeSHAP se refere a outros modelos congelados.")
        return config

    def data_manifest(self) -> dict[str, Any]:
        return self.read_json(self.data_dir / "manifest.json")

    def load_frozen(self, frozen_run: Path, name: str) -> LoadedModel:
        path = frozen_run / name
        if sha256(path / "data-manifest.json") != sha256(self.data_dir / "manifest.json"):
            raise NidsError(f"O modelo congelado {name} foi treinado com outro manifesto de dados.")
        return ModelArtifactRepository(self.root, self.data_dir, self.runs_dir).load(path)

    def segment(self, manifest_paths: tuple[Path, ...], name: str) -> dict[str, Any]:
        """Trecho preparado, procurado pelo nome nos manifestos, com os arquivos conferidos pelo hash."""
        found = [(path, manifest) for path in manifest_paths
                 if name in (manifest := self.read_json(path))["segments"]]
        if len(found) != 1:
            raise NidsError(f"Trecho desconhecido: {name}." if not found else f"Trecho {name} em mais de um manifesto.")
        manifest_path, manifest = found[0]
        info = manifest["segments"][name]
        for key in ("pcap", "reference", "carried_over", "addresses"):
            if key in info:
                self.checked(info[key])
        return {**info, "name": name, "border_seconds": manifest["border_seconds"],
                "manifest": self.relative(manifest_path), "manifest_sha256": sha256(manifest_path)}

    def rewrite_tool(self) -> dict[str, Any]:
        """tcprewrite compilado por tcpreplay/build.sh, conferido com o registro da compilação."""
        build = self.root / "tcpreplay" / "build"
        record = self.read_json(build / "tcpreplay-build.json")
        entry = record.get("binaries", {}).get("tcprewrite")
        path = build / "tcprewrite"
        if entry is None or not path.is_file() or sha256(path) != entry["sha256"]:
            raise NidsError("O tcprewrite está ausente ou difere do registro da compilação. Rode tcpreplay/build.sh.")
        return {"path": path, "record": {"version": record["version"], "file": "tcpreplay/build/tcprewrite",
                                         "sha256": entry["sha256"]}}

    def carried_over(self, info: dict[str, Any]) -> set[tuple[Any, ...]]:
        """Conexões com pacotes antes do início do trecho. Um trecho que começa na captura não tem nenhuma."""
        if "carried_over" not in info:
            return set()
        return {tuple(item) for item in self.read_json(self.checked(info["carried_over"]))}

    def stream_rows(self, path: Path) -> Iterator[dict[str, str]]:
        """Linhas de uma tabela já conferida, uma de cada vez, para tabelas que não cabem na memória."""
        with path.open(newline="", encoding="utf-8") as stream:
            yield from csv.DictReader(stream)

    def read_rows(self, info: dict[str, Any]) -> list[dict[str, str]]:
        with self.checked(info).open(newline="", encoding="utf-8") as stream:
            return list(csv.DictReader(stream))

    def checked(self, info: dict[str, Any]) -> Path:
        path = self.root / info["file"]
        if path.stat().st_size != info["bytes"] or sha256(path) != info["sha256"]:
            raise NidsError(f"Hash ou tamanho divergente em {path}.")
        return path

    def create_run(self, kind: str) -> Path:
        path = self.runs_dir / "nids" / kind / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path.mkdir(parents=True, exist_ok=False)
        return path

    def open_channel(self, run_dir: Path) -> IO[str]:
        """Canal de saída do NIDS: uma linha JSON por classificação, entregue ao sistema a cada escrita."""
        return (run_dir / "classifications.jsonl").open("w", encoding="utf-8")

    def open_explanations(self, run_dir: Path) -> IO[str]:
        """Canal de saída das explicações: uma linha JSON por fluxo explicado, entregue ao sistema a cada escrita."""
        return (run_dir / "explanations.jsonl").open("w", encoding="utf-8")

    def open_table(self, run_dir: Path, header: list[str], name: str = "flows.csv") -> tuple[IO[str], Any]:
        stream = (run_dir / name).open("w", newline="", encoding="utf-8")
        writer = csv.DictWriter(stream, fieldnames=header)
        writer.writeheader()
        return stream, writer

    def read_table(self, info: dict[str, Any]) -> list[dict[str, str]]:
        return self.read_rows(info)

    def artifact(self, path: Path) -> dict[str, Any]:
        return {"file": self.relative(path), "bytes": path.stat().st_size, "sha256": sha256(path)}

    def read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def write_json(self, path: Path, value: dict[str, Any]) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    def write_report(self, name: str, text: str) -> Path:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        path = self.reports_dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def signal_ready(self, path: Path, run_dir: Path) -> None:
        """Avisa que a captura está aberta e informa onde fica o registro da execução."""
        path.write_text(json.dumps({"pid": os.getpid(), "run_dir": str(run_dir)}) + "\n", encoding="utf-8")

    def relative(self, path: Path) -> str:
        """Caminho relativo à raiz do projeto. Um arquivo fora do projeto, como uma configuração passada por
        --config, fica com o caminho absoluto."""
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root.resolve()):
            return resolved.as_posix()
        return resolved.relative_to(self.root.resolve()).as_posix()

    def environment(self) -> dict[str, Any]:
        """Versões do Python e das bibliotecas, incluindo o shap e o threadpoolctl, e a máquina."""
        return ExplanationRepository(self.root, self.data_dir, self.runs_dir, self.reports_dir).environment()

    def read_explanation_records(self, report: dict[str, Any]) -> dict[int, dict[str, Any]]:
        """Registros do canal de saída das explicações de uma execução, conferidos pelo hash, pelo número de
        sequência do fluxo."""
        info = report["artifacts"].get("explanations.jsonl")
        if info is None:
            return {}
        with self.checked(info).open(encoding="utf-8") as stream:
            return {record["seq"]: record for record in map(json.loads, stream)}

    def read_flow_marks(self, report: dict[str, Any]) -> list[dict[str, str]]:
        """Colunas de classificação e de seleção da tabela por fluxo de uma execução, conferida pelo hash."""
        keep = ("seq", "error", "attack_probability", "prediction", "selected", "explanation")
        with self.checked(report["artifacts"]["flows.csv"]).open(newline="", encoding="utf-8") as stream:
            return [{key: row[key] for key in keep} for row in csv.DictReader(stream)]

    def cpu_state(self) -> dict[str, Any]:
        return ExplanationRepository(self.root, self.data_dir, self.runs_dir, self.reports_dir).cpu_state()
