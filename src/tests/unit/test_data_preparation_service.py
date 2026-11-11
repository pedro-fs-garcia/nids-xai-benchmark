from pathlib import Path
from typing import Any

import numpy as np
import pytest

from domains.data_preparation.exceptions import (
    InconsistentAttemptedLabelError,
    NonFiniteValuesError,
    SourceChangedError,
    UnexpectedColumnsError,
)
from domains.data_preparation.schemas import ArtifactFile, RawRecords, SourceFile, SplitData
from domains.data_preparation.service import (
    ATTACK,
    BENIGN,
    EXCLUDED_COLUMNS,
    EXPECTED_INPUT_COUNT,
    INFINITE_RATE_COLUMNS,
    LABEL_COLUMNS,
    METADATA_COLUMNS,
    SPLIT_NAMES,
    DataPreparationService,
    assign_groups,
    binary_label,
    group_identical_rows,
    replace_infinite_rates,
    require_consistent_attempted,
    select_input_columns,
    stratification_labels,
)

FRACTIONS = (0.70, 0.15, 0.15)
OTHER_INPUTS = tuple(f"Atributo {i}" for i in range(EXPECTED_INPUT_COUNT - len(INFINITE_RATE_COLUMNS)))
INPUT_NAMES = INFINITE_RATE_COLUMNS + OTHER_INPUTS
HEADER = METADATA_COLUMNS + INPUT_NAMES[:40] + EXCLUDED_COLUMNS + INPUT_NAMES[40:] + LABEL_COLUMNS


# --------------------------------------------------------------------------- #
# Decisão 3: entradas do classificador
# --------------------------------------------------------------------------- #


def test_select_input_columns_keeps_csv_order_without_labels_metadata_and_excluded() -> None:
    assert select_input_columns(HEADER) == INPUT_NAMES


def test_select_input_columns_rejects_missing_required_column() -> None:
    header = tuple(name for name in HEADER if name != "Dst Port")

    with pytest.raises(UnexpectedColumnsError) as error:
        select_input_columns(header)

    assert error.value.missing == ("Dst Port",)


def test_select_input_columns_rejects_unexpected_input_count() -> None:
    with pytest.raises(UnexpectedColumnsError) as error:
        select_input_columns((*HEADER, "Atributo novo"))

    assert error.value.input_count == EXPECTED_INPUT_COUNT + 1


# --------------------------------------------------------------------------- #
# Decisão 1: rótulo binário
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("BENIGN", BENIGN),
        ("DoS Slowloris - Attempted", BENIGN),
        ("Botnet - Attempted", BENIGN),
        ("DoS Hulk", ATTACK),
        ("Infiltration - Portscan", ATTACK),
        ("Heartbleed", ATTACK),
    ],
)
def test_binary_label(label: str, expected: int) -> None:
    assert binary_label(label) == expected


def test_require_consistent_attempted_accepts_matching_suffix_and_category() -> None:
    names = ("BENIGN", "Botnet", "Botnet - Attempted")

    require_consistent_attempted(names, np.array([0, 1, 2]), np.array([-1, -1, 1]))


def test_require_consistent_attempted_rejects_mismatch() -> None:
    names = ("BENIGN", "Botnet", "Botnet - Attempted")

    with pytest.raises(InconsistentAttemptedLabelError) as error:
        require_consistent_attempted(names, np.array([0, 1, 2]), np.array([-1, 4, -1]))

    assert error.value.records == 2


# --------------------------------------------------------------------------- #
# Decisão 2: taxas infinitas
# --------------------------------------------------------------------------- #


def test_replace_infinite_rates_writes_minus_one_and_counts_records() -> None:
    inputs = np.ones((3, EXPECTED_INPUT_COUNT))
    inputs[1, 0] = inputs[1, 1] = np.inf

    replaced = replace_infinite_rates(inputs, INPUT_NAMES)

    assert replaced == 1
    assert inputs[1, 0] == inputs[1, 1] == -1.0
    assert np.isfinite(inputs).all()


