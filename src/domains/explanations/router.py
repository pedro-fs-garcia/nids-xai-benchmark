import argparse
import json
import sys
from pathlib import Path
from typing import Any

from config import get_settings
from domains.explanations.dependencies import get_explanation_service
from domains.explanations.schemas import MODELS


def register(subparsers: Any) -> None:
    for command, handler, help_text in (
        ("explicar-exemplo", run_example, "Explica um registro da validação com o Random Forest piloto."),
        ("validar-treeshap", run_validate, "Verifica o TreeSHAP nos dois modelos congelados, na validação."),
        ("medir-treeshap", run_measure, "Mede inferência e TreeSHAP isolados, em processos novos."),
    ):
        parser = subparsers.add_parser(command, help=help_text)
        parser.add_argument("--config", type=Path, default=get_settings().tree_shap_config)
        if command == "medir-treeshap":
            parser.add_argument("--validacao", type=Path, required=True,
                                help="Diretório de uma execução aprovada de validar-treeshap.")
        parser.set_defaults(handler=handler)
    process = subparsers.add_parser("medir-treeshap-processo", help="Uso interno de medir-treeshap: uma repetição.")
    process.add_argument("--run-dir", type=Path, required=True)
    process.add_argument("--modelo", choices=MODELS, required=True)
    process.add_argument("--repeticao", type=int, required=True)
    process.set_defaults(handler=run_measure_process)


def run_example(args: argparse.Namespace) -> int:
    return _execute(lambda: _summary(get_explanation_service(args.config).explain_example()))


def run_validate(args: argparse.Namespace) -> int:
    return _execute(lambda: _summary(get_explanation_service(args.config).validate()))


def run_measure(args: argparse.Namespace) -> int:
    return _execute(lambda: _summary(get_explanation_service(args.config).measure(args.validacao.resolve())))


def run_measure_process(args: argparse.Namespace) -> int:
    return _execute(lambda: get_explanation_service().measure_process(args.run_dir.resolve(), args.modelo,
                                                                      args.repeticao))


def _summary(result: Any) -> dict[str, Any]:
    return {"run_dir": str(result.run_dir), "report": str(result.report_path),
            "passed": result.summary.get("passed", True)}


def _execute(operation: Any) -> int:
    try:
        result = operation()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        print(f"Erro no TreeSHAP: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0
