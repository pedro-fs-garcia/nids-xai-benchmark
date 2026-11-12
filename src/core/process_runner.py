"""Execução de um comando Python em um interpretador novo."""

import json
import os
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any


class PythonProcessRunner:
    def run(self, arguments: list[str], cpus: Iterable[int] | None = None) -> dict[str, Any]:
        source = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, str(source / "main.py"), *arguments],
            cwd=source, capture_output=True, text=True, check=False,
            preexec_fn=_pin_to(set(cpus)) if cpus is not None else None,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return json.loads(result.stdout)


def _pin_to(cpus: set[int]) -> Callable[[], None]:
    # A afinidade é aplicada antes do interpretador iniciar, e todas as threads do processo a herdam.
    def pin() -> None:
        os.sched_setaffinity(0, cpus)

    return pin
