# Execução do NIDS de referência: XGBoost, interface

A execução passou nas verificações. O NIDS leu a interface `h2-eth0`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o XGBoost congelado, na estratégia Sem XAI. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](protocolo-experimental.md).

O tráfego é o trecho `validacao` da captura de terça-feira, até `2017-07-04T12:30:00Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 3.942.621 |
| Pacotes IPv4 usados na formação dos fluxos | 3.935.460 |
| Pacotes descartados por não serem IPv4 | 7.161 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 32.099 |
| Fluxos recebidos pelo classificador | 32.099 |
| Fluxos classificados | 32.071 |
| Fluxos com erro nas entradas | 28 |

Estatísticas do libpcap: 3.954.069 pacotes recebidos, 11.448 descartados por falta de espaço no buffer e 0 descartados pela interface.

Causas de emissão: varredura do tempo limite (31.735), nova conexão TCP depois do encerramento (364).

Exemplos de erro: fluxo 257 (`192.168.10.51-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 306 (`192.168.10.17-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 348 (`192.168.10.19-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 699 (`192.168.10.12-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 1121 (`192.168.10.16-128.100.100.128-123-123-17`): Valor não finito em Flow IAT Mean..

## Verificações

| Verificação | Resultado |
|---|---|
| Fluxos emitidos pelo extrator = fluxos recebidos pelo classificador | aprovada |
| Fluxos recebidos = classificados + erros | aprovada |
| t0 ≤ t1 ≤ t2 ≤ t3 em todos os fluxos classificados | aprovada |
| Nenhum pacote chegou a um fluxo já emitido (modo arquivo) | aprovada |

## Tempos

Os tempos abaixo mostram que a instrumentação funciona. A execução não controla a carga, então eles não são resultados do experimento.

| Medida | Média (ms) | Mediana (ms) | p95 (ms) | p99 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|---:|
| Tempo de inferência, t2 − t1 | 0,672 | 0,578 | 1,452 | 1,902 | 74,546 |
| Latência de classificação, t3 − t0 | 11,832 | 5,834 | 42,458 | 93,974 | 234,121 |
| Espera e preparo da entrada, t1 − t0 | 11,050 | 5,183 | 41,704 | 93,342 | 233,449 |
| Entrega no canal de saída, t3 − t2 | 0,110 | 0,095 | 0,239 | 0,324 | 8,106 |

O processo do classificador usou 75,1 s de CPU, com pico de 438 MiB de memória. O extrator usou 198,7 s de CPU, com pico de 1.876 MiB.

O registro da execução está em [training-runs/nids/interface/20261113T180244497948Z/report.json](../training-runs/nids/interface/20261113T180244497948Z/report.json).
