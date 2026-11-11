import argparse
import json
import sys
from pathlib import Path
from typing import Any

from config import get_settings
from domains.model_artifacts.dependencies import get_model_artifact_service


def register(subparsers: Any) -> None:
    freeze = subparsers.add_parser("congelar-modelos", help="Salva o contrato e verifica os modelos em novos processos.")
    freeze.add_argument("--config", type=Path, default=get_settings().model_freezing_config)
    freeze.set_defaults(handler=run_freeze)
    for command, handler, help_text in (
        ("verificar-modelo", run_verify, "Compara o modelo carregado com as previsões salvas do teste."),
        ("classificar-fluxo", run_predict, "Classifica os atributos de um fluxo em JSON."),
    ):
        parser = subparsers.add_parser(command, help=help_text)
        parser.add_argument("--artifact", type=Path, required=True)
        if command == "verificar-modelo":
            parser.add_argument("--data-dir", type=Path)
        else:
            parser.add_argument("--input", type=Path, required=True)
        parser.set_defaults(handler=handler)


def run_freeze(args: argparse.Namespace) -> int:
    return execute(lambda: _freeze(args))


def _freeze(args: argparse.Namespace) -> dict[str, Any]:
    result = get_model_artifact_service().freeze(args.config)
    return {"run_dir": str(result.run_dir), "models": result.models}


def run_verify(args: argparse.Namespace) -> int:
    return execute(lambda: get_model_artifact_service(args.data_dir).verify(args.artifact))


def run_predict(args: argparse.Namespace) -> int:
    return execute(lambda: get_model_artifact_service().predict_flow(args.artifact, args.input))


def execute(operation: Any) -> int:
    try:
        result = operation()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        print(f"Erro no artefato do modelo: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0
