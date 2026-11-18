# Execução do NIDS: Assíncrono, XGBoost, arquivo

A execução passou nas verificações. O NIDS leu o arquivo `/home/pedro/projects/explicabilidade-ia/derived-data/pcap/tuesday-campanha/segment-campanha.pcap`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o XGBoost congelado, na estratégia Assíncrono. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

O tráfego é o trecho `campanha` da captura de terça-feira, até `2017-07-04T12:30:00Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 3.706.151 |
| Pacotes IPv4 usados na formação dos fluxos | 3.703.160 |
| Pacotes descartados por não serem IPv4 | 2.991 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 24.413 |
| Fluxos descartados na fila de saída do extrator | 0 |
| Fluxos recebidos pelo classificador | 24.413 |
| Fluxos classificados | 24.396 |
| Fluxos não classificáveis | 17 |

Causas de emissão: nova conexão TCP depois do encerramento (363), varredura do tempo limite (21.842), fim da captura (2.208).

Exemplos de fluxos não classificáveis: fluxo 181 (`208.81.233.32-192.168.10.14-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 376 (`63.241.108.104-192.168.10.14-443-49832-6`): Valor não finito em Flow Bytes/s.; fluxo 396 (`63.241.108.104-192.168.10.14-80-49856-6`): Valor não finito em Flow Bytes/s.; fluxo 957 (`13.107.4.50-192.168.10.14-80-49694-6`): Valor não finito em Flow Bytes/s.; fluxo 4968 (`192.168.10.16-23.96.179.163-52322-443-6`): Valor não finito em Flow Bytes/s..

## Explicações

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 24,999 ms, e as chamadas de aquecimento levaram 1,762 ms na inferência e 1,709 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 24.396 | 100,00% |
| Selecionados para explicação | 24.396 | 100,00% |
| Com a explicação concluída | 24.396 | 100,00% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 7.1e-06, na escala de log-odds, contra a tolerância de 0.0001.

### Fila de explicações pendentes

A fila tem limite de 10.000 solicitações. Com ela cheia, a solicitação espera vaga na fila, porque na leitura de arquivo não há captura a perder.

| Solicitações | Quantidade |
|---|---:|
| Feitas | 24.396 |
| Aceitas na fila | 24.396 |
| Descartadas com a fila cheia | 0 |
| Concluídas | 24.396 |
| Pendentes no fim | 0 |

A fila chegou a 19 solicitações pendentes. A última explicação ficou disponível 1,815 ms depois da última solicitação.

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
| Cada fluxo selecionado tem a solicitação aceita na fila ou descartada | aprovada |
| Toda explicação concluída corresponde a uma solicitação aceita | aprovada |
| Marcações dos fluxos explicados na ordem da estratégia: t2 ≤ seleção ≤ explicação ≤ t4 = t3 nas síncronas; t3 ≤ solicitação ≤ retirada da fila ≤ explicação ≤ t4 no modo assíncrono | aprovada |
| A saída explicada leva à probabilidade registrada na classificação | aprovada |
| Cada explicação tem uma contribuição por entrada do classificador | aprovada |
| Solicitações aceitas e descartadas = contadores da fila no classificador | aprovada |
| O processo explicador retirou da fila todas as solicitações aceitas | aprovada |
| O processo explicador terminou sem erro | aprovada |
| Nenhuma explicação pendente quando o processo explicador termina normalmente | aprovada |
| Nenhuma solicitação descartada (modo arquivo) | aprovada |
| O processo explicador carregou o mesmo modelo congelado do classificador | aprovada |
| Classificador, explicador e extrator nas CPUs configuradas | aprovada |

## Conferência com a tabela de referência

O trecho começa no meio da captura. 3.024 fluxos do NIDS pertencem a 1.582 conexões que já tinham pacotes antes do início e ficam fora da conferência, porque não correspondem aos fluxos do CSV.

Fora da borda dos últimos 120 s, 19.438 fluxos do NIDS correspondem a fluxos de `tuesday.csv`. Ficaram 0 fluxos só no CSV e 11 só no NIDS. Destes, 11 têm algum valor `NaN`: são fluxos de um único pacote, que a rotulagem dos autores descartou com `dropna` e que o NIDS registra como não classificáveis.

As entradas inteiras coincidem exatamente com as do CSV. 37.533 valores com fração diferem nos últimos algarismos, com diferença relativa de no máximo 5.6e-15, como na conferência da extração.

O modelo aplicado às linhas da tabela de referência e o NIDS produziram previsões diferentes em 0 de 19.438 fluxos. A maior diferença de probabilidade foi 0, contra a tolerância de 1e-12. A conferência não calcula métricas de detecção.

## Tempos

Os tempos abaixo mostram que a instrumentação funciona. A execução não controla a carga, então eles não são resultados do experimento.

| Medida | Média (ms) | Mediana (ms) | p95 (ms) | p99 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|---:|
| Tempo de inferência, t2 − t1 | 0,465 | 0,426 | 0,889 | 1,265 | 124,647 |
| Tempo de explicação | 0,803 | 0,729 | 1,521 | 2,284 | 11,496 |
| Latência de classificação, t3 − t0 | 58,421 | 55,178 | 128,619 | 160,012 | 4.723,774 |
| Latência de explicação, t4 − t0 | 60,699 | 57,043 | 132,712 | 163,426 | 4.728,593 |
| Espera e preparo da entrada, t1 − t0 | 57,696 | 54,701 | 127,868 | 159,110 | 3.653,596 |
| Espera na fila de explicações pendentes | 1,357 | 0,782 | 4,266 | 11,509 | 53,242 |
| Seleção para explicação | 0,001 | 0,001 | 0,002 | 0,003 | 0,024 |
| Escrita nos canais de saída | 0,237 | 0,035 | 0,082 | 0,135 | 4.721,271 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 27,8 | 394 |
| explicador | 0 | 0 | 23,8 | 204 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 132,7 | 1.675 |

A máquina tinha 7.278 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/arquivo/20261115T201018001853Z/report.json](../training-runs/nids/arquivo/20261115T201018001853Z/report.json).
