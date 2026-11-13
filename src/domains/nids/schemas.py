from dataclasses import dataclass
from pathlib import Path
from typing import Any

MODELS = ("random-forest", "xgboost")


@dataclass(frozen=True)
class NidsConfig:
    path: Path
    sha256: str
    content: dict[str, Any]
    frozen_run: Path
    preparation_manifest: Path
    extractor: dict[str, int]
    classifier_threads: int
    shared_clock_tolerance_ns: int


@dataclass(frozen=True)
class CommandResult:
    run_dir: Path
    report_path: Path
    summary: dict[str, Any]
