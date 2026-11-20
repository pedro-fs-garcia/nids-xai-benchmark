# Execução do NIDS: Síncrono condicional, Random Forest, interface

A execução passou nas verificações. O NIDS leu a interface `h2-eth0`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o Random Forest congelado, na estratégia Síncrono condicional. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

O tráfego é o trecho `campanha` da captura de terça-feira, até `2017-07-04T12:30:00Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 14.824.604 |
| Pacotes IPv4 usados na formação dos fluxos | 14.812.640 |
| Pacotes descartados por não serem IPv4 | 11.964 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 97.622 |
| Fluxos descartados na fila de saída do extrator | 0 |
| Fluxos recebidos pelo classificador | 97.622 |
| Fluxos classificados | 97.554 |
| Fluxos não classificáveis | 68 |

Estatísticas do libpcap: 14.824.604 pacotes recebidos, 0 descartados por falta de espaço no buffer e 0 descartados pela interface.

O buffer de captura foi pedido com 256 MiB, e o kernel mapeou 256 MiB.

A fila de saída do extrator chegou a 6.125 fluxos à espera da escrita, com limite de 10.000.

Causas de emissão: nova conexão TCP depois do encerramento (1.452), varredura do tempo limite (96.170).

Exemplos de fluxos não classificáveis: fluxo 710 (`208.81.233.32-192.168.10.14-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 724 (`100.64.1.132-100.64.0.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 725 (`100.64.33.132-100.64.32.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 726 (`100.64.17.132-100.64.16.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1489 (`63.241.108.104-192.168.10.14-443-49832-6`): Valor não finito em Flow Bytes/s..

## Explicações

O NIDS seleciona para explicação os fluxos em que a distância entre a probabilidade de ataque e 0,5 é menor ou igual a 0,4. O limiar vem da calibração registrada em [training-runs/nids/calibracao/20261114T204351398308Z](../training-runs/nids/calibracao/20261114T204351398308Z/report.json).

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 12,918 ms, e as chamadas de aquecimento levaram 20,073 ms na inferência e 12,988 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 97.554 | 100,00% |
| Selecionados para explicação | 131 | 0,13% |
| Com a explicação concluída | 131 | 0,13% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 2.8e-16, na escala de probabilidade, contra a tolerância de 1e-09.

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
| Tempo de inferência, t2 − t1 | 6,586 | 6,495 | 9,516 | 12,654 | 33,986 |
| Tempo de explicação | 10,481 | 10,591 | 15,341 | 20,678 | 28,632 |
| Latência de classificação, t3 − t0 | 12.476,138 | 8.085,730 | 42.934,722 | 45.110,467 | 47.127,323 |
| Latência de explicação, t4 − t0 | 7.829,888 | 6.040,850 | 43.174,599 | 43.424,095 | 43.448,275 |
| Espera e preparo da entrada, t1 − t0 | 12.469,427 | 8.076,906 | 42.928,322 | 45.103,924 | 47.119,596 |
| Seleção para explicação | 0,002 | 0,002 | 0,003 | 0,004 | 0,214 |
| Escrita nos canais de saída | 0,073 | 0,067 | 0,117 | 0,216 | 13,419 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 713,9 | 270 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 333,7 | 4.921 |

A máquina tinha 9.490 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/interface/20261119T225402028747Z/report.json](../training-runs/nids/interface/20261119T225402028747Z/report.json).
