# Execução do NIDS de referência: Random Forest, interface

A execução passou nas verificações. O NIDS leu a interface `h2-eth0`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o Random Forest congelado, na estratégia Sem XAI. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](protocolo-experimental.md).

O tráfego é o trecho `validacao` da captura de terça-feira, até `2017-07-04T12:30:00Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 3.540.441 |
| Pacotes IPv4 usados na formação dos fluxos | 3.533.385 |
| Pacotes descartados por não serem IPv4 | 7.056 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 30.970 |
| Fluxos recebidos pelo classificador | 30.970 |
| Fluxos classificados | 30.860 |
| Fluxos com erro nas entradas | 110 |

Estatísticas do libpcap: 3.954.069 pacotes recebidos, 413.628 descartados por falta de espaço no buffer e 0 descartados pela interface.

Causas de emissão: varredura do tempo limite (30.606), nova conexão TCP depois do encerramento (364).

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
| Tempo de inferência, t2 − t1 | 14,062 | 15,278 | 22,819 | 26,421 | 108,153 |
| Latência de classificação, t3 − t0 | 520,807 | 275,474 | 1.698,045 | 1.961,720 | 2.258,307 |
| Espera e preparo da entrada, t1 − t0 | 506,543 | 261,410 | 1.679,863 | 1.939,425 | 2.235,791 |
| Entrega no canal de saída, t3 − t2 | 0,202 | 0,179 | 0,269 | 0,379 | 556,361 |

O processo do classificador usou 490,8 s de CPU, com pico de 418 MiB de memória. O extrator usou 269,7 s de CPU, com pico de 1.688 MiB.

O registro da execução está em [training-runs/nids/interface/20261113T172323165539Z/report.json](../training-runs/nids/interface/20261113T172323165539Z/report.json).
