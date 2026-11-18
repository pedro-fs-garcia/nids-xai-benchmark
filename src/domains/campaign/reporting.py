"""Relatório legível da análise de uma matriz de ensaios."""

from typing import Any

MODEL_NAMES = {"random-forest": "RF", "xgboost": "XGB"}
CONFIGURATION_NAMES = {"sem-xai": "Sem XAI", "sincrono-total": "Síncrono total",
                       "sincrono-condicional-probabilidade": "Condicional (probabilidade)",
                       "sincrono-condicional-incerteza": "Condicional (incerteza)", "assincrono": "Assíncrono"}


def render_analysis(summary: dict[str, Any]) -> str:
    trials = summary["trials"]
    measured = [trial for trial in trials if "timings" in trial]
    lines = [
        f"# Análise da matriz `{summary['matrix']}`",
        "",
        f"A matriz tem {summary['cells']} células, no trecho `{summary['segment']}`. {summary['done']} têm um ensaio "
        f"válido, {len(summary['exhausted'])} esgotaram as tentativas e {len(summary['pending'])} estão pendentes. "
        f"O registro tem {summary['attempts']} tentativas. Um ensaio é válido quando termina sem erro, o NIDS passa "
        "nas próprias verificações, o tcpreplay envia todos os pacotes e a máquina fica na tomada. Descartes e "
        "pendências não invalidam um ensaio: são resultados. Os termos seguem o [glossário](../docs/glossario.md).",
        "",
    ]
    invalid = [trial for trial in trials if not trial["valid"]]
    if invalid:
        lines += ["## Tentativas inválidas", "", "| Célula | Tentativa | Motivo |", "|---|---:|---|",
                  *[f"| `{trial['cell']['id']}` | {trial['attempt']} | {'; '.join(trial['reasons'])} |"
                    for trial in invalid], ""]
    lines += [
        "## Carga e descartes",
        "",
        "| Célula | Cópias | Fluxos/s | Pacotes/s | Descartes na captura | Fluxos descartados no extrator | "
        "Maior fila do extrator | Validação |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for trial in measured:
        drops, load = trial["drops"], trial["load"]
        capture = sum(value or 0 for value in (drops["h2_interface"], drops["libpcap"], drops["libpcap_interface"]))
        lines.append(
            f"| {_cell(trial)} | {trial['copies']} | {_decimal(load['flows_per_second'], 1)} | "
            f"{_decimal(load['packets_per_second'], 0)} | {_integer(capture)} | "
            f"{_integer(drops['extractor_queue_flows'])} ({_percent(drops['extractor_queue_share'])}) | "
            f"{_integer(drops['extractor_queue_max'])} | {_validation(trial['validation'])} |")
    lines += [
        "",
        "## Latências",
        "",
        "Em milissegundos. A latência de classificação vai de `t0` a `t3`, e a de explicação, de `t0` a `t4`.",
        "",
        "| Célula | Inferência, média | Classificação, média | Classificação, p95 | Classificação, p99 | "
        "Explicação, p95 | Explicação, p99 | Cobertura explicativa |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for trial in measured:
        timings = trial["timings"]
        lines.append(
            f"| {_cell(trial)} | {_ms(timings, 'inference_ns', 'mean', 3)} | "
            f"{_ms(timings, 'classification_latency_ns', 'mean')} | {_ms(timings, 'classification_latency_ns', 'p95')} | "
            f"{_ms(timings, 'classification_latency_ns', 'p99')} | {_ms(timings, 'explanation_latency_ns', 'p95')} | "
            f"{_ms(timings, 'explanation_latency_ns', 'p99')} | "
            f"{_percent(trial['explanations']['completed_share'])} |")
    queued = [trial for trial in measured if trial["queue"].get("max") is not None]
    if queued:
        lines += [
            "",
            "## Fila de explicações pendentes",
            "",
            "Uma fila que só cresce tem o maior tamanho no fim da execução. Uma fila que se estabiliza ou esvazia "
            "tem, no último décimo da execução, um tamanho menor que o maior.",
            "",
            "| Célula | Solicitadas | Descartadas | Pendentes | Maior tamanho | Posição do maior tamanho | "
            "Maior tamanho no último décimo | Esvaziamento depois da captura (s) |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for trial in queued:
            queue = trial["queue"]
            drain = queue.get("drain_after_end_of_capture_ns")
            lines.append(
                f"| {_cell(trial)} | {_integer(queue['requested'])} | {_integer(queue['dropped'])} | "
                f"{_integer(queue['pending'])} | {_integer(queue['max'])} | "
                f"{_percent(queue['max_at_share_of_run'])} | {_integer(queue['max_in_last_tenth'])} | "
                f"{_decimal(None if drain is None else drain / 1e9, 1)} |")
    lines += [
        "",
        "## Recursos e máquina",
        "",
        "CPU em segundos e pico de memória residente em MiB, de cada processo. O classificador é medido durante a "
        "captura, e o processo explicador, durante o atendimento das solicitações. A frequência é a mediana das "
        "leituras de cada segundo. As CPUs 1 e 3 dividem os núcleos físicos do processo explicador e do "
        "classificador e deveriam ficar ociosas.",
        "",
        "| Célula | CPU classificador | CPU explicador | CPU extrator | Memória classificador | Memória extrator | "
        "Frequência CPU 2 (MHz) | Frequência CPU 0 (MHz) | Maior ocupação das CPUs 1 e 3 | Memória livre mínima |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for trial in measured:
        resources, machine = trial["resources"], trial["machine"]
        busy = [value for value in machine["busy_share_sibling_cpus"].values() if value is not None]
        lines.append(
            f"| {_cell(trial)} | {_resource(resources, 'classifier', 'cpu_seconds')} | "
            f"{_resource(resources, 'explainer', 'cpu_seconds')} | {_resource(resources, 'extractor', 'cpu_seconds')} | "
            f"{_resource(resources, 'classifier', 'max_rss_mib')} | {_resource(resources, 'extractor', 'max_rss_mib')} | "
            f"{_decimal(machine['frequency_mhz']['2'], 0)} | {_decimal(machine['frequency_mhz']['0'], 0)} | "
            f"{_percent(max(busy) if busy else None)} | {_decimal(machine['memory_available_mib_min'], 0)} |")
    if summary["variability"]:
        lines += [
            "",
            "## Variação entre ensaios da mesma combinação",
            "",
            "Em milissegundos: mínimo, mediana e máximo entre os ensaios válidos, e a amplitude relativa à mediana.",
            "",
            "| Combinação | Ensaios | Inferência, média | Classificação, p95 | Classificação, p99 |",
            "|---|---:|---|---|---|",
            *[f"| {MODEL_NAMES[item['model']]}, {CONFIGURATION_NAMES[item['configuration']]}, {item['load']} "
              f"{'cópia' if item['load'] == 1 else 'cópias'} | {item['trials']} | "
              f"{_spread(item['inference_ns_mean'])} | {_spread(item['classification_latency_ns_p95'])} | "
              f"{_spread(item['classification_latency_ns_p99'])} |" for item in summary["variability"]],
        ]
    if summary["acceleration_run"]:
        lines += ["", f"O efeito da aceleração da reprodução está em `{summary['acceleration_run']}`."]
    lines += [
        "",
        "## Reprodução",
        "",
        "```bash",
        f"cd src && python main.py matriz-analisar --matriz ../{summary['matrix_config']}",
        "```",
        "",
        f"O registro dos ensaios está em `{summary['registry']}`, e o da análise, em "
        f"`training-runs/nids/analise-{summary['matrix']}/{summary['run_id']}/report.json`.",
        "",
    ]
    return "\n".join(lines)


def _cell(trial: dict[str, Any]) -> str:
    cell = trial["cell"]
    return (f"{MODEL_NAMES[cell['model']]}, {CONFIGURATION_NAMES[cell['configuration']]}, {cell['load']}× "
            f"(`{cell['block']}`, rep. {cell['repetition']})")


def _validation(validation: dict[str, Any] | None) -> str:
    if not validation:
        return "—"
    if validation["status"] != "aprovada":
        return validation["status"]
    return (f"aprovada; só no arquivo {_integer(validation['file_only_inside'])}, só na reprodução "
            f"{_integer(validation['replay_only_inside'])}, previsões diferentes "
            f"{_integer(validation['predictions_differing'])}")


def _ms(timings: dict[str, Any], key: str, stat: str, digits: int = 1) -> str:
    return "—" if key not in timings else _decimal(timings[key][stat] / 1e6, digits)


def _resource(resources: dict[str, Any], name: str, key: str) -> str:
    return "—" if not resources.get(name) else _decimal(resources[name][key], 0)


def _spread(spread: dict[str, float] | None) -> str:
    if not spread:
        return "—"
    return (f"{_decimal(spread['min'], 2)} / {_decimal(spread['median'], 2)} / {_decimal(spread['max'], 2)} "
            f"({_percent(spread['relative_range'])})")


def _integer(value: int | None) -> str:
    return "—" if value is None else f"{value:,}".replace(",", ".")


def _decimal(value: float | None, digits: int) -> str:
    if value is None:
        return "—"
    return f"{value:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _percent(share: float | None) -> str:
    return "—" if share is None else _decimal(share * 100, 1) + "%"