def test_replace_infinite_rates_rejects_infinite_outside_the_rates() -> None:
    inputs = np.ones((2, EXPECTED_INPUT_COUNT))
    inputs[0, 5] = np.inf

    with pytest.raises(NonFiniteValuesError) as error:
        replace_infinite_rates(inputs, INPUT_NAMES)

    assert error.value.columns == {INPUT_NAMES[5]: 1}


@pytest.mark.parametrize("value", [np.nan, -np.inf])
def test_replace_infinite_rates_rejects_nan_and_negative_infinity(value: float) -> None:
    inputs = np.ones((2, EXPECTED_INPUT_COUNT))
    inputs[0, 0] = value

    with pytest.raises(NonFiniteValuesError):
        replace_infinite_rates(inputs, INPUT_NAMES)


# --------------------------------------------------------------------------- #
# Decisão 4: agrupamento e divisão
# --------------------------------------------------------------------------- #


def test_group_identical_rows_groups_only_equal_rows() -> None:
    inputs = np.array([[1.0, 2.0], [3.0, 4.0], [1.0, 2.0], [1.0, 2.5]])

    assert group_identical_rows(inputs).tolist() == [0, 1, 0, 2]


def test_stratification_labels_use_most_frequent_label_and_lowest_on_tie() -> None:
    group_index = np.array([0, 0, 0, 1, 1, 2])
    label_index = np.array([2, 1, 2, 3, 0, 4])

    assert stratification_labels(group_index, label_index, n_labels=5).tolist() == [2, 0, 4]


def test_assign_groups_is_deterministic_for_a_seed() -> None:
    rng = np.random.default_rng(0)
    sizes = rng.integers(1, 50, size=500)
    strata = rng.integers(0, 4, size=500)

    first = assign_groups(sizes, strata, FRACTIONS, seed=42)
    second = assign_groups(sizes, strata, FRACTIONS, seed=42)

    assert np.array_equal(first, second)
    assert not np.array_equal(first, assign_groups(sizes, strata, FRACTIONS, seed=7))


def test_assign_groups_approximates_fractions_in_every_stratum() -> None:
    rng = np.random.default_rng(1)
    sizes = rng.integers(1, 20, size=3000)
    strata = rng.integers(0, 3, size=3000)

    assignment = assign_groups(sizes, strata, FRACTIONS, seed=42)

    for stratum in range(3):
        members = strata == stratum
        total = sizes[members].sum()
        for split, fraction in enumerate(FRACTIONS):
            share = sizes[members & (assignment == split)].sum() / total
            assert share == pytest.approx(fraction, abs=0.01)


def test_assign_groups_puts_a_small_stratum_in_every_split() -> None:
    sizes = np.ones(5, dtype=np.int64)
    strata = np.zeros(5, dtype=np.int64)

    assignment = assign_groups(sizes, strata, FRACTIONS, seed=42)

    assert np.bincount(assignment, minlength=3).tolist() == [3, 1, 1]


# --------------------------------------------------------------------------- #
# Preparação completa, com o repositório substituído
# --------------------------------------------------------------------------- #


class FakeRepository:
    """Guarda os conjuntos em memória no lugar dos arquivos."""

    def __init__(self, raw: RawRecords, header: tuple[str, ...] = HEADER) -> None:
        self.raw = raw
        self.header = header
        self.splits: dict[str, SplitData] = {}
        self.manifest: dict[str, Any] | None = None
        self.fingerprints = [(SourceFile("a.csv", 10, "hash-a"),), (SourceFile("a.csv", 10, "hash-a"),)]

    def fingerprint_sources(self) -> tuple[SourceFile, ...]:
        return self.fingerprints.pop(0)

    def read_header(self) -> tuple[str, ...]:
        return self.header

    def read_records(self, input_names: Any, *_columns: str) -> RawRecords:
        assert tuple(input_names) == self.raw.input_names
        return self.raw

    def write_split(self, split: SplitData) -> dict[str, ArtifactFile]:
        self.splits[split.name] = split
        return {
            prefix: ArtifactFile(f"{prefix}_{split.name}.npy", 0, "hash", str(array.dtype), array.shape)
            for prefix, array in (("X", split.inputs), ("y", split.labels), ("origin", split.origin))
        }

    def load_split(self, name: str) -> SplitData:
        return self.splits[name]

    def write_manifest(self, manifest: dict[str, Any]) -> Path:
        self.manifest = manifest
        return Path("manifest.json")


