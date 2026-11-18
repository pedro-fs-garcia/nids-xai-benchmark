"""Estado da máquina durante um ensaio, lido uma vez por segundo numa thread à parte do NIDS.

Cada leitura registra a fonte de energia, a frequência e a contagem de limitações térmicas de cada CPU, a fração
de tempo ocupado de cada CPU, a memória disponível e o swap livre. Antes de um ensaio, a mesma leitura confere se
a máquina está na tomada, ociosa e com memória disponível.

Só a biblioteca padrão é usada, porque o script de emulação roda com o Python do sistema."""

import json
import os
import statistics
import threading
import time
from pathlib import Path
from typing import Any

CPU_ROOT = Path("/sys/devices/system/cpu")
POWER_ROOT = Path("/sys/class/power_supply")


def _read(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except OSError:
        return None


def mains_online() -> bool | None:
    """Fonte de energia externa ligada. None quando a máquina não informa."""
    for supply in sorted(POWER_ROOT.glob("*")):
        if _read(supply / "type") == "Mains":
            return _read(supply / "online") == "1"
    return None


def frequencies_khz(cpus: list[int]) -> dict[int, int | None]:
    values = {cpu: _read(CPU_ROOT / f"cpu{cpu}" / "cpufreq" / "scaling_cur_freq") for cpu in cpus}
    return {cpu: None if value is None else int(value) for cpu, value in values.items()}


def throttle_counts(cpus: list[int]) -> dict[int, dict[str, int | None]]:
    """Contagens de limitação térmica do núcleo e do pacote, acumuladas desde o início do sistema."""
    result = {}
    for cpu in cpus:
        folder = CPU_ROOT / f"cpu{cpu}" / "thermal_throttle"
        values = {name: _read(folder / f"{name}_throttle_count") for name in ("core", "package")}
        result[cpu] = {name: None if value is None else int(value) for name, value in values.items()}
    return result


def cpu_times() -> dict[int, tuple[int, int]]:
    """Tempo ocupado e tempo total de cada CPU, em unidades do relógio do kernel, desde o início do sistema."""
    times = {}
    for line in Path("/proc/stat").read_text().splitlines():
        name, *fields = line.split()
        if not name.startswith("cpu") or name == "cpu":
            continue
        values = [int(value) for value in fields[:8]]
        idle = values[3] + values[4]
        times[int(name[3:])] = (sum(values) - idle, sum(values))
    return times


def busy_shares(before: dict[int, tuple[int, int]], after: dict[int, tuple[int, int]]) -> dict[int, float]:
    """Fração do tempo em que cada CPU esteve ocupada entre duas leituras de cpu_times."""
    shares = {}
    for cpu, (busy, total) in after.items():
        previous_busy, previous_total = before.get(cpu, (busy, total))
        elapsed = total - previous_total
        shares[cpu] = (busy - previous_busy) / elapsed if elapsed > 0 else 0.0
    return shares


def memory_kib() -> dict[str, int | None]:
    fields = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        name, _, value = line.partition(":")
        fields[name] = int(value.split()[0])
    return {"available": fields.get("MemAvailable"), "swap_free": fields.get("SwapFree"),
            "swap_total": fields.get("SwapTotal")}


def readiness(require_mains: bool, max_busy_share: float, min_available_mib: int, window_s: float) -> dict[str, Any]:
    """Confere, numa janela de tempo, se a máquina está pronta para um ensaio e diz o que falta."""
    before = cpu_times()
    time.sleep(window_s)
    shares = busy_shares(before, cpu_times())
    busy = sum(shares.values()) / len(shares) if shares else 0.0
    mains, memory = mains_online(), memory_kib()
    reasons = []
    if require_mains and mains is not True:
        reasons.append("fora da tomada")
    if busy > max_busy_share:
        reasons.append(f"CPU ocupada em {busy:.1%}, acima de {max_busy_share:.1%}")
    if (memory["available"] or 0) < min_available_mib * 1024:
        reasons.append(f"{(memory['available'] or 0) // 1024} MiB de memória disponível, abaixo de "
                       f"{min_available_mib} MiB")
    return {"ready": not reasons, "reasons": reasons, "mains_online": mains, "busy_share": busy,
            "busy_share_by_cpu": {str(cpu): share for cpu, share in shares.items()},
            "memory_kib": memory, "window_s": window_s}


def wait_until_ready(settings: dict[str, Any], log: Any = None) -> dict[str, Any]:
    """Repete a conferência até a máquina ficar pronta ou o tempo máximo de espera acabar."""
    deadline = time.monotonic() + settings["max_wait_s"]
    attempts = 0
    while True:
        attempts += 1
        check = readiness(settings["require_mains"], settings["max_busy_share"], settings["min_available_mib"],
                          settings["window_s"])
        if check["ready"] or time.monotonic() >= deadline:
            return {**check, "attempts": attempts, "settings": settings}
        if log is not None:
            log("Máquina não está pronta: " + "; ".join(check["reasons"]) + ". Nova conferência em 30 s.")
        time.sleep(min(30.0, max(0.0, deadline - time.monotonic())))


class MachineSampler:
    """Thread que grava uma linha JSON por segundo com o estado da máquina, fixa nas CPUs dadas."""

    def __init__(self, path: Path, pinned_cpus: list[int], interval_s: float = 1.0) -> None:
        self.path = path
        self.pinned_cpus = pinned_cpus
        self.interval_s = interval_s
        self.cpus = sorted(cpu_times())
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="amostrador", daemon=True)
        self._samples: list[dict[str, Any]] = []

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        self._thread.join()
        return summarize(self._samples, self.cpus)

    def _run(self) -> None:
        # Na thread, o identificador 0 fixa só a própria thread.
        os.sched_setaffinity(0, set(self.pinned_cpus))
        previous = cpu_times()
        with self.path.open("w", encoding="utf-8") as stream:
            while not self._stop.wait(self.interval_s):
                current = cpu_times()
                sample = {"monotonic_ns": time.monotonic_ns(), "mains_online": mains_online(),
                          "frequency_khz": frequencies_khz(self.cpus), "throttle": throttle_counts(self.cpus),
                          "busy_share": busy_shares(previous, current), "memory_kib": memory_kib()}
                previous = current
                self._samples.append(sample)
                stream.write(json.dumps(sample) + "\n")
                stream.flush()


