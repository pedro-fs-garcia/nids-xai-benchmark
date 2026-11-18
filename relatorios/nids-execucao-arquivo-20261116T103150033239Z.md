# Execução do NIDS: Sem XAI, XGBoost, arquivo

A execução passou nas verificações. O NIDS leu o arquivo `/home/pedro/projects/explicabilidade-ia/training-runs/nids/aceleracao/20261116T102343628819Z/segment-campanha-x2.pcap`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o XGBoost congelado, na estratégia Sem XAI. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 3.706.151 |
| Pacotes IPv4 usados na formação dos fluxos | 3.703.160 |
| Pacotes descartados por não serem IPv4 | 2.991 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 22.993 |
| Fluxos descartados na fila de saída do extrator | 0 |
| Fluxos recebidos pelo classificador | 22.993 |
| Fluxos classificados | 22.983 |
| Fluxos não classificáveis | 10 |

Causas de emissão: nova conexão TCP depois do encerramento (363), varredura do tempo limite (18.957), fim da captura (3.673).

Exemplos de fluxos não classificáveis: fluxo 352 (`208.81.233.32-192.168.10.14-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 544 (`63.241.108.104-192.168.10.14-443-49832-6`): Valor não finito em Flow Bytes/s.; fluxo 563 (`63.241.108.104-192.168.10.14-80-49856-6`): Valor não finito em Flow Bytes/s.; fluxo 1048 (`13.107.4.50-192.168.10.14-80-49694-6`): Valor não finito em Flow Bytes/s.; fluxo 5129 (`192.168.10.19-77.238.121.220-53961-443-6`): Valor não finito em Flow Bytes/s..

## Explicações

A estratégia Sem XAI não gera explicações. A chamada de aquecimento da inferência, antes de a captura abrir, levou 6,306 ms.

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
| Tempo de inferência, t2 − t1 | 0,671 | 0,592 | 1,283 | 1,657 | 9,714 |
| Latência de classificação, t3 − t0 | 85,928 | 97,942 | 176,937 | 252,308 | 318,179 |
| Espera e preparo da entrada, t1 − t0 | 85,139 | 97,376 | 175,745 | 250,795 | 316,454 |
| Seleção para explicação | 0,001 | 0,001 | 0,003 | 0,004 | 0,034 |
| Escrita nos canais de saída | 0,076 | 0,064 | 0,154 | 0,213 | 6,813 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 42,0 | 436 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 228,2 | 1.554 |

A máquina tinha 4.895 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/arquivo/20261116T103150033239Z/report.json](../training-runs/nids/arquivo/20261116T103150033239Z/report.json).