LABEL_NAMES = ("BENIGN", "Botnet", "Botnet - Attempted", "DoS Hulk")


def make_raw(seed: int = 0) -> RawRecords:
    """300 vetores distintos; os 100 primeiros aparecem três vezes. 500 registros."""
    rng = np.random.default_rng(seed)
    distinct = rng.integers(0, 1_000_000, size=(300, EXPECTED_INPUT_COUNT)).astype(np.float64)
    label_of_vector = np.arange(300) % len(LABEL_NAMES)
    rows = np.concatenate([np.arange(300), np.arange(100), np.arange(100)])
    rows = rows[rng.permutation(len(rows))]
    inputs = distinct[rows]
    label_index = label_of_vector[rows]
    inputs[0, 0] = inputs[0, 1] = np.inf
    return RawRecords(
        input_names=INPUT_NAMES,
        inputs=inputs,
        label_names=LABEL_NAMES,
        label_index=label_index,
        attempted_category=np.where(label_index == 2, 1, -1),
        source_index=np.zeros(len(rows), dtype=np.int64),
        record_id=np.arange(1, len(rows) + 1),
        records_per_source=(len(rows),),
    )


def prepare(repo: FakeRepository) -> dict[str, Any]:
    service = DataPreparationService(repo=repo, fractions=FRACTIONS, seed=42)  # type: ignore[arg-type]
    return service.prepare().manifest


def test_prepare_writes_three_disjoint_splits_that_cover_every_record() -> None:
    repo = FakeRepository(make_raw())

    manifest = prepare(repo)

    assert set(repo.splits) == set(SPLIT_NAMES)
    ids = np.concatenate([repo.splits[name].origin[:, 1] for name in SPLIT_NAMES])
    assert sorted(ids.tolist()) == list(range(1, 501))
    rows = {name: {row.tobytes() for row in repo.splits[name].inputs} for name in SPLIT_NAMES}
    assert not rows["train"] & rows["validation"]
    assert not rows["train"] & rows["test"]
    assert not rows["validation"] & rows["test"]
    assert manifest["records"]["total"] == 500
    assert manifest["records"]["groups"] == 300
    assert manifest["records"]["groups_with_several_records"] == 100


def test_prepare_applies_label_and_infinite_rate_decisions() -> None:
    repo = FakeRepository(make_raw())

    manifest = prepare(repo)

    for name in SPLIT_NAMES:
        split = repo.splits[name]
        original = split.origin[:, 2]
        assert np.array_equal(split.labels == ATTACK, np.isin(original, [1, 3]))
        assert np.isfinite(split.inputs).all()
    assert manifest["records"]["with_replaced_infinite_rate"] == 1
    assert manifest["records"]["benign"] + manifest["records"]["attack"] == 500
    assert [entry["class"] for entry in manifest["original_labels"]] == [
        "benign",
        "attack",
        "benign",
        "attack",
    ]


def test_prepare_keeps_every_original_label_in_every_split() -> None:
    repo = FakeRepository(make_raw())

    manifest = prepare(repo)

    for name in SPLIT_NAMES:
        assert all(count > 0 for count in manifest["splits"][name]["original_labels"].values())


def test_prepare_is_reproducible() -> None:
    first, second = FakeRepository(make_raw()), FakeRepository(make_raw())

    prepare(first)
    prepare(second)

    for name in SPLIT_NAMES:
        assert np.array_equal(first.splits[name].inputs, second.splits[name].inputs)
        assert np.array_equal(first.splits[name].origin, second.splits[name].origin)


def test_prepare_fails_when_a_source_file_changes() -> None:
    repo = FakeRepository(make_raw())
    repo.fingerprints[1] = (SourceFile("a.csv", 10, "outro-hash"),)

    with pytest.raises(SourceChangedError) as error:
        prepare(repo)

    assert error.value.files == ("a.csv",)
    assert repo.manifest is None
