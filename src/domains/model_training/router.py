import argparse
import sys
from typing import Any

from domains.model_training.dependencies import get_model_training_service
from domains.model_training.exceptions import ModelTrainingError


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "treinar-rf-piloto", help="Treina o primeiro Random Forest e avalia na validação."
    )
    parser.set_defaults(handler=run)


def run(_args: argparse.Namespace) -> int:
    try:
        result = get_model_training_service().run_pilot()
    except ModelTrainingError as error:
        print(f"Erro no treinamento: {error}", file=sys.stderr)
        return 1
    summary = result.summary
    metrics = summary["validation"]["metrics"]
    resources = summary["resources"]
    print(f"Amostra de treino: {summary['sample']['records']} registros")
    print(f"Validação: {summary['validation']['records']} registros")
    print(f"Matriz de confusão: {metrics['confusion_matrix']}")
    for name in ("precision", "recall", "f1", "false_positive_rate", "roc_auc"):
        print(f"{name}: {metrics[name]:.6f}")
    print(f"Tempo de ajuste: {resources['fit_seconds']:.3f} s")
    print(f"Pico de memória do processo: {resources['peak_process_memory_mib']:.1f} MiB")
    print(f"Modelo: {result.run_dir / 'model.joblib'}")
    print(f"Relatório: {result.report_path}")
    return 0
