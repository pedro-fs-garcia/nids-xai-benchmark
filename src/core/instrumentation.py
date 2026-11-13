"""Marcações de tempo do NIDS. Único ponto que define o relógio de t1, t2 e t3 e sua base comum com t0."""

import time

# t0 é lido no extrator Java com System.nanoTime(), que no Linux usa CLOCK_MONOTONIC.
# t1, t2 e t3 são lidos aqui com time.monotonic_ns(), que usa o mesmo relógio.
monotonic_ns = time.monotonic_ns


def verify_shared_clock(remote_ns: int, tolerance_ns: int) -> int:
    """Confere que uma leitura do extrator e a leitura local usam o mesmo relógio.

    A leitura local é feita depois da remota, então a diferença deve ser não negativa e pequena.
    Relógios de bases diferentes dariam uma diferença negativa ou da ordem do tempo desde o boot.
    """
    difference = monotonic_ns() - remote_ns
    if not 0 <= difference <= tolerance_ns:
        raise ValueError(f"O extrator e o NIDS não compartilham o relógio monotônico (diferença de {difference} ns).")
    return difference
