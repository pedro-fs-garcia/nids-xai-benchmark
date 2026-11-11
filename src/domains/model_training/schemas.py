from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class PilotConfig:
    sample_size: int
    sample_seed: int
    model: dict[str, Any]


@dataclass(frozen=True)
class TrainingSplit:
    inputs: np.ndarray
    labels: np.ndarray
    origin: np.ndarray


@dataclass(frozen=True)
class PilotDataset:
    manifest: dict[str, Any]
    manifest_sha256: str
    train: TrainingSplit
    validation: TrainingSplit


@dataclass(frozen=True)
class PilotResult:
    run_dir: Path
    report_path: Path
    summary: dict[str, Any]


@dataclass(frozen=True)
class ForestAlternative:
    name: str
    overrides: dict[str, int]


@dataclass(frozen=True)
class ForestComparisonConfig:
    reference_run: Path
    alternatives: tuple[ForestAlternative, ...]
    selection_metric: str = "f1"


@dataclass(frozen=True)
class ReferenceRun:
    summary: dict[str, Any]
    summary_sha256: str
    sample_indices: np.ndarray


@dataclass(frozen=True)
class XGBoostComparisonConfig:
    reference_run: Path
    model: dict[str, Any]
    alternatives: tuple[ForestAlternative, ...]
    selection_metric: str = "f1"
