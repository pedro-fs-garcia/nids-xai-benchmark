import argparse
import json
import sys
from pathlib import Path
from typing import Any

from domains.campaign.dependencies import get_campaign_service


def register(subparsers: Any) -> None:
    analyze = subparsers.add_parser(
        "matriz-analisar", help="Valida e resume os ensaios de uma matriz executada na rede emulada.")
    analyze.add_argument("--matriz", type=Path, required=True, help="Configuração da matriz, em configs/.")
    analyze.add_argument("--aceleracao", type=Path, help="Pasta da medição do efeito da aceleração, se houver.")
    analyze.set_defaults(handler=run_analysis)


def run_analysis(args: argparse.Namespace) -> int:
    try:
        result = get_campaign_service().analyze(args.matriz.resolve(),
                                                None if args.aceleracao is None else args.aceleracao.resolve())
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        print(f"Erro na análise da matriz: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"run_dir": str(result.run_dir), "report": str(result.report_path)}, ensure_ascii=False))
    return 0
