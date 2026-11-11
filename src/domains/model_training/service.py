import resource
import sys
import time

import numpy as np

from core.classification import RandomForestAdapter, binary_metrics
from domains.model_training.exceptions import InvalidPilotConfigError
from domains.model_training.repository import ModelTrainingRepository
from domains.model_training.schemas import PilotConfig, PilotResult


def sample_training_indices(original_labels: np.ndarray, size: int, seed: int) -> np.ndarray:
    """Seleciona sem reposição, proporcionalmente aos rótulos, com pelo menos um de cada."""
    labels, counts = np.unique(original_labels, return_counts=True)
    if not len(labels) <= size <= len(original_labels):
        raise InvalidPilotConfigError(
            f"A amostra deve ter entre {len(labels)} e {len(original_labels)} registros."
        )
    if size == len(original_labels):
        return np.arange(size, dtype=np.int64)

    capacity = counts - 1
    remaining = size - len(labels)
    quotas = remaining * capacity / capacity.sum()
    allocated = np.floor(quotas).astype(np.int64)
    remainder = remaining - int(allocated.sum())
    order = np.argsort(-(quotas - allocated), kind="stable")
    allocated[order[:remainder]] += 1
    allocated += 1

    rng = np.random.default_rng(seed)
    chosen = [
        rng.choice(np.flatnonzero(original_labels == label), size=int(count), replace=False)
        for label, count in zip(labels, allocated, strict=True)
    ]
    return np.sort(np.concatenate(chosen))


def peak_memory_mib() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 * 1024 if sys.platform == "darwin" else 1024)


class ModelTrainingService:
    def __init__(self, repo: ModelTrainingRepository, config: PilotConfig, model: RandomForestAdapter) -> None:
        self.repo = repo
        self.config = config
        self.model = model

    def run_pilot(self) -> PilotResult:
        started = time.perf_counter()
        dataset = self.repo.load_pilot_dataset()
        manifest = dataset.manifest
        selected = sample_training_indices(
            dataset.train.origin[:, 2], self.config.sample_size, self.config.sample_seed
        )
        sample_inputs = dataset.train.inputs[selected]
        sample_labels = dataset.train.labels[selected]

        fit_started = time.perf_counter()
        self.model.fit(sample_inputs, sample_labels)
        fit_seconds = time.perf_counter() - fit_started

        validation_started = time.perf_counter()
        predictions, probabilities = self.model.predict(dataset.validation.inputs)
        metrics = binary_metrics(dataset.validation.labels, predictions, probabilities)
        validation_seconds = time.perf_counter() - validation_started

        sample_label_counts = {}
        validation_by_label = {}
        for entry in manifest["original_labels"]:
            index, label = entry["index"], entry["label"]
            sample_label_counts[label] = int((dataset.train.origin[selected, 2] == index).sum())
            mask = dataset.validation.origin[:, 2] == index
            validation_by_label[label] = {
                "records": int(mask.sum()),
                "class": entry["class"],
                "predicted_attack": int(predictions[mask].sum()),
            }

        self.repo.verify_inputs_unchanged(dataset)
        run_dir = self.repo.create_run()
        artifacts = {
            "model": self.repo.save_model(run_dir, self.model.estimator, manifest["inputs"]),
            "sample_indices": self.repo.save_array(run_dir, "sample_indices", selected),
            "sample_origin": self.repo.save_array(run_dir, "sample_origin", dataset.train.origin[selected]),
            "validation_predictions": self.repo.save_array(run_dir, "validation_predictions", predictions),
            "validation_attack_probability": self.repo.save_array(
                run_dir, "validation_attack_probability", probabilities
            ),
        }
        summary = {
            "stage": "pilot",
            "run_id": run_dir.name,
            "configuration": {
                "sample_size": self.config.sample_size,
                "sample_seed": self.config.sample_seed,
                "model": self.model.parameters(),
            },
            "data_manifest_sha256": dataset.manifest_sha256,
            "data_files": {name: manifest["splits"][name]["files"] for name in ("train", "validation")},
            "inputs": manifest["inputs"],
            "classes": manifest["classes"],
            "origin_columns": manifest["origin_columns"],
            "source_files": [entry["file"] for entry in manifest["sources"]],
            "original_label_indices": {entry["label"]: entry["index"] for entry in manifest["original_labels"]},
            "sample": {
                "source_split": "train",
                "without_replacement": True,
                "stratification": "original labels; at least one record per label",
                "records": len(selected),
                "benign": int((sample_labels == 0).sum()),
                "attack": int((sample_labels == 1).sum()),
                "original_labels": sample_label_counts,
            },
            "validation": {
                "records": len(predictions),
                "metrics": metrics,
                "by_original_label": validation_by_label,
            },
            "test_used": False,
            "classification_rule": "attack if P(attack) > 0.5; benign otherwise",
            "complexity": self.model.complexity(),
            "artifacts": artifacts,
            "environment": self.repo.environment(),
            "resources": {
                "fit_seconds": fit_seconds,
                "validation_seconds": validation_seconds,
                "peak_process_memory_mib": peak_memory_mib(),
                "elapsed_seconds": time.perf_counter() - started,
            },
        }
        report_path = self.repo.write_reports(run_dir, summary)
        return PilotResult(run_dir=run_dir, report_path=report_path, summary=summary)
