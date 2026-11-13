"""Relatórios legíveis das execuções e da validação do NIDS de referência."""

from typing import Any

MODEL_NAMES = {"random-forest": "Random Forest", "xgboost": "XGBoost"}
CAUSES = {
    "timeout_sweep": "varredura do tempo limite",
    "timeout_next_packet": "tempo limite, no pacote seguinte",
    "tcp_new_connection": "nova conexão TCP depois do encerramento",
    "icmp_change": "mudança de código e tipo ICMP",
    "end_of_capture": "fim da captura",
}
CHECKS = {
    "emitted_equals_received": "Fluxos emitidos pelo extrator = fluxos recebidos pelo classificador",
    "received_equals_classified_plus_errors": "Fluxos recebidos = classificados + erros",
    "timestamps_ordered": "t0 ≤ t1 ≤ t2 ≤ t3 em todos os fluxos classificados",
    "no_packets_after_emission_in_file_mode": "Nenhum pacote chegou a um fluxo já emitido (modo arquivo)",
}


def render_run(summary: dict[str, Any]) -> str:
    flows, timings, end = summary["flows"], summary["timings"], summary["extractor_end"]
    source = summary["source"]
    origin = (f"o arquivo `{source.get('pcap')}`" if source["kind"] == "arquivo"
              else f"a interface `{source.get('iface')}`")
    lines = [
        f"# Execução do NIDS de referência: {MODEL_NAMES[summary['model']]}, {source['kind']}",
        "",
        f"A execução {'passou' if summary['passed'] else 'não passou'} nas verificações. O NIDS leu {origin}, "
        f"formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o "
        f"{MODEL_NAMES[summary['model']]} congelado, na estratégia Sem XAI. Os termos seguem o "
        "[glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do "
        "[protocolo](protocolo-experimental.md).",
        "",
    ]
    if summary["segment"]:
        lines += [f"O tráfego é o trecho `{summary['segment']['name']}` da captura de terça-feira, até "
                  f"`{summary['segment']['stop']}` (UTC).", ""]
    lines += [
        "## Contadores",
        "",
        "| Contador | Valor |",
        "|---|---:|",
        f"| Pacotes lidos | {_integer(end.get('packets_read', 0))} |",
        f"| Pacotes IPv4 usados na formação dos fluxos | {_integer(end.get('packets_valid', 0))} |",
        f"| Pacotes descartados por não serem IPv4 | {_integer(end.get('packets_discarded', 0))} |",
        f"| Pacotes que chegaram a um fluxo já emitido | {_integer(end.get('packets_after_emission', 0))} |",
        f"| Fluxos emitidos pelo extrator | {_integer(end.get('flows_emitted', 0))} |",
        f"| Fluxos recebidos pelo classificador | {_integer(flows['received'])} |",
        f"| Fluxos classificados | {_integer(flows['classified'])} |",
        f"| Fluxos com erro nas entradas | {_integer(flows['errors'])} |",
        "",
    ]
    if end.get("pcap_stats"):
        stats = end["pcap_stats"]
        lines += [f"Estatísticas do libpcap: {_integer(stats['received'])} pacotes recebidos, "
                  f"{_integer(stats['dropped'])} descartados por falta de espaço no buffer e "
                  f"{_integer(stats['interface_dropped'])} descartados pela interface.", ""]
    lines += ["Causas de emissão: " + ", ".join(
        f"{CAUSES.get(cause, cause)} ({_integer(count)})" for cause, count in flows["by_cause"].items()) + ".", ""]
    if flows["error_examples"]:
        lines += ["Exemplos de erro: " + "; ".join(f"fluxo {item['seq']} (`{item['flow_id']}`): {item['error']}"
                                                   for item in flows["error_examples"]) + ".", ""]
    lines += ["## Verificações", "", "| Verificação | Resultado |", "|---|---|",
              *[f"| {CHECKS[name]} | {'aprovada' if value else 'reprovada'} |"
                for name, value in summary["checks"].items()], ""]
    conference = summary.get("conference")
    if conference:
        lines += [
            "## Conferência com a tabela de referência",
            "",
            f"Fora da borda dos últimos {summary['segment']['border_seconds']} s, "
            f"{_integer(conference['matched_inside'])} fluxos do NIDS correspondem a fluxos de `tuesday.csv`. "
            f"Ficaram {_integer(conference['reference_only_inside'])} fluxos só no CSV e "
            f"{_integer(conference['nids_only_inside'])} só no NIDS. Destes, "
            f"{_integer(conference['nids_only_inside_with_nan'])} têm algum valor `NaN`: são fluxos de um único "
            "pacote, que a rotulagem dos autores descartou com `dropna` e que o NIDS registra como erro de entrada.",
            "",
            ("As entradas inteiras coincidem exatamente com as do CSV. "
             f"{_integer(conference['rounding_differences'])} valores com fração diferem nos últimos algarismos, com "
             f"diferença relativa de no máximo {conference['max_rounding_relative']:.2g}, como na conferência da extração."
             if not conference["attribute_mismatches"] else "Entradas divergentes: " + ", ".join(
                f"{name} ({_integer(item['mismatches'])})" for name, item in conference["attribute_mismatches"].items())
             + "."),
            "",
            f"O modelo aplicado às linhas da tabela de referência e o NIDS produziram previsões diferentes em "
            f"{_integer(conference['differing_predictions'])} de {_integer(conference['compared_predictions'])} "
            f"fluxos. A maior diferença de probabilidade foi {conference['max_probability_difference']:g}, contra a "
            f"tolerância de {conference['probability_atol']:g}. A conferência não calcula métricas de detecção.",
            "",
        ]
    if timings:
        lines += [
            "## Tempos",
            "",
            "Os tempos abaixo mostram que a instrumentação funciona. A execução não controla a carga, então eles "
            "não são resultados do experimento.",
            "",
            "| Medida | Média (ms) | Mediana (ms) | p95 (ms) | p99 (ms) | Máximo (ms) |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for key, label in (("inference_ns", "Tempo de inferência, t2 − t1"),
                           ("classification_latency_ns", "Latência de classificação, t3 − t0"),
                           ("wait_before_inference_ns", "Espera e preparo da entrada, t1 − t0"),
                           ("delivery_ns", "Entrega no canal de saída, t3 − t2")):
            item = timings[key]
            lines.append(f"| {label} | {_ms(item['mean'])} | {_ms(item['median'])} | {_ms(item['p95'])} | "
                         f"{_ms(item['p99'])} | {_ms(item['max'])} |")
        lines += [""]
    resources = summary["resources"]
    classifier, extractor = resources["classifier_process"], resources["extractor_process"]
    lines += [
        f"O processo do classificador usou {_decimal(classifier['user_seconds'] + classifier['system_seconds'], 1)} s "
        f"de CPU, com pico de {_integer(round(classifier['max_rss_kib'] / 1024))} MiB de memória. O extrator usou "
        f"{_decimal(extractor['user_seconds'] + extractor['system_seconds'], 1)} s de CPU, com pico de "
        f"{_integer(round(extractor['max_rss_kib'] / 1024))} MiB.",
        "",
        f"O registro da execução está em [training-runs/nids/{summary['source']['kind']}/{summary['run_id']}/report.json]"
        f"(../training-runs/nids/{summary['source']['kind']}/{summary['run_id']}/report.json).",
        "",
    ]
    return "\n".join(lines)


