"""Afinidade de CPU e uso de recursos de um processo. Único módulo que lê /proc para o NIDS."""

import os
import resource
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any


def pin_all_threads(cpus: Iterable[int]) -> list[int]:
    """Fixa nas CPUs dadas todas as threads que o processo já tem. As threads criadas depois herdam a afinidade.

    No Linux, sched_setaffinity com o identificador 0 só altera a thread que chama. As bibliotecas numéricas
    criam threads ao serem importadas, e cada uma precisa ser fixada pelo seu identificador."""
    target = set(cpus)
    for thread in os.listdir("/proc/self/task"):
        try:
            os.sched_setaffinity(int(thread), target)
        except ProcessLookupError:
            continue
    return sorted(target)


def pin_before_exec(cpus: Iterable[int]) -> Callable[[], None]:
    """Fixa um processo filho antes de o programa começar, para que todas as suas threads herdem a afinidade."""
    target = set(cpus)

    def pin() -> None:
        os.sched_setaffinity(0, target)

    return pin


def thread_affinities() -> list[list[int]]:
    """Conjuntos distintos de CPUs em que as threads do processo podem rodar."""
    found = set()
    for thread in os.listdir("/proc/self/task"):
        try:
            found.add(tuple(sorted(os.sched_getaffinity(int(thread)))))
        except ProcessLookupError:
            continue
    return [list(cpus) for cpus in sorted(found)]


def self_usage() -> dict[str, Any]:
    """CPU e pico de memória residente do próprio processo."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {"user_seconds": usage.ru_utime, "system_seconds": usage.ru_stime, "max_rss_kib": usage.ru_maxrss,
            "threads": len(os.listdir("/proc/self/task")), "thread_affinities": thread_affinities()}


def reset_peak_rss() -> bool:
    """Zera o pico de memória residente do processo (VmHWM). Devolve False quando o kernel não permite."""
    try:
        Path("/proc/self/clear_refs").write_text("5")
    except OSError:
        return False
    return True


def peak_rss_kib() -> int | None:
    """Pico de memória residente do processo desde o início ou desde o último reset_peak_rss."""
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1])
    return None


def start_phase() -> dict[str, Any]:
    """Marca o início de uma fase do processo: guarda o uso de CPU até aqui e zera o pico de memória."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {"user_seconds": usage.ru_utime, "system_seconds": usage.ru_stime, "peak_reset": reset_peak_rss()}


def phase_usage(start: dict[str, Any]) -> dict[str, Any]:
    """CPU usada desde start_phase e pico de memória residente da fase, com as threads e as CPUs do processo."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {"user_seconds": usage.ru_utime - start["user_seconds"],
            "system_seconds": usage.ru_stime - start["system_seconds"],
            "max_rss_kib": peak_rss_kib() if start["peak_reset"] else usage.ru_maxrss,
            "peak_since_phase_start": start["peak_reset"],
            "threads": len(os.listdir("/proc/self/task")), "thread_affinities": thread_affinities()}


def children_usage() -> dict[str, Any]:
    """CPU e o maior pico de memória entre os processos filhos já encerrados, somados pelo sistema."""
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {"user_seconds": usage.ru_utime, "system_seconds": usage.ru_stime, "max_rss_kib": usage.ru_maxrss}


def memory_available_kib() -> int | None:
    """Memória disponível na máquina, segundo o kernel."""
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1])
    return None
