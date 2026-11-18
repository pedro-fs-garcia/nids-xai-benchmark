"""Relatórios legíveis das execuções e da validação do NIDS de referência."""

from pathlib import Path
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
    "emitted_equals_received_plus_dropped": "Fluxos emitidos pelo extrator = fluxos recebidos pelo classificador + "
                                            "fluxos descartados na fila de saída do extrator",
    "no_dropped_flow_in_file_mode": "Nenhum fluxo descartado na fila de saída do extrator (modo arquivo)",
    "received_equals_classified_plus_errors": "Fluxos recebidos = classificados + não classificáveis",
    "timestamps_ordered": "t0 ≤ t1 ≤ t2 ≤ t3 em todos os fluxos classificados",
    "no_packets_after_emission_in_file_mode": "Nenhum pacote chegou a um fluxo já emitido (modo arquivo)",
    "selection_follows_strategy": "Fluxos selecionados = fluxos que a estratégia manda explicar",
    "explanations_match_classifications": "Cada explicação corresponde a um fluxo classificado, pelo número de "
                                          "sequência e pelo `Flow ID`",
    "contributions_cover_every_input": "Cada explicação tem uma contribuição por entrada do classificador",
    "sum_identity": "Valor de referência + soma das contribuições = saída explicada, dentro da tolerância",
    "explained_output_matches_classification": "A saída explicada leva à probabilidade registrada na classificação",
    "explained_equals_selected": "Fluxos explicados = fluxos selecionados",
    "explanation_marks_ordered": "Marcações dos fluxos explicados na ordem da estratégia: t2 ≤ seleção ≤ explicação "
                                 "≤ t4 = t3 nas síncronas; t3 ≤ solicitação ≤ retirada da fila ≤ explicação ≤ t4 "
                                 "no modo assíncrono",
    "every_selected_flow_requested_or_dropped": "Cada fluxo selecionado tem a solicitação aceita na fila ou descartada",
    "no_explanation_without_accepted_request": "Toda explicação concluída corresponde a uma solicitação aceita",
    "explanation_requests_accounted": "Solicitações aceitas e descartadas = contadores da fila no classificador",
    "explainer_received_every_accepted_request": "O processo explicador retirou da fila todas as solicitações aceitas",
    "explainer_ended_without_error": "O processo explicador terminou sem erro",
    "no_pending_after_normal_end": "Nenhuma explicação pendente quando o processo explicador termina normalmente",
    "no_dropped_request_in_file_mode": "Nenhuma solicitação descartada (modo arquivo)",
    "explainer_uses_the_same_model": "O processo explicador carregou o mesmo modelo congelado do classificador",
    "processes_on_configured_cpus": "Classificador, explicador e extrator nas CPUs configuradas",
}
SCALES = {"probability": "probabilidade", "log-odds": "log-odds"}


