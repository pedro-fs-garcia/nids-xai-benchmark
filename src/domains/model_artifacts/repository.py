"""Persistência dos modelos congelados e de suas referências de verificação."""

import json
import platform
import shutil
from importlib.metadata import version
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from domains.model_artifacts.schemas import LoadedModel
from domains.model_artifacts.exceptions import ModelArtifactError
from domains.model_training.repository import ModelTrainingRepository, artifact_info, sha256


class ModelArtifactRepository:
    def __init__(self, root: Path, data_dir: Path, runs_dir: Path) -> None:
        self.root = root
        self.data_dir = data_dir
        self.runs_dir = runs_dir

    def read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def write_json(self, path: Path, value: dict[str, Any]) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    def manifest_hash(self, path: Path) -> str:
        return sha256(path / "manifest.json")

    def create_run(self) -> Path:
        from datetime import datetime, timezone

        path = self.runs_dir / "frozen-models" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path.mkdir(parents=True, exist_ok=False)
        return path

    def checked_file(self, directory: Path, info: dict[str, Any]) -> Path:
        if Path(info["file"]).name != info["file"]:
            raise ValueError("Nome de artefato inválido.")
        path = directory / info["file"]
        if path.stat().st_size != info["bytes"] or sha256(path) != info["sha256"]:
            raise ValueError(f"Hash ou tamanho divergente em {path}.")
        return path

    def prepare_bundle(self, source: Path, target: Path, name: str) -> None:
        report = self.read_json(source / "report.json")
        fixed = self.read_json(source / "fixed-before-test.json")
        selection = self.read_json(source / "selection.json")
        data = self.read_json(self.data_dir / "manifest.json")
        data_hash = sha256(self.data_dir / "manifest.json")
        if not (data_hash == report["data_manifest_sha256"] == fixed["data_manifest_sha256"]):
            raise ValueError("Os manifestos de treinamento e de dados divergem.")
        if not (selection["model"] == fixed["model"] == report["final"]["parameters"]):
            raise ValueError("Os parâmetros finais divergem da seleção.")
        if not (data["inputs"] == report["inputs"] == fixed["inputs"]):
            raise ValueError("A ordem dos atributos diverge entre os registros.")
        if fixed["artifact"]["sha256"] != report["final"]["model"]["sha256"]:
            raise ValueError("O modelo diverge do artefato fixado antes do teste.")
        if not report["test_used_only_after_selection_and_full_training"] or fixed["test_used"]:
            raise ValueError("O registro não confirma a seleção anterior ao teste.")
        target.mkdir(exist_ok=False)
        model = report["final"]["model"]
        files = {}
        for key, info in [("model", model), *[(k, model[k]) for k in ("native", "effective_configuration") if k in model]]:
            original = self.checked_file(source / "final", info)
            destination = target / original.name
            shutil.copyfile(original, destination)
            files[key] = artifact_info(destination)
        for key in ("predictions", "probabilities"):
            info = report["final"]["test"][key]
            original = self.checked_file(source / "final", info)
            destination = target / original.name
            shutil.copyfile(original, destination)
            files[key] = {**info, **artifact_info(destination)}
        for key, original in {
            "training_report": source / "report.json",
            "selection": source / "selection.json",
            "fixed_before_test": source / "fixed-before-test.json",
            "data_manifest": self.data_dir / "manifest.json",
            "requirements": self.root / "src" / "requirements.txt",
        }.items():
            destination = target / ("data-manifest.json" if key == "data_manifest" else original.name)
            shutil.copyfile(original, destination)
            files[key] = artifact_info(destination)
        configuration = data["configuration"]
        self.write_json(target / "manifest.json", {
            "format_version": 1, "name": name, "source_run": str(source.relative_to(self.root)),
            "inputs": data["inputs"], "classes": data["classes"],
            "parameters": report["final"]["parameters"],
            "data_manifest_sha256": data_hash, "environment": report["environment"],
            "preprocessing": {
                "dtype": "float64", "normalization": "none",
                "positive_infinity_columns": configuration["infinite_rate_columns"],
                "positive_infinity_replacement": configuration["infinite_rate_replacement"],
                "reject_other_nonfinite": True,
                "columns_outside_inputs": data["columns_outside_inputs"],
            },
            "classification": {"attack_threshold": 0.5, "comparison": ">", "tie_class": 0},
            "verification": {"split": "test", "probability_atol": 1e-12, "probability_rtol": 0},
            "files": files,
        })

    def load(self, path: Path) -> LoadedModel:
        manifest = self.read_json(path / "manifest.json")
        if manifest["format_version"] != 1:
            raise ValueError("Versão de artefato não suportada.")
        expected = manifest["environment"]
        if platform.python_version() != expected["python"]:
            raise ValueError("A versão do Python diverge do treinamento.")
        for library, required in expected["libraries"].items():
            if version(library) != required:
                raise ValueError(f"Versão incompatível de {library}; esperada {required}.")
        for info in manifest["files"].values():
            self.checked_file(path, info)
        for line in (path / manifest["files"]["requirements"]["file"]).read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                library, required = line.split("==")
                if version(library) != required:
                    raise ModelArtifactError(f"Versão incompatível de {library}; esperada {required}.")
        data = self.read_json(path / "data-manifest.json")
        report = self.read_json(path / "report.json")
        expected_preprocessing = {
            "dtype": "float64", "normalization": "none",
            "positive_infinity_columns": data["configuration"]["infinite_rate_columns"],
            "positive_infinity_replacement": data["configuration"]["infinite_rate_replacement"],
            "reject_other_nonfinite": True, "columns_outside_inputs": data["columns_outside_inputs"],
        }
        if (manifest["preprocessing"] != expected_preprocessing
                or manifest["inputs"] != data["inputs"]
                or manifest["classes"] != {"benign": 0, "attack": 1}
                or manifest["parameters"] != report["final"]["parameters"]
                or manifest["environment"] != report["environment"]
                or manifest["data_manifest_sha256"] != sha256(path / "data-manifest.json")
                or manifest["classification"] != {"attack_threshold": 0.5, "comparison": ">", "tie_class": 0}
                or manifest["verification"] != {"split": "test", "probability_atol": 1e-12, "probability_rtol": 0}):
            raise ModelArtifactError("O contrato do artefato diverge dos registros de treinamento.")
        bundle = joblib.load(path / manifest["files"]["model"]["file"])
        if bundle["inputs"] != manifest["inputs"] or bundle["classes"] != manifest["classes"]:
            raise ValueError("O contrato de entrada diverge do modelo salvo.")
        if bundle["estimator"].n_features_in_ != len(manifest["inputs"]):
            raise ValueError("Número de atributos incompatível com o modelo.")
        actual_parameters = bundle["estimator"].get_params(deep=False)
        if any(actual_parameters.get(key) != value for key, value in manifest["parameters"].items()):
            raise ModelArtifactError("Os parâmetros do modelo divergem do manifesto.")
        return LoadedModel(manifest, bundle["estimator"])

    def verification_arrays(self, path: Path, manifest: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        data = self.read_json(path / "data-manifest.json")
        arrays = []
        for key in ("X", "origin"):
            info = data["splits"]["test"]["files"][key]
            source = self.checked_file(self.data_dir, info)
            array = np.load(source, mmap_mode="r", allow_pickle=False)
            if list(array.shape) != info["shape"] or str(array.dtype) != info["dtype"]:
                raise ValueError("Formato dos dados de verificação incompatível.")
            arrays.append(array)
        for key in ("predictions", "probabilities"):
            source = self.checked_file(path, manifest["files"][key])
            arrays.append(np.load(source, allow_pickle=False))
        return arrays[0], arrays[1], arrays[2], arrays[3]

    def environment(self) -> dict[str, Any]:
        return ModelTrainingRepository(self.data_dir, self.runs_dir, self.root / "relatorios").environment()
