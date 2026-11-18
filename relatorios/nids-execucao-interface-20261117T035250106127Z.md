# Execução do NIDS: Sem XAI, XGBoost, interface

A execução passou nas verificações. O NIDS leu a interface `h2-eth0`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o XGBoost congelado, na estratégia Sem XAI. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

O tráfego é o trecho `campanha` da captura de terça-feira, até `2017-07-04T12:30:00Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 14.276.092 |
| Pacotes IPv4 usados na formação dos fluxos | 14.240.226 |
| Pacotes descartados por não serem IPv4 | 35.866 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 277.940 |
| Fluxos descartados na fila de saída do extrator | 21.639 |
| Fluxos recebidos pelo classificador | 256.301 |
| Fluxos classificados | 250.373 |
| Fluxos não classificáveis | 5.928 |

Estatísticas do libpcap: 59.298.416 pacotes recebidos, 45.022.324 descartados por falta de espaço no buffer e 0 descartados pela interface.

O buffer de captura foi pedido com 256 MiB, e o kernel mapeou 256 MiB.

A fila de saída do extrator chegou a 10.000 fluxos à espera da escrita, com limite de 10.000.

Causas de emissão: nova conexão TCP depois do encerramento (5.552), varredura do tempo limite (250.749).

Exemplos de fluxos não classificáveis: fluxo 2820 (`208.81.233.32-192.168.10.14-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 2828 (`100.64.1.132-100.64.0.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 2841 (`100.64.17.132-100.64.16.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 2861 (`100.64.33.132-100.64.32.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 2875 (`100.64.49.132-100.64.48.1-80-49870-6`): Valor não finito em Flow Bytes/s..

## Explicações

A estratégia Sem XAI não gera explicações. A chamada de aquecimento da inferência, antes de a captura abrir, levou 1,586 ms.

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
| Tempo de inferência, t2 − t1 | 0,321 | 0,291 | 0,564 | 0,810 | 84,385 |
| Latência de classificação, t3 − t0 | 5.987,843 | 808,605 | 30.672,982 | 38.666,133 | 44.161,211 |
| Espera e preparo da entrada, t1 − t0 | 5.987,465 | 808,272 | 30.672,271 | 38.665,032 | 44.160,767 |
| Seleção para explicação | 0,001 | 0,000 | 0,001 | 0,001 | 0,084 |
| Escrita nos canais de saída | 0,038 | 0,030 | 0,065 | 0,160 | 16,415 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 229,5 | 439 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 2.633,5 | 4.703 |

A máquina tinha 10.068 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/interface/20261117T035250106127Z/report.json](../training-runs/nids/interface/20261117T035250106127Z/report.json).
