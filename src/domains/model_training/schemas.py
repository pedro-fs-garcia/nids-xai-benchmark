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
