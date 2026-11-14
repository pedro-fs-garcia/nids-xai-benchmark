# Execução do NIDS de referência: Random Forest, interface

A execução passou nas verificações. O NIDS leu a interface `h2-eth0`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o Random Forest congelado, na estratégia Sem XAI. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](protocolo-experimental.md).

O tráfego é o trecho `dev` da captura de terça-feira, até `2017-07-04T11:58:44Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 18.354 |
| Pacotes IPv4 usados na formação dos fluxos | 15.647 |
| Pacotes descartados por não serem IPv4 | 2.707 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 1.175 |
| Fluxos recebidos pelo classificador | 1.175 |
| Fluxos classificados | 1.170 |
| Fluxos não classificáveis | 5 |

Estatísticas do libpcap: 18.354 pacotes recebidos, 0 descartados por falta de espaço no buffer e 0 descartados pela interface.

O buffer de captura foi pedido com 256 MiB, e o kernel mapeou 256 MiB.

A fila de saída do extrator chegou a 34 fluxos à espera da escrita.

Causas de emissão: varredura do tempo limite (1.174), nova conexão TCP depois do encerramento (1).

Exemplos de fluxos não classificáveis: fluxo 257 (`192.168.10.51-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 306 (`192.168.10.17-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 348 (`192.168.10.19-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 699 (`192.168.10.12-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 1121 (`192.168.10.16-128.100.100.128-123-123-17`): Valor não finito em Flow IAT Mean..

## Verificações

| Verificação | Resultado |
|---|---|
| Fluxos emitidos pelo extrator = fluxos recebidos pelo classificador | aprovada |
| Fluxos recebidos = classificados + não classificáveis | aprovada |
| t0 ≤ t1 ≤ t2 ≤ t3 em todos os fluxos classificados | aprovada |
| Nenhum pacote chegou a um fluxo já emitido (modo arquivo) | aprovada |

## Tempos

Os tempos abaixo mostram que a instrumentação funciona. A execução não controla a carga, então eles não são resultados do experimento.

| Medida | Média (ms) | Mediana (ms) | p95 (ms) | p99 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|---:|
| Tempo de inferência, t2 − t1 | 11,066 | 9,481 | 28,521 | 37,724 | 46,870 |
| Latência de classificação, t3 − t0 | 137,265 | 51,246 | 562,141 | 700,771 | 820,781 |
| Espera e preparo da entrada, t1 − t0 | 126,044 | 39,079 | 555,144 | 695,763 | 802,730 |
| Entrega no canal de saída, t3 − t2 | 0,154 | 0,138 | 0,322 | 0,381 | 0,544 |

O processo do classificador usou 18,6 s de CPU, com pico de 203 MiB de memória. O extrator usou 19,8 s de CPU, com pico de 470 MiB.

O registro da execução está em [training-runs/nids/interface/20261113T234521228788Z/report.json](../training-runs/nids/interface/20261113T234521228788Z/report.json).
