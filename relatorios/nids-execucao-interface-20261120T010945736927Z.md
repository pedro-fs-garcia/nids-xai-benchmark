# Execução do NIDS: Síncrono condicional, XGBoost, interface

A execução passou nas verificações. O NIDS leu a interface `h2-eth0`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o XGBoost congelado, na estratégia Síncrono condicional. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

O tráfego é o trecho `campanha` da captura de terça-feira, até `2017-07-04T12:30:00Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 7.412.302 |
| Pacotes IPv4 usados na formação dos fluxos | 7.406.320 |
| Pacotes descartados por não serem IPv4 | 5.982 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 48.816 |
| Fluxos descartados na fila de saída do extrator | 0 |
| Fluxos recebidos pelo classificador | 48.816 |
| Fluxos classificados | 48.782 |
| Fluxos não classificáveis | 34 |

Estatísticas do libpcap: 7.412.302 pacotes recebidos, 0 descartados por falta de espaço no buffer e 0 descartados pela interface.

O buffer de captura foi pedido com 256 MiB, e o kernel mapeou 256 MiB.

A fila de saída do extrator chegou a 33 fluxos à espera da escrita, com limite de 10.000.

Causas de emissão: nova conexão TCP depois do encerramento (726), varredura do tempo limite (48.090).

Exemplos de fluxos não classificáveis: fluxo 357 (`208.81.233.32-192.168.10.14-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 364 (`100.64.1.132-100.64.0.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 747 (`63.241.108.104-192.168.10.14-443-49832-6`): Valor não finito em Flow Bytes/s.; fluxo 754 (`100.64.6.114-100.64.0.1-443-49832-6`): Valor não finito em Flow Bytes/s.; fluxo 789 (`63.241.108.104-192.168.10.14-80-49856-6`): Valor não finito em Flow Bytes/s..

## Explicações

O NIDS seleciona para explicação os fluxos em que a probabilidade de ataque é maior ou igual a 0,5. O limiar vem da calibração registrada em [training-runs/nids/calibracao/20261114T204351398308Z](../training-runs/nids/calibracao/20261114T204351398308Z/report.json).

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 12,489 ms, e as chamadas de aquecimento levaram 0,423 ms na inferência e 0,435 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 48.782 | 100,00% |
| Selecionados para explicação | 1.390 | 2,85% |
| Com a explicação concluída | 1.390 | 2,85% |

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
| Tempo de inferência, t2 − t1 | 0,283 | 0,188 | 0,699 | 1,264 | 4,592 |
| Tempo de explicação | 0,656 | 0,468 | 1,664 | 2,102 | 4,392 |
| Latência de classificação, t3 − t0 | 4,895 | 2,717 | 16,623 | 30,891 | 55,522 |
| Latência de explicação, t4 − t0 | 2,760 | 1,847 | 6,000 | 9,797 | 24,619 |
| Espera e preparo da entrada, t1 − t0 | 4,544 | 2,334 | 16,365 | 30,644 | 55,345 |
| Seleção para explicação | 0,001 | 0,000 | 0,002 | 0,003 | 0,036 |
| Escrita nos canais de saída | 0,033 | 0,018 | 0,089 | 0,165 | 7,391 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 37,3 | 250 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 113,6 | 3.627 |

A máquina tinha 11.031 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/interface/20261120T010945736927Z/report.json](../training-runs/nids/interface/20261120T010945736927Z/report.json).
