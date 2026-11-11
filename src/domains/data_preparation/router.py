import argparse
import sys
from typing import Any

from domains.data_preparation.dependencies import get_data_preparation_service
from domains.data_preparation.exceptions import DataPreparationError

COMMAND = "preparar-dados"


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        COMMAND,
        help="Gera os conjuntos de treino, validação e teste a partir dos CSVs originais.",
    )
    parser.set_defaults(handler=run)


def run(_args: argparse.Namespace) -> int:
    try:
        report = get_data_preparation_service().prepare()
    except DataPreparationError as error:
        print(f"Erro na preparação dos dados: {error}", file=sys.stderr)
        return 1

    manifest = report.manifest
    records = manifest["records"]
    print(f"Registros: {records['total']} ({records['benign']} benignos, {records['attack']} ataques)")
    print(f"Registros com taxa infinita substituída: {records['with_replaced_infinite_rate']}")
    print(
        f"Grupos de entradas idênticas: {records['groups']} "
        f"({records['groups_with_several_records']} com mais de um registro)"
    )
    for name, split in manifest["splits"].items():
        print(
            f"{name}: {split['records']} registros ({split['fraction']:.2%}), "
            f"{split['attack_fraction']:.2%} de ataques"
        )
    print("Verificações aprovadas: " + ", ".join(manifest["verifications"]))
    print(f"Pico de memória: {manifest['execution']['peak_memory_mb']} MB")
    print(f"Manifesto: {report.manifest_path}")
    return 0
