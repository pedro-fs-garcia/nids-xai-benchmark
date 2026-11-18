# Execução do NIDS: Sem XAI, XGBoost, arquivo

A execução passou nas verificações. O NIDS leu o arquivo `/home/pedro/projects/explicabilidade-ia/training-runs/nids/copia/20261115T193223330810Z/segment-campanha-copia-16.pcap`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o XGBoost congelado, na estratégia Sem XAI. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 3.706.151 |
| Pacotes IPv4 usados na formação dos fluxos | 3.703.160 |
| Pacotes descartados por não serem IPv4 | 2.991 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 24.413 |
| Fluxos descartados na fila de saída do extrator | 0 |
| Fluxos recebidos pelo classificador | 24.413 |
| Fluxos classificados | 24.396 |
| Fluxos não classificáveis | 17 |

Causas de emissão: nova conexão TCP depois do encerramento (363), varredura do tempo limite (21.842), fim da captura (2.208).

Exemplos de fluxos não classificáveis: fluxo 181 (`100.64.225.132-100.64.224.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 376 (`100.64.230.114-100.64.224.1-443-49832-6`): Valor não finito em Flow Bytes/s.; fluxo 396 (`100.64.230.114-100.64.224.1-80-49856-6`): Valor não finito em Flow Bytes/s.; fluxo 957 (`100.64.224.0-100.64.224.1-80-49694-6`): Valor não finito em Flow Bytes/s.; fluxo 4968 (`100.64.224.7-100.64.228.167-52322-443-6`): Valor não finito em Flow Bytes/s..

## Explicações

A estratégia Sem XAI não gera explicações. A chamada de aquecimento da inferência, antes de a captura abrir, levou 5,593 ms.

## Verificações

| Verificação | Resultado |
|---|---|
| Fluxos emitidos pelo extrator = fluxos recebidos pelo classificador + fluxos descartados na fila de saída do extrator | aprovada |
| Nenhum fluxo descartado na fila de saída do extrator (modo arquivo) | aprovada |
| Fluxos recebidos = classificados + não classificáveis | aprovada |
| t0 ≤ t1 ≤ t2 ≤ t3 em todos os fluxos classificados | aprovada |
| Nenhum pacote chegou a um fluxo já emitido (modo arquivo) | aprovada |
| Fluxos selecionados = fluxos que a estratégia manda explicar | aprovada |
| Cada explicação corresponde a um fluxo classificado, pelo número de sequência e pelo `Flow ID` | aprovada |
| Valor de referência + soma das contribuições = saída explicada, dentro da tolerância | aprovada |
| Fluxos explicados = fluxos selecionados | aprovada |
| Marcações dos fluxos explicados na ordem da estratégia: t2 ≤ seleção ≤ explicação ≤ t4 = t3 nas síncronas; t3 ≤ solicitação ≤ retirada da fila ≤ explicação ≤ t4 no modo assíncrono | aprovada |
| A saída explicada leva à probabilidade registrada na classificação | aprovada |
| Cada explicação tem uma contribuição por entrada do classificador | aprovada |
| Classificador, explicador e extrator nas CPUs configuradas | aprovada |

## Tempos

Os tempos abaixo mostram que a instrumentação funciona. A execução não controla a carga, então eles não são resultados do experimento.

| Medida | Média (ms) | Mediana (ms) | p95 (ms) | p99 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|---:|
| Tempo de inferência, t2 − t1 | 0,364 | 0,305 | 0,793 | 1,235 | 112,225 |
| Latência de classificação, t3 − t0 | 42,330 | 34,617 | 112,566 | 140,216 | 216,131 |
| Espera e preparo da entrada, t1 − t0 | 41,901 | 34,414 | 111,983 | 139,384 | 215,419 |
| Seleção para explicação | 0,001 | 0,001 | 0,002 | 0,003 | 0,031 |
| Escrita nos canais de saída | 0,044 | 0,031 | 0,091 | 0,186 | 23,221 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 23,4 | 372 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 207,6 | 1.740 |

A máquina tinha 6.268 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/arquivo/20261115T193553979282Z/report.json](../training-runs/nids/arquivo/20261115T193553979282Z/report.json).