def render_run(summary: dict[str, Any]) -> str:
    flows, timings, end = summary["flows"], summary["timings"], summary["extractor_end"]
    source = summary["source"]
    origin = (f"o arquivo `{source.get('pcap')}`" if source["kind"] == "arquivo"
              else f"a interface `{source.get('iface')}`")
    lines = [
        f"# Execução do NIDS: {summary['strategy']}, {MODEL_NAMES[summary['model']]}, {source['kind']}",
        "",
        f"A execução {'passou' if summary['passed'] else 'não passou'} nas verificações. O NIDS leu {origin}, "
        f"formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o "
        f"{MODEL_NAMES[summary['model']]} congelado, na estratégia {summary['strategy']}. Os termos seguem o "
        "[glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do "
        "[protocolo](../docs/protocolo-experimental.md).",
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
        f"| Fluxos descartados na fila de saída do extrator | {_integer(end.get('flows_dropped') or 0)} |",
        f"| Fluxos recebidos pelo classificador | {_integer(flows['received'])} |",
        f"| Fluxos classificados | {_integer(flows['classified'])} |",
        f"| Fluxos não classificáveis | {_integer(flows['errors'])} |",
        "",
    ]
    if end.get("pcap_stats"):
        stats = end["pcap_stats"]
        lines += [f"Estatísticas do libpcap: {_integer(stats['received'])} pacotes recebidos, "
                  f"{_integer(stats['dropped'])} descartados por falta de espaço no buffer e "
                  f"{_integer(stats['interface_dropped'])} descartados pela interface.", ""]
    start = summary["extractor_start"]
    if start.get("buffer_bytes"):
        ring = start.get("ring_bytes")
        lines += [f"O buffer de captura foi pedido com {_integer(round(start['buffer_bytes'] / 2**20))} MiB"
                  + (f", e o kernel mapeou {_integer(round(ring / 2**20))} MiB" if ring else "") + ".", ""]
    if end.get("output_queue_max") is not None:
        limit = start.get("flow_queue_limit")
        lines += [f"A fila de saída do extrator chegou a {_integer(end['output_queue_max'])} fluxos à espera da "
                  "escrita" + (f", com limite de {_integer(limit)}" if limit else "") + ".", ""]
    lines += ["Causas de emissão: " + ", ".join(
        f"{CAUSES.get(cause, cause)} ({_integer(count)})" for cause, count in flows["by_cause"].items()) + ".", ""]
    if flows["error_examples"]:
        lines += ["Exemplos de fluxos não classificáveis: " + "; ".join(f"fluxo {item['seq']} (`{item['flow_id']}`): {item['error']}"
                                                   for item in flows["error_examples"]) + ".", ""]
    lines += _explanation_lines(summary)
    lines += ["## Verificações", "", "| Verificação | Resultado |", "|---|---|",
              *[f"| {CHECKS[name]} | {'aprovada' if value else 'reprovada'} |"
                for name, value in summary["checks"].items()], ""]
    conference = summary.get("conference")
    if conference:
        lines += [
            "## Conferência com a tabela de referência",
            "",
            *([f"O trecho começa no meio da captura. {_integer(conference['carried_over']['flows'])} fluxos do NIDS "
               f"pertencem a {_integer(conference['carried_over']['connections'])} conexões que já tinham pacotes "
               "antes do início e ficam fora da conferência, porque não correspondem aos fluxos do CSV.", ""]
              if (conference.get("carried_over") or {}).get("connections") else []),
            f"Fora da borda dos últimos {summary['segment']['border_seconds']} s, "
            f"{_integer(conference['matched_inside'])} fluxos do NIDS correspondem a fluxos de `tuesday.csv`. "
            f"Ficaram {_integer(conference['reference_only_inside'])} fluxos só no CSV e "
            f"{_integer(conference['nids_only_inside'])} só no NIDS. Destes, "
            f"{_integer(conference['nids_only_inside_with_nan'])} têm algum valor `NaN`: são fluxos de um único "
            "pacote, que a rotulagem dos autores descartou com `dropna` e que o NIDS registra como não classificáveis.",
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
                           ("explanation_ns", "Tempo de explicação"),
                           ("classification_latency_ns", "Latência de classificação, t3 − t0"),
                           ("explanation_latency_ns", "Latência de explicação, t4 − t0"),
                           ("wait_before_inference_ns", "Espera e preparo da entrada, t1 − t0"),
                           ("queue_wait_ns", "Espera na fila de explicações pendentes"),
                           ("selection_ns", "Seleção para explicação"),
                           ("delivery_ns", "Escrita nos canais de saída")):
            if key not in timings:
                continue
            item = timings[key]
            lines.append(f"| {label} | {_ms(item['mean'])} | {_ms(item['median'])} | {_ms(item['p95'])} | "
                         f"{_ms(item['p99'])} | {_ms(item['max'])} |")
        lines += [""]
    lines += _resource_lines(summary["resources"])
    lines += [
        f"O registro da execução está em [training-runs/nids/{summary['source']['kind']}/{summary['run_id']}/report.json]"
        f"(../training-runs/nids/{summary['source']['kind']}/{summary['run_id']}/report.json).",
        "",
    ]
    return "\n".join(lines)


CRITERION_NAMES = {"probabilidade": "Probabilidade", "incerteza": "Incerteza"}
CRITERION_RULES = {
    "probabilidade": "a probabilidade de ataque é maior ou igual a {threshold}",
    "incerteza": "a distância entre a probabilidade de ataque e 0,5 é menor ou igual a {threshold}",
}


