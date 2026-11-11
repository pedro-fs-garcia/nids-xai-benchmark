import csv
import hashlib
from pathlib import Path

import numpy as np
import pytest

from domains.data_preparation.exceptions import (
    HeaderMismatchError,
    MalformedRecordError,
    SourceFileMissingError,
)
from domains.data_preparation.repository import DataPreparationRepository
from domains.data_preparation.schemas import SplitData

HEADER = ["id", "Flow ID", "Rate", "Count", "Label", "Attempted Category"]
INPUTS = ("Rate", "Count")


def write_csv(path: Path, rows: list[list[str]], header: list[str] = HEADER) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    write_csv(raw / "a.csv", [["1", "x", "inf", "2", "BENIGN", "-1"], ["2", "y", "0.5", "3", "DoS Hulk", "-1"]])
    write_csv(raw / "b.csv", [["1", "z", "1.5", "4", "Botnet - Attempted", "1"]])
    return raw


def make_repo(raw_dir: Path, tmp_path: Path, files: tuple[str, ...] = ("a.csv", "b.csv")) -> DataPreparationRepository:
    return DataPreparationRepository(raw_dir=raw_dir, derived_dir=tmp_path / "derived", source_files=files)


def test_read_records_returns_inputs_labels_and_origin(raw_dir: Path, tmp_path: Path) -> None:
    raw = make_repo(raw_dir, tmp_path).read_records(INPUTS, "Label", "Attempted Category", "id")

    assert raw.input_names == INPUTS
    assert np.isposinf(raw.inputs[0, 0])
    assert raw.inputs[1:].tolist() == [[0.5, 3.0], [1.5, 4.0]]
    assert raw.label_names == ("BENIGN", "Botnet - Attempted", "DoS Hulk")
    assert raw.label_index.tolist() == [0, 2, 1]
    assert raw.attempted_category.tolist() == [-1, -1, 1]
    assert raw.source_index.tolist() == [0, 0, 1]
    assert raw.record_id.tolist() == [1, 2, 1]
    assert raw.records_per_source == (2, 1)


def test_reading_does_not_change_the_source_files(raw_dir: Path, tmp_path: Path) -> None:
    repo = make_repo(raw_dir, tmp_path)
    before = repo.fingerprint_sources()

    repo.read_records(INPUTS, "Label", "Attempted Category", "id")

    assert repo.fingerprint_sources() == before
    assert before[0].sha256 == hashlib.sha256((raw_dir / "a.csv").read_bytes()).hexdigest()


def test_read_header_rejects_different_headers(raw_dir: Path, tmp_path: Path) -> None:
    write_csv(raw_dir / "b.csv", [], header=[*HEADER[:-1], "Outra"])

    with pytest.raises(HeaderMismatchError):
        make_repo(raw_dir, tmp_path).read_header()


def test_read_records_rejects_row_with_wrong_field_count(raw_dir: Path, tmp_path: Path) -> None:
    with (raw_dir / "b.csv").open("a") as stream:
        stream.write("2,w,1.0\n")

    with pytest.raises(MalformedRecordError):
        make_repo(raw_dir, tmp_path).read_records(INPUTS, "Label", "Attempted Category", "id")


def test_read_records_rejects_non_numeric_input(raw_dir: Path, tmp_path: Path) -> None:
    write_csv(raw_dir / "b.csv", [["1", "z", "abc", "4", "BENIGN", "-1"]])

    with pytest.raises(MalformedRecordError):
        make_repo(raw_dir, tmp_path).read_records(INPUTS, "Label", "Attempted Category", "id")


def test_missing_source_file_is_reported(raw_dir: Path, tmp_path: Path) -> None:
    with pytest.raises(SourceFileMissingError):
        make_repo(raw_dir, tmp_path, files=("a.csv", "c.csv")).fingerprint_sources()


def test_written_split_is_loaded_back_unchanged(raw_dir: Path, tmp_path: Path) -> None:
    repo = make_repo(raw_dir, tmp_path)
    split = SplitData(
        name="train",
        inputs=np.array([[1.0, 2.0]]),
        labels=np.array([1], dtype=np.int8),
        origin=np.array([[0, 7, 2]], dtype=np.int64),
    )

    artifacts = repo.write_split(split)
    loaded = repo.load_split("train")

    assert np.array_equal(loaded.inputs, split.inputs)
    assert np.array_equal(loaded.labels, split.labels)
    assert np.array_equal(loaded.origin, split.origin)
    path = tmp_path / "derived" / "X_train.npy"
    assert artifacts["X"].sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert artifacts["X"].shape == (1, 2)
