# Execução do NIDS: Síncrono condicional, XGBoost, interface

A execução passou nas verificações. O NIDS leu a interface `h2-eth0`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o XGBoost congelado, na estratégia Síncrono condicional. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

O tráfego é o trecho `campanha` da captura de terça-feira, até `2017-07-04T12:30:00Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 14.814.373 |
| Pacotes IPv4 usados na formação dos fluxos | 14.802.409 |
| Pacotes descartados por não serem IPv4 | 11.964 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 97.889 |
| Fluxos descartados na fila de saída do extrator | 0 |
| Fluxos recebidos pelo classificador | 97.889 |
| Fluxos classificados | 97.797 |
| Fluxos não classificáveis | 92 |

Estatísticas do libpcap: 14.824.604 pacotes recebidos, 10.231 descartados por falta de espaço no buffer e 0 descartados pela interface.

O buffer de captura foi pedido com 256 MiB, e o kernel mapeou 256 MiB.

A fila de saída do extrator chegou a 1.159 fluxos à espera da escrita, com limite de 10.000.

Causas de emissão: nova conexão TCP depois do encerramento (1.452), varredura do tempo limite (96.437).

Exemplos de fluxos não classificáveis: fluxo 713 (`208.81.233.32-192.168.10.14-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 719 (`100.64.1.132-100.64.0.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 725 (`100.64.17.132-100.64.16.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 728 (`100.64.33.132-100.64.32.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1483 (`63.241.108.104-192.168.10.14-443-49832-6`): Valor não finito em Flow Bytes/s..

## Explicações

O NIDS seleciona para explicação os fluxos em que a probabilidade de ataque é maior ou igual a 0,5. O limiar vem da calibração registrada em [training-runs/nids/calibracao/20261114T204351398308Z](../training-runs/nids/calibracao/20261114T204351398308Z/report.json).

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 14,007 ms, e as chamadas de aquecimento levaram 0,423 ms na inferência e 0,460 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 97.797 | 100,00% |
| Selecionados para explicação | 2.767 | 2,83% |
| Com a explicação concluída | 2.767 | 2,83% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 4.5e-06, na escala de log-odds, contra a tolerância de 0.0001.

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
| Tempo de inferência, t2 − t1 | 0,317 | 0,234 | 0,720 | 1,184 | 37,670 |
| Tempo de explicação | 1,794 | 0,652 | 1,714 | 2,631 | 2.604,339 |
| Latência de classificação, t3 − t0 | 159,536 | 6,607 | 221,399 | 4.984,972 | 8.462,271 |
| Latência de explicação, t4 − t0 | 340,898 | 4,566 | 2.994,908 | 6.294,726 | 8.185,014 |
| Espera e preparo da entrada, t1 − t0 | 158,524 | 6,222 | 219,507 | 4.954,622 | 8.462,045 |
| Seleção para explicação | 0,001 | 0,001 | 0,002 | 0,003 | 0,044 |
| Escrita nos canais de saída | 0,624 | 0,024 | 0,100 | 0,202 | 8.181,644 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 88,1 | 269 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 280,2 | 4.886 |

A máquina tinha 9.759 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/interface/20261118T194206328208Z/report.json](../training-runs/nids/interface/20261118T194206328208Z/report.json).
