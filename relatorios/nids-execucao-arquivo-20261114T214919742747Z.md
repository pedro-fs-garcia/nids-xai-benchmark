# Execução do NIDS: Assíncrono, Random Forest, arquivo

A execução passou nas verificações. O NIDS leu o arquivo `/home/pedro/projects/explicabilidade-ia/derived-data/pcap/tuesday/segment-dev.pcap`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o Random Forest congelado, na estratégia Assíncrono. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

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

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 8,435 ms, e as chamadas de aquecimento levaram 5,993 ms na inferência e 10,289 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 1.170 | 100,00% |
| Selecionados para explicação | 1.170 | 100,00% |
| Com a explicação concluída | 1.170 | 100,00% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 4.5e-16, na escala de probabilidade, contra a tolerância de 1e-09.

### Fila de explicações pendentes

A fila tem limite de 10.000 solicitações. Com ela cheia, a solicitação espera vaga na fila, porque na leitura de arquivo não há captura a perder.

| Solicitações | Quantidade |
|---|---:|
| Feitas | 1.170 |
| Aceitas na fila | 1.170 |
| Descartadas com a fila cheia | 0 |
| Concluídas | 1.170 |
| Pendentes no fim | 0 |

A fila chegou a 403 solicitações pendentes. A última explicação ficou disponível 2.864,806 ms depois da última solicitação.

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

Fora da borda dos últimos 120 s, 243 fluxos do NIDS correspondem a fluxos de `tuesday.csv`. Ficaram 0 fluxos só no CSV e 0 só no NIDS. Destes, 0 têm algum valor `NaN`: são fluxos de um único pacote, que a rotulagem dos autores descartou com `dropna` e que o NIDS registra como não classificáveis.

As entradas inteiras coincidem exatamente com as do CSV. 391 valores com fração diferem nos últimos algarismos, com diferença relativa de no máximo 2.3e-15, como na conferência da extração.

O modelo aplicado às linhas da tabela de referência e o NIDS produziram previsões diferentes em 0 de 243 fluxos. A maior diferença de probabilidade foi 0, contra a tolerância de 1e-12. A conferência não calcula métricas de detecção.

## Tempos

Os tempos abaixo mostram que a instrumentação funciona. A execução não controla a carga, então eles não são resultados do experimento.

| Medida | Média (ms) | Mediana (ms) | p95 (ms) | p99 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|---:|
| Tempo de inferência, t2 − t1 | 6,193 | 6,023 | 7,717 | 8,896 | 10,124 |
| Tempo de explicação | 9,142 | 9,821 | 11,800 | 14,627 | 16,698 |
| Latência de classificação, t3 − t0 | 561,985 | 570,948 | 732,162 | 774,724 | 801,511 |
| Latência de explicação, t4 − t0 | 2.461,702 | 2.854,457 | 3.443,119 | 3.467,643 | 3.484,915 |
| Espera e preparo da entrada, t1 − t0 | 555,693 | 564,732 | 724,806 | 766,661 | 794,808 |
| Espera na fila de explicações pendentes | 1.890,456 | 2.239,417 | 2.864,739 | 2.869,915 | 2.870,781 |
| Seleção para explicação | 0,001 | 0,001 | 0,002 | 0,002 | 0,009 |
| Escrita nos canais de saída | 0,066 | 0,062 | 0,099 | 0,148 | 0,261 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 12,5 | 210 |
| explicador | 0 | 0 | 12,3 | 201 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 4,5 | 203 |

A máquina tinha 9.097 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/arquivo/20261114T214919742747Z/report.json](../training-runs/nids/arquivo/20261114T214919742747Z/report.json).
