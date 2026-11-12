"""Ponto de entrada do projeto. Monta os subcomandos."""

import argparse
import sys
from collections.abc import Sequence

from domains.data_preparation import router as data_preparation_router
from domains.model_training import router as model_training_router
from domains.model_artifacts import router as model_artifacts_router
from domains.explanations import router as explanations_router


def verify_environment(_args: argparse.Namespace) -> int:
    """Importa o scikit-learn e carrega o conjunto Iris, sem treinar nenhum modelo."""
    import sklearn
    from sklearn.datasets import load_iris

    print(f"scikit-learn {sklearn.__version__}")

    iris = load_iris()
    classes = [str(name) for name in iris.target_names]
    print(f"Exemplo carregado: Iris, {iris.data.shape[0]} amostras, "
          f"{iris.data.shape[1]} atributos, classes {classes}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Comandos do projeto.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    environment = subparsers.add_parser(
        "verificar-ambiente", help="Confere se as bibliotecas do ambiente estão instaladas."
    )
    environment.set_defaults(handler=verify_environment)
    data_preparation_router.register(subparsers)
    model_training_router.register(subparsers)
    model_artifacts_router.register(subparsers)
    explanations_router.register(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handler = args.handler
    return int(handler(args))


if __name__ == "__main__":
    sys.exit(main())
