"""Separação dos fluxos de uma execução com várias cópias do trecho, pela cópia de origem.

Cada fluxo de uma cópia volta aos endereços originais, para ser comparado com o fluxo correspondente da execução
por arquivo. Um fluxo com endereços fora da lista do trecho, ou com pontas de cópias diferentes, fica sem cópia.
É o caso dos fluxos que o extrator forma de quadros que não são IPv4, como o ARP, que a reescrita não altera e que
se juntam entre as cópias."""

from collections import defaultdict
from typing import Any

from core.traffic_copies import copy_of


def assign_copy(row: dict[str, str], positions: dict[str, int], addresses: list[str]
                ) -> tuple[int, dict[str, str]] | None:
    """Cópia de um fluxo e o fluxo com os endereços originais. Sem cópia, devolve None."""
    source = copy_of(row["Src IP"], positions, addresses)
    destination = copy_of(row["Dst IP"], positions, addresses)
    if source is None or destination is None or source[0] != destination[0]:
        return None
    original = {row["Src IP"]: source[1], row["Dst IP"]: destination[1]}
    parts = row["Flow ID"].split("-")
    parts[0], parts[1] = original.get(parts[0], parts[0]), original.get(parts[1], parts[1])
    return source[0], {**row, "Src IP": source[1], "Dst IP": destination[1], "Flow ID": "-".join(parts),
                       "_copy": str(source[0])}


def split_copies(rows: list[dict[str, str]], addresses: list[str]
                 ) -> tuple[dict[int, list[dict[str, str]]], list[dict[str, str]]]:
    """Fluxos de cada cópia, com os endereços originais, e os fluxos sem cópia."""
    positions = {address: index for index, address in enumerate(addresses)}
    groups: dict[int, list[dict[str, str]]] = defaultdict(list)
    unassigned = []
    for row in rows:
        assigned = assign_copy(row, positions, addresses)
        if assigned is None:
            unassigned.append(row)
        else:
            groups[assigned[0]].append(assigned[1])
    return dict(groups), unassigned


def in_segment(row: dict[str, Any], addresses: set[str]) -> bool:
    """Fluxo com as duas pontas entre os endereços IPv4 do trecho, o único que pertence a uma cópia."""
    return row["Src IP"] in addresses and row["Dst IP"] in addresses
