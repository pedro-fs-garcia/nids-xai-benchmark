import argparse
import sys
from typing import Any

from domains.model_training.dependencies import get_forest_comparison_service, get_model_training_service
from domains.model_training.exceptions import ModelTrainingError


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "treinar-rf-piloto", help="Treina o primeiro Random Forest e avalia na validação."
    )
    parser.set_defaults(handler=run)
    comparison = subparsers.add_parser(
        "comparar-rf", help="Compara três configurações e avalia o modelo escolhido no teste."
    )
    comparison.set_defaults(handler=run_comparison)


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


def run_comparison(_args: argparse.Namespace) -> int:
    try:
        result = get_forest_comparison_service().run(progress=lambda message: print(message, flush=True))
    except ModelTrainingError as error:
        print(f"Erro na comparação: {error}", file=sys.stderr)
        return 1
    final = result.summary["final"]
    print(f"Configuração selecionada: {result.summary['selection']['selected']}")
    print(f"Registros do treino completo: {final['training_records']}")
    print(f"Métricas no teste: {final['test']['metrics']}")
    print(f"Modelo: {result.run_dir / 'final' / 'model.joblib'}")
    print(f"Relatório: {result.report_path}")
    return 0
