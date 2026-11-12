from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

MODELS = ("random-forest", "xgboost")
EXPLAINER = {
    "feature_perturbation": "tree_path_dependent",
    "model_output": "raw",
    "approximate": False,
    "check_additivity": False,
}


@dataclass(frozen=True)
class SampleConfig:
    size: int
    seed: int
    minimum_per_label: int


@dataclass(frozen=True)
class MeasurementConfig:
    flows: int
    batch_sizes: tuple[int, ...]
    processes: int
    passes: int
    cpu: int
    threads: int
    require_mains_power: bool


@dataclass(frozen=True)
class TreeShapConfig:
    path: Path
    sha256: str
    content: dict[str, Any]
    pilot_run: Path
    frozen_run: Path
    example_label: str
    example_class: int
    sample: SampleConfig
    tolerances: dict[str, dict[str, float]]
    measurement: MeasurementConfig


@dataclass(frozen=True)
class SplitData:
    name: str
    manifest: dict[str, Any]
    manifest_sha256: str
    inputs: np.ndarray
    labels: np.ndarray
    origin: np.ndarray


@dataclass(frozen=True)
class PilotModel:
    estimator: Any
    report: dict[str, Any]
    predictions: np.ndarray
    probabilities: np.ndarray


@dataclass(frozen=True)
class CommandResult:
    run_dir: Path
    report_path: Path
    summary: dict[str, Any]
