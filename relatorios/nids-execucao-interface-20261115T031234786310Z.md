# Execução do NIDS: Síncrono condicional, XGBoost, interface

A execução passou nas verificações. O NIDS leu a interface `h2-eth0`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o XGBoost congelado, na estratégia Síncrono condicional. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

O tráfego é o trecho `validacao` da captura de terça-feira, até `2017-07-04T12:30:00Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 3.954.069 |
| Pacotes IPv4 usados na formação dos fluxos | 3.946.908 |
| Pacotes descartados por não serem IPv4 | 7.161 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 32.108 |
| Fluxos descartados na fila de saída do extrator | 0 |
| Fluxos recebidos pelo classificador | 32.108 |
| Fluxos classificados | 32.086 |
| Fluxos não classificáveis | 22 |

Estatísticas do libpcap: 3.954.069 pacotes recebidos, 0 descartados por falta de espaço no buffer e 0 descartados pela interface.

O buffer de captura foi pedido com 256 MiB, e o kernel mapeou 256 MiB.

A fila de saída do extrator chegou a 36 fluxos à espera da escrita, com limite de 10.000.

Causas de emissão: varredura do tempo limite (31.744), nova conexão TCP depois do encerramento (364).

Exemplos de fluxos não classificáveis: fluxo 257 (`192.168.10.51-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 306 (`192.168.10.17-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 348 (`192.168.10.19-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 699 (`192.168.10.12-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 1121 (`192.168.10.16-128.100.100.128-123-123-17`): Valor não finito em Flow IAT Mean..

## Explicações

O NIDS seleciona para explicação os fluxos em que a probabilidade de ataque é maior ou igual a 0,5. O limiar vem da calibração registrada em [training-runs/nids/calibracao/20261114T204351398308Z](../training-runs/nids/calibracao/20261114T204351398308Z/report.json).

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 36,076 ms, e as chamadas de aquecimento levaram 0,918 ms na inferência e 1,128 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 32.086 | 100,00% |
| Selecionados para explicação | 688 | 2,14% |
| Com a explicação concluída | 688 | 2,14% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 4e-06, na escala de log-odds, contra a tolerância de 0.0001.

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
| Tempo de inferência, t2 − t1 | 0,264 | 0,178 | 0,586 | 1,247 | 55,396 |
| Tempo de explicação | 0,640 | 0,442 | 1,682 | 2,003 | 4,352 |
| Latência de classificação, t3 − t0 | 3,750 | 2,279 | 11,298 | 21,987 | 59,145 |
| Latência de explicação, t4 − t0 | 2,663 | 1,805 | 5,779 | 9,366 | 18,400 |
| Espera e preparo da entrada, t1 − t0 | 3,429 | 2,001 | 11,074 | 21,811 | 58,786 |
| Seleção para explicação | 0,001 | 0,000 | 0,002 | 0,004 | 0,025 |
| Escrita nos canais de saída | 0,027 | 0,015 | 0,070 | 0,139 | 11,427 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 38,3 | 447 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 143,6 | 2.090 |

A máquina tinha 6.014 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/interface/20261115T031234786310Z/report.json](../training-runs/nids/interface/20261115T031234786310Z/report.json).
