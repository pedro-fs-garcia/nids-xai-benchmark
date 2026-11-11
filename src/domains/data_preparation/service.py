"""Regras da preparação dos dados, definidas em docs/decisoes.md (decisões 1 a 4)."""

import hashlib
import platform
import resource
import time
from collections.abc import Iterator, Sequence
from typing import Any

import numpy as np

from domains.data_preparation.exceptions import (
    InconsistentAttemptedLabelError,
    NonFiniteValuesError,
    SourceChangedError,
    SplitVerificationError,
    UnexpectedColumnsError,
)
from domains.data_preparation.repository import DataPreparationRepository
from domains.data_preparation.schemas import (
    FloatMatrix,
    IntArray,
    LabelArray,
    PreparationReport,
    RawRecords,
    SplitData,
)

LABEL_COLUMN = "Label"
ATTEMPTED_COLUMN = "Attempted Category"
ID_COLUMN = "id"

# Decisão 3: colunas fora das entradas do classificador.
LABEL_COLUMNS = (LABEL_COLUMN, ATTEMPTED_COLUMN)
METADATA_COLUMNS = ("id", "Flow ID", "Src IP", "Src Port", "Dst IP", "Dst Port", "Timestamp")
EXCLUDED_COLUMNS = ("Fwd Header Length", "Bwd Header Length")
EXPECTED_INPUT_COUNT = 80

# Decisão 2: taxas que valem inf quando a duração do fluxo é 0.
INFINITE_RATE_COLUMNS = ("Flow Bytes/s", "Flow Packets/s")
INFINITE_RATE_REPLACEMENT = -1.0

# Decisão 1: rótulo binário.
BENIGN = 0
ATTACK = 1
CLASS_NAMES = ("benign", "attack")
BENIGN_LABEL = "BENIGN"
ATTEMPTED_SUFFIX = " - Attempted"
NOT_ATTEMPTED = -1

SPLIT_NAMES = ("train", "validation", "test")
ORIGIN_COLUMNS = ("source_file_index", "id", "original_label_index")


def select_input_columns(header: Sequence[str]) -> tuple[str, ...]:
    """Decisão 3: as entradas são as colunas do CSV, em ordem, menos rótulos, metadados e excluídas."""
    not_input = LABEL_COLUMNS + METADATA_COLUMNS + EXCLUDED_COLUMNS
    missing = [name for name in not_input + INFINITE_RATE_COLUMNS if name not in header]
    inputs = tuple(name for name in header if name not in not_input)
    if missing or len(inputs) != EXPECTED_INPUT_COUNT:
        raise UnexpectedColumnsError(missing, len(inputs), EXPECTED_INPUT_COUNT)
    return inputs


def binary_label(label: str) -> int:
    """Decisão 1: BENIGN e os rótulos Attempted são benignos; os demais são ataque."""
    if label == BENIGN_LABEL or label.endswith(ATTEMPTED_SUFFIX):
        return BENIGN
    return ATTACK


def require_consistent_attempted(
    label_names: Sequence[str], label_index: IntArray, attempted_category: IntArray
) -> None:
    """Decisão 1: os rótulos Attempted são exatamente os registros com Attempted Category != -1."""
    has_suffix = np.array([name.endswith(ATTEMPTED_SUFFIX) for name in label_names])
    mismatches = int((has_suffix[label_index] != (attempted_category != NOT_ATTEMPTED)).sum())
    if mismatches:
        raise InconsistentAttemptedLabelError(mismatches)


def replace_infinite_rates(inputs: FloatMatrix, input_names: Sequence[str]) -> int:
    """Decisão 2: troca inf por -1 nas duas taxas, no próprio array. Devolve os registros alterados."""
    columns = [input_names.index(name) for name in INFINITE_RATE_COLUMNS]
    rates = inputs[:, columns]
    infinite = np.isposinf(rates)
    rates[infinite] = INFINITE_RATE_REPLACEMENT
    inputs[:, columns] = rates

    non_finite = (~np.isfinite(inputs)).sum(axis=0)
    if non_finite.any():
        raise NonFiniteValuesError(
            {input_names[i]: int(count) for i, count in enumerate(non_finite) if count}
        )
    return int(infinite.any(axis=1).sum())


def group_identical_rows(inputs: FloatMatrix) -> IntArray:
    """Decisão 4: registros com as entradas idênticas recebem o mesmo índice de grupo."""
    groups: dict[bytes, int] = {}
    index = np.empty(len(inputs), dtype=np.int64)
    for position, digest in enumerate(_row_digests(inputs)):
        index[position] = groups.setdefault(digest, len(groups))
    return index


