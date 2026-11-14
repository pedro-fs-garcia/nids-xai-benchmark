"""Arquivos do NIDS: configuração, modelos congelados, trechos preparados, canal de saída e registros."""

import csv
import json
import os
import resource
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any

from domains.explanations.repository import ExplanationRepository
from domains.model_artifacts.repository import ModelArtifactRepository
from domains.model_artifacts.schemas import LoadedModel
from domains.model_training.repository import ModelTrainingRepository, sha256
from domains.nids.exceptions import NidsError
from domains.nids.schemas import NidsConfig

csv.field_size_limit(1 << 20)


class NidsRepository:
    def __init__(self, root: Path, data_dir: Path, runs_dir: Path, reports_dir: Path) -> None:
        self.root = root
        self.data_dir = data_dir
        self.runs_dir = runs_dir
        self.reports_dir = reports_dir

    def read_config(self, path: Path) -> NidsConfig:
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
            if set(content) != {"frozen_run", "preparation_manifest", "extractor", "classifier_threads",
                                "shared_clock_tolerance_ns"}:
                raise ValueError("campos inesperados ou ausentes")
            if set(content["extractor"]) != {"snaplen", "read-timeout-ms", "idle-margin-us", "buffer-bytes"}:
                raise ValueError("extractor deve ter snaplen, read-timeout-ms, idle-margin-us e buffer-bytes")
            if type(content["classifier_threads"]) is not int or content["classifier_threads"] < 1:
                raise ValueError("classifier_threads deve ser um inteiro positivo")
            return NidsConfig(path, sha256(path), content, self.root / content["frozen_run"],
                              self.root / content["preparation_manifest"], dict(content["extractor"]),
                              content["classifier_threads"], int(content["shared_clock_tolerance_ns"]))
        except (OSError, KeyError, ValueError, TypeError) as error:
            raise NidsError(f"Configuração inválida em {path}: {error}") from error

    def data_manifest(self) -> dict[str, Any]:
        return self.read_json(self.data_dir / "manifest.json")

    def load_frozen(self, frozen_run: Path, name: str) -> LoadedModel:
        path = frozen_run / name
        if sha256(path / "data-manifest.json") != sha256(self.data_dir / "manifest.json"):
            raise NidsError(f"O modelo congelado {name} foi treinado com outro manifesto de dados.")
        return ModelArtifactRepository(self.root, self.data_dir, self.runs_dir).load(path)

    def segment(self, manifest_path: Path, name: str) -> dict[str, Any]:
        """Trecho preparado, com o PCAP e a tabela de referência conferidos pelo hash."""
        manifest = self.read_json(manifest_path)
        if name not in manifest["segments"]:
            raise NidsError(f"Trecho desconhecido: {name}.")
        info = manifest["segments"][name]
        for key in ("pcap", "reference"):
            self.checked(info[key])
        return {**info, "name": name, "border_seconds": manifest["border_seconds"],
                "manifest": self.relative(manifest_path), "manifest_sha256": sha256(manifest_path)}

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

    def open_table(self, run_dir: Path, header: list[str]) -> tuple[IO[str], Any]:
        stream = (run_dir / "flows.csv").open("w", newline="", encoding="utf-8")
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
        return path.resolve().relative_to(self.root.resolve()).as_posix()

    def environment(self) -> dict[str, Any]:
        return ModelTrainingRepository(self.data_dir, self.runs_dir, self.reports_dir).environment()

    def cpu_state(self) -> dict[str, Any]:
        return ExplanationRepository(self.root, self.data_dir, self.runs_dir, self.reports_dir).cpu_state()

    def resource_usage(self) -> dict[str, Any]:
        """CPU e pico de memória do processo do NIDS e, separadamente, do extrator, que é um processo filho."""
        usage = {}
        for name, who in (("classifier_process", resource.RUSAGE_SELF), ("extractor_process", resource.RUSAGE_CHILDREN)):
            value = resource.getrusage(who)
            usage[name] = {"user_seconds": value.ru_utime, "system_seconds": value.ru_stime,
                           "max_rss_kib": value.ru_maxrss}
        return usage
