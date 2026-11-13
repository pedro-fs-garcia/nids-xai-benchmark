import argparse
import json
import sys
from pathlib import Path
from typing import Any

from config import get_settings
from domains.traffic_preparation.dependencies import get_traffic_preparation_service


def register(subparsers: Any) -> None:
    prepare = subparsers.add_parser("preparar-pcap", help="Verifica, corrige, reordena e corta o PCAP de entrada.")
    prepare.add_argument("--config", type=Path, default=get_settings().pcap_preparation_config)
    prepare.set_defaults(handler=run_prepare)
    check = subparsers.add_parser("conferir-extracao", help="Compara a extração de um trecho com os fluxos rotulados.")
    check.add_argument("--config", type=Path, default=get_settings().pcap_preparation_config)
    check.add_argument("--trecho", required=True)
    check.set_defaults(handler=run_check)


def run_prepare(args: argparse.Namespace) -> int:
    return _execute(lambda: get_traffic_preparation_service(args.config).prepare())


def run_check(args: argparse.Namespace) -> int:
    return _execute(lambda: get_traffic_preparation_service(args.config).check_extraction(args.trecho))


def _execute(operation: Any) -> int:
    try:
        result = operation()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        print(f"Erro no tráfego de entrada: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"path": str(result.path), "report": str(result.report_path) if result.report_path else None,
                      "passed": result.summary.get("passed", True)}, ensure_ascii=False))
    return 0
