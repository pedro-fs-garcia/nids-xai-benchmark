from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

FloatMatrix = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]
LabelArray = npt.NDArray[np.int8]


@dataclass(frozen=True)
class SourceFile:
    name: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class RawRecords:
    """Registros dos CSVs originais, na ordem dos arquivos e das linhas."""

    input_names: tuple[str, ...]
    inputs: FloatMatrix
    label_names: tuple[str, ...]
    label_index: IntArray
    attempted_category: IntArray
    source_index: IntArray
    record_id: IntArray
    records_per_source: tuple[int, ...]


@dataclass(frozen=True)
class SplitData:
    """Um conjunto derivado. `origin` guarda arquivo, id e rótulo original de cada registro."""

    name: str
    inputs: FloatMatrix
    labels: LabelArray
    origin: IntArray


@dataclass(frozen=True)
class ArtifactFile:
    file: str
    bytes: int
    sha256: str
    dtype: str
    shape: tuple[int, ...]


@dataclass(frozen=True)
class PreparationReport:
    manifest_path: Path
    manifest: dict[str, Any]
