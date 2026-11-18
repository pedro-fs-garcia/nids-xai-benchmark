# Execução do NIDS: Síncrono condicional, Random Forest, interface

A execução passou nas verificações. O NIDS leu a interface `h2-eth0`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o Random Forest congelado, na estratégia Síncrono condicional. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

O tráfego é o trecho `campanha` da captura de terça-feira, até `2017-07-04T12:30:00Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 14.556.369 |
| Pacotes IPv4 usados na formação dos fluxos | 14.536.507 |
| Pacotes descartados por não serem IPv4 | 19.862 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 165.852 |
| Fluxos descartados na fila de saída do extrator | 40.234 |
| Fluxos recebidos pelo classificador | 125.618 |
| Fluxos classificados | 124.605 |
| Fluxos não classificáveis | 1.013 |

Estatísticas do libpcap: 29.649.208 pacotes recebidos, 15.092.839 descartados por falta de espaço no buffer e 0 descartados pela interface.

O buffer de captura foi pedido com 256 MiB, e o kernel mapeou 256 MiB.

A fila de saída do extrator chegou a 10.000 fluxos à espera da escrita, com limite de 10.000.

Causas de emissão: nova conexão TCP depois do encerramento (2.784), varredura do tempo limite (122.834).

Exemplos de fluxos não classificáveis: fluxo 1413 (`208.81.233.32-192.168.10.14-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1420 (`100.64.1.132-100.64.0.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1433 (`100.64.17.132-100.64.16.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1439 (`100.64.33.132-100.64.32.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1463 (`100.64.49.132-100.64.48.1-80-49870-6`): Valor não finito em Flow Bytes/s..

## Explicações

O NIDS seleciona para explicação os fluxos em que a probabilidade de ataque é maior ou igual a 0,5. O limiar vem da calibração registrada em [training-runs/nids/calibracao/20261114T204351398308Z](../training-runs/nids/calibracao/20261114T204351398308Z/report.json).

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 11,524 ms, e as chamadas de aquecimento levaram 19,889 ms na inferência e 11,728 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 124.605 | 100,00% |
| Selecionados para explicação | 1.725 | 1,38% |
| Com a explicação concluída | 1.725 | 1,38% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 5.6e-16, na escala de probabilidade, contra a tolerância de 1e-09.

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
| Tempo de inferência, t2 − t1 | 6,558 | 6,051 | 10,312 | 14,088 | 102,079 |
| Tempo de explicação | 10,785 | 10,479 | 17,769 | 24,601 | 77,084 |
| Latência de classificação, t3 − t0 | 63.898,946 | 57.196,037 | 160.916,509 | 182.894,339 | 192.298,261 |
| Latência de explicação, t4 − t0 | 83.170,978 | 119.902,891 | 166.648,760 | 189.330,712 | 189.907,180 |
| Espera e preparo da entrada, t1 − t0 | 63.892,114 | 57.190,017 | 160.907,351 | 182.888,350 | 192.290,654 |
| Seleção para explicação | 0,002 | 0,001 | 0,003 | 0,003 | 1,175 |
| Escrita nos canais de saída | 0,086 | 0,066 | 0,150 | 0,365 | 14,746 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 919,1 | 322 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 2.088,9 | 4.670 |

A máquina tinha 10.746 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/interface/20261117T081315617941Z/report.json](../training-runs/nids/interface/20261117T081315617941Z/report.json).
