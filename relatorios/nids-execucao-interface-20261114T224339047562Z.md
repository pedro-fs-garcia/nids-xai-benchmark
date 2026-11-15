# Execução do NIDS: Síncrono total, Random Forest, interface

A execução passou nas verificações. O NIDS leu a interface `h2-eth0`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o Random Forest congelado, na estratégia Síncrono total. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

O tráfego é o trecho `dev` da captura de terça-feira, até `2017-07-04T11:58:44Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 18.354 |
| Pacotes IPv4 usados na formação dos fluxos | 15.647 |
| Pacotes descartados por não serem IPv4 | 2.707 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 1.175 |
| Fluxos descartados na fila de saída do extrator | 0 |
| Fluxos recebidos pelo classificador | 1.175 |
| Fluxos classificados | 1.170 |
| Fluxos não classificáveis | 5 |

Estatísticas do libpcap: 18.354 pacotes recebidos, 0 descartados por falta de espaço no buffer e 0 descartados pela interface.

O buffer de captura foi pedido com 256 MiB, e o kernel mapeou 256 MiB.

A fila de saída do extrator chegou a 35 fluxos à espera da escrita, com limite de 10.000.

Causas de emissão: varredura do tempo limite (1.174), nova conexão TCP depois do encerramento (1).

Exemplos de fluxos não classificáveis: fluxo 257 (`192.168.10.51-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 306 (`192.168.10.17-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 348 (`192.168.10.19-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 699 (`192.168.10.12-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 1121 (`192.168.10.16-128.100.100.128-123-123-17`): Valor não finito em Flow IAT Mean..

## Explicações

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 6,464 ms, e as chamadas de aquecimento levaram 10,570 ms na inferência e 10,512 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 1.170 | 100,00% |
| Selecionados para explicação | 1.170 | 100,00% |
| Com a explicação concluída | 1.170 | 100,00% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 4.5e-16, na escala de probabilidade, contra a tolerância de 1e-09.

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
| Tempo de inferência, t2 − t1 | 5,685 | 3,481 | 11,238 | 15,484 | 22,671 |
| Tempo de explicação | 8,668 | 5,334 | 17,978 | 22,924 | 29,392 |
| Latência de classificação, t3 − t0 | 174,873 | 74,137 | 643,379 | 1.018,268 | 1.088,923 |
| Latência de explicação, t4 − t0 | 174,873 | 74,137 | 643,379 | 1.018,268 | 1.088,923 |
| Espera e preparo da entrada, t1 − t0 | 160,333 | 57,758 | 635,142 | 1.010,284 | 1.080,750 |
| Seleção para explicação | 0,001 | 0,001 | 0,002 | 0,003 | 0,010 |
| Escrita nos canais de saída | 0,155 | 0,133 | 0,307 | 0,437 | 0,498 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 21,7 | 215 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 21,1 | 446 |

A máquina tinha 9.098 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/interface/20261114T224339047562Z/report.json](../training-runs/nids/interface/20261114T224339047562Z/report.json).
