# Execução do NIDS de referência: Random Forest, arquivo

A execução passou nas verificações. O NIDS leu o arquivo `/home/pedro/projects/explicabilidade-ia/derived-data/pcap/tuesday/segment-dev.pcap`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o Random Forest congelado, na estratégia Sem XAI. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](protocolo-experimental.md).

O tráfego é o trecho `dev` da captura de terça-feira, até `2017-07-04T11:58:44Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 18.354 |
| Pacotes IPv4 usados na formação dos fluxos | 15.647 |
| Pacotes descartados por não serem IPv4 | 2.707 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 1.175 |
| Fluxos recebidos pelo classificador | 1.175 |
| Fluxos classificados | 1.170 |
| Fluxos não classificáveis | 5 |

Causas de emissão: varredura do tempo limite (243), nova conexão TCP depois do encerramento (1), fim da captura (931).

Exemplos de fluxos não classificáveis: fluxo 307 (`192.168.10.12-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 426 (`192.168.10.19-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 484 (`192.168.10.16-128.100.100.128-123-123-17`): Valor não finito em Flow IAT Mean.; fluxo 815 (`192.168.10.17-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 881 (`192.168.10.51-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s..

## Verificações

| Verificação | Resultado |
|---|---|
| Fluxos emitidos pelo extrator = fluxos recebidos pelo classificador | aprovada |
| Fluxos recebidos = classificados + não classificáveis | aprovada |
| t0 ≤ t1 ≤ t2 ≤ t3 em todos os fluxos classificados | aprovada |
| Nenhum pacote chegou a um fluxo já emitido (modo arquivo) | aprovada |

## Conferência com a tabela de referência

Fora da borda dos últimos 120 s, 243 fluxos do NIDS correspondem a fluxos de `tuesday.csv`. Ficaram 0 fluxos só no CSV e 0 só no NIDS. Destes, 0 têm algum valor `NaN`: são fluxos de um único pacote, que a rotulagem dos autores descartou com `dropna` e que o NIDS registra como não classificáveis.

As entradas inteiras coincidem exatamente com as do CSV. 391 valores com fração diferem nos últimos algarismos, com diferença relativa de no máximo 2.3e-15, como na conferência da extração.

O modelo aplicado às linhas da tabela de referência e o NIDS produziram previsões diferentes em 0 de 243 fluxos. A maior diferença de probabilidade foi 0, contra a tolerância de 1e-12. A conferência não calcula métricas de detecção.

## Tempos

Os tempos abaixo mostram que a instrumentação funciona. A execução não controla a carga, então eles não são resultados do experimento.

| Medida | Média (ms) | Mediana (ms) | p95 (ms) | p99 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|---:|
| Tempo de inferência, t2 − t1 | 7,545 | 4,749 | 20,562 | 30,257 | 33,176 |
| Latência de classificação, t3 − t0 | 674,966 | 680,183 | 1.164,622 | 1.392,750 | 1.421,027 |
| Espera e preparo da entrada, t1 − t0 | 667,291 | 673,713 | 1.151,701 | 1.388,207 | 1.417,958 |
| Entrega no canal de saída, t3 − t2 | 0,130 | 0,104 | 0,290 | 0,350 | 0,509 |

O processo do classificador usou 13,9 s de CPU, com pico de 202 MiB de memória. O extrator usou 4,0 s de CPU, com pico de 250 MiB.

O registro da execução está em [training-runs/nids/arquivo/20261113T232850899573Z/report.json](../training-runs/nids/arquivo/20261113T232850899573Z/report.json).
