# Execução do NIDS: Síncrono total, XGBoost, interface

A execução passou nas verificações. O NIDS leu a interface `h2-eth0`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o XGBoost congelado, na estratégia Síncrono total. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

O tráfego é o trecho `campanha` da captura de terça-feira, até `2017-07-04T12:30:00Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 15.500.122 |
| Pacotes IPv4 usados na formação dos fluxos | 15.479.415 |
| Pacotes descartados por não serem IPv4 | 20.707 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 169.519 |
| Fluxos descartados na fila de saída do extrator | 116 |
| Fluxos recebidos pelo classificador | 169.403 |
| Fluxos classificados | 168.263 |
| Fluxos não classificáveis | 1.140 |

Estatísticas do libpcap: 29.649.208 pacotes recebidos, 14.149.086 descartados por falta de espaço no buffer e 0 descartados pela interface.

O buffer de captura foi pedido com 256 MiB, e o kernel mapeou 256 MiB.

A fila de saída do extrator chegou a 10.000 fluxos à espera da escrita, com limite de 10.000.

Causas de emissão: nova conexão TCP depois do encerramento (2.784), varredura do tempo limite (166.619).

Exemplos de fluxos não classificáveis: fluxo 1413 (`208.81.233.32-192.168.10.14-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1424 (`100.64.1.132-100.64.0.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1432 (`100.64.17.132-100.64.16.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1442 (`100.64.33.132-100.64.32.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1444 (`100.64.49.132-100.64.48.1-80-49870-6`): Valor não finito em Flow Bytes/s..

## Explicações

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 37,993 ms, e as chamadas de aquecimento levaram 1,392 ms na inferência e 1,040 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 168.263 | 100,00% |
| Selecionados para explicação | 168.263 | 100,00% |
| Com a explicação concluída | 168.263 | 100,00% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 7.4e-06, na escala de log-odds, contra a tolerância de 0.0001.

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
| Tempo de inferência, t2 − t1 | 0,372 | 0,332 | 0,694 | 1,025 | 85,743 |
| Tempo de explicação | 0,671 | 0,642 | 1,093 | 1,529 | 27,242 |
| Latência de classificação, t3 − t0 | 8.521,884 | 852,585 | 45.592,786 | 55.787,658 | 61.478,596 |
| Latência de explicação, t4 − t0 | 8.521,884 | 852,585 | 45.592,786 | 55.787,658 | 61.478,596 |
| Espera e preparo da entrada, t1 − t0 | 8.520,686 | 851,416 | 45.590,873 | 55.785,729 | 61.477,338 |
| Seleção para explicação | 0,001 | 0,001 | 0,001 | 0,002 | 0,086 |
| Escrita nos canais de saída | 0,132 | 0,117 | 0,228 | 0,428 | 16,242 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 294,7 | 517 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 2.068,8 | 4.684 |

A máquina tinha 10.550 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/interface/20261117T124450541633Z/report.json](../training-runs/nids/interface/20261117T124450541633Z/report.json).