def _integer(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _decimal(value: float, digits: int) -> str:
    return f"{value:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _ms(nanoseconds: float) -> str:
    return _decimal(nanoseconds / 1e6, 3)


VALIDATION_CHECKS = {
    "tcpreplay_sent_whole_segment": "O tcpreplay processou todos os pacotes do trecho (enviados + falhos)",
    "h1_sent_equals_tcpreplay_successful": "Pacotes transmitidos por h1 = pacotes enviados pelo tcpreplay",
    "h2_received_equals_h1_sent": "Pacotes recebidos por h2 = pacotes transmitidos por h1",
    "no_capture_drops": "Nenhum descarte na interface de h2 nem no libpcap",
    "extractor_read_equals_h2_received": "Pacotes lidos pelo extrator = pacotes recebidos por h2",
    "replay_run_flow_chain": "Fluxos emitidos = recebidos = classificados + erros, na execução reproduzida",
}


def render_validation(summary: dict[str, Any]) -> str:
    flows, counters, predictions = summary["flows"], summary["counters"], summary["predictions"]
    tcpreplay, replay = summary["tcpreplay"], summary["replay"]
    lines = [
        f"# Validação do NIDS em baixa carga: {MODEL_NAMES[summary['model']]}, trecho `{summary['segment']}`",
        "",
        f"A validação foi {'aprovada' if summary['passed'] else 'reprovada'}. Ela compara a execução do NIDS que "
        "capturou o trecho reproduzido na rede emulada com a execução que leu o mesmo trecho do arquivo. A execução "
        "por arquivo já foi conferida com `tuesday.csv`. Os termos seguem o [glossário](../docs/glossario.md).",
        "",
        "## Reprodução",
        "",
        f"O Mininet criou dois hosts ligados por um enlace direto, sem switch, com MTU de "
        f"{_integer(replay['topology']['mtu'])} bytes, IPv6 desativado e as descargas de processamento das placas "
        "desligadas. O host h1 enviou o trecho com o tcpreplay na velocidade original "
        f"(`{' '.join(replay['replay_command'][:-1])}`), e o NIDS capturou a interface de h2. A reprodução levou "
        f"{_decimal(replay['replay_seconds'], 1)} s, a {_decimal(tcpreplay.get('rated_mbps') or 0, 3)} Mbps e "
        f"{_decimal(tcpreplay.get('rated_packets_per_second') or 0, 1)} pacotes/s. Depois do último pacote, a execução "
        f"esperou {_decimal(replay['wait_after_replay_s'], 0)} s para a varredura emitir os últimos fluxos.",
        "",
        "## Cadeia de contadores",
        "",
        "| Contador | Valor |",
        "|---|---:|",
        *[f"| {label} | {_integer(counters[key]) if counters[key] is not None else '—'} |" for key, label in (
            ("segment_packets", "Pacotes no trecho"), ("tcpreplay_successful", "Enviados pelo tcpreplay"),
            ("tcpreplay_failed", "Falhas de envio do tcpreplay"), ("tcpreplay_truncated", "Truncados pelo tcpreplay"),
            ("h1_sent", "Transmitidos pela interface de h1"), ("h2_received", "Recebidos pela interface de h2"),
            ("h2_dropped", "Descartados pela interface de h2"), ("pcap_received", "Recebidos pelo libpcap"),
            ("pcap_dropped", "Descartados pelo libpcap"), ("extractor_read", "Lidos pelo extrator"),
            ("extractor_valid", "IPv4 usados pelo extrator"), ("file_extractor_read", "Lidos do arquivo, na execução por arquivo"),
            ("packets_after_emission", "Chegaram a um fluxo já emitido"), ("flows_emitted", "Fluxos emitidos"),
            ("flows_received", "Fluxos recebidos pelo classificador"), ("flows_classified", "Fluxos classificados"),
            ("flows_with_error", "Fluxos com erro"))],
        "",
        "| Verificação | Resultado |",
        "|---|---|",
        *[f"| {VALIDATION_CHECKS[name]} | {'aprovada' if value else 'reprovada'} |"
          for name, value in summary["checks"].items()],
        "",
        "## Fluxos",
        "",
        "Os fluxos das duas execuções são casados pela quíntupla, pelo `Flow ID` e pela ordem de ocorrência, porque "
        "os instantes da reprodução são os da emulação, e não os de 2017. A borda dos últimos 120 s do trecho fica "
        "de fora, como na conferência por arquivo.",
        "",
        "| Situação | Fluxos |",
        "|---|---:|",
        f"| Na execução por arquivo | {_integer(flows['file'])} |",
        f"| Na execução reproduzida | {_integer(flows['replay'])} |",
        f"| Casados fora da borda | {_integer(flows['matched_inside'])} |",
        f"| Casados na borda | {_integer(flows['matched_border'])} |",
        f"| Só no arquivo, fora da borda | {_integer(flows['file_only_inside'])} |",
        f"| Só na reprodução, fora da borda | {_integer(flows['replay_only_inside'])} |",
        f"| Dos não casados, com o sentido invertido | {_integer(flows['swapped_direction_inside'])} |",
        "",
        "Rótulos dos fluxos casados fora da borda, pela tabela de referência: " + ", ".join(
            f"{label} ({_integer(count)})" for label, count in sorted(summary["labels"]["matched_inside"].items())) + ".",
        "",
        "## Atributos",
        "",
        f"Em {_integer(summary['flows_with_equal_exact_attributes'])} de {_integer(flows['matched_inside'])} fluxos "
        "casados, os atributos de contagem, tamanho e flags coincidem exatamente. "
        + ("Nenhum desses atributos diverge." if not summary["exact_attributes"] else "Divergem: " + ", ".join(
            f"{name} ({_integer(item['mismatches'])})" for name, item in summary["exact_attributes"].items()) + "."),
        "",
        "Os atributos temporais dependem dos instantes de captura, que a reprodução altera:",
        "",
        "| Atributo | Fluxos com diferença | Maior diferença absoluta | Diferença relativa mediana |",
        "|---|---:|---:|---:|",
        *[f"| {name} | {_integer(item['differing'])} | {item['max_abs_difference']:g} | "
          f"{item['median_relative_difference']:.2e} |" for name, item in summary["temporal_attributes"].items()],
        "",
        "## Previsões",
        "",
        f"As previsões diferem em {_integer(predictions['differing'])} de {_integer(predictions['compared'])} fluxos "
        f"casados. Em {_integer(predictions['differing_with_equal_exact_attributes'])} deles, os atributos de "
        "contagem, tamanho e flags são iguais, e só os atributos temporais mudaram.",
        "",
    ]
    if predictions["examples"]:
        lines += ["```json", *[str(example) for example in predictions["examples"]], "```", ""]
    for title, key in (("Fluxos só no arquivo", "file_only_examples"), ("Fluxos só na reprodução", "replay_only_examples")):
        if flows[key]:
            lines += [f"### {title}, fora da borda", "", "```json", *[str(row) for row in flows[key]], "```", ""]
    lines += [
        "## Reprodução do ensaio",
        "",
        "```bash",
        f"sudo python3 scripts/emular_baixa_carga.py --modelo {summary['model']} --trecho {summary['segment']}",
        f"cd src && python main.py nids-validar --reproduzida ../{summary['replay_run']} --arquivo ../{summary['file_run']}",
        "```",
        "",
        f"O registro da validação está em [training-runs/nids/validacao/{summary['run_id']}/report.json]"
        f"(../training-runs/nids/validacao/{summary['run_id']}/report.json).",
        "",
    ]
    return "\n".join(lines)