def render_calibration(summary: dict[str, Any]) -> str:
    lines = [
        "# Calibração do critério de seleção do Síncrono condicional",
        "",
        "Este relatório mostra, no conjunto de validação, quantos registros cada critério de seleção escolhe para "
        "explicação, por limiar. Ele sustenta a escolha dos limiares da estratégia Síncrono condicional. O conjunto "
        "de teste não foi usado. Os termos seguem o [glossário](../docs/glossario.md).",
        "",
        f"A validação tem {_integer(summary['records'])} registros, com {_integer(summary['attacks'])} ataques e "
        f"{_integer(summary['benign'])} benignos. A classe prevista de cada registro vem do limiar de classificação "
        "de 0,5, fixado nas [decisões 5 e 6](../docs/decisoes.md).",
        "",
        "## Critérios",
        "",
        "- **Probabilidade.** O fluxo é selecionado quando a probabilidade de ataque é maior ou igual ao limiar. "
        "Com limiar de até 0,5, o critério seleciona os fluxos classificados como ataque e os benignos mais "
        "próximos da fronteira de classificação.",
        "- **Incerteza.** O fluxo é selecionado quando a distância entre a probabilidade de ataque e 0,5 é menor "
        "ou igual ao limiar. O critério seleciona os fluxos de classificação menos segura, das duas classes.",
        "",
        "Nas tabelas, as proporções de ataques e de benignos são calculadas sobre os registros de cada classe, "
        "pelo rótulo. Os erros de classificação são os registros cuja classe prevista difere do rótulo.",
        "",
    ]
    for name, model in summary["models"].items():
        errors = model["false_negatives"] + model["false_positives"]
        lines += [
            f"## {MODEL_NAMES[name]}",
            "",
            f"O {MODEL_NAMES[name]} erra {_integer(errors)} registros da validação: "
            f"{_integer(model['false_negatives'])} ataques classificados como benignos e "
            f"{_integer(model['false_positives'])} benignos classificados como ataque.",
            "",
        ]
        for criterion, rows in model["criteria"].items():
            lines += [
                f"### {CRITERION_NAMES[criterion]}",
                "",
                "| Limiar | Registros selecionados | Ataques selecionados | Benignos selecionados | "
                "Erros de classificação selecionados |",
                "|---:|---:|---:|---:|---:|",
                *[f"| {_number(row['threshold'])} | {_integer(row['selected'])} ({_percent(row['selected_share'], 3)}) | "
                  f"{_integer(row['attacks_selected'])} ({_percent(row['attacks_selected_share'], 3)}) | "
                  f"{_integer(row['benign_selected'])} ({_percent(row['benign_selected_share'], 3)}) | "
                  f"{_integer(row['errors_selected'])} de {_integer(errors)} |" for row in rows],
                "",
            ]
    lines += [
        "## Reprodução",
        "",
        "```bash",
        "cd src && python main.py calibrar-selecao",
        "```",
        "",
        f"A grade de limiares está em [{summary['config']}](../{summary['config']}). O registro da calibração está em "
        f"[training-runs/nids/calibracao/{summary['run_id']}/report.json]"
        f"(../training-runs/nids/calibracao/{summary['run_id']}/report.json).",
        "",
    ]
    return "\n".join(lines)


COMPARISON_CHECKS = {
    "four_strategies_once_each": "Uma execução de cada estratégia, e de cada critério do Síncrono condicional",
    "same_fixed_inputs": "Mesmas entradas fixas: configuração, modelo, TreeSHAP, extrator, tráfego, CPUs e versões",
    "every_run_passed": "Todas as execuções passaram nas próprias verificações",
    "measurement_points_present": "Cada execução registra os tempos da sua estratégia",
    "processes_on_configured_cpus": "Classificador, explicador e extrator nas CPUs configuradas, em todas as execuções",
    "identical_classifications": "Arquivos de classificação idênticos",
    "same_flows": "Mesmos fluxos recebidos, classificados e não classificáveis",
    "async_explanations_equal_total": "Assíncrono explica os mesmos fluxos que o Síncrono total, com as mesmas "
                                      "contribuições",
}

COPY_CHECKS = {
    "every_flow_in_one_copy": "Todo fluxo com endereços do trecho pertence à cópia conferida",
    "same_flows": "Cada fluxo da cópia corresponde a um fluxo do trecho original, e vice-versa",
    "same_inputs": "As 80 entradas de cada fluxo são idênticas às do fluxo original",
    "same_predictions": "A probabilidade de ataque e a previsão de cada fluxo são idênticas às do fluxo original",
}


