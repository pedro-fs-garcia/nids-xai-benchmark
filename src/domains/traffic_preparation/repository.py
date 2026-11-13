"""Leitura e gravação dos arquivos de tráfego: PCAPs, tabelas de referência, manifestos e relatórios."""

import csv
import json
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from domains.model_training.repository import ModelTrainingRepository, sha256
from domains.traffic_preparation.exceptions import TrafficPreparationError
from domains.traffic_preparation.schemas import PreparationConfig, SourcePcap

csv.field_size_limit(1 << 20)


class TrafficRepository:
    def __init__(self, root: Path, data_dir: Path, runs_dir: Path, reports_dir: Path) -> None:
        self.root = root
        self.data_dir = data_dir
        self.runs_dir = runs_dir
        self.reports_dir = reports_dir

    def read_config(self, path: Path) -> PreparationConfig:
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
            source = content["source"]
            segments = {name: datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                        for name, stamp in content["segments"].items()}
            if any(moment.tzinfo != timezone.utc for moment in segments.values()):
                raise ValueError("os instantes de corte devem estar em UTC")
            return PreparationConfig(
                path=path, sha256=sha256(path),
                source=SourcePcap(self.root / source["file"], source["mirror"], source["mirror_commit"],
                                  source["path_in_mirror"], int(source["bytes"]), source["sha256"]),
                flows_csv=self.root / content["flows_csv"], output_dir=self.root / content["output_dir"],
                segments=segments, border_seconds=int(content["border_seconds"]),
            )
        except (OSError, KeyError, ValueError, TypeError) as error:
            raise TrafficPreparationError(f"Configuração inválida em {path}: {error}") from error

    def data_manifest(self) -> dict[str, Any]:
        return self.read_json(self.data_dir / "manifest.json")

    def checked_flows_csv(self, config: PreparationConfig) -> dict[str, Any]:
        """Confere que o CSV de fluxos é o mesmo usado na preparação dos dados de treino."""
        name = config.flows_csv.name
        entries = [entry for entry in self.data_manifest()["sources"] if entry["file"] == name]
        if len(entries) != 1:
            raise TrafficPreparationError(f"{name} não consta no manifesto dos dados.")
        if config.flows_csv.stat().st_size != entries[0]["bytes"] or sha256(config.flows_csv) != entries[0]["sha256"]:
            raise TrafficPreparationError(f"{name} difere do arquivo usado na preparação dos dados.")
        return entries[0]

    def iter_csv(self, path: Path) -> Iterator[dict[str, str]]:
        with path.open(newline="", encoding="utf-8") as stream:
            yield from csv.DictReader(stream)

    def csv_header(self, path: Path) -> list[str]:
        with path.open(newline="", encoding="utf-8") as stream:
            return next(csv.reader(stream))

    def read_extracted_csv(self, path: Path) -> tuple[list[str], list[dict[str, str]]]:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.reader(stream)
            header = next(reader)
            rows = [dict(zip(header, row)) for row in reader if row != header]
        return header, rows

    def write_csv(self, path: Path, header: list[str], rows: list[dict[str, str]]) -> dict[str, Any]:
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=header, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        return self.artifact(path)

    def artifact(self, path: Path) -> dict[str, Any]:
        return {"file": self.relative(path), "bytes": path.stat().st_size, "sha256": sha256(path)}

    def checked(self, info: dict[str, Any]) -> Path:
        path = self.root / info["file"]
        if path.stat().st_size != info["bytes"] or sha256(path) != info["sha256"]:
            raise TrafficPreparationError(f"Hash ou tamanho divergente em {path}.")
        return path

    def read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def write_json(self, path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    def create_run(self, kind: str) -> Path:
        path = self.runs_dir / "traffic" / kind / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path.mkdir(parents=True, exist_ok=False)
        return path

    def write_report(self, name: str, text: str) -> Path:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        path = self.reports_dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root.resolve()).as_posix()

    def environment(self) -> dict[str, Any]:
        return ModelTrainingRepository(self.data_dir, self.runs_dir, self.reports_dir).environment()
