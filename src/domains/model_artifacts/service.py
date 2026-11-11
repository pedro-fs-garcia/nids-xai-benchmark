"""Congelamento e reprodução das previsões de classificadores selecionados."""

import os
from pathlib import Path
from typing import Any

import numpy as np

from core.frozen_prediction import FrozenPredictor
from core.process_runner import PythonProcessRunner
from domains.model_artifacts.repository import ModelArtifactRepository
from domains.model_artifacts.schemas import FreezeResult


def prepare_flow(flow: dict[str, Any], manifest: dict[str, Any]) -> np.ndarray:
    names = manifest["inputs"]
    if set(flow) != set(names):
        missing, extra = sorted(set(names) - set(flow)), sorted(set(flow) - set(names))
        raise ValueError(f"Atributos ausentes: {missing}; atributos adicionais: {extra}.")
    rules = manifest["preprocessing"]
    values = []
    for name in names:
        value = flow[name]
        if value == "inf" and name in rules["positive_infinity_columns"]:
            value = float("inf")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Valor não numérico em {name}.")
        if np.isposinf(value) and name in rules["positive_infinity_columns"]:
            value = rules["positive_infinity_replacement"]
        if not np.isfinite(value):
            raise ValueError(f"Valor não finito em {name}.")
        values.append(value)
    return np.asarray([values], dtype=np.float64)


class ModelArtifactService:
    def __init__(self, repo: ModelArtifactRepository, runner: PythonProcessRunner) -> None:
        self.repo = repo
        self.runner = runner

    def freeze(self, config_path: Path) -> FreezeResult:
        config = self.repo.read_json(config_path)
        if set(config["models"]) != {"random-forest", "xgboost"}:
            raise ValueError("A configuração deve identificar Random Forest e XGBoost.")
        run_dir = self.repo.create_run()
        results = {}
        for name, reference in config["models"].items():
            target = run_dir / name
            self.repo.prepare_bundle(self.repo.root / reference, target, name)
            verification = self.runner.run([
                "verificar-modelo", "--artifact", str(target),
                "--data-dir", str(self.repo.data_dir),
            ])
            if verification["pid"] == os.getpid() or verification["passed"] is not True:
                raise ValueError("A verificação deve ocorrer com sucesso em um processo novo.")
            self.repo.write_json(target / "verification.json", verification)
            results[name] = verification
        self.repo.write_json(run_dir / "report.json", {
            "passed": True, "parent_pid": os.getpid(), "models": results,
        })
        return FreezeResult(run_dir, results)

    def verify(self, path: Path) -> dict[str, Any]:
        loaded = self.repo.load(path)
        predictor = FrozenPredictor(loaded.estimator)
        inputs, origin, expected, expected_probability = self.repo.verification_arrays(path, loaded.manifest)
        predictions, probability = predictor.predict(inputs)
        if expected.shape != predictions.shape or expected_probability.shape != probability.shape:
            raise ValueError("Formato das previsões de referência incompatível.")
        differences = int(np.count_nonzero(predictions != expected))
        delta = float(np.max(np.abs(probability - expected_probability)))
        if differences or not np.allclose(probability, expected_probability, atol=1e-12, rtol=0):
            raise ValueError(f"Previsões divergentes: {differences}; diferença máxima de probabilidade: {delta}.")
        flow = dict(zip(loaded.manifest["inputs"], inputs[0].tolist()))
        single_prediction, single_probability = predictor.predict(prepare_flow(flow, loaded.manifest))
        if single_prediction[0] != expected[0] or abs(float(single_probability[0]) - float(expected_probability[0])) > 1e-12:
            raise ValueError("A inferência de um fluxo diverge da previsão de referência.")
        self.repo.write_json(path / "example-flow.json", flow)
        return {
            "passed": True, "pid": os.getpid(), "manifest_sha256": self.repo.manifest_hash(path),
            "records": len(predictions), "prediction_mismatches": differences,
            "probabilities_bitwise_equal": bool(np.array_equal(probability, expected_probability)),
            "max_probability_absolute_difference": delta, "probability_atol": 1e-12, "probability_rtol": 0,
            "model_sha256": loaded.manifest["files"]["model"]["sha256"],
            "single_flow": {"test_index": 0, "origin": origin[0].tolist(),
                            "prediction": int(single_prediction[0]), "attack_probability": float(single_probability[0])},
            "environment": self.repo.environment(),
        }

    def predict_flow(self, path: Path, flow_path: Path) -> dict[str, Any]:
        loaded = self.repo.load(path)
        flow = self.repo.read_json(flow_path)
        predictions, probabilities = FrozenPredictor(loaded.estimator).predict(prepare_flow(flow, loaded.manifest))
        return {"prediction": int(predictions[0]), "class": "attack" if predictions[0] else "benign",
                "attack_probability": float(probabilities[0])}
