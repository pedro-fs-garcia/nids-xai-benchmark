"""Treinamento completo e acesso ao teste após fixação das escolhas."""

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from core.classification import binary_metrics
from domains.model_training.repository import ModelTrainingRepository
from domains.model_training.schemas import PilotDataset, TrainingSplit


def by_original_label(
    split: TrainingSplit, predictions: np.ndarray, original_labels: list[dict[str, Any]]
) -> dict[str, Any]:
    result = {}
    for entry in original_labels:
        mask = split.origin[:, 2] == entry["index"]
        result[entry["label"]] = {
            "records": int(mask.sum()),
            "class": entry["class"],
            "predicted_attack": int(predictions[mask].sum()),
        }
    return result


def fit_and_evaluate(
    repo: ModelTrainingRepository, dataset: PilotDataset, model: Any,
    run_dir: Path, progress: Callable[[str], None],
) -> dict[str, Any]:
    manifest = dataset.manifest
    started = time.perf_counter()
    model.fit(dataset.train.inputs, dataset.train.labels)
    fit_seconds = time.perf_counter() - started
    final_dir = run_dir / "final"
    artifact = repo.save_model(final_dir, model.estimator, manifest["inputs"])
    validation_predictions, validation_probability = model.predict(dataset.validation.inputs)
    validation_metrics = binary_metrics(dataset.validation.labels, validation_predictions, validation_probability)
    repo.save_array(final_dir, "validation_predictions", validation_predictions)
    repo.save_array(final_dir, "validation_attack_probability", validation_probability)
    repo.verify_inputs_unchanged(dataset)
    repo.write_record(run_dir, "fixed-before-test", {
        "model": model.parameters(), "inputs": manifest["inputs"],
        "data_manifest_sha256": dataset.manifest_sha256, "artifact": artifact,
        "classification_rule": "attack if P(attack) > 0.5; benign otherwise",
        "environment": repo.environment(), "test_used": False,
    })
    progress("Modelo final salvo e parâmetros fixados. Avaliando no teste reservado...")
    test = repo.load_reserved_test(run_dir, dataset)
    predictions, probabilities = model.predict(test.inputs)
    metrics = binary_metrics(test.labels, predictions, probabilities)
    prediction_artifact = repo.save_array(final_dir, "test_predictions", predictions)
    probability_artifact = repo.save_array(final_dir, "test_attack_probability", probabilities)
    repo.verify_test_unchanged(dataset)
    return {
        "parameters": model.parameters(), "training_records": len(dataset.train.labels),
        "fit_seconds": fit_seconds, "complexity": model.complexity(), "model": artifact,
        "validation": {
            "records": len(dataset.validation.labels), "metrics": validation_metrics,
            "by_original_label": by_original_label(dataset.validation, validation_predictions, manifest["original_labels"]),
        },
        "test": {
            "records": len(test.labels), "metrics": metrics,
            "benign": int((test.labels == 0).sum()), "attack": int((test.labels == 1).sum()),
            "by_original_label": by_original_label(test, predictions, manifest["original_labels"]),
            "predictions": prediction_artifact, "probabilities": probability_artifact,
        },
    }
