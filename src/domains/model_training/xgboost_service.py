import time
from collections.abc import Callable
from typing import Any

from core.classification import binary_metrics
from core.xgboost_model import XGBoostAdapter
from domains.model_training.comparison import by_original_label, select_candidate
from domains.model_training.final_evaluation import fit_and_evaluate
from domains.model_training.repository import ModelTrainingRepository
from domains.model_training.schemas import PilotResult, XGBoostComparisonConfig
from domains.model_training.service import peak_memory_mib


class XGBoostComparisonService:
    def __init__(
        self, repo: ModelTrainingRepository, config: XGBoostComparisonConfig,
        model_factory: Callable[[dict[str, Any]], XGBoostAdapter],
    ) -> None:
        self.repo, self.config, self.model_factory = repo, config, model_factory

    def run(self, progress: Callable[[str], None] | None = None) -> PilotResult:
        started = time.perf_counter()
        emit = progress or (lambda _message: None)
        dataset = self.repo.load_pilot_dataset()
        manifest = dataset.manifest
        reference = self.repo.load_reference(self.config.reference_run, dataset)
        indices = reference.sample_indices
        sample_inputs, sample_labels = dataset.train.inputs[indices], dataset.train.labels[indices]
        run_dir = self.repo.create_run("xgboost-comparison")
        self.repo.save_array(run_dir, "sample_indices", indices)
        self.repo.save_array(run_dir, "sample_origin", dataset.train.origin[indices])
        settings = [("reference", {})] + [(a.name, a.overrides) for a in self.config.alternatives]
        candidates = []
        for name, overrides in settings:
            model = self.model_factory({**self.config.model, **overrides})
            emit(f"Treinando XGBoost {name} na amostra de {len(indices)} registros...")
            fit_started = time.perf_counter()
            model.fit(sample_inputs, sample_labels)
            fit_seconds = time.perf_counter() - fit_started
            predictions, probabilities = model.predict(dataset.validation.inputs)
            metrics = binary_metrics(dataset.validation.labels, predictions, probabilities)
            directory = run_dir / name
            artifact = self.repo.save_model(directory, model.estimator, manifest["inputs"])
            self.repo.save_array(directory, "validation_predictions", predictions)
            self.repo.save_array(directory, "validation_attack_probability", probabilities)
            candidates.append({
                "name": name, "parameters": model.parameters(), "metrics": metrics,
                "by_original_label": by_original_label(dataset.validation, predictions, manifest["original_labels"]),
                "complexity": model.complexity(), "fit_seconds": fit_seconds,
                "artifact": artifact, "reused": False,
            })
            emit(f"{name}: F1={metrics['f1']:.6f}; ajuste={fit_seconds:.1f} s")

        selected = select_candidate(candidates)
        selection = {
            "criterion": "highest validation F1; ties: fewest nodes, then fewest trees",
            "selected": selected["name"], "model": selected["parameters"],
            "data_manifest_sha256": dataset.manifest_sha256,
            "sample_records": len(indices), "candidates": candidates, "test_used": False,
        }
        self.repo.write_record(run_dir, "selection", selection)
        emit(f"Configuração escolhida: {selected['name']}. Treinando com todos os {len(dataset.train.labels)} registros...")
        final_model = self.model_factory(selected["parameters"])
        final = fit_and_evaluate(self.repo, dataset, final_model, run_dir, emit)
        example = final_model.prediction_example(dataset.validation.inputs)
        example["origin"] = dataset.validation.origin[0].tolist()
        example["actual_class"] = int(dataset.validation.labels[0])
        summary = {
            "algorithm": "xgboost", "stage": "xgboost-selection-and-final-evaluation",
            "run_id": run_dir.name,
            "reference_run": str(self.config.reference_run),
            "reference_scope": "training sample only; no Random Forest metric used for selection",
            "reference_report_sha256": reference.summary_sha256,
            "sample_seed": reference.summary["configuration"]["sample_seed"],
            "sample_records": len(indices),
            "sample_original_labels": reference.summary["sample"]["original_labels"],
            "data_manifest_sha256": dataset.manifest_sha256,
            "data_files": {name: manifest["splits"][name]["files"] for name in ("train", "validation", "test")},
            "inputs": manifest["inputs"], "classes": manifest["classes"],
            "selection": selection,
            "test_used_only_after_selection_and_full_training": True,
            "final": final, "prediction_example": example,
            "environment": self.repo.environment(),
            "resources": {
                "peak_process_memory_mib": peak_memory_mib(),
                "elapsed_seconds": time.perf_counter() - started,
            },
        }
        path = self.repo.write_comparison_reports(run_dir, summary)
        return PilotResult(run_dir, path, summary)
