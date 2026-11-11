from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LoadedModel:
    manifest: dict[str, Any]
    estimator: Any


@dataclass(frozen=True)
class FreezeResult:
    run_dir: Path
    models: dict[str, dict[str, Any]]
