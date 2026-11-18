import argparse
import json
import sys
from pathlib import Path
from typing import Any

from config import get_settings
from domains.nids.dependencies import get_nids_service
from domains.nids.schemas import CRITERIA, MODELS, STRATEGIES


def register(subparsers: Any) -> None:
    run = subparsers.add_parser("nids-executar", help="Executa o NIDS com uma estratégia de explicação.")
    run.add_argument("--config", type=Path, default=get_settings().nids_config)
    run.add_argument("--modelo", choices=MODELS, required=True)
    run.add_argument("--estrategia", choices=tuple(STRATEGIES), default="sem-xai",
                     help="Estratégia de explicação. O padrão é sem-xai.")
    run.add_argument("--criterio", choices=tuple(CRITERIA),
                     help="Critério de seleção do sincrono-condicional, com o limiar fixado na configuração.")
    run.add_argument("--trecho", help="Trecho preparado por preparar-pcap. Sem --interface, é lido do arquivo.")
    run.add_argument("--pcap", type=Path, help="Arquivo PCAP qualquer, sem conferência com a tabela de referência.")
    run.add_argument("--interface", help="Interface de rede para a captura ao vivo.")
    run.add_argument("--sinal-pronto", type=Path, help="Arquivo criado quando a captura está aberta.")
    run.set_defaults(handler=run_nids)
    calibration = subparsers.add_parser(
        "calibrar-selecao", help="Mostra, na validação, o que cada critério de seleção escolhe, por limiar.")
    calibration.add_argument("--config", type=Path, default=get_settings().nids_config)
    calibration.set_defaults(handler=run_calibration)
    compare = subparsers.add_parser(
        "nids-comparar-estrategias", help="Confere a comparabilidade de execuções das quatro estratégias.")
    compare.add_argument("--config", type=Path, default=get_settings().nids_config)
    compare.add_argument("--execucoes", type=Path, nargs="+", required=True,
                         help="Pastas das execuções do mesmo modelo e da mesma fonte, uma por estratégia e critério.")
    compare.set_defaults(handler=run_compare)
    copy = subparsers.add_parser(
        "nids-conferir-copia", help="Confere, sem rede, que uma cópia do trecho produz os mesmos fluxos do original.")
    copy.add_argument("--config", type=Path, default=get_settings().nids_config)
    copy.add_argument("--modelo", choices=MODELS, required=True)
    copy.add_argument("--trecho", required=True)
    copy.add_argument("--numero", type=int, required=True, help="Número da cópia, de 2 em diante.")
    copy.add_argument("--original", type=Path, required=True,
                      help="Execução por arquivo do trecho original, com o mesmo modelo, sem XAI.")
    copy.set_defaults(handler=run_copy_check)
    acceleration = subparsers.add_parser(
        "nids-efeito-aceleracao", help="Mede, sem rede, como a reprodução acelerada muda fluxos e previsões.")
    acceleration.add_argument("--config", type=Path, default=get_settings().nids_config)
    acceleration.add_argument("--trecho", required=True)
    acceleration.add_argument("--fatores", type=float, nargs="+", required=True)
    acceleration.add_argument("--originais", type=Path, nargs="+", required=True,
                              help="Leituras por arquivo do trecho, sem XAI, uma por classificador.")
    acceleration.set_defaults(handler=run_acceleration)
    validate = subparsers.add_parser("nids-validar", help="Compara uma execução reproduzida com a do mesmo arquivo.")
    validate.add_argument("--config", type=Path, default=get_settings().nids_config)
    validate.add_argument("--reproduzida", type=Path, required=True)
    validate.add_argument("--arquivo", type=Path, required=True)
    validate.set_defaults(handler=run_validate)


def run_nids(args: argparse.Namespace) -> int:
    return _execute(lambda: get_nids_service(args.config).run(
        args.modelo, pcap=args.pcap, interface=args.interface, segment=args.trecho, ready_file=args.sinal_pronto,
        strategy_key=args.estrategia, criterion=args.criterio))


def run_compare(args: argparse.Namespace) -> int:
    return _execute(lambda: get_nids_service(args.config).compare_strategies(
        [path.resolve() for path in args.execucoes]))


def run_calibration(args: argparse.Namespace) -> int:
    return _execute(lambda: get_nids_service(args.config).calibrate_selection())


def run_copy_check(args: argparse.Namespace) -> int:
    return _execute(lambda: get_nids_service(args.config).check_copy(
        args.modelo, args.trecho, args.numero, args.original.resolve()))


def run_acceleration(args: argparse.Namespace) -> int:
    return _execute(lambda: get_nids_service(args.config).acceleration_effect(
        args.trecho, args.fatores, [path.resolve() for path in args.originais]))


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
