from dataclasses import dataclass
from pathlib import Path
from typing import Any

MODELS = ("random-forest", "xgboost")
# Nome de cada estratégia de explicação no glossário, pela opção de linha de comando.
STRATEGIES = {"sem-xai": "Sem XAI", "sincrono-total": "Síncrono total",
              "sincrono-condicional": "Síncrono condicional", "assincrono": "Assíncrono"}
# Critérios de seleção do Síncrono condicional e o maior limiar que cada um admite.
CRITERIA = {"probabilidade": 1.0, "incerteza": 0.5}


@dataclass(frozen=True)
class NidsConfig:
    path: Path
    sha256: str
    content: dict[str, Any]
    frozen_run: Path
    preparation_manifest: Path
    tree_shap_config: Path
    selection: dict[str, Any]
    explanation_queue: dict[str, Any]
    resources: dict[str, Any]
    extractor: dict[str, int]
    classifier_threads: int
    shared_clock_tolerance_ns: int


@dataclass(frozen=True)
class CommandResult:
    run_dir: Path
    report_path: Path
    summary: dict[str, Any]
