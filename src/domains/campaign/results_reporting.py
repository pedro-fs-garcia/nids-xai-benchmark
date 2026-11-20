"""Relatório legível dos resultados de uma matriz executada."""

from typing import Any

from domains.campaign.reporting import CONFIGURATION_NAMES, MODEL_NAMES, _decimal, _integer, _percent

DECISIONS = "../docs/decisoes.md"
CONFIGURATION_ORDER = ("sem-xai", "sincrono-total", "sincrono-condicional-probabilidade",
                       "sincrono-condicional-incerteza", "assincrono")
FIGURE_TITLES = {
    "classification_latency": "p95 e p99 da latência de classificação por nível de carga",
    "latency_distribution": "Distribuição acumulada da latência de classificação de cada execução",
    "emitted_per_second": "Fluxos emitidos pelo extrator a cada segundo",
    "pending_classification": "Maior número de fluxos pendentes de classificação a cada 10 s, na repetição 1",
    "explanation_latency": "p95 e p99 da latência de explicação por nível de carga",
    "explanation_queue": "Fila de explicações pendentes ao longo da execução, no Assíncrono",
    "cpu": "Tempo de CPU de cada processo por nível de carga",
}


def render_results(summary: dict[str, Any]) -> str:
    combinations = summary["combinations"]
    explaining = [item for item in combinations if item["configuration"] != "sem-xai"]
    asynchronous = [item for item in combinations if item["configuration"] == "assincrono"]
    figure = lambda name: f"![{FIGURE_TITLES[name]}](../{summary['figures'][name]})"  # noqa: E731
    lines = [
        f"# Resultados da matriz `{summary['matrix']}`",
        "",
        f"Este relatório reúne as medidas das {len(summary['executions'])} execuções válidas da matriz "
        f"`{summary['matrix']}`, no trecho `{summary['segment']}`. Cada combinação de classificador, configuração de "
        f"explicação e nível de carga tem {_repetitions(summary)} execuções. Cada célula das tabelas traz a mediana "
        "das execuções da combinação e, entre "
        "parênteses, o mínimo e o máximo. O nível de carga é o número de cópias do trecho reproduzidas ao mesmo tempo "
        "([decisão 15](../docs/decisoes.md#15-carga-por-sobreposição-de-cópias)). Os termos seguem o "
        "[glossário](../docs/glossario.md).",
        "",
        f"A [auditoria]({summary['audit_report']}) aprovou a matriz. Em cada execução, o hash da tabela por "
        "fluxo e o da tabela de explicações coincidem com os registrados, e as latências, a cobertura explicativa, "
        "os descartes e a fila de explicações pendentes recalculados dessas tabelas coincidem com o registro do NIDS.",
        "",
        "## Viabilidade",
        "",
        "Uma execução é viável quando a latência de classificação não passa de 1 s no p95 nem de 2 s no p99, nenhum "
        "fluxo é descartado na fila de saída do extrator e, no Assíncrono, a fila de explicações pendentes não cresce "
        "até o fim ([protocolo](../docs/protocolo-experimental.md), seção 8). A fila cresce até o fim quando atinge o "
        "maior tamanho pela primeira vez no último décimo da execução, ou quando está no limite no último décimo "
        f"([decisão 23]({DECISIONS}#23-critério-da-fila-de-explicações-pendentes)). Cada coluna de critério conta as "
        "execuções que o atendem. A combinação é viável quando todas as execuções são "
        f"([decisão 24]({DECISIONS}#24-viabilidade-de-uma-combinação)). A coluna dos explicados traz a proporção dos "
        "fluxos classificados com a explicação concluída.",
        "",
        "| Combinação | Latência | Sem fluxo descartado | Fila | Execuções viáveis | Viável | Explicados |",
        "|---|---:|---:|---:|---:|---|---:|",
        *[f"| {_name(item)} | {_count(item, 'latency')} | {_count(item, 'no_dropped_flow')} | "
          f"{_count(item, 'queue') if item['configuration'] == 'assincrono' else '—'} | {_count(item, 'viable')} | "
          f"{'sim' if item['viable'] else 'não'} | {_range(item['measures']['completed_share'], _percent)} |"
          for item in combinations],
        "",
        "## Sobrecarga de latência",
        "",
        "A sobrecarga de latência é a diferença entre a mediana das execuções da estratégia e a do Sem XAI, com o mesmo "
        f"classificador e a mesma carga, em milissegundos ([decisão 25]({DECISIONS}#25-sobrecarga-de-latência)). A "
        "estratégia difere do Sem XAI quando os intervalos do mínimo ao máximo das execuções não se sobrepõem "
        f"([decisão 26]({DECISIONS}#26-diferença-entre-combinações)). Quando se sobrepõem, a tabela marca que a estratégia "
        "não se distingue do Sem XAI.",
        "",
        "| Combinação | Média | p95 | p99 |",
        "|---|---:|---:|---:|",
        *[f"| {_name(item)} | {_overhead(item, 'mean')} | {_overhead(item, 'p95')} | {_overhead(item, 'p99')} |"
          for item in explaining],
        "",
        "## Carga efetiva",
        "",
        "A carga efetiva é o número de fluxos emitidos pelo extrator por segundo de reprodução, com os pacotes por "
        "segundo enviados pelas cópias.",
        "",
        "| Nível de carga | Execuções | Fluxos emitidos | Fluxos/s | Pacotes/s |",
        "|---:|---:|---:|---:|---:|",
        *[f"| {item['load']}× | {item['executions']} | {_range(item['flows_emitted'], _whole)} | "
          f"{_range(item['flows_per_second'], lambda value: _decimal(value, 1))} | "
          f"{_range(item['packets_per_second'], _whole)} |" for item in summary["loads"]],
        "",
        figure("emitted_per_second"),
        "",
        "## Latência de classificação",
        "",
        "A latência de classificação vai do fim da extração dos atributos do fluxo (`t0`) ao momento em que a "
        "classificação fica disponível (`t3`). Os valores estão em milissegundos.",
        "",
        figure("classification_latency"),
        "",
        figure("latency_distribution"),
        "",
        "| Combinação | Média | p95 | p99 | Vazão (fluxos/s) | Fluxos descartados | Pacotes perdidos na captura |",
        "|---|---:|---:|---:|---:|---:|---:|",
        *[f"| {_name(item)} | {_range(item['measures']['classification_mean_ms'], _ms)} | "
          f"{_range(item['measures']['classification_p95_ms'], _ms)} | "
          f"{_range(item['measures']['classification_p99_ms'], _ms)} | "
          f"{_range(item['measures']['classified_per_second'], lambda value: _decimal(value, 1))} | "
          f"{_range(item['measures']['flows_dropped_share'], _percent)} | "
          f"{_range(item['measures']['capture_lost_packets'], _whole)} |" for item in combinations],
        "",
        "A vazão é o número de fluxos classificados dividido pelo tempo entre o primeiro `t0` e o último `t3` da "
        "execução. Os fluxos descartados são os que a fila de saída do extrator recusou, em proporção dos emitidos.",
        "",
        "## Fluxos pendentes de classificação",
        "",
        "Um fluxo fica pendente de classificação de `t0` até `t3`. O número de fluxos pendentes soma os que esperam na "
        "fila de saída do extrator e o que está no classificador. Um intervalo com fluxo pendente começa quando um "
        "fluxo é emitido sem nenhum outro pendente e termina quando nenhum fica pendente. O NIDS satura numa execução "
        "quando um único intervalo com fluxo pendente cobre mais da metade do tempo entre o primeiro fluxo emitido e "
        f"a última classificação ([decisão 27]({DECISIONS}#27-saturação)).",
        "",
        "A figura mostra a repetição 1 do Sem XAI, do Síncrono total e do Assíncrono, com o maior número de fluxos "
        "pendentes a cada 10 s. Os dois condicionais estão só na tabela.",
        "",
        figure("pending_classification"),
        "",
        "| Combinação | Maior número de fluxos pendentes | Intervalo mais longo com fluxo pendente (s) | "
        "Intervalo mais longo, em fração do tempo | Fração do tempo com fluxo pendente | Execuções saturadas |",
        "|---|---:|---:|---:|---:|---:|",
        *[f"| {_name(item)} | {_range(item['measures']['pending_classification_max'], _whole)} | "
          f"{_range(item['measures']['pending_classification_longest_s'], _seconds)} | "
          f"{_range(item['measures']['pending_classification_longest_share'], _percent)} | "
          f"{_range(item['measures']['pending_classification_busy_share'], _percent)} | "
          f"{item['saturated']} de {item['executions']} |" for item in combinations],
        "",
        "## Explicações",
        "",
        "A latência de explicação vai de `t0` ao momento em que a explicação fica disponível (`t4`). Os selecionados e "
        "os explicados estão em proporção dos fluxos classificados, e as latências, em milissegundos.",
        "",
        figure("explanation_latency"),
        "",
        "| Combinação | Selecionados | Explicados | Latência de explicação, média | p95 | p99 |",
        "|---|---:|---:|---:|---:|---:|",
        *[f"| {_name(item)} | {_range(item['measures']['selected_share'], _percent)} | "
          f"{_range(item['measures']['completed_share'], _percent)} | "
          f"{_range(item['measures']['explanation_latency_mean_ms'], _ms)} | "
          f"{_range(item['measures']['explanation_latency_p95_ms'], _ms)} | "
          f"{_range(item['measures']['explanation_latency_p99_ms'], _ms)} |" for item in explaining],
        "",
        "No Assíncrono, a espera na fila vai da solicitação de explicação à retirada pelo processo explicador, em "
        "milissegundos. O tempo de esvaziamento vai da última solicitação aceita à última explicação disponível. A "
        "posição do maior tamanho é o instante em que a fila o atinge, em fração da execução.",
        "",
        figure("explanation_queue"),
        "",
        "| Combinação | Solicitações descartadas | Pendentes no fim | Espera na fila, média | Espera na fila, p95 | "
        "Maior tamanho | Posição do maior tamanho | Maior tamanho no último décimo | Esvaziamento (s) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        *[f"| {_name(item)} | {_range(item['measures']['requests_dropped'], _whole)} | "
          f"{_range(item['measures']['requests_pending'], _whole)} | "
          f"{_range(item['measures']['queue_wait_mean_ms'], _ms)} | "
          f"{_range(item['measures']['queue_wait_p95_ms'], _ms)} | "
          f"{_range(item['measures']['queue_max'], _whole)} | "
          f"{_range(item['measures']['queue_max_at_share'], _percent)} | "
          f"{_range(item['measures']['queue_max_in_last_tenth'], _whole)} | "
          f"{_range(item['measures']['drain_s'], _seconds)} |" for item in asynchronous],
        "",
        "O tamanho da fila é reconstruído dos instantes de solicitação e de retirada "
        "([decisão 13](../docs/decisoes.md#13-limites-das-filas-e-política-de-descarte)). O classificador lê o "
        "instante da solicitação antes de pôr a solicitação na fila, e o processo explicador lê o instante da "
        "retirada depois de tirá-la (`src/domains/nids/service.py` e `src/core/explanation_worker.py`). Por isso, com "
        "a fila cheia, o tamanho reconstruído pode passar do limite de 10.000 solicitações, que a fila do NIDS não "
        "ultrapassa.",
        "",
        "## Recursos",
        "",
        "Tempo de CPU em segundos e pico de memória residente em MiB. O classificador é medido do início ao fim da "
        "captura, o processo explicador, do fim da carga do modelo ao fim do atendimento das solicitações, e o "
        "extrator, do início ao fim do processo ([decisão 14](../docs/decisoes.md#14-orçamento-de-cpu-e-de-memória)). "
        "O tempo de CPU por fluxo divide o tempo de CPU do processo pelo número de fluxos classificados, em "
        "milissegundos.",
        "",
        figure("cpu"),
        "",
        "| Combinação | CPU do classificador | CPU do processo explicador | CPU do extrator | "
        "CPU do classificador por fluxo | CPU do processo explicador por fluxo | Memória do classificador | "
        "Memória do processo explicador | Memória do extrator |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        *[f"| {_name(item)} | {_range(item['measures']['cpu_classifier_s'], _whole)} | "
          f"{_range(item['measures']['cpu_explainer_s'], _whole)} | "
          f"{_range(item['measures']['cpu_extractor_s'], _whole)} | "
          f"{_range(item['measures']['cpu_classifier_ms_per_flow'], _ms)} | "
          f"{_range(item['measures']['cpu_explainer_ms_per_flow'], _ms)} | "
          f"{_range(item['measures']['rss_classifier_mib'], _whole)} | "
          f"{_range(item['measures']['rss_explainer_mib'], _whole)} | "
          f"{_range(item['measures']['rss_extractor_mib'], _whole)} |" for item in combinations],
        "",
        "## Tempo de inferência e estado da máquina",
        "",
        "O tempo de inferência e o tempo de explicação são as médias da duração de cada chamada, em milissegundos. A "
        "frequência é a mediana das leituras de cada segundo, em MHz. O classificador roda na CPU 2 e o processo "
        "explicador, na CPU 0. As CPUs 1 e 3 dividem os núcleos físicos dessas duas CPUs e não recebem processos do "
        "experimento. A memória disponível é a menor leitura da execução, em MiB.",
        "",
        "| Combinação | Inferência | Explicação | Frequência da CPU 2 | Frequência da CPU 0 | "
        "Maior ocupação das CPUs 1 e 3 | Memória disponível |",
        "|---|---:|---:|---:|---:|---:|---:|",
        *[f"| {_name(item)} | {_range(item['measures']['inference_mean_ms'], _ms)} | "
          f"{_range(item['measures']['explanation_mean_ms'], _ms)} | "
          f"{_range(item['measures']['frequency_cpu2_mhz'], _whole)} | "
          f"{_range(item['measures']['frequency_cpu0_mhz'], _whole)} | "
          f"{_range(item['measures']['busy_share_sibling_cpus_max'], _percent)} | "
          f"{_range(item['measures']['memory_available_mib_min'], _whole)} |" for item in combinations],
        "",
        "## Reprodução",
        "",
        "```bash",
        f"cd src && python main.py campanha-resultados --matriz ../{summary['matrix_config']}",
        "```",
        "",
        f"O registro dos ensaios está em `{summary['registry']}`, e o dos resultados, com as medidas de cada execução, "
        f"em `training-runs/nids/resultados-{summary['matrix']}/{summary['run_id']}/report.json`.",
        "",
    ]
    return "\n".join(lines)