def stratification_labels(group_index: IntArray, label_index: IntArray, n_labels: int) -> IntArray:
    """Decisão 4: o rótulo de estratificação de um grupo é o rótulo original mais frequente nele.

    Em caso de empate, vale o rótulo de menor índice.
    """
    pairs, counts = np.unique(group_index * n_labels + label_index, return_counts=True)
    group, label = pairs // n_labels, pairs % n_labels
    order = np.lexsort((label, -counts, group))
    group, label = group[order], label[order]
    first = np.ones(len(group), dtype=bool)
    first[1:] = group[1:] != group[:-1]
    strata = np.empty(int(group_index.max()) + 1, dtype=np.int64)
    strata[group[first]] = label[first]
    return strata


def assign_groups(
    sizes: IntArray, strata: IntArray, fractions: Sequence[float], seed: int
) -> LabelArray:
    """Decisão 4: distribui grupos inteiros entre os conjuntos, estrato por estrato.

    Em cada estrato, os grupos são embaralhados com a semente, ordenados do maior para o
    menor e entregues ao conjunto mais distante da sua proporção de registros.
    """
    rng = np.random.default_rng(seed)
    assignment = np.empty(len(sizes), dtype=np.int8)
    for stratum in np.unique(strata):
        members = np.flatnonzero(strata == stratum)
        members = members[rng.permutation(len(members))]
        members = members[np.argsort(-sizes[members], kind="stable")]
        counts = [0] * len(fractions)
        total = 0
        for group, size in zip(members.tolist(), sizes[members].tolist(), strict=True):
            total += size
            target = max(range(len(fractions)), key=lambda k: fractions[k] * total - counts[k])
            counts[target] += size
            assignment[group] = target
    return assignment


