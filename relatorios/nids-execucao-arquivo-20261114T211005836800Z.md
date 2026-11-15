# Execução do NIDS: Síncrono total, XGBoost, arquivo

A execução passou nas verificações. O NIDS leu o arquivo `/home/pedro/projects/explicabilidade-ia/derived-data/pcap/tuesday/segment-validacao.pcap`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o XGBoost congelado, na estratégia Síncrono total. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

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

Causas de emissão: varredura do tempo limite (29.537), nova conexão TCP depois do encerramento (364), fim da captura (2.207).

Exemplos de fluxos não classificáveis: fluxo 257 (`192.168.10.51-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 306 (`192.168.10.17-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 348 (`192.168.10.19-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 699 (`192.168.10.12-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 1121 (`192.168.10.16-128.100.100.128-123-123-17`): Valor não finito em Flow IAT Mean..

## Explicações

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 38,715 ms, e as chamadas de aquecimento levaram 0,976 ms na inferência e 1,205 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 32.086 | 100,00% |
| Selecionados para explicação | 32.086 | 100,00% |
| Com a explicação concluída | 32.086 | 100,00% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 7.1e-06, na escala de log-odds, contra a tolerância de 0.0001.

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

Fora da borda dos últimos 120 s, 29.880 fluxos do NIDS correspondem a fluxos de `tuesday.csv`. Ficaram 0 fluxos só no CSV e 21 só no NIDS. Destes, 21 têm algum valor `NaN`: são fluxos de um único pacote, que a rotulagem dos autores descartou com `dropna` e que o NIDS registra como não classificáveis.

As entradas inteiras coincidem exatamente com as do CSV. 54.980 valores com fração diferem nos últimos algarismos, com diferença relativa de no máximo 6e-15, como na conferência da extração.

O modelo aplicado às linhas da tabela de referência e o NIDS produziram previsões diferentes em 0 de 29.880 fluxos. A maior diferença de probabilidade foi 0, contra a tolerância de 1e-12. A conferência não calcula métricas de detecção.

## Tempos

Os tempos abaixo mostram que a instrumentação funciona. A execução não controla a carga, então eles não são resultados do experimento.

| Medida | Média (ms) | Mediana (ms) | p95 (ms) | p99 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|---:|
| Tempo de inferência, t2 − t1 | 0,258 | 0,228 | 0,508 | 0,744 | 3,268 |
| Tempo de explicação | 0,482 | 0,455 | 0,792 | 1,181 | 74,904 |
| Latência de classificação, t3 − t0 | 72,795 | 86,633 | 125,184 | 165,848 | 230,176 |
| Latência de explicação, t4 − t0 | 72,795 | 86,633 | 125,184 | 165,848 | 230,176 |
| Espera e preparo da entrada, t1 − t0 | 71,950 | 85,850 | 124,271 | 164,624 | 228,394 |
| Seleção para explicação | 0,000 | 0,000 | 0,001 | 0,002 | 0,017 |
| Escrita nos canais de saída | 0,089 | 0,083 | 0,146 | 0,223 | 3,285 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 122,4 | 609 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 138,0 | 1.875 |

A máquina tinha 9.121 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/arquivo/20261114T211005836800Z/report.json](../training-runs/nids/arquivo/20261114T211005836800Z/report.json).