def _repetitions(summary: dict[str, Any]) -> str:
    counts = [item["executions"] for item in summary["combinations"]]
    return str(min(counts)) if min(counts) == max(counts) else f"de {min(counts)} a {max(counts)}"


def _count(item: dict[str, Any], criterion: str) -> str:
    return f"{item['viability'][criterion]} de {item['executions']}"


def _overhead(item: dict[str, Any], stat: str) -> str:
    value = item["overhead"][stat]
    text = _ms(value["ms"]).replace("-", "−")
    return text if value["comparison"] != "não se distingue" else f"{text} (não se distingue)"


def _name(item: dict[str, Any]) -> str:
    return f"{MODEL_NAMES[item['model']]}, {CONFIGURATION_NAMES[item['configuration']]}, {item['load']}×"


def _range(spread: dict[str, float] | None, fmt: Any) -> str:
    if not spread:
        return "—"
    if fmt(spread["min"]) == fmt(spread["max"]):
        return fmt(spread["median"])
    return f"{fmt(spread['median'])} ({fmt(spread['min'])}–{fmt(spread['max'])})"


def _ms(value: float | None) -> str:
    if value is None:
        return "—"
    digits = 3 if abs(value) < 1 else 2 if abs(value) < 10 else 1 if abs(value) < 100 else 0
    return _decimal(value, digits)


def _seconds(value: float | None) -> str:
    return "—" if value is None else _decimal(value, 3 if abs(value) < 1 else 1)


def _whole(value: float | None) -> str:
    return "—" if value is None else _integer(round(value))
