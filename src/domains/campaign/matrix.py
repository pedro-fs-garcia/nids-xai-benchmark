"""Matriz de ensaios do piloto e da campanha: células, ordem de execução, registro e validade de cada ensaio.

Uma célula é a combinação de classificador, configuração de explicação, nível de carga e repetição, dentro de um
bloco da matriz. O registro da matriz é um arquivo JSON Lines com uma linha por tentativa, só acrescentado, nunca
reescrito. Só a biblioteca padrão é usada, porque o executor da matriz roda com o Python do sistema."""

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

MODELS = ("random-forest", "xgboost")
# Configuração de explicação: estratégia e critério de seleção do Síncrono condicional.
CONFIGURATIONS = {
    "sem-xai": ("sem-xai", None),
    "sincrono-total": ("sincrono-total", None),
    "sincrono-condicional-probabilidade": ("sincrono-condicional", "probabilidade"),
    "sincrono-condicional-incerteza": ("sincrono-condicional", "incerteza"),
    "assincrono": ("assincrono", None),
}
MATRIX_FIELDS = {"name", "segment", "seed", "machine", "max_attempts", "blocks"}
BLOCK_FIELDS = {"label", "models", "configurations", "loads", "repetitions"}
MACHINE_FIELDS = {"require_mains", "max_busy_share", "min_available_mib", "window_s", "max_wait_s"}


@dataclass(frozen=True)
class Cell:
    block: str
    model: str
    configuration: str
    load: int
    repetition: int

    @property
    def id(self) -> str:
        return f"{self.block}/{self.model}/{self.configuration}/carga-{self.load}/rep-{self.repetition}"

    @property
    def strategy(self) -> str:
        return CONFIGURATIONS[self.configuration][0]

    @property
    def criterion(self) -> str | None:
        return CONFIGURATIONS[self.configuration][1]

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "id": self.id, "strategy": self.strategy, "criterion": self.criterion}


def read_matrix(path: Path) -> dict[str, Any]:
    """Configuração da matriz, conferida. Um valor nulo é uma decisão ainda não tomada e impede a execução."""
    matrix = json.loads(path.read_text(encoding="utf-8"))
    if set(matrix) != MATRIX_FIELDS:
        raise ValueError(f"A matriz deve ter os campos {sorted(MATRIX_FIELDS)}.")
    if set(matrix["machine"]) != MACHINE_FIELDS:
        raise ValueError(f"machine deve ter os campos {sorted(MACHINE_FIELDS)}.")
    if type(matrix["max_attempts"]) is not int or matrix["max_attempts"] < 1:
        raise ValueError("max_attempts deve ser um inteiro positivo.")
    labels = set()
    for block in matrix["blocks"]:
        if set(block) != BLOCK_FIELDS:
            raise ValueError(f"Cada bloco deve ter os campos {sorted(BLOCK_FIELDS)}.")
        if block["label"] in labels:
            raise ValueError(f"Bloco repetido: {block['label']}.")
        labels.add(block["label"])
        if block["loads"] is None or block["repetitions"] is None or None in block["loads"]:
            raise ValueError(f"O bloco {block['label']} tem valores ainda não fixados.")
        if not block["models"] or not set(block["models"]) <= set(MODELS):
            raise ValueError(f"Modelos inválidos no bloco {block['label']}.")
        if not block["configurations"] or not set(block["configurations"]) <= set(CONFIGURATIONS):
            raise ValueError(f"Configurações inválidas no bloco {block['label']}.")
        if not block["loads"] or any(type(load) is not int or load < 1 for load in block["loads"]):
            raise ValueError(f"Níveis de carga inválidos no bloco {block['label']}.")
        if type(block["repetitions"]) is not int or block["repetitions"] < 1:
            raise ValueError(f"Número de repetições inválido no bloco {block['label']}.")
    return matrix


def expand(matrix: dict[str, Any]) -> list[Cell]:
    """Células na ordem de execução. Os blocos seguem a ordem da configuração. Dentro de um bloco, cada repetição
    reúne todas as combinações, em ordem sorteada com a semente da matriz, para que uma variação lenta da máquina
    não recaia sempre sobre as mesmas combinações."""
    cells = []
    for block in matrix["blocks"]:
        combinations = [(model, configuration, load) for model in block["models"]
                        for configuration in block["configurations"] for load in block["loads"]]
        for repetition in range(1, block["repetitions"] + 1):
            order = list(combinations)
            random.Random(f"{matrix['seed']}/{block['label']}/{repetition}").shuffle(order)
            cells += [Cell(block["label"], model, configuration, load, repetition)
                      for model, configuration, load in order]
    return cells


def read_registry(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def append_registry(path: Path, entry: dict[str, Any]) -> None:
    """Acrescenta uma tentativa ao registro. As linhas anteriores nunca são alteradas."""
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")


def status(cells: list[Cell], registry: list[dict[str, Any]], max_attempts: int) -> dict[str, Any]:
    """Situação de cada célula: concluída, esgotada ou pendente, com o número da próxima tentativa.

    Uma tentativa que não começou, porque a máquina não ficou pronta, não conta no limite de tentativas."""
    attempts: dict[str, list[dict[str, Any]]] = {}
    for entry in registry:
        attempts.setdefault(entry["cell"]["id"], []).append(entry)
    done, exhausted, pending = [], [], []
    for cell in cells:
        entries = attempts.get(cell.id, [])
        started = [entry for entry in entries if entry["result"].get("started", True)]
        if any(entry["validity"]["valid"] for entry in started):
            done.append(cell)
        elif len(started) >= max_attempts:
            exhausted.append(cell)
        else:
            pending.append((cell, len(started) + 1))
    unknown = sorted(set(attempts) - {cell.id for cell in cells})
    return {"done": done, "exhausted": exhausted, "pending": pending, "unknown_cells": unknown}


def validity(result: dict[str, Any], replay: dict[str, Any] | None, report: dict[str, Any] | None) -> dict[str, Any]:
    """Critérios de validade de um ensaio que começou. Descartes e pendências não invalidam: são resultados."""
    reasons = []
    if not result.get("started", True):
        reasons.append("não iniciado: a máquina não ficou pronta")
    if result.get("exit_code") != 0:
        reasons.append(f"encerrado com código {result.get('exit_code')}" + (
            f": {result['error']}" if result.get("error") else ""))
    if report is None:
        reasons.append("sem o registro da execução do NIDS")
    elif not report.get("passed"):
        reasons.append("o NIDS não passou nas próprias verificações")
    if replay is not None:
        tcpreplay = replay.get("tcpreplay") or {}
        if tcpreplay.get("failed") not in (0, None) or tcpreplay.get("exit_code") not in (0, None):
            reasons.append("o tcpreplay não enviou todos os pacotes")
        if not (replay.get("machine") or {}).get("mains_online_in_every_sample", False):
            reasons.append("a máquina saiu da tomada durante o ensaio")
        if replay.get("nids_stop_timeout"):
            reasons.append("o NIDS não encerrou no tempo máximo")
    return {"valid": not reasons, "reasons": reasons}
