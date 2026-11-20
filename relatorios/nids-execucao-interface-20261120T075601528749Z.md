# Execução do NIDS: Síncrono total, Random Forest, interface

A execução passou nas verificações. O NIDS leu a interface `h2-eth0`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o Random Forest congelado, na estratégia Síncrono total. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

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

A fila de saída do extrator chegou a 2.674 fluxos à espera da escrita, com limite de 10.000.

Causas de emissão: nova conexão TCP depois do encerramento (726), varredura do tempo limite (48.090).

Exemplos de fluxos não classificáveis: fluxo 357 (`208.81.233.32-192.168.10.14-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 364 (`100.64.1.132-100.64.0.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 747 (`63.241.108.104-192.168.10.14-443-49832-6`): Valor não finito em Flow Bytes/s.; fluxo 754 (`100.64.6.114-100.64.0.1-443-49832-6`): Valor não finito em Flow Bytes/s.; fluxo 789 (`63.241.108.104-192.168.10.14-80-49856-6`): Valor não finito em Flow Bytes/s..

## Explicações

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 9,114 ms, e as chamadas de aquecimento levaram 10,901 ms na inferência e 11,410 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 48.782 | 100,00% |
| Selecionados para explicação | 48.782 | 100,00% |
| Com a explicação concluída | 48.782 | 100,00% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 6.7e-16, na escala de probabilidade, contra a tolerância de 1e-09.

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
| Tempo de inferência, t2 − t1 | 4,325 | 4,309 | 5,578 | 7,900 | 25,075 |
| Tempo de explicação | 7,168 | 7,249 | 9,083 | 12,250 | 32,635 |
| Latência de classificação, t3 − t0 | 7.247,905 | 2.975,919 | 28.672,213 | 32.845,785 | 34.431,442 |
| Latência de explicação, t4 − t0 | 7.247,905 | 2.975,919 | 28.672,213 | 32.845,785 | 34.431,442 |
| Espera e preparo da entrada, t1 − t0 | 7.236,275 | 2.963,294 | 28.660,726 | 32.834,236 | 34.419,921 |
| Seleção para explicação | 0,001 | 0,001 | 0,001 | 0,002 | 0,015 |
| Escrita nos canais de saída | 0,115 | 0,106 | 0,168 | 0,218 | 11,778 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 586,8 | 290 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 123,2 | 3.211 |

A máquina tinha 11.518 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/interface/20261120T075601528749Z/report.json](../training-runs/nids/interface/20261120T075601528749Z/report.json).
