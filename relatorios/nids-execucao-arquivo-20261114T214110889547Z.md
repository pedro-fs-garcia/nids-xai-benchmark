# Execução do NIDS: Assíncrono, Random Forest, arquivo

A execução passou nas verificações. O NIDS leu o arquivo `/home/pedro/projects/explicabilidade-ia/derived-data/pcap/tuesday/segment-validacao.pcap`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o Random Forest congelado, na estratégia Assíncrono. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

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

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 8,308 ms, e as chamadas de aquecimento levaram 11,742 ms na inferência e 9,713 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 32.086 | 100,00% |
| Selecionados para explicação | 32.086 | 100,00% |
| Com a explicação concluída | 32.086 | 100,00% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 5.6e-16, na escala de probabilidade, contra a tolerância de 1e-09.

### Fila de explicações pendentes

A fila tem limite de 10.000 solicitações. Com ela cheia, a solicitação espera vaga na fila, porque na leitura de arquivo não há captura a perder.

| Solicitações | Quantidade |
|---|---:|
| Feitas | 32.086 |
| Aceitas na fila | 32.086 |
| Descartadas com a fila cheia | 0 |
| Concluídas | 32.086 |
| Pendentes no fim | 0 |

A fila chegou a 8.864 solicitações pendentes. A última explicação ficou disponível 60.583,506 ms depois da última solicitação.

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

Fora da borda dos últimos 120 s, 29.880 fluxos do NIDS correspondem a fluxos de `tuesday.csv`. Ficaram 0 fluxos só no CSV e 21 só no NIDS. Destes, 21 têm algum valor `NaN`: são fluxos de um único pacote, que a rotulagem dos autores descartou com `dropna` e que o NIDS registra como não classificáveis.

As entradas inteiras coincidem exatamente com as do CSV. 54.980 valores com fração diferem nos últimos algarismos, com diferença relativa de no máximo 6e-15, como na conferência da extração.

O modelo aplicado às linhas da tabela de referência e o NIDS produziram previsões diferentes em 0 de 29.880 fluxos. A maior diferença de probabilidade foi 0, contra a tolerância de 1e-12. A conferência não calcula métricas de detecção.

## Tempos

Os tempos abaixo mostram que a instrumentação funciona. A execução não controla a carga, então eles não são resultados do experimento.

| Medida | Média (ms) | Mediana (ms) | p95 (ms) | p99 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|---:|
| Tempo de inferência, t2 − t1 | 6,353 | 6,054 | 8,283 | 9,675 | 105,558 |
| Tempo de explicação | 9,636 | 9,801 | 13,367 | 15,774 | 22,235 |
| Latência de classificação, t3 − t0 | 510,423 | 540,883 | 680,530 | 766,754 | 909,194 |
| Latência de explicação, t4 − t0 | 53.368,424 | 60.528,011 | 93.255,016 | 95.940,736 | 96.249,453 |
| Espera e preparo da entrada, t1 − t0 | 503,968 | 534,877 | 672,741 | 759,230 | 900,668 |
| Espera na fila de explicações pendentes | 52.848,238 | 59.979,916 | 92.705,074 | 95.428,681 | 95.599,189 |
| Seleção para explicação | 0,001 | 0,001 | 0,002 | 0,002 | 0,019 |
| Escrita nos canais de saída | 0,067 | 0,061 | 0,106 | 0,226 | 10,484 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 324,6 | 604 |
| explicador | 0 | 0 | 315,4 | 209 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 196,4 | 1.682 |

A máquina tinha 9.212 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/arquivo/20261114T214110889547Z/report.json](../training-runs/nids/arquivo/20261114T214110889547Z/report.json).