def render_copy_check(summary: dict[str, Any]) -> str:
    flows, rewrite = summary["flows"], summary["rewrite"]
    lines = [
        f"# Conferência da cópia {summary['copy']} do trecho `{summary['segment']}`: {MODEL_NAMES[summary['model']]}",
        "",
        f"A conferência foi {'aprovada' if summary['passed'] else 'reprovada'}. Ela grava a cópia "
        f"{summary['copy']} do trecho com o `tcprewrite` {rewrite['tool']['version']}, que troca cada um dos "
        f"{_integer(rewrite['pnat_pairs'])} endereços IPv4 do trecho pelo endereço da cópia, com a mesma biblioteca "
        "de edição que o `tcpreplay-edit` usa na rede emulada. O NIDS lê a cópia do arquivo, sem XAI, e cada fluxo, "
        "com os endereços de volta aos originais, é comparado com o fluxo da leitura do trecho original. O primeiro "
        f"endereço da cópia é `{summary['addresses']['first_copy_address']}`.",
        "",
        "| Situação | Fluxos |",
        "|---|---:|",
        f"| No trecho original | {_integer(flows['original'])} |",
        f"| Na cópia | {_integer(flows['copy'])} |",
        f"| Na cópia, com endereços da cópia | {_integer(flows['mapped'])} |",
        f"| Na cópia, sem endereço IPv4 do trecho | {_integer(flows['without_copy'])} |",
        f"| Casados | {_integer(flows['matched'])} |",
        f"| Só no original | {_integer(flows['only_original'])} |",
        f"| Só na cópia | {_integer(flows['only_copy'])} |",
        f"| Casados com as 80 entradas idênticas | {_integer(flows['exact_values'])} |",
        f"| Casados com previsão ou probabilidade diferente | {_integer(flows['differing_predictions'])} |",
        "",
        "Os fluxos sem endereço IPv4 do trecho são os que o extrator forma de quadros que não são IPv4, como o ARP. "
        "A troca de endereços não os altera, e eles são comparados sem conversão.",
        "",
        "| Verificação | Resultado |",
        "|---|---|",
        *[f"| {COPY_CHECKS[name]} | {'aprovada' if value else 'reprovada'} |"
          for name, value in summary["checks"].items()],
        "",
    ]
    if summary["attribute_mismatches"]:
        lines += ["Entradas divergentes: " + ", ".join(f"{name} ({_integer(item['mismatches'])})" for name, item
                                                      in summary["attribute_mismatches"].items()) + ".", ""]
    lines += [
        "## Reprodução",
        "",
        "```bash",
        f"cd src && python main.py nids-conferir-copia --modelo {summary['model']} --trecho {summary['segment']} "
        f"--numero {summary['copy']} --original ../{summary['original_run']}",
        "```",
        "",
        f"A cópia gravada tinha SHA-256 `{summary['copy_pcap']['sha256']}` e foi apagada depois da leitura. A leitura "
        f"da cópia está em [{summary['copy_run']}](../{summary['copy_run']}/report.json), e o registro da conferência, "
        f"em [training-runs/nids/copia/{summary['run_id']}/report.json]"
        f"(../training-runs/nids/copia/{summary['run_id']}/report.json).",
        "",
    ]
    return "\n".join(lines)


