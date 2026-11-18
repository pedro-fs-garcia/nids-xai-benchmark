# Execução do NIDS: Assíncrono, Random Forest, interface

A execução passou nas verificações. O NIDS leu a interface `h2-eth0`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o Random Forest congelado, na estratégia Assíncrono. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

O tráfego é o trecho `campanha` da captura de terça-feira, até `2017-07-04T12:30:00Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 12.946.502 |
| Pacotes IPv4 usados na formação dos fluxos | 12.926.221 |
| Pacotes descartados por não serem IPv4 | 20.281 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 154.270 |
| Fluxos descartados na fila de saída do extrator | 43.197 |
| Fluxos recebidos pelo classificador | 111.073 |
| Fluxos classificados | 110.066 |
| Fluxos não classificáveis | 1.007 |

Estatísticas do libpcap: 29.649.208 pacotes recebidos, 16.702.706 descartados por falta de espaço no buffer e 0 descartados pela interface.

O buffer de captura foi pedido com 256 MiB, e o kernel mapeou 256 MiB.

A fila de saída do extrator chegou a 10.000 fluxos à espera da escrita, com limite de 10.000.

Causas de emissão: nova conexão TCP depois do encerramento (2.795), varredura do tempo limite (108.278).

Exemplos de fluxos não classificáveis: fluxo 1413 (`208.81.233.32-192.168.10.14-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1424 (`100.64.1.132-100.64.0.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1432 (`100.64.17.132-100.64.16.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1451 (`100.64.33.132-100.64.32.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1452 (`100.64.49.132-100.64.48.1-80-49870-6`): Valor não finito em Flow Bytes/s..

## Explicações

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 7,898 ms, e as chamadas de aquecimento levaram 17,977 ms na inferência e 9,403 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 110.066 | 100,00% |
| Selecionados para explicação | 110.066 | 100,00% |
| Com a explicação concluída | 97.024 | 88,15% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 6.7e-16, na escala de probabilidade, contra a tolerância de 1e-09.

### Fila de explicações pendentes

A fila tem limite de 10.000 solicitações. Com ela cheia, a solicitação que chega com a fila cheia é descartada.

| Solicitações | Quantidade |
|---|---:|
| Feitas | 110.066 |
| Aceitas na fila | 97.024 |
| Descartadas com a fila cheia | 13.042 |
| Concluídas | 97.024 |
| Pendentes no fim | 0 |

A fila chegou a 10.001 solicitações pendentes. A última explicação ficou disponível 68.413,446 ms depois da última solicitação.

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

## Tempos

Os tempos abaixo mostram que a instrumentação funciona. A execução não controla a carga, então eles não são resultados do experimento.

| Medida | Média (ms) | Mediana (ms) | p95 (ms) | p99 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|---:|
| Tempo de inferência, t2 − t1 | 8,372 | 7,622 | 14,025 | 17,750 | 114,171 |
| Tempo de explicação | 13,215 | 12,909 | 20,566 | 23,959 | 91,803 |
| Latência de classificação, t3 − t0 | 85.424,318 | 79.459,355 | 177.890,494 | 186.785,416 | 190.711,546 |
| Latência de explicação, t4 − t0 | 198.428,911 | 204.574,471 | 321.446,761 | 327.333,538 | 329.698,798 |
| Espera e preparo da entrada, t1 − t0 | 85.415,784 | 79.451,792 | 177.881,471 | 186.776,897 | 190.703,964 |
| Espera na fila de explicações pendentes | 109.589,674 | 120.674,465 | 167.914,480 | 168.456,734 | 168.909,302 |
| Seleção para explicação | 0,001 | 0,001 | 0,002 | 0,003 | 0,035 |
| Escrita nos canais de saída | 0,114 | 0,080 | 0,285 | 0,505 | 18,230 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 1.002,2 | 395 |
| explicador | 0 | 0 | 1.291,4 | 201 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 2.102,3 | 4.675 |

A máquina tinha 10.805 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/interface/20261117T062347024051Z/report.json](../training-runs/nids/interface/20261117T062347024051Z/report.json).
