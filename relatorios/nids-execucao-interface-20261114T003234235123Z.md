# Execução do NIDS de referência: XGBoost, interface

A execução passou nas verificações. O NIDS leu a interface `h2-eth0`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o XGBoost congelado, na estratégia Sem XAI. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](protocolo-experimental.md).

O tráfego é o trecho `validacao` da captura de terça-feira, até `2017-07-04T12:30:00Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 3.954.069 |
| Pacotes IPv4 usados na formação dos fluxos | 3.946.908 |
| Pacotes descartados por não serem IPv4 | 7.161 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 32.108 |
| Fluxos recebidos pelo classificador | 32.108 |
| Fluxos classificados | 32.086 |
| Fluxos não classificáveis | 22 |

Estatísticas do libpcap: 3.954.069 pacotes recebidos, 0 descartados por falta de espaço no buffer e 0 descartados pela interface.

O buffer de captura foi pedido com 256 MiB, e o kernel mapeou 256 MiB.

A fila de saída do extrator chegou a 35 fluxos à espera da escrita.

Causas de emissão: varredura do tempo limite (31.744), nova conexão TCP depois do encerramento (364).

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
| Tempo de inferência, t2 − t1 | 0,656 | 0,563 | 1,453 | 1,901 | 121,520 |
| Latência de classificação, t3 − t0 | 10,699 | 6,158 | 35,694 | 62,539 | 147,165 |
| Espera e preparo da entrada, t1 − t0 | 9,935 | 5,488 | 34,971 | 61,565 | 146,266 |
| Entrega no canal de saída, t3 − t2 | 0,108 | 0,093 | 0,237 | 0,324 | 14,006 |

O processo do classificador usou 70,6 s de CPU, com pico de 439 MiB de memória. O extrator usou 254,2 s de CPU, com pico de 2.116 MiB.

O registro da execução está em [training-runs/nids/interface/20261114T003234235123Z/report.json](../training-runs/nids/interface/20261114T003234235123Z/report.json).