def render_acceleration(summary: dict[str, Any]) -> str:
    rows = summary["rows"]
    lines = [
        f"# Efeito da aceleração sobre os fluxos: trecho `{summary['segment']}`",
        "",
        "O NIDS leu o trecho com os intervalos entre pacotes divididos por cada fator, sem rede, como chegaria numa "
        "reprodução acelerada sem atraso de envio nem de captura. Cada leitura acelerada é comparada com a leitura "
        "original do mesmo classificador. Os fluxos são casados pela quíntupla, pelo `Flow ID` e pela ordem de "
        "ocorrência. Os atributos de contagem, tamanho e flags não dependem dos instantes. Os temporais dependem. "
        "Os termos seguem o [glossário](../docs/glossario.md).",
        "",
        "## Fluxos",
        "",
        "| Classificador | Fator | Fluxos originais | Fluxos acelerados | Casados | Só no original | Só no acelerado | "
        "Casados com contagem, tamanho e flags iguais | Casados com atributos temporais iguais |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        flows = row["flows"]
        lines.append(
            f"| {MODEL_NAMES[row['model']]} | {_number(row['factor'])} | {_integer(flows['original'])} | "
            f"{_integer(flows['scaled'])} | {_integer(flows['matched'])} | {_integer(flows['only_original'])} | "
            f"{_integer(flows['only_scaled'])} | {_integer(row['matched_with_equal_exact_attributes'])} | "
            f"{_integer(row['matched_with_equal_temporal_attributes'])} |")
    lines += [
        "",
        "## Previsões e seleção",
        "",
        "| Classificador | Fator | Previsões diferentes, entre os casados | Ataques previstos, original → acelerado | "
        "Seleção por probabilidade, original → acelerado | Seleção por incerteza, original → acelerado |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        predictions, selection = row["predictions"], row["selection"]
        lines.append(
            f"| {MODEL_NAMES[row['model']]} | {_number(row['factor'])} | {_integer(predictions['differing'])} de "
            f"{_integer(predictions['compared'])} | {_integer(predictions['attacks_original'])} → "
            f"{_integer(predictions['attacks_scaled'])} | "
            + " | ".join(f"{_integer(selection[name]['selected_original'])} → "
                         f"{_integer(selection[name]['selected_scaled'])}" for name in ("probabilidade", "incerteza"))
            + " |")
    lines += [
        "",
        "Os limiares de seleção são os de [configs/nids.json](../configs/nids.json): "
        + "; ".join(f"{criterion} {', '.join(f'{MODEL_NAMES[model]} {_number(value)}' for model, value in values.items())}"
                    for criterion, values in summary["thresholds"].items()) + ".",
        "",
        "## Reprodução",
        "",
        "```bash",
        f"cd src && python main.py nids-efeito-aceleracao --trecho {summary['segment']} --fatores "
        + " ".join(_number(factor) for factor in summary["factors"]) + " --originais "
        + " ".join(f"../{run}" for run in summary["original_runs"].values()),
        "```",
        "",
        f"As leituras aceleradas estão em {', '.join(f'`{row['run']}`' for row in rows)}. Os arquivos acelerados "
        f"foram apagados depois da leitura. O registro está em [training-runs/nids/aceleracao/{summary['run_id']}/"
        f"report.json](../training-runs/nids/aceleracao/{summary['run_id']}/report.json).",
        "",
    ]
    return "\n".join(lines)


def render_comparison(summary: dict[str, Any]) -> str:
    source = ("o mesmo arquivo" if summary["file_mode"] else "a captura do mesmo trecho reproduzido na rede emulada")
    segment = f" do trecho `{summary['segment']}`" if summary["segment"] else ""
    lines = [
        f"# Comparabilidade das estratégias de explicação: {MODEL_NAMES[summary['model']]}",
        "",
        f"A conferência foi {'aprovada' if summary['passed'] else 'reprovada'}. Ela compara execuções do NIDS com o "
        f"{MODEL_NAMES[summary['model']]} que leram {source}{segment}, uma por estratégia de explicação. Os termos "
        "seguem o [glossário](../docs/glossario.md).",
        "",
    ]
    if not summary["file_mode"]:
        lines += ["Na rede emulada, os atributos temporais variam entre as execuções, e as previsões e as explicações "
                  "do mesmo fluxo não precisam coincidir. Cada execução é conferida com a execução por arquivo da "
                  "mesma estratégia por `nids-validar`.", ""]
    labels = {**COMPARISON_CHECKS, **{
        name: f"Síncrono condicional por {name.split('_')[1]} explica exatamente os fluxos que o critério seleciona, "
              "com as contribuições do Síncrono total"
        for name in summary["checks"] if name.startswith("conditional_")}}
    lines += ["## Verificações", "", "| Verificação | Resultado |", "|---|---|",
              *[f"| {labels[name]} | {'aprovada' if value else 'reprovada'} |"
                for name, value in summary["checks"].items()], ""]
    if summary["differences"]:
        lines += ["| Explicações comparadas | Fluxos explicados nas duas | Maior diferença absoluta |",
                  "|---|---:|---:|",
                  *[f"| {_difference_name(name)} | {_integer(item['common'])} | {item['max_abs_difference']:g} |"
                    for name, item in summary["differences"].items()], ""]
    lines += [
        "## Execuções",
        "",
        "| Estratégia | Classificados | Selecionados | Explicados | Descartados | Pendentes | Maior fila |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["runs"]:
        name = row["strategy"] + (f" ({row['criterion']}, limiar {_number(row['threshold'])})" if row["criterion"] else "")
        lines.append(f"| [{name}](nids-execucao-{row['source_kind']}-{row['run_id']}.md) | {_integer(row['classified'])} | "
                     f"{_integer(row['selected'])} | {_integer(row['completed'])} | {_integer(row['dropped'])} | "
                     f"{_integer(row['pending'])} | {'—' if row['queue_max'] is None else _integer(row['queue_max'])} |")
    lines += [
        "",
        "Os tempos abaixo mostram que a instrumentação funciona nas quatro estratégias. As execuções não controlam a "
        "carga, então eles não são resultados do experimento.",
        "",
        "| Estratégia | Inferência, média (ms) | Explicação, média (ms) | Latência de classificação, p95 / p99 (ms) | "
        "Latência de explicação, p95 / p99 (ms) | CPU: classificador / explicador / extrator (s) |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in summary["runs"]:
        timings, cpu = row["timings"], row["cpu_seconds"]
        name = row["strategy"] + (f" ({row['criterion']})" if row["criterion"] else "")
        lines.append(
            f"| {name} | {_ms(timings['inference_ns']['mean'])} | "
            f"{_ms(timings['explanation_ns']['mean']) if 'explanation_ns' in timings else '—'} | "
            f"{_ms(timings['classification_latency_ns']['p95'])} / {_ms(timings['classification_latency_ns']['p99'])} | "
            + (f"{_ms(timings['explanation_latency_ns']['p95'])} / {_ms(timings['explanation_latency_ns']['p99'])}"
               if "explanation_latency_ns" in timings else "—")
            + " | " + " / ".join("—" if cpu[name] is None else _decimal(cpu[name], 1)
                                 for name in ("classifier", "explainer", "extractor")) + " |")
    lines += [
        "",
        "## Reprodução",
        "",
        "```bash",
        "cd src && python main.py nids-comparar-estrategias --execucoes "
        + " ".join(f"../{path}" for path in summary["compared_runs"]),
        "```",
        "",
        f"O registro da conferência está em [training-runs/nids/comparacao/{summary['run_id']}/report.json]"
        f"(../training-runs/nids/comparacao/{summary['run_id']}/report.json).",
        "",
    ]
    return "\n".join(lines)


def _difference_name(name: str) -> str:
    if name == "total_vs_async":
        return "Síncrono total e Assíncrono"
    return f"Síncrono total e Síncrono condicional por {name.removeprefix('total_vs_conditional_')}"


def _number(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def _explanation_lines(summary: dict[str, Any]) -> list[str]:
    explanations, warmup = summary["explanations"], summary["warmup"]
    lines = ["## Explicações", ""]
    selection = summary.get("selection")
    if selection:
        rule = CRITERION_RULES[selection["criterion"]].format(threshold=_number(selection["threshold"]))
        lines += [f"O NIDS seleciona para explicação os fluxos em que {rule}. O limiar vem da calibração registrada "
                  f"em [{selection['calibration_run']}](../{selection['calibration_run']}/report.json).", ""]
    if not explanations["selected"] and warmup["explainer_construction_ns"] is None:
        return lines + [f"A estratégia {summary['strategy']} não gera explicações. A chamada de aquecimento da "
                        f"inferência, antes de a captura abrir, levou {_ms(warmup['inference_ns'])} ms.", ""]
    identity = explanations["sum_identity"]
    lines += [
        f"O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador "
        f"levou {_ms(warmup['explainer_construction_ns'])} ms, e as chamadas de aquecimento levaram "
        f"{_ms(warmup['inference_ns'])} ms na inferência e {_ms(warmup['explanation_ns'])} ms na explicação.",
        "",
        "| Cobertura explicativa | Fluxos | Proporção dos classificados |",
        "|---|---:|---:|",
        f"| Classificados | {_integer(explanations['eligible'])} | 100,00% |",
        f"| Selecionados para explicação | {_integer(explanations['selected'])} | "
        f"{_percent(explanations['selected_share'])} |",
        f"| Com a explicação concluída | {_integer(explanations['completed'])} | "
        f"{_percent(explanations['completed_share'])} |",
        "",
    ]
    if identity["residual"] is not None:
        lines += [f"A soma do valor de referência com as contribuições difere da saída explicada em no máximo "
                  f"{identity['residual']:.2g}, na escala de {SCALES[explanations['scale']]}, contra a tolerância de "
                  f"{identity['tolerance']:g}.", ""]
    return lines + _queue_lines(summary)


PROCESS_NAMES = {"classifier": "classificador", "explainer": "explicador", "extractor": "extrator"}


def _resource_lines(resources: dict[str, Any]) -> list[str]:
    rows = []
    for key, process in (("classifier", resources["classifier_process"]), ("explainer", resources["explainer_process"]),
                         ("extractor", resources["extractor_process"])):
        if not process:
            continue
        cpu_seconds = (process["cpu_ns"] / 1e9 if "cpu_ns" in process
                       else process["user_seconds"] + process["system_seconds"])
        configured = resources["cpus"]["configured"][key]
        rows.append(f"| {PROCESS_NAMES[key]} | {', '.join(map(str, configured))} | "
                    f"{_cpu_text(resources['cpus'][key])} | "
                    f"{_decimal(cpu_seconds, 1)} | {_integer(round(process['max_rss_kib'] / 1024))} |")
    available = resources.get("memory_available_kib_at_start")
    return [
        "## Recursos",
        "",
        "| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |",
        "|---|---|---|---:|---:|",
        *rows,
        "",
        *([f"A máquina tinha {_integer(round(available / 1024))} MiB de memória disponível no início da execução.", ""]
          if available else []),
    ]


def _cpu_text(value: list[Any] | None) -> str:
    """CPUs observadas: uma lista por grupo de threads com a mesma afinidade, ou uma lista só."""
    if value is None:
        return "—"
    groups = value if value and isinstance(value[0], list) else [value]
    return "; ".join(", ".join(map(str, group)) for group in groups)


def _queue_lines(summary: dict[str, Any]) -> list[str]:
    queue = summary.get("explanation_queue")
    if not queue:
        return []
    size = queue["size"]
    policy = ("a solicitação espera vaga na fila, porque na leitura de arquivo não há captura a perder"
              if queue["full_queue_policy"] == "wait" else "a solicitação que chega com a fila cheia é descartada")
    lines = [
        "### Fila de explicações pendentes",
        "",
        f"A fila tem limite de {_integer(queue['limit'])} solicitações. Com ela cheia, {policy}.",
        "",
        "| Solicitações | Quantidade |",
        "|---|---:|",
        f"| Feitas | {_integer(queue['requested'])} |",
        f"| Aceitas na fila | {_integer(queue['accepted'])} |",
        f"| Descartadas com a fila cheia | {_integer(queue['dropped'])} |",
        f"| Concluídas | {_integer(queue['completed'])} |",
        f"| Pendentes no fim | {_integer(queue['pending'])} |",
        "",
        f"A fila chegou a {_integer(size['max'])} solicitações pendentes.",
    ]
    if queue["drain_after_last_request_ns"] is not None:
        lines[-1] += (f" A última explicação ficou disponível {_ms(queue['drain_after_last_request_ns'])} ms depois "
                      "da última solicitação.")
    if queue["killed_after_drain_timeout"]:
        lines[-1] += (f" O processo explicador não esvaziou a fila em {_decimal(queue['drain_timeout_s'], 0)} s e foi "
                      "encerrado.")
    return lines + [""]


def _percent(share: float | None, digits: int = 2) -> str:
    return "—" if share is None else _decimal(share * 100, digits) + "%"


def _copy_lines(summary: dict[str, Any]) -> list[str]:
    """Comparação de cada cópia com a execução por arquivo, depois de os endereços voltarem aos originais."""
    copies = summary.get("copies")
    if not copies:
        return []
    flows = summary["flows"]
    lines = [
        "## Cópias",
        "",
        f"Cada fluxo da reprodução foi atribuído à cópia dos seus endereços e voltou aos endereços originais. "
        f"{_integer(flows['without_copy'])} fluxos ficaram sem cópia: o extrator os forma de quadros que não são "
        "IPv4, como o ARP, que a troca de endereços não altera, e eles juntam pacotes de todas as cópias. Por isso, "
        f"a comparação usa os {_integer(flows['compared_file'])} fluxos da execução por arquivo com as duas pontas "
        "entre os endereços do trecho.",
        "",
        "| Cópia | Fluxos | Casados fora da borda | Casados na borda | Só no arquivo | Só na reprodução | "
        "Contagem, tamanho e flags iguais | Previsões diferentes |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for copy, row in copies.items():
        lines.append(f"| {copy} | {_integer(row['replay_flows'])} | {_integer(row['matched_inside'])} | "
                     f"{_integer(row['matched_border'])} | {_integer(row['file_only_inside'])} | "
                     f"{_integer(row['replay_only_inside'])} | {_integer(row['flows_with_equal_exact_attributes'])} | "
                     f"{_integer(row['predictions_differing'])} de {_integer(row['predictions_compared'])} |")
    return lines + [""]


def _packet_shift_lines(shifts: dict[str, Any] | None) -> list[str]:
    if not shifts or not shifts["flows"]:
        return []
    text = (f"O número de pacotes difere em {_integer(shifts['flows'])} fluxos casados. Em "
            f"{_integer(shifts['conserved_in_connection'])} deles, de {_integer(shifts['connections'])} conexões, o "
            "total de pacotes da conexão é igual nas duas execuções. Nesses fluxos, pacotes próximos do tempo limite "
            "de 120 s ficaram no fluxo anterior ou no seguinte da mesma conexão, porque a reprodução desloca os "
            "instantes de captura.")
    rest = shifts["flows"] - shifts["conserved_in_connection"]
    if rest:
        text += f" Nos outros {_integer(rest)}, o total de pacotes da conexão também difere."
    return [text, ""]


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
    "replay_run_flow_chain": "A execução reproduzida passou nas próprias verificações, incluindo fluxos emitidos = "
                             "recebidos + descartados na fila de saída do extrator e recebidos = classificados + "
                             "não classificáveis",
}


def render_validation(summary: dict[str, Any]) -> str:
    flows, counters, predictions = summary["flows"], summary["counters"], summary["predictions"]
    tcpreplay, replay = summary["tcpreplay"], summary["replay"]
    build = replay.get("tcpreplay_build") or {}
    tool = f"tcpreplay {build['version']}" if build else "tcpreplay"
    command = " ".join([Path(replay["replay_command"][0]).name, *replay["replay_command"][1:-1]])
    copies = int(replay.get("copies") or 1)
    sent = ("o trecho" if copies == 1 else
            f"{copies} cópias do trecho ao mesmo tempo, a cópia 1 sem alteração e as demais com os endereços IPv4 "
            "trocados pelos do bloco de cada cópia,")
    lines = [
        f"# Validação do NIDS na rede emulada: {summary.get('strategy', 'Sem XAI')}, {MODEL_NAMES[summary['model']]}, "
        f"trecho `{summary['segment']}`, {copies} {'cópia' if copies == 1 else 'cópias'}",
        "",
        f"A validação foi {'aprovada' if summary['passed'] else 'reprovada'}. Ela compara a execução do NIDS que "
        "capturou o trecho reproduzido na rede emulada com a execução que leu o mesmo trecho do arquivo. A execução "
        "por arquivo já foi conferida com `tuesday.csv`. Os termos seguem o [glossário](../docs/glossario.md).",
        "",
        "## Reprodução",
        "",
        f"O Mininet criou dois hosts ligados por um enlace direto, sem switch, com MTU de "
        f"{_integer(replay['topology']['mtu'])} bytes, IPv6 desativado e as descargas de processamento das placas "
        f"desligadas. O host h1 enviou {sent} com o {tool} na velocidade original "
        f"(`{command}`), e o NIDS capturou a interface de h2. A reprodução levou "
        f"{_decimal(replay['replay_seconds'], 1)} s, a {_decimal(tcpreplay.get('rated_mbps') or 0, 3)} Mbps e "
        f"{_decimal(tcpreplay.get('rated_packets_per_second') or 0, 1)} pacotes/s. Depois do último pacote, a execução "
        f"esperou {_decimal(replay['wait_after_replay_s'], 0)} s para a varredura emitir os últimos fluxos.",
        "",
        *([f"O extrator emitiu {_integer(summary['emission']['flows'])} fluxos, "
           f"{_decimal(summary['emission']['per_second'], 2)} por segundo de reprodução, com até "
           f"{_integer(summary['emission']['peak_per_second'])} emissões num mesmo segundo.", ""]
          if summary.get("emission") else []),
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
            ("flows_dropped_in_extractor_queue", "Fluxos descartados na fila de saída do extrator"),
            ("flows_received", "Fluxos recebidos pelo classificador"), ("flows_classified", "Fluxos classificados"),
            ("flows_with_error", "Fluxos não classificáveis"))],
        "",
        "| Verificação | Resultado |",
        "|---|---|",
        *[f"| {VALIDATION_CHECKS[name]} | {'aprovada' if value else 'reprovada'} |"
          for name, value in summary["checks"].items()],
        "",
        *_copy_lines(summary),
        "## Fluxos" + (" da cópia 1" if copies > 1 else ""),
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
        *_packet_shift_lines(summary.get("packet_shifts")),
        "Os atributos temporais dependem dos instantes de captura, que a reprodução altera. Os atributos de rajada "
        "(`Bulk`) estão entre eles, porque o extrator reinicia a rajada quando dois pacotes com carga ficam mais de "
        "1 s afastados.",
        "",
        "| Atributo | Fluxos com diferença | Maior diferença absoluta | Diferença relativa mediana, entre os que diferem |",
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
        f"sudo python3 scripts/emular_trecho.py --modelo {summary['model']} --trecho {summary['segment']} "
        f"--estrategia {summary.get('strategy_key', 'sem-xai')}"
        + (f" --criterio {summary['selection']['criterion']}" if summary.get("selection") else "")
        + f" --carga {copies}",
        f"cd src && python main.py nids-validar --reproduzida ../{summary['replay_run']} --arquivo ../{summary['file_run']}",
        "```",
        "",
        f"O registro da validação está em [training-runs/nids/validacao/{summary['run_id']}/report.json]"
        f"(../training-runs/nids/validacao/{summary['run_id']}/report.json).",
        "",
    ]
    return "\n".join(lines)
