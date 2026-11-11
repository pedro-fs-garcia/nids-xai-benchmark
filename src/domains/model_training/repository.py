import hashlib
import json
import os
import platform
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from domains.model_training.exceptions import InvalidPilotConfigError, InvalidTrainingDataError
from domains.model_training.reporting import render_forest_comparison_report, render_pilot_report
from domains.model_training.schemas import (
    ForestAlternative, ForestComparisonConfig, PilotConfig, PilotDataset, ReferenceRun, TrainingSplit,
)


class ModelTrainingRepository:
    def __init__(self, data_dir: Path, runs_dir: Path, reports_dir: Path) -> None:
        self.data_dir = data_dir
        self.runs_dir = runs_dir
        self.reports_dir = reports_dir

    def read_config(self, path: Path) -> PilotConfig:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if set(data) != {"sample_size", "sample_seed", "model"}:
                raise ValueError("campos esperados: sample_size, sample_seed e model")
            if type(data["sample_size"]) is not int or data["sample_size"] <= 0:
                raise ValueError("sample_size deve ser um inteiro positivo")
            if type(data["sample_seed"]) is not int or data["sample_seed"] < 0:
                raise ValueError("sample_seed deve ser um inteiro não negativo")
            if not isinstance(data["model"], dict):
                raise ValueError("model deve conter os parâmetros do Random Forest")
            return PilotConfig(**data)
        except (OSError, ValueError, TypeError) as error:
            raise InvalidPilotConfigError(f"Configuração inválida em {path}: {error}") from error

    def load_pilot_dataset(self) -> PilotDataset:
        try:
            raw_manifest = (self.data_dir / "manifest.json").read_bytes()
            manifest = json.loads(raw_manifest)
            if len(manifest["inputs"]) != 80 or manifest["classes"] != {"benign": 0, "attack": 1}:
                raise ValueError("esperadas 80 entradas e as classes benign=0 e attack=1")
            required = (
                "every_record_in_exactly_one_split",
                "no_input_vector_in_more_than_one_split",
                "every_original_label_in_every_split",
                "all_values_finite",
                "sources_unchanged",
            )
            if not all(manifest["verifications"].get(check) is True for check in required):
                raise ValueError("as verificações da preparação dos dados devem estar aprovadas")
            return PilotDataset(
                manifest=manifest,
                manifest_sha256=hashlib.sha256(raw_manifest).hexdigest(),
                train=self._load_split("train", manifest),
                validation=self._load_split("validation", manifest),
            )
        except (OSError, KeyError, ValueError, TypeError) as error:
            raise InvalidTrainingDataError(f"Dados derivados inválidos: {error}") from error

    def _load_split(self, name: str, manifest: dict[str, Any]) -> TrainingSplit:
        # Este caminho de execução permite apenas treino e validação.
        if name not in {"train", "validation"}:
            raise InvalidTrainingDataError(f"Conjunto não permitido no piloto: {name}")
        return self._read_verified_split(name, manifest)

    def _read_verified_split(self, name: str, manifest: dict[str, Any]) -> TrainingSplit:
        arrays = {}
        info = manifest["splits"][name]
        for key in ("X", "y", "origin"):
            expected = info["files"][key]
            path = self.data_dir / expected["file"]
            if path.name != f"{key}_{name}.npy":
                raise ValueError(f"arquivo inesperado para {key} de {name}")
            if path.stat().st_size != expected["bytes"] or sha256(path) != expected["sha256"]:
                raise ValueError(f"hash ou tamanho diverge do manifesto em {path.name}")
            array = np.load(path, mmap_mode="r", allow_pickle=False)
            if list(array.shape) != expected["shape"] or str(array.dtype) != expected["dtype"]:
                raise ValueError(f"tipo ou formato diverge do manifesto em {path.name}")
            arrays[key] = array
        records = info["records"]
        if (
            arrays["X"].shape != (records, len(manifest["inputs"]))
            or arrays["y"].shape != (records,)
            or arrays["origin"].shape != (records, 3)
        ):
            raise ValueError(f"dimensões incompatíveis no conjunto {name}")
        if not np.isfinite(arrays["X"]).all() or not np.isin(arrays["y"], [0, 1]).all():
            raise ValueError(f"entradas não finitas ou rótulos inválidos no conjunto {name}")
        if set(np.unique(arrays["y"]).tolist()) != {0, 1}:
            raise ValueError(f"as duas classes devem estar presentes em {name}")
        return TrainingSplit(inputs=arrays["X"], labels=arrays["y"], origin=arrays["origin"])

    def verify_inputs_unchanged(self, dataset: PilotDataset) -> None:
        if sha256(self.data_dir / "manifest.json") != dataset.manifest_sha256:
            raise InvalidTrainingDataError("O manifesto mudou durante o treinamento.")
        for name in ("train", "validation"):
            for artifact in dataset.manifest["splits"][name]["files"].values():
                if sha256(self.data_dir / artifact["file"]) != artifact["sha256"]:
                    raise InvalidTrainingDataError(f"O arquivo {artifact['file']} mudou.")

    def create_run(self, kind: str = "random-forest-pilot") -> Path:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        run_dir = self.runs_dir / kind / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        return run_dir

    def save_model(self, run_dir: Path, model: Any, inputs: list[str]) -> dict[str, Any]:
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / "model.joblib"
        joblib.dump({"estimator": model, "inputs": inputs, "classes": {"benign": 0, "attack": 1}}, path)
        return artifact_info(path)

    def save_array(self, run_dir: Path, name: str, values: np.ndarray) -> dict[str, Any]:
        path = run_dir / f"{name}.npy"
        np.save(path, values, allow_pickle=False)
        return {**artifact_info(path), "shape": list(values.shape), "dtype": str(values.dtype)}

    def write_reports(self, run_dir: Path, summary: dict[str, Any]) -> Path:
        (run_dir / "report.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        path = self.reports_dir / f"random-forest-pilot-{run_dir.name}.md"
        path.write_text(render_pilot_report(summary), encoding="utf-8")
        return path

    def read_comparison_config(self, path: Path) -> ForestComparisonConfig:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if set(data) != {"reference_run", "selection_metric", "alternatives"}:
                raise ValueError("campos inesperados na configuração da comparação")
            if data["selection_metric"] != "f1":
                raise ValueError("o critério de seleção desta comparação é F1")
            alternatives = []
            names = {"reference", "final"}
            for entry in data["alternatives"]:
                name, overrides = entry["name"], entry["overrides"]
                if not name or name in names or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in name):
                    raise ValueError("nome de alternativa inválido ou repetido")
                if not overrides or not set(overrides) <= {"n_estimators", "max_depth"}:
                    raise ValueError("somente número de árvores e profundidade podem variar")
                if any(type(value) is not int or value <= 0 for value in overrides.values()):
                    raise ValueError("os valores das alternativas devem ser inteiros positivos")
                alternatives.append(ForestAlternative(name, overrides))
                names.add(name)
            if len(alternatives) != 2:
                raise ValueError("a comparação deve ter exatamente duas alternativas")
            return ForestComparisonConfig(
                reference_run=path.parent.parent / data["reference_run"],
                alternatives=tuple(alternatives),
            )
        except (OSError, KeyError, TypeError, ValueError) as error:
            raise InvalidPilotConfigError(f"Configuração da comparação inválida: {error}") from error

    def load_reference(self, run_dir: Path, dataset: PilotDataset) -> ReferenceRun:
        try:
            report_path = run_dir / "report.json"
            summary = json.loads(report_path.read_text(encoding="utf-8"))
            if summary["data_manifest_sha256"] != dataset.manifest_sha256:
                raise ValueError("o piloto usa outro manifesto de dados")
            if summary["inputs"] != dataset.manifest["inputs"] or summary["test_used"]:
                raise ValueError("atributos incompatíveis ou teste já usado no piloto")
            for info in summary["artifacts"].values():
                path = run_dir / info["file"]
                if path.stat().st_size != info["bytes"] or sha256(path) != info["sha256"]:
                    raise ValueError(f"artefato do piloto foi alterado: {path.name}")
            indices = np.load(run_dir / "sample_indices.npy", allow_pickle=False)
            if (indices.ndim != 1 or indices.dtype != np.int64 or len(np.unique(indices)) != len(indices)
                    or (indices < 0).any() or (indices >= len(dataset.train.labels)).any()):
                raise ValueError("índices da amostra inválidos")
            origin = np.load(run_dir / "sample_origin.npy", allow_pickle=False)
            if not np.array_equal(origin, dataset.train.origin[indices]):
                raise ValueError("a origem da amostra diverge do treino")
            return ReferenceRun(summary, sha256(report_path), indices)
        except (OSError, KeyError, TypeError, ValueError) as error:
            raise InvalidTrainingDataError(f"Execução de referência inválida: {error}") from error

    def write_record(self, run_dir: Path, name: str, record: dict[str, Any]) -> Path:
        path = run_dir / f"{name}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        return path

    def load_reserved_test(self, run_dir: Path, dataset: PilotDataset) -> TrainingSplit:
        """Abre o teste somente depois de gravados a seleção e o modelo final fixo."""
        try:
            selection = json.loads((run_dir / "selection.json").read_text(encoding="utf-8"))
            frozen = json.loads((run_dir / "fixed-before-test.json").read_text(encoding="utf-8"))
            if selection["model"] != frozen["model"] or frozen["data_manifest_sha256"] != dataset.manifest_sha256:
                raise ValueError("o modelo fixo diverge da seleção ou dos dados")
            if sha256(run_dir / "final" / "model.joblib") != frozen["artifact"]["sha256"]:
                raise ValueError("o modelo final mudou depois de ser fixado")
            if sha256(self.data_dir / "manifest.json") != dataset.manifest_sha256:
                raise ValueError("o manifesto de dados mudou")
            return self._read_verified_split("test", dataset.manifest)
        except (OSError, KeyError, TypeError, ValueError) as error:
            raise InvalidTrainingDataError(f"Teste reservado não liberado: {error}") from error

    def verify_test_unchanged(self, dataset: PilotDataset) -> None:
        for info in dataset.manifest["splits"]["test"]["files"].values():
            if sha256(self.data_dir / info["file"]) != info["sha256"]:
                raise InvalidTrainingDataError(f"O arquivo de teste {info['file']} mudou.")

    def write_comparison_reports(self, run_dir: Path, summary: dict[str, Any]) -> Path:
        self.write_record(run_dir, "report", summary)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        path = self.reports_dir / f"random-forest-comparison-{run_dir.name}.md"
        path.write_text(render_forest_comparison_report(summary), encoding="utf-8")
        return path

    def environment(self) -> dict[str, Any]:
        cpu = platform.processor()
        cpuinfo = Path("/proc/cpuinfo")
        if cpuinfo.is_file():
            cpu = next(
                (line.split(":", 1)[1].strip() for line in cpuinfo.read_text().splitlines()
                 if line.startswith("model name")), cpu
            )
        return {
            "python": platform.python_version(),
            "libraries": {name: version(name) for name in ("numpy", "scikit-learn", "scipy", "joblib")},
            "platform": platform.platform(),
            "cpu": cpu,
            "logical_cpus": os.cpu_count(),
        }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def artifact_info(path: Path) -> dict[str, Any]:
    return {"file": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}
