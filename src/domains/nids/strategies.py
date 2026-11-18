"""Estratégias de explicação do NIDS: quais fluxos são explicados e se a entrega da classificação espera a explicação."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from domains.nids.exceptions import NidsError
from domains.nids.schemas import STRATEGIES

# Situação da explicação de um fluxo classificado, registrada na tabela por fluxo. No modo assíncrono, a
# tabela registra a solicitação aceita ou descartada, e a conclusão vem das marcações do processo explicador.
NOT_SELECTED, COMPLETED, REQUESTED, DROPPED = "nao_selecionada", "concluida", "solicitada", "descartada"


@dataclass(frozen=True)
class Strategy:
    key: str
    name: str
    # Decide, pela probabilidade de ataque, se o fluxo é explicado.
    select: Callable[[float], bool]
    # A explicação é gerada antes de a classificação ser disponibilizada.
    synchronous: bool
    # Critério de seleção e limiar, só no Síncrono condicional.
    criterion: str | None = None
    threshold: float | None = None

    @property
    def explains(self) -> bool:
        return self.key != "sem-xai"


def selection_rule(criterion: str, threshold: float) -> Callable[[Any], Any]:
    """Regra de um critério de seleção. Vale para a probabilidade de um fluxo e para um vetor de probabilidades."""
    if criterion == "probabilidade":
        return lambda probability: probability >= threshold
    if criterion == "incerteza":
        return lambda probability: abs(probability - 0.5) <= threshold
    raise NidsError(f"Critério de seleção desconhecido: {criterion}.")


def build_strategy(key: str, criterion: str | None = None, threshold: float | None = None) -> Strategy:
    if key not in STRATEGIES:
        raise NidsError(f"Estratégia desconhecida: {key}.")
    if key == "sincrono-condicional":
        if criterion is None or threshold is None:
            raise NidsError("O Síncrono condicional exige um critério de seleção com o limiar fixado.")
        return Strategy(key, STRATEGIES[key], selection_rule(criterion, threshold), True, criterion, threshold)
    if criterion is not None:
        raise NidsError(f"O critério de seleção só se aplica ao Síncrono condicional, e não a {STRATEGIES[key]}.")
    if key == "sem-xai":
        return Strategy(key, STRATEGIES[key], lambda probability: False, synchronous=False)
    return Strategy(key, STRATEGIES[key], lambda probability: True, synchronous=key == "sincrono-total")


def selection_table(criterion: str, thresholds: list[float], probability: np.ndarray, labels: np.ndarray,
                    predictions: np.ndarray) -> list[dict[str, Any]]:
    """Para cada limiar, quantos registros o critério seleciona, no total, entre os ataques, entre os benignos e
    entre os erros de classificação."""
    attack, wrong = labels == 1, predictions != labels
    rows = []
    for threshold in thresholds:
        selected = selection_rule(criterion, threshold)(probability)
        rows.append({
            "threshold": threshold, "selected": int(selected.sum()), "selected_share": float(selected.mean()),
            "attacks_selected": int(selected[attack].sum()), "attacks_selected_share": float(selected[attack].mean()),
            "benign_selected": int(selected[~attack].sum()), "benign_selected_share": float(selected[~attack].mean()),
            "errors_selected": int(selected[wrong].sum()),
            "errors_selected_share": float(selected[wrong].mean()) if wrong.any() else None,
        })
    return rows


def explanation_checks(strategy: Strategy, flows: list[dict[str, Any]], explanations: list[dict[str, Any]],
                       residual: float | None, tolerance: float) -> dict[str, bool]:
    """Verificações das explicações de uma execução, feitas depois da captura.

    Cada fluxo traz as marcações lidas pelo classificador. Cada explicação junta o registro do canal de saída das
    explicações com as marcações de quem a gerou. O resíduo é a maior diferença entre a saída explicada de um
    fluxo e o valor de referência somado às suas contribuições."""
    classified = {flow["seq"]: flow for flow in flows if flow["error"] is None}
    selected = {seq for seq, flow in classified.items() if flow["selected"]}
    by_seq = {item["seq"]: item for item in explanations}
    known = [item for item in explanations if item["seq"] in classified]
    checks = {
        "selection_follows_strategy": all(bool(flow["selected"]) == bool(strategy.select(flow["attack_probability"]))
                                          for flow in classified.values()),
        "explanations_match_classifications": len(explanations) == len(by_seq) == len(known) and all(
            item["flow_id"] == classified[item["seq"]]["flow_id"] for item in known),
        "sum_identity": residual is None or residual <= tolerance,
    }
    if strategy.synchronous or not strategy.explains:
        checks["explained_equals_selected"] = set(by_seq) == selected
        checks["explanation_marks_ordered"] = all(
            classified[item["seq"]]["t2_ns"] <= classified[item["seq"]]["selection_start_ns"]
            <= classified[item["seq"]]["selection_end_ns"] <= item["explanation_start_ns"]
            <= item["explanation_end_ns"] <= item["t4_ns"] == classified[item["seq"]]["t3_ns"] for item in known)
        return checks
    accepted = {seq for seq, flow in classified.items() if flow["explanation"] == REQUESTED}
    dropped = {seq for seq, flow in classified.items() if flow["explanation"] == DROPPED}
    checks["every_selected_flow_requested_or_dropped"] = accepted | dropped == selected and not accepted & dropped
    checks["no_explanation_without_accepted_request"] = set(by_seq) <= accepted
    # No modo assíncrono, a solicitação entra na fila depois de t3, e t4 vem depois da retirada da fila.
    checks["explanation_marks_ordered"] = all(
        classified[item["seq"]]["t2_ns"] <= classified[item["seq"]]["selection_start_ns"]
        <= classified[item["seq"]]["selection_end_ns"] <= classified[item["seq"]]["t3_ns"]
        <= classified[item["seq"]]["explanation_requested_ns"] <= item["dequeued_ns"] <= item["explanation_start_ns"]
        <= item["explanation_end_ns"] <= item["t4_ns"] for item in known)
    return checks


def pending_series(requested_ns: list[int], dequeued_ns: list[int], origin_ns: int) -> dict[str, Any]:
    """Tamanho da fila de explicações pendentes, reconstruído dos instantes de solicitação e de retirada.

    Devolve o maior tamanho, o primeiro instante em que ele ocorreu e o maior tamanho em cada segundo, contado
    desde a origem, que teve alguma solicitação ou retirada. Num segundo sem nenhuma delas, o tamanho não muda."""
    events = sorted([(instant, 1) for instant in requested_ns] + [(instant, -1) for instant in dequeued_ns])
    size, largest, largest_at, by_second = 0, 0, None, {}
    for instant, change in events:
        size += change
        second = (instant - origin_ns) // 1_000_000_000
        by_second[second] = max(by_second.get(second, 0), size)
        if size > largest:
            largest, largest_at = size, instant
    return {"max": largest, "max_at_ns": largest_at,
            "max_by_second": [[int(second), value] for second, value in sorted(by_second.items())]}
