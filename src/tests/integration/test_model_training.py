import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pytest

from core.classification import RandomForestAdapter
from domains.model_training.exceptions import InvalidPilotConfigError, InvalidTrainingDataError
from domains.model_training.repository import ModelTrainingRepository
from domains.model_training.schemas import PilotConfig
from domains.model_training.service import ModelTrainingService


@pytest.fixture
def repo(tmp_path: Path) -> ModelTrainingRepository:
    data = tmp_path / "derived-data"
    data.mkdir()
    rng = np.random.default_rng(4)
    manifest = {
        "inputs": [f"feature_{i}" for i in range(80)],
        "classes": {"benign": 0, "attack": 1},
        "original_labels": [
            {"index": 0, "label": "BENIGN", "class": "benign"},
            {"index": 1, "label": "Botnet - Attempted", "class": "benign"},
            {"index": 2, "label": "DoS Hulk", "class": "attack"},
        ],
        "origin_columns": ["source_file_index", "id", "original_label_index"],
        "sources": [{"file": "fixture.csv"}],
        "verifications": {key: True for key in (
            "every_record_in_exactly_one_split", "no_input_vector_in_more_than_one_split",
            "every_original_label_in_every_split", "all_values_finite", "sources_unchanged",
        )},
        "splits": {},
    }
    for name, n in (("train", 90), ("validation", 30)):
        original = np.arange(n, dtype=np.int64) % 3
        inputs = rng.normal(size=(n, 80))
        labels = (original == 2).astype(np.int8)
        inputs[:, 0] = labels
        origin = np.column_stack((np.zeros(n, dtype=np.int64), np.arange(n), original))
        manifest["splits"][name] = {"records": n, "files": {}}
        for key, values in (("X", inputs), ("y", labels), ("origin", origin)):
            path = data / f"{key}_{name}.npy"
            np.save(path, values, allow_pickle=False)
            manifest["splits"][name]["files"][key] = {
                "file": path.name, "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "shape": list(values.shape), "dtype": str(values.dtype),
            }
    (data / "manifest.json").write_text(json.dumps(manifest))
    # O piloto deve funcionar mesmo sem arquivos de teste no diretório.
    return ModelTrainingRepository(data, tmp_path / "training-runs", tmp_path / "relatorios")


def test_pilot_saves_model_sample_validation_predictions_and_report_without_test_data(repo) -> None:
    config = PilotConfig(24, 42, {"n_estimators": 3, "max_depth": 3, "n_jobs": 1, "random_state": 42})
    service = ModelTrainingService(repo, config, RandomForestAdapter(config.model))
    result = service.run_pilot()
    saved = joblib.load(result.run_dir / "model.joblib")
    validation = np.load(repo.data_dir / "X_validation.npy")
    probability = np.load(result.run_dir / "validation_attack_probability.npy")
    selected = np.load(result.run_dir / "sample_indices.npy")
    origin = np.load(repo.data_dir / "origin_train.npy")
    sample_origin = np.load(result.run_dir / "sample_origin.npy")

    assert np.array_equal(saved["estimator"].predict_proba(validation)[:, 1], probability)
    assert np.array_equal(sample_origin, origin[selected])
    assert len(saved["inputs"]) == 80
    assert result.summary["sample"]["records"] == 24
    assert all(n > 0 for n in result.summary["sample"]["original_labels"].values())
    assert result.summary["test_used"] is False
    assert set(result.summary["data_files"]) == {"train", "validation"}
    assert result.summary["stage"] == "pilot"
    assert result.summary["resources"]["fit_seconds"] > 0
    assert result.report_path.is_file()
    assert json.loads((result.run_dir / "report.json").read_text())["inputs"] == saved["inputs"]
    assert sum(result.summary["validation"]["metrics"]["confusion_matrix"].values()) == 30
    for info in result.summary["artifacts"].values():
        path = result.run_dir / info["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == info["sha256"]


def test_repository_refuses_changed_training_file(repo) -> None:
    path = repo.data_dir / "X_train.npy"
    with path.open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(InvalidTrainingDataError, match="hash ou tamanho"):
        repo.load_pilot_dataset()


def test_repository_rejects_failed_data_preparation_verification(repo) -> None:
    path = repo.data_dir / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["verifications"]["no_input_vector_in_more_than_one_split"] = False
    path.write_text(json.dumps(manifest))
    with pytest.raises(InvalidTrainingDataError, match="verificações"):
        repo.load_pilot_dataset()


def test_repository_refuses_manifest_changed_during_training(repo) -> None:
    dataset = repo.load_pilot_dataset()
    path = repo.data_dir / "manifest.json"
    path.write_text(path.read_text() + "\n")
    with pytest.raises(InvalidTrainingDataError, match="manifesto mudou"):
        repo.verify_inputs_unchanged(dataset)


def test_repository_rejects_test_access_in_pilot(repo) -> None:
    with pytest.raises(InvalidTrainingDataError, match="não permitido"):
        repo._load_split("test", {})


def test_invalid_sample_configuration_is_reported(repo, tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"sample_size": 0, "sample_seed": 42, "model": {}}))
    with pytest.raises(InvalidPilotConfigError):
        repo.read_config(path)


def test_new_runs_use_different_directories(repo) -> None:
    assert repo.create_run() != repo.create_run()
