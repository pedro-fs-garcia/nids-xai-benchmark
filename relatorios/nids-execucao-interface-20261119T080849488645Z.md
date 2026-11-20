# Execução do NIDS: Síncrono total, Random Forest, interface

A execução passou nas verificações. O NIDS leu a interface `h2-eth0`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o Random Forest congelado, na estratégia Síncrono total. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

O tráfego é o trecho `campanha` da captura de terça-feira, até `2017-07-04T12:30:00Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 14.824.604 |
| Pacotes IPv4 usados na formação dos fluxos | 14.812.640 |
| Pacotes descartados por não serem IPv4 | 11.964 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 97.622 |
| Fluxos descartados na fila de saída do extrator | 11.388 |
| Fluxos recebidos pelo classificador | 86.234 |
| Fluxos classificados | 86.172 |
| Fluxos não classificáveis | 62 |

Estatísticas do libpcap: 14.824.604 pacotes recebidos, 0 descartados por falta de espaço no buffer e 0 descartados pela interface.

O buffer de captura foi pedido com 256 MiB, e o kernel mapeou 256 MiB.

A fila de saída do extrator chegou a 10.000 fluxos à espera da escrita, com limite de 10.000.

Causas de emissão: nova conexão TCP depois do encerramento (1.452), varredura do tempo limite (84.782).

Exemplos de fluxos não classificáveis: fluxo 713 (`208.81.233.32-192.168.10.14-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 714 (`100.64.1.132-100.64.0.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 727 (`100.64.17.132-100.64.16.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 730 (`100.64.33.132-100.64.32.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1477 (`63.241.108.104-192.168.10.14-443-49832-6`): Valor não finito em Flow Bytes/s..

## Explicações

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 4,337 ms, e as chamadas de aquecimento levaram 4,419 ms na inferência e 4,645 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 86.172 | 100,00% |
| Selecionados para explicação | 86.172 | 100,00% |
| Com a explicação concluída | 86.172 | 100,00% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 5.6e-16, na escala de probabilidade, contra a tolerância de 1e-09.

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
| Tempo de inferência, t2 − t1 | 5,280 | 5,340 | 6,744 | 8,914 | 18,608 |
| Tempo de explicação | 8,791 | 8,897 | 11,078 | 14,830 | 27,369 |
| Latência de classificação, t3 − t0 | 101.888,296 | 115.966,207 | 159.775,168 | 162.280,339 | 166.092,257 |
| Latência de explicação, t4 − t0 | 101.888,296 | 115.966,207 | 159.775,168 | 162.280,339 | 166.092,257 |
| Espera e preparo da entrada, t1 − t0 | 101.874,045 | 115.952,823 | 159.759,847 | 162.265,478 | 166.079,380 |
| Seleção para explicação | 0,001 | 0,001 | 0,001 | 0,002 | 0,108 |
| Escrita nos canais de saída | 0,152 | 0,144 | 0,221 | 0,328 | 11,453 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 1.270,2 | 357 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 304,3 | 4.981 |

A máquina tinha 11.229 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/interface/20261119T080849488645Z/report.json](../training-runs/nids/interface/20261119T080849488645Z/report.json).
