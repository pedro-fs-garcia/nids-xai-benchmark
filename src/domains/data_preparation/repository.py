import csv
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from domains.data_preparation.exceptions import (
    HeaderMismatchError,
    MalformedRecordError,
    SourceFileMissingError,
)
from domains.data_preparation.schemas import (
    ArtifactFile,
    RawRecords,
    SourceFile,
    SplitData,
)

_BLOCK_BYTES = 8 * 1024 * 1024
_CHUNK_RECORDS = 50_000
MANIFEST_FILE = "manifest.json"


class DataPreparationRepository:
    """Lê os CSVs originais e grava os conjuntos derivados. Nunca escreve nos originais."""

    def __init__(self, raw_dir: Path, derived_dir: Path, source_files: Sequence[str]) -> None:
        self.raw_dir = raw_dir
        self.derived_dir = derived_dir
        self.source_files = tuple(source_files)

    def fingerprint_sources(self) -> tuple[SourceFile, ...]:
        return tuple(
            SourceFile(name=name, bytes=path.stat().st_size, sha256=_sha256(path))
            for name, path in self._source_paths()
        )

    def read_header(self) -> tuple[str, ...]:
        reference: tuple[str, ...] | None = None
        for name, path in self._source_paths():
            with path.open(newline="") as stream:
                header = tuple(next(csv.reader(stream)))
            if reference is None:
                reference = header
            elif header != reference:
                raise HeaderMismatchError(name, self.source_files[0])
        assert reference is not None
        return reference

    def read_records(
        self,
        input_names: Sequence[str],
        label_column: str,
        attempted_column: str,
        id_column: str,
    ) -> RawRecords:
        header = self.read_header()
        input_columns = [header.index(name) for name in input_names]
        label_at = header.index(label_column)
        attempted_at = header.index(attempted_column)
        id_at = header.index(id_column)

        paths = self._source_paths()
        expected = [_count_records(path) for _, path in paths]
        total = sum(expected)

        inputs = np.empty((total, len(input_columns)), dtype=np.float64)
        label_index = np.empty(total, dtype=np.int64)
        attempted = np.empty(total, dtype=np.int64)
        source_index = np.empty(total, dtype=np.int64)
        record_id = np.empty(total, dtype=np.int64)
        labels: dict[str, int] = {}

        position = 0
        for source, (name, path) in enumerate(paths):
            start = position
            with path.open(newline="") as stream:
                reader = csv.reader(stream)
                next(reader)
                chunk: list[list[str]] = []
                for row in reader:
                    if len(row) != len(header):
                        raise MalformedRecordError(
                            name, reader.line_num, f"{len(row)} campos em vez de {len(header)}"
                        )
                    if position >= total:
                        raise MalformedRecordError(name, reader.line_num, "registro excedente")
                    chunk.append([row[column] for column in input_columns])
                    label_index[position] = labels.setdefault(row[label_at], len(labels))
                    attempted[position] = int(row[attempted_at])
                    record_id[position] = int(row[id_at])
                    position += 1
                    if len(chunk) == _CHUNK_RECORDS:
                        _store(inputs, chunk, position, name, reader.line_num)
                        chunk = []
                if chunk:
                    _store(inputs, chunk, position, name, reader.line_num)
            source_index[start:position] = source
            if position - start != expected[source]:
                raise MalformedRecordError(
                    name, 0, f"{position - start} registros lidos, {expected[source]} esperados"
                )

        # Índices de rótulo em ordem alfabética, independentes da ordem de leitura.
        ordered = sorted(labels)
        remap = np.empty(len(labels), dtype=np.int64)
        for new_index, label in enumerate(ordered):
            remap[labels[label]] = new_index

        return RawRecords(
            input_names=tuple(input_names),
            inputs=inputs,
            label_names=tuple(ordered),
            label_index=remap[label_index],
            attempted_category=attempted,
            source_index=source_index,
            record_id=record_id,
            records_per_source=tuple(expected),
        )

    def write_split(self, split: SplitData) -> dict[str, ArtifactFile]:
        self.derived_dir.mkdir(parents=True, exist_ok=True)
        arrays = {"X": split.inputs, "y": split.labels, "origin": split.origin}
        artifacts = {}
        for prefix, array in arrays.items():
            path = self._split_path(prefix, split.name)
            np.save(path, array, allow_pickle=False)
            artifacts[prefix] = ArtifactFile(
                file=path.name,
                bytes=path.stat().st_size,
                sha256=_sha256(path),
                dtype=str(array.dtype),
                shape=tuple(array.shape),
            )
        return artifacts

    def load_split(self, name: str) -> SplitData:
        def load(prefix: str) -> Any:
            return np.load(self._split_path(prefix, name), mmap_mode="r", allow_pickle=False)

        return SplitData(name=name, inputs=load("X"), labels=load("y"), origin=load("origin"))

    def write_manifest(self, manifest: dict[str, Any]) -> Path:
        self.derived_dir.mkdir(parents=True, exist_ok=True)
        path = self.derived_dir / MANIFEST_FILE
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def _source_paths(self) -> list[tuple[str, Path]]:
        paths = [(name, self.raw_dir / name) for name in self.source_files]
        for _, path in paths:
            if not path.is_file():
                raise SourceFileMissingError(path)
        return paths

    def _split_path(self, prefix: str, name: str) -> Path:
        return self.derived_dir / f"{prefix}_{name}.npy"


def _store(
    inputs: np.ndarray, chunk: list[list[str]], position: int, file: str, line: int
) -> None:
    try:
        inputs[position - len(chunk) : position] = np.array(chunk, dtype=np.float64)
    except ValueError as error:
        raise MalformedRecordError(file, line, f"valor não numérico no bloco ({error})") from error


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(_BLOCK_BYTES):
            digest.update(block)
    return digest.hexdigest()


def _count_records(path: Path) -> int:
    lines = 0
    last = b"\n"
    with path.open("rb") as stream:
        while block := stream.read(_BLOCK_BYTES):
            lines += block.count(b"\n")
            last = block[-1:]
    if last != b"\n":
        lines += 1
    return lines - 1
