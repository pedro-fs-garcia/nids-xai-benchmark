# Execução do NIDS: Síncrono condicional, Random Forest, interface

A execução passou nas verificações. O NIDS leu a interface `h2-eth0`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o Random Forest congelado, na estratégia Síncrono condicional. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

O tráfego é o trecho `campanha` da captura de terça-feira, até `2017-07-04T12:30:00Z` (UTC).

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

Estatísticas do libpcap: 3.706.151 pacotes recebidos, 0 descartados por falta de espaço no buffer e 0 descartados pela interface.

O buffer de captura foi pedido com 256 MiB, e o kernel mapeou 256 MiB.

A fila de saída do extrator chegou a 35 fluxos à espera da escrita, com limite de 10.000.

Causas de emissão: nova conexão TCP depois do encerramento (363), varredura do tempo limite (24.050).

Exemplos de fluxos não classificáveis: fluxo 181 (`208.81.233.32-192.168.10.14-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 376 (`63.241.108.104-192.168.10.14-443-49832-6`): Valor não finito em Flow Bytes/s.; fluxo 396 (`63.241.108.104-192.168.10.14-80-49856-6`): Valor não finito em Flow Bytes/s.; fluxo 957 (`13.107.4.50-192.168.10.14-80-49694-6`): Valor não finito em Flow Bytes/s.; fluxo 4968 (`192.168.10.16-23.96.179.163-52322-443-6`): Valor não finito em Flow Bytes/s..

## Explicações

O NIDS seleciona para explicação os fluxos em que a distância entre a probabilidade de ataque e 0,5 é menor ou igual a 0,4. O limiar vem da calibração registrada em [training-runs/nids/calibracao/20261114T204351398308Z](../training-runs/nids/calibracao/20261114T204351398308Z/report.json).

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 4,532 ms, e as chamadas de aquecimento levaram 24,544 ms na inferência e 12,008 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 24.396 | 100,00% |
| Selecionados para explicação | 34 | 0,14% |
| Com a explicação concluída | 34 | 0,14% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 2.2e-16, na escala de probabilidade, contra a tolerância de 1e-09.

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
| Tempo de inferência, t2 − t1 | 3,558 | 3,071 | 7,004 | 10,635 | 23,110 |
| Tempo de explicação | 8,177 | 5,101 | 17,701 | 20,712 | 21,664 |
| Latência de classificação, t3 − t0 | 28,910 | 13,461 | 112,652 | 221,812 | 402,065 |
| Latência de explicação, t4 − t0 | 20,273 | 20,289 | 39,040 | 46,512 | 49,078 |
| Espera e preparo da entrada, t1 − t0 | 25,287 | 10,179 | 109,006 | 217,289 | 397,212 |
| Seleção para explicação | 0,001 | 0,001 | 0,002 | 0,003 | 0,019 |
| Escrita nos canais de saída | 0,036 | 0,028 | 0,070 | 0,114 | 11,284 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 97,5 | 225 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 72,4 | 1.877 |

A máquina tinha 11.339 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/interface/20261120T071050476668Z/report.json](../training-runs/nids/interface/20261120T071050476668Z/report.json).