def summarize(samples: list[dict[str, Any]], cpus: list[int]) -> dict[str, Any]:
    """Resumo das leituras: fonte de energia, frequência, limitações térmicas, ocupação e memória."""
    if not samples:
        return {"samples": 0}

    def spread(values: list[float]) -> dict[str, float] | None:
        values = [value for value in values if value is not None]
        if not values:
            return None
        return {"min": min(values), "median": statistics.median(values), "max": max(values)}

    first, last = samples[0]["throttle"], samples[-1]["throttle"]
    throttles = {}
    for cpu in cpus:
        deltas = {name: (last[cpu][name] - first[cpu][name]) if last[cpu][name] is not None
                  and first[cpu][name] is not None else None for name in ("core", "package")}
        throttles[str(cpu)] = deltas
    return {
        "samples": len(samples),
        "mains_online_in_every_sample": all(sample["mains_online"] is True for sample in samples),
        "frequency_khz": {str(cpu): spread([sample["frequency_khz"][cpu] for sample in samples]) for cpu in cpus},
        "throttle_events": throttles,
        "busy_share": {str(cpu): spread([sample["busy_share"][cpu] for sample in samples]) for cpu in cpus},
        "memory_available_kib": spread([sample["memory_kib"]["available"] for sample in samples]),
        "swap_free_kib": spread([sample["memory_kib"]["swap_free"] for sample in samples]),
    }
