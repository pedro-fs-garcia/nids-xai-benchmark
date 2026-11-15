# Execução do NIDS: Síncrono total, Random Forest, arquivo

A execução passou nas verificações. O NIDS leu o arquivo `/home/pedro/projects/explicabilidade-ia/derived-data/pcap/tuesday/segment-dev.pcap`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o Random Forest congelado, na estratégia Síncrono total. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

O tráfego é o trecho `dev` da captura de terça-feira, até `2017-07-04T11:58:44Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 18.354 |
| Pacotes IPv4 usados na formação dos fluxos | 15.647 |
| Pacotes descartados por não serem IPv4 | 2.707 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 1.175 |
| Fluxos descartados na fila de saída do extrator | 0 |
| Fluxos recebidos pelo classificador | 1.175 |
| Fluxos classificados | 1.170 |
| Fluxos não classificáveis | 5 |

Causas de emissão: varredura do tempo limite (243), nova conexão TCP depois do encerramento (1), fim da captura (931).

Exemplos de fluxos não classificáveis: fluxo 307 (`192.168.10.12-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 426 (`192.168.10.19-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 484 (`192.168.10.16-128.100.100.128-123-123-17`): Valor não finito em Flow IAT Mean.; fluxo 815 (`192.168.10.17-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 881 (`192.168.10.51-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s..

## Explicações

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 5,170 ms, e as chamadas de aquecimento levaram 5,360 ms na inferência e 5,881 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 1.170 | 100,00% |
| Selecionados para explicação | 1.170 | 100,00% |
| Com a explicação concluída | 1.170 | 100,00% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 4.5e-16, na escala de probabilidade, contra a tolerância de 1e-09.

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

## Conferência com a tabela de referência

Fora da borda dos últimos 120 s, 243 fluxos do NIDS correspondem a fluxos de `tuesday.csv`. Ficaram 0 fluxos só no CSV e 0 só no NIDS. Destes, 0 têm algum valor `NaN`: são fluxos de um único pacote, que a rotulagem dos autores descartou com `dropna` e que o NIDS registra como não classificáveis.

As entradas inteiras coincidem exatamente com as do CSV. 391 valores com fração diferem nos últimos algarismos, com diferença relativa de no máximo 2.3e-15, como na conferência da extração.

O modelo aplicado às linhas da tabela de referência e o NIDS produziram previsões diferentes em 0 de 243 fluxos. A maior diferença de probabilidade foi 0, contra a tolerância de 1e-12. A conferência não calcula métricas de detecção.

## Tempos

Os tempos abaixo mostram que a instrumentação funciona. A execução não controla a carga, então eles não são resultados do experimento.

| Medida | Média (ms) | Mediana (ms) | p95 (ms) | p99 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|---:|
| Tempo de inferência, t2 − t1 | 4,565 | 4,360 | 5,873 | 7,091 | 8,478 |
| Tempo de explicação | 7,415 | 7,070 | 9,545 | 11,081 | 12,259 |
| Latência de classificação, t3 − t0 | 1.037,689 | 1.040,506 | 1.263,879 | 1.390,473 | 1.466,477 |
| Latência de explicação, t4 − t0 | 1.037,689 | 1.040,506 | 1.263,879 | 1.390,473 | 1.466,477 |
| Espera e preparo da entrada, t1 − t0 | 1.025,533 | 1.028,578 | 1.251,972 | 1.376,271 | 1.452,119 |
| Seleção para explicação | 0,001 | 0,001 | 0,002 | 0,002 | 0,008 |
| Escrita nos canais de saída | 0,146 | 0,144 | 0,196 | 0,228 | 0,308 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 19,1 | 216 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 4,3 | 196 |

A máquina tinha 9.093 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/arquivo/20261114T214852703538Z/report.json](../training-runs/nids/arquivo/20261114T214852703538Z/report.json).
