import argparse
import json
import sys
from pathlib import Path
from typing import Any

from config import get_settings
from domains.nids.dependencies import get_nids_service
from domains.nids.schemas import MODELS


def register(subparsers: Any) -> None:
    run = subparsers.add_parser("nids-executar", help="Executa o NIDS de referência, sem explicações.")
    run.add_argument("--config", type=Path, default=get_settings().nids_config)
    run.add_argument("--modelo", choices=MODELS, required=True)
    run.add_argument("--trecho", help="Trecho preparado por preparar-pcap. Sem --interface, é lido do arquivo.")
    run.add_argument("--pcap", type=Path, help="Arquivo PCAP qualquer, sem conferência com a tabela de referência.")
    run.add_argument("--interface", help="Interface de rede para a captura ao vivo.")
    run.add_argument("--sinal-pronto", type=Path, help="Arquivo criado quando a captura está aberta.")
    run.set_defaults(handler=run_nids)
    validate = subparsers.add_parser("nids-validar", help="Compara uma execução reproduzida com a do mesmo arquivo.")
    validate.add_argument("--config", type=Path, default=get_settings().nids_config)
    validate.add_argument("--reproduzida", type=Path, required=True)
    validate.add_argument("--arquivo", type=Path, required=True)
    validate.set_defaults(handler=run_validate)


def run_nids(args: argparse.Namespace) -> int:
    return _execute(lambda: get_nids_service(args.config).run(
        args.modelo, pcap=args.pcap, interface=args.interface, segment=args.trecho, ready_file=args.sinal_pronto))


def run_validate(args: argparse.Namespace) -> int:
    return _execute(lambda: get_nids_service(args.config).validate(args.reproduzida.resolve(), args.arquivo.resolve()))


def _execute(operation: Any) -> int:
    try:
        result = operation()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        print(f"Erro no NIDS: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"run_dir": str(result.run_dir), "report": str(result.report_path),
                      "passed": result.summary.get("passed", True)}, ensure_ascii=False))
    return 0
