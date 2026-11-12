"""Leitura dos dados e modelos verificados e gravação das execuções do TreeSHAP."""

import hashlib
import json
import os
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from domains.explanations.exceptions import ExplanationError
from domains.explanations.schemas import (
    EXPLAINER, MODELS, MeasurementConfig, PilotModel, SampleConfig, SplitData, TreeShapConfig,
)
from domains.model_artifacts.repository import ModelArtifactRepository
from domains.model_artifacts.schemas import LoadedModel
from domains.model_training.repository import ModelTrainingRepository, artifact_info, sha256

_LIBRARIES = ("shap", "matplotlib", "threadpoolctl", "pandas")
_REQUIRED_DATA_CHECKS = (
    "every_record_in_exactly_one_split",
    "no_input_vector_in_more_than_one_split",
    "every_original_label_in_every_split",
    "all_values_finite",
    "sources_unchanged",
)


class ExplanationRepository:
    def __init__(self, root: Path, data_dir: Path, runs_dir: Path, reports_dir: Path) -> None:
        self.root = root
        self.data_dir = data_dir
        self.runs_dir = runs_dir
        self.reports_dir = reports_dir

    def read_config(self, path: Path) -> TreeShapConfig:
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
            _expect_keys(content, {"explainer", "pilot_run", "frozen_run", "example", "validation_sample",
                                   "tolerances", "measurement"}, "configuração")
            if content["explainer"] != EXPLAINER:
                raise ValueError(f"explainer deve ser {EXPLAINER}")
            example = content["example"]
            _expect_keys(example, {"original_label", "predicted_class"}, "example")
            if example["predicted_class"] not in (0, 1):
                raise ValueError("predicted_class deve ser 0 ou 1")
            sample = content["validation_sample"]
            _expect_keys(sample, {"size", "seed", "minimum_per_label"}, "validation_sample")
            tolerances = content["tolerances"]
            _expect_keys(tolerances, set(MODELS), "tolerances")
            _expect_keys(tolerances["random-forest"], {"sum_identity"}, "tolerances.random-forest")
            _expect_keys(tolerances["xgboost"], {"sum_identity", "reference_value"}, "tolerances.xgboost")
            if not all(isinstance(value, float) and value > 0
                       for model in tolerances.values() for value in model.values()):
                raise ValueError("as tolerâncias devem ser números positivos")
            measurement = content["measurement"]
            _expect_keys(measurement, {"flows", "batch_sizes", "processes", "passes", "cpu", "threads",
                                       "require_mains_power"}, "measurement")
            integers = [sample["size"], sample["seed"], sample["minimum_per_label"], measurement["flows"],
                        measurement["processes"], measurement["passes"], measurement["cpu"],
                        measurement["threads"], *measurement["batch_sizes"]]
            if not all(type(value) is int and value >= 0 for value in integers):
                raise ValueError("tamanhos, sementes, repetições e CPU devem ser inteiros não negativos")
            if measurement["threads"] != 1:
                raise ValueError("a medição usa uma thread")
            if measurement["flows"] > sample["size"]:
                raise ValueError("os fluxos medidos devem pertencer à amostra de validação")
            if any(size <= 0 or measurement["flows"] % size for size in measurement["batch_sizes"]):
                raise ValueError("cada tamanho de lote deve dividir o número de fluxos medidos")
            return TreeShapConfig(
                path=path, sha256=sha256(path), content=content,
                pilot_run=self.root / content["pilot_run"], frozen_run=self.root / content["frozen_run"],
                example_label=example["original_label"], example_class=example["predicted_class"],
                sample=SampleConfig(**sample), tolerances=tolerances,
                measurement=MeasurementConfig(**{**measurement, "batch_sizes": tuple(measurement["batch_sizes"])}),
            )
        except (OSError, KeyError, ValueError, TypeError) as error:
            raise ExplanationError(f"Configuração inválida em {path}: {error}") from error

    def load_split(self, name: str) -> SplitData:
        # As explicações só usam a validação. O teste fica reservado à avaliação final.
        if name != "validation":
            raise ExplanationError(f"Conjunto não permitido nas explicações: {name}")
        try:
            raw = (self.data_dir / "manifest.json").read_bytes()
            manifest = json.loads(raw)
            if not all(manifest["verifications"].get(check) is True for check in _REQUIRED_DATA_CHECKS):
                raise ValueError("as verificações da preparação dos dados devem estar aprovadas")
            arrays = {}
            for key in ("X", "y", "origin"):
                info = manifest["splits"][name]["files"][key]
                path = self.data_dir / info["file"]
                if path.name != f"{key}_{name}.npy":
                    raise ValueError(f"arquivo inesperado para {key}")
                if path.stat().st_size != info["bytes"] or sha256(path) != info["sha256"]:
                    raise ValueError(f"hash ou tamanho diverge do manifesto em {path.name}")
                array = np.load(path, mmap_mode="r", allow_pickle=False)
                if list(array.shape) != info["shape"] or str(array.dtype) != info["dtype"]:
                    raise ValueError(f"tipo ou formato diverge do manifesto em {path.name}")
                arrays[key] = array
            return SplitData(name, manifest, _sha256_bytes(raw), arrays["X"], arrays["y"], arrays["origin"])
        except (OSError, KeyError, ValueError, TypeError) as error:
            raise ExplanationError(f"Dados derivados inválidos: {error}") from error

    def load_pilot(self, run_dir: Path, data: SplitData) -> PilotModel:
        report = self.read_json(run_dir / "report.json")
        if report["test_used"] is not False or report["data_manifest_sha256"] != data.manifest_sha256:
            raise ExplanationError("O piloto deve usar os dados atuais e não ter aberto o teste.")
        for library, required in report["environment"]["libraries"].items():
            if version(library) != required:
                raise ExplanationError(f"Versão incompatível de {library}; o piloto usou {required}.")
        artifacts = report["artifacts"]
        bundle = joblib.load(self._checked(run_dir, artifacts["model"]))
        if bundle["inputs"] != data.manifest["inputs"] or bundle["classes"] != {"benign": 0, "attack": 1}:
            raise ExplanationError("O contrato de entrada do piloto diverge dos dados.")
        arrays = [np.load(self._checked(run_dir, artifacts[key]), allow_pickle=False)
                  for key in ("validation_predictions", "validation_attack_probability")]
        if any(array.shape != data.labels.shape for array in arrays):
            raise ExplanationError("As previsões salvas do piloto não cobrem a validação.")
        return PilotModel(bundle["estimator"], report, arrays[0], arrays[1])

    def load_frozen(self, run_dir: Path, name: str, data: SplitData) -> LoadedModel:
        path = run_dir / name
        if sha256(path / "data-manifest.json") != data.manifest_sha256:
            raise ExplanationError(f"O modelo congelado {name} foi treinado com outro manifesto de dados.")
        loaded = ModelArtifactRepository(self.root, self.data_dir, self.runs_dir).load(path)
        if loaded.manifest["inputs"] != data.manifest["inputs"]:
            raise ExplanationError(f"A ordem dos atributos de {name} diverge dos dados.")
        return loaded

    def frozen_manifest_hash(self, run_dir: Path, name: str) -> str:
        return sha256(run_dir / name / "manifest.json")

    def create_run(self, kind: str) -> Path:
        path = self.runs_dir / "tree-shap" / kind / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path.mkdir(parents=True, exist_ok=False)
        return path

    def read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def write_json(self, path: Path, value: dict[str, Any]) -> dict[str, Any]:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        return artifact_info(path)

    def save_array(self, run_dir: Path, name: str, values: np.ndarray) -> dict[str, Any]:
        path = run_dir / f"{name}.npy"
        np.save(path, values, allow_pickle=False)
        return {**artifact_info(path), "shape": list(values.shape), "dtype": str(values.dtype)}

    def load_array(self, run_dir: Path, info: dict[str, Any]) -> np.ndarray:
        array = np.load(self._checked(run_dir, info), allow_pickle=False)
        if list(array.shape) != info["shape"] or str(array.dtype) != info["dtype"]:
            raise ExplanationError(f"Tipo ou formato diverge do registro em {info['file']}.")
        return array

    def report_path(self, name: str) -> Path:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        return self.reports_dir / name

    def write_report(self, name: str, text: str) -> Path:
        path = self.report_path(name)
        path.write_text(text, encoding="utf-8")
        return path

    def relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root.resolve()).as_posix()

    def environment(self) -> dict[str, Any]:
        environment = ModelTrainingRepository(self.data_dir, self.runs_dir, self.reports_dir).environment()
        environment["libraries"].update({name: version(name) for name in _LIBRARIES})
        return environment

    def cpu_state(self) -> dict[str, Any]:
        cpus = sorted(os.sched_getaffinity(0))
        governors = {}
        for cpu in cpus:
            path = Path(f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor")
            governors[str(cpu)] = path.read_text().strip() if path.is_file() else None
        return {"affinity": cpus, "scaling_governor": governors, "mains_power_online": _mains_power()}

    def _checked(self, directory: Path, info: dict[str, Any]) -> Path:
        if Path(info["file"]).name != info["file"]:
            raise ExplanationError("Nome de artefato inválido.")
        path = directory / info["file"]
        if path.stat().st_size != info["bytes"] or sha256(path) != info["sha256"]:
            raise ExplanationError(f"Hash ou tamanho divergente em {path}.")
        return path


def _expect_keys(value: dict[str, Any], keys: set[str], name: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{name} deve ter exatamente os campos {sorted(keys)}")


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _mains_power() -> bool | None:
    supplies = [path for path in Path("/sys/class/power_supply").glob("*")
                if (path / "type").is_file() and (path / "type").read_text().strip() == "Mains"]
    if not supplies:
        return None
    return any((path / "online").read_text().strip() == "1" for path in supplies)
