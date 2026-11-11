"""Comparação curta na amostra, seguida de treinamento completo e avaliação final."""

import time
from collections.abc import Callable
from typing import Any

import numpy as np

from core.classification import RandomForestAdapter, binary_metrics
from domains.model_training.repository import ModelTrainingRepository
from domains.model_training.schemas import ForestComparisonConfig, PilotResult, TrainingSplit
from domains.model_training.service import peak_memory_mib


def select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Escolhe maior F1; empates favorecem menos nós e depois menos árvores."""
    return max(candidates, key=lambda entry: (
        entry["metrics"]["f1"], -entry["complexity"]["nodes_total"], -entry["complexity"]["trees"],
    ))


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


class ForestComparisonService:
    def __init__(
        self, repo: ModelTrainingRepository, config: ForestComparisonConfig,
        model_factory: Callable[[dict[str, Any]], RandomForestAdapter],
    ) -> None:
        self.repo, self.config, self.model_factory = repo, config, model_factory

    def run(self, progress: Callable[[str], None] | None = None) -> PilotResult:
        started = time.perf_counter()
        emit = progress or (lambda _message: None)
        dataset = self.repo.load_pilot_dataset()
        manifest = dataset.manifest
        reference = self.repo.load_reference(self.config.reference_run, dataset)
        original = reference.summary
        sample_indices = reference.sample_indices
        sample_inputs = dataset.train.inputs[sample_indices]
        sample_labels = dataset.train.labels[sample_indices]
        run_dir = self.repo.create_run("random-forest-comparison")
        self.repo.save_array(run_dir, "sample_indices", sample_indices)
        self.repo.save_array(run_dir, "sample_origin", dataset.train.origin[sample_indices])
        candidates = [{
            "name": "reference",
            "parameters": original["configuration"]["model"],
            "metrics": original["validation"]["metrics"],
            "by_original_label": original["validation"]["by_original_label"],
            "complexity": original["complexity"],
            "fit_seconds": original["resources"]["fit_seconds"],
            "reused": True,
        }]
        for alternative in self.config.alternatives:
            parameters = {**original["configuration"]["model"], **alternative.overrides}
            model = self.model_factory(parameters)
            emit(f"Treinando alternativa {alternative.name} na mesma amostra de {len(sample_indices)} registros...")
            fit_started = time.perf_counter()
            model.fit(sample_inputs, sample_labels)
            fit_seconds = time.perf_counter() - fit_started
            predictions, probabilities = model.predict(dataset.validation.inputs)
            metrics = binary_metrics(dataset.validation.labels, predictions, probabilities)
            directory = run_dir / alternative.name
            artifact = self.repo.save_model(directory, model.estimator, manifest["inputs"])
            self.repo.save_array(directory, "validation_predictions", predictions)
            self.repo.save_array(directory, "validation_attack_probability", probabilities)
            candidates.append({
                "name": alternative.name,
                "parameters": model.parameters(),
                "metrics": metrics,
                "by_original_label": by_original_label(dataset.validation, predictions, manifest["original_labels"]),
                "complexity": model.complexity(),
                "fit_seconds": fit_seconds,
                "artifact": artifact,
                "reused": False,
            })
            emit(f"{alternative.name}: F1={metrics['f1']:.6f}; ajuste={fit_seconds:.1f} s")

        selected = select_candidate(candidates)
        selection = {
            "criterion": "highest validation F1; ties: fewest nodes, then fewest trees",
            "selected": selected["name"],
            "model": selected["parameters"],
            "data_manifest_sha256": dataset.manifest_sha256,
            "sample_records": len(sample_indices),
            "candidates": candidates,
            "test_used": False,
        }
        self.repo.write_record(run_dir, "selection", selection)
        emit(f"Configuração escolhida: {selected['name']}. Treinando com todos os {len(dataset.train.labels)} registros do treino...")
        final_model = self.model_factory(selected["parameters"])
        final_started = time.perf_counter()
        final_model.fit(dataset.train.inputs, dataset.train.labels)
        final_fit_seconds = time.perf_counter() - final_started
        final_dir = run_dir / "final"
        final_artifact = self.repo.save_model(final_dir, final_model.estimator, manifest["inputs"])
        validation_predictions, validation_probability = final_model.predict(dataset.validation.inputs)
        final_validation = binary_metrics(dataset.validation.labels, validation_predictions, validation_probability)
        self.repo.save_array(final_dir, "validation_predictions", validation_predictions)
        self.repo.save_array(final_dir, "validation_attack_probability", validation_probability)
        self.repo.verify_inputs_unchanged(dataset)
        self.repo.write_record(run_dir, "fixed-before-test", {
            "model": final_model.parameters(),
            "inputs": manifest["inputs"],
            "data_manifest_sha256": dataset.manifest_sha256,
            "artifact": final_artifact,
            "classification_rule": "attack if P(attack) > 0.5; benign otherwise",
            "environment": self.repo.environment(),
            "test_used": False,
        })
        emit("Modelo final salvo e parâmetros fixados. Avaliando no teste reservado...")
        test = self.repo.load_reserved_test(run_dir, dataset)
        predictions, probabilities = final_model.predict(test.inputs)
        test_metrics = binary_metrics(test.labels, predictions, probabilities)
        prediction_artifact = self.repo.save_array(final_dir, "test_predictions", predictions)
        probability_artifact = self.repo.save_array(final_dir, "test_attack_probability", probabilities)
        self.repo.verify_test_unchanged(dataset)
        summary = {
            "stage": "random-forest-selection-and-final-evaluation",
            "run_id": run_dir.name,
            "reference_run": str(self.config.reference_run),
            "reference_report_sha256": reference.summary_sha256,
            "sample_seed": original["configuration"]["sample_seed"],
            "sample_records": len(sample_indices),
            "sample_original_labels": original["sample"]["original_labels"],
            "data_manifest_sha256": dataset.manifest_sha256,
            "data_files": {name: manifest["splits"][name]["files"] for name in ("train", "validation", "test")},
            "inputs": manifest["inputs"],
            "classes": manifest["classes"],
            "selection": selection,
            "test_used_only_after_selection_and_full_training": True,
            "final": {
                "parameters": final_model.parameters(),
                "training_records": len(dataset.train.labels),
                "fit_seconds": final_fit_seconds,
                "complexity": final_model.complexity(),
                "model": final_artifact,
                "validation": {
                    "records": len(dataset.validation.labels), "metrics": final_validation,
                    "by_original_label": by_original_label(dataset.validation, validation_predictions, manifest["original_labels"]),
                },
                "test": {
                    "records": len(test.labels), "metrics": test_metrics,
                    "benign": int((test.labels == 0).sum()), "attack": int((test.labels == 1).sum()),
                    "by_original_label": by_original_label(test, predictions, manifest["original_labels"]),
                    "predictions": prediction_artifact, "probabilities": probability_artifact,
                },
            },
            "environment": self.repo.environment(),
            "resources": {
                "peak_process_memory_mib": peak_memory_mib(),
                "elapsed_seconds": time.perf_counter() - started,
            },
        }
        path = self.repo.write_comparison_reports(run_dir, summary)
        return PilotResult(run_dir, path, summary)
