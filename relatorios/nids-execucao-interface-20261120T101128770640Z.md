# Execução do NIDS: Assíncrono, Random Forest, interface

A execução passou nas verificações. O NIDS leu a interface `h2-eth0`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o Random Forest congelado, na estratégia Assíncrono. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

O tráfego é o trecho `campanha` da captura de terça-feira, até `2017-07-04T12:30:00Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 14.824.604 |
| Pacotes IPv4 usados na formação dos fluxos | 14.812.640 |
| Pacotes descartados por não serem IPv4 | 11.964 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 97.622 |
| Fluxos descartados na fila de saída do extrator | 0 |
| Fluxos recebidos pelo classificador | 97.622 |
| Fluxos classificados | 97.554 |
| Fluxos não classificáveis | 68 |

Estatísticas do libpcap: 14.824.604 pacotes recebidos, 0 descartados por falta de espaço no buffer e 0 descartados pela interface.

O buffer de captura foi pedido com 256 MiB, e o kernel mapeou 256 MiB.

A fila de saída do extrator chegou a 6.406 fluxos à espera da escrita, com limite de 10.000.

Causas de emissão: nova conexão TCP depois do encerramento (1.452), varredura do tempo limite (96.170).

Exemplos de fluxos não classificáveis: fluxo 714 (`208.81.233.32-192.168.10.14-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 718 (`100.64.1.132-100.64.0.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 722 (`100.64.17.132-100.64.16.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 730 (`100.64.33.132-100.64.32.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1492 (`63.241.108.104-192.168.10.14-443-49832-6`): Valor não finito em Flow Bytes/s..

## Explicações

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 7,416 ms, e as chamadas de aquecimento levaram 4,339 ms na inferência e 9,865 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 97.554 | 100,00% |
| Selecionados para explicação | 97.554 | 100,00% |
| Com a explicação concluída | 97.015 | 99,45% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 6.7e-16, na escala de probabilidade, contra a tolerância de 1e-09.

### Fila de explicações pendentes

A fila tem limite de 10.000 solicitações. Com ela cheia, a solicitação que chega com a fila cheia é descartada.

| Solicitações | Quantidade |
|---|---:|
| Feitas | 97.554 |
| Aceitas na fila | 97.015 |
| Descartadas com a fila cheia | 539 |
| Concluídas | 97.015 |
| Pendentes no fim | 0 |

A fila chegou a 10.001 solicitações pendentes. A última explicação ficou disponível 752,864 ms depois da última solicitação.

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
| Tempo de inferência, t2 − t1 | 6,751 | 6,692 | 9,087 | 11,791 | 32,327 |
| Tempo de explicação | 10,672 | 11,188 | 14,099 | 17,777 | 53,086 |
| Latência de classificação, t3 − t0 | 12.846,345 | 7.981,031 | 45.591,261 | 49.670,277 | 50.842,475 |
| Latência de explicação, t4 − t0 | 54.653,673 | 50.504,856 | 121.371,164 | 144.059,886 | 147.171,694 |
| Espera e preparo da entrada, t1 − t0 | 12.839,493 | 7.973,187 | 45.582,397 | 49.662,150 | 50.835,866 |
| Espera na fila de explicações pendentes | 41.790,674 | 34.806,752 | 99.019,179 | 106.968,315 | 107.659,491 |
| Seleção para explicação | 0,001 | 0,001 | 0,002 | 0,002 | 0,293 |
| Escrita nos canais de saída | 0,068 | 0,060 | 0,107 | 0,246 | 11,003 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 729,9 | 372 |
| explicador | 0 | 0 | 1.049,2 | 202 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 329,1 | 4.920 |

A máquina tinha 11.675 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/interface/20261120T101128770640Z/report.json](../training-runs/nids/interface/20261120T101128770640Z/report.json).
