"""Execução de um comando Python em um interpretador novo."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class PythonProcessRunner:
    def run(self, arguments: list[str]) -> dict[str, Any]:
        source = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, str(source / "main.py"), *arguments],
            cwd=source, capture_output=True, text=True, check=False,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return json.loads(result.stdout)