class DataPreparationService:
    def __init__(
        self,
        repo: DataPreparationRepository,
        fractions: Sequence[float],
        seed: int,
    ) -> None:
        self.repo = repo
        self.fractions = tuple(fractions)
        self.seed = seed

    def prepare(self) -> PreparationReport:
        started = time.perf_counter()
        sources = self.repo.fingerprint_sources()

        input_names = select_input_columns(self.repo.read_header())
        raw = self.repo.read_records(input_names, LABEL_COLUMN, ATTEMPTED_COLUMN, ID_COLUMN)
        require_consistent_attempted(raw.label_names, raw.label_index, raw.attempted_category)

        class_by_label = np.array([binary_label(name) for name in raw.label_names], dtype=np.int8)
        labels = class_by_label[raw.label_index]

        inputs = raw.inputs
        replaced = replace_infinite_rates(inputs, input_names)
        # -0.0 e 0.0 são a mesma entrada para o classificador; grava-se sempre 0.0.
        np.add(inputs, 0.0, out=inputs)

        group_index = group_identical_rows(inputs)
        sizes = np.bincount(group_index)
        strata = stratification_labels(group_index, raw.label_index, len(raw.label_names))
        record_split = assign_groups(sizes, strata, self.fractions, self.seed)[group_index]

        origin = np.column_stack((raw.source_index, raw.record_id, raw.label_index))
        files = {}
        for split, name in enumerate(SPLIT_NAMES):
            mask = record_split == split
            files[name] = self.repo.write_split(
                SplitData(name=name, inputs=inputs[mask], labels=labels[mask], origin=origin[mask])
            )

        splits = self._verify(len(inputs), len(input_names), class_by_label, raw.label_names)

        after = self.repo.fingerprint_sources()
        changed = [a.name for a, b in zip(sources, after, strict=True) if a != b]
        if changed:
            raise SourceChangedError(changed)

        attacks_per_group = np.bincount(group_index, weights=labels)
        manifest = {
            "dataset": "Improved CIC-IDS2017",
            "decisions": "docs/decisoes.md",
            "configuration": {
                "seed": self.seed,
                "fractions": dict(zip(SPLIT_NAMES, self.fractions, strict=True)),
                "grouping": "records with identical inputs",
                "stratification": "most frequent original label of each group",
                "infinite_rate_columns": list(INFINITE_RATE_COLUMNS),
                "infinite_rate_replacement": INFINITE_RATE_REPLACEMENT,
            },
            "sources": [
                {"file": s.name, "bytes": s.bytes, "sha256": s.sha256, "records": records}
                for s, records in zip(sources, raw.records_per_source, strict=True)
            ],
            "inputs": list(input_names),
            "columns_outside_inputs": {
                "labels": list(LABEL_COLUMNS),
                "metadata": list(METADATA_COLUMNS),
                "excluded": list(EXCLUDED_COLUMNS),
            },
            "classes": {name: value for value, name in enumerate(CLASS_NAMES)},
            "original_labels": [
                {
                    "index": index,
                    "label": name,
                    "class": CLASS_NAMES[class_by_label[index]],
                    "records": int(count),
                }
                for index, (name, count) in enumerate(
                    zip(
                        raw.label_names,
                        np.bincount(raw.label_index, minlength=len(raw.label_names)),
                        strict=True,
                    )
                )
            ],
            "origin_columns": list(ORIGIN_COLUMNS),
            "records": {
                "total": len(inputs),
                "benign": int((labels == BENIGN).sum()),
                "attack": int((labels == ATTACK).sum()),
                "with_replaced_infinite_rate": replaced,
                "groups": len(sizes),
                "groups_with_several_records": int((sizes > 1).sum()),
                "records_in_groups_with_several_records": int(sizes[sizes > 1].sum()),
                "groups_with_both_classes": int(
                    ((attacks_per_group > 0) & (attacks_per_group < sizes)).sum()
                ),
            },
            "splits": {
                name: {
                    **splits[name],
                    "groups": int(np.unique(group_index[record_split == split]).size),
                    "files": {
                        prefix: {
                            "file": artifact.file,
                            "bytes": artifact.bytes,
                            "sha256": artifact.sha256,
                            "dtype": artifact.dtype,
                            "shape": list(artifact.shape),
                        }
                        for prefix, artifact in files[name].items()
                    },
                }
                for split, name in enumerate(SPLIT_NAMES)
            },
            "verifications": {
                "every_record_in_exactly_one_split": True,
                "no_input_vector_in_more_than_one_split": True,
                "every_original_label_in_every_split": True,
                "all_values_finite": True,
                "sources_unchanged": True,
            },
            "software": {"python": platform.python_version(), "numpy": np.__version__},
            "execution": {
                "peak_memory_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024),
                "elapsed_seconds": round(time.perf_counter() - started),
            },
        }
        return PreparationReport(manifest_path=self.repo.write_manifest(manifest), manifest=manifest)

    def _verify(
        self,
        total: int,
        n_inputs: int,
        class_by_label: LabelArray,
        label_names: Sequence[str],
    ) -> dict[str, dict[str, Any]]:
        """Decisão 4: confere os conjuntos gravados, relidos do disco."""
        n_labels = len(class_by_label)
        summaries: dict[str, dict[str, Any]] = {}
        digests: dict[str, set[bytes]] = {}
        keys = []
        for name in SPLIT_NAMES:
            split = self.repo.load_split(name)
            records = len(split.labels)
            if (
                split.inputs.shape != (records, n_inputs)
                or split.inputs.dtype != np.float64
                or split.labels.dtype != np.int8
                or split.origin.shape != (records, len(ORIGIN_COLUMNS))
                or split.origin.dtype != np.int64
            ):
                raise SplitVerificationError("tipos", f"formato inesperado no conjunto {name}")
            if not np.isfinite(split.inputs).all():
                raise SplitVerificationError("valores finitos", f"valor não finito em {name}")

            original = np.asarray(split.origin[:, 2])
            if not np.array_equal(split.labels, class_by_label[original]):
                raise SplitVerificationError(
                    "rótulos", f"rótulo binário diverge do rótulo original em {name}"
                )
            label_counts = np.bincount(original, minlength=n_labels)
            if (label_counts == 0).any():
                absent = np.flatnonzero(label_counts == 0).tolist()
                raise SplitVerificationError(
                    "cobertura de rótulos", f"rótulos originais {absent} ausentes de {name}"
                )

            digests[name] = set(_row_digests(split.inputs))
            keys.append(np.asarray(split.origin[:, 0]) * 2**32 + np.asarray(split.origin[:, 1]))
            attacks = int(np.asarray(split.labels).sum())
            summaries[name] = {
                "records": records,
                "fraction": round(records / total, 6),
                "benign": records - attacks,
                "attack": attacks,
                "attack_fraction": round(attacks / records, 6),
                "original_labels": dict(zip(label_names, label_counts.tolist(), strict=True)),
            }

        all_keys = np.concatenate(keys)
        if len(all_keys) != total or len(np.unique(all_keys)) != total:
            raise SplitVerificationError(
                "partição", f"os conjuntos somam {len(all_keys)} registros; o total é {total}"
            )
        for i, first in enumerate(SPLIT_NAMES):
            for second in SPLIT_NAMES[i + 1 :]:
                shared = len(digests[first] & digests[second])
                if shared:
                    raise SplitVerificationError(
                        "independência",
                        f"{shared} vetores de entrada aparecem em {first} e em {second}",
                    )
        return summaries


def _row_digests(inputs: FloatMatrix) -> Iterator[bytes]:
    """Resumo de 128 bits dos bytes de cada linha."""
    rows, width = inputs.shape
    step = width * inputs.dtype.itemsize
    view = memoryview(np.ascontiguousarray(inputs)).cast("B")
    for start in range(0, rows * step, step):
        yield hashlib.blake2b(view[start : start + step], digest_size=16).digest()
