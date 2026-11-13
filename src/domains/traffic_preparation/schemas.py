from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourcePcap:
    file: Path
    mirror: str
    mirror_commit: str
    path_in_mirror: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class PreparationConfig:
    path: Path
    sha256: str
    source: SourcePcap
    flows_csv: Path
    output_dir: Path
    segments: dict[str, datetime]
    border_seconds: int


@dataclass(frozen=True)
class CommandResult:
    path: Path
    report_path: Path | None
    summary: dict[str, Any]
