# Execução do NIDS de referência: Random Forest, arquivo

A execução passou nas verificações. O NIDS leu o arquivo `/home/pedro/projects/explicabilidade-ia/derived-data/pcap/tuesday/segment-validacao.pcap`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o Random Forest congelado, na estratégia Sem XAI. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](protocolo-experimental.md).

O tráfego é o trecho `validacao` da captura de terça-feira, até `2017-07-04T12:30:00Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 3.954.069 |
| Pacotes IPv4 usados na formação dos fluxos | 3.946.908 |
| Pacotes descartados por não serem IPv4 | 7.161 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 32.108 |
| Fluxos recebidos pelo classificador | 32.108 |
| Fluxos classificados | 32.086 |
| Fluxos com erro nas entradas | 22 |

Causas de emissão: varredura do tempo limite (29.537), nova conexão TCP depois do encerramento (364), fim da captura (2.207).

Exemplos de erro: fluxo 257 (`192.168.10.51-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 306 (`192.168.10.17-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 348 (`192.168.10.19-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 699 (`192.168.10.12-224.0.0.22-0-0-0`): Valor não finito em Flow Bytes/s.; fluxo 1121 (`192.168.10.16-128.100.100.128-123-123-17`): Valor não finito em Flow IAT Mean..

## Verificações

| Verificação | Resultado |
|---|---|
| Fluxos emitidos pelo extrator = fluxos recebidos pelo classificador | aprovada |
| Fluxos recebidos = classificados + erros | aprovada |
| t0 ≤ t1 ≤ t2 ≤ t3 em todos os fluxos classificados | aprovada |
| Nenhum pacote chegou a um fluxo já emitido (modo arquivo) | aprovada |

## Conferência com a tabela de referência

Fora da borda dos últimos 120 s, 29.880 fluxos do NIDS correspondem a fluxos de `tuesday.csv`. Ficaram 0 fluxos só no CSV e 21 só no NIDS. Destes, 21 têm algum valor `NaN`: são fluxos de um único pacote, que a rotulagem dos autores descartou com `dropna` e que o NIDS registra como erro de entrada.

As entradas inteiras coincidem exatamente com as do CSV. 54.980 valores com fração diferem nos últimos algarismos, com diferença relativa de no máximo 6e-15, como na conferência da extração.

O modelo aplicado às linhas da tabela de referência e o NIDS produziram previsões diferentes em 0 de 29.880 fluxos. A maior diferença de probabilidade foi 0, contra a tolerância de 1e-12. A conferência não calcula métricas de detecção.

## Tempos

Os tempos abaixo mostram que a instrumentação funciona. A execução não controla a carga, então eles não são resultados do experimento.

| Medida | Média (ms) | Mediana (ms) | p95 (ms) | p99 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|---:|
| Tempo de inferência, t2 − t1 | 10,321 | 8,225 | 22,259 | 27,058 | 310,583 |
| Latência de classificação, t3 − t0 | 879,588 | 853,844 | 1.363,430 | 1.574,205 | 2.003,074 |
| Espera e preparo da entrada, t1 − t0 | 869,091 | 843,915 | 1.349,721 | 1.558,492 | 1.993,608 |
| Entrega no canal de saída, t3 − t2 | 0,176 | 0,155 | 0,312 | 0,475 | 7,284 |

O processo do classificador usou 378,8 s de CPU, com pico de 431 MiB de memória. O extrator usou 195,8 s de CPU, com pico de 1.885 MiB.

O registro da execução está em [training-runs/nids/arquivo/20261112T232930075685Z/report.json](../training-runs/nids/arquivo/20261112T232930075685Z/report.json).
