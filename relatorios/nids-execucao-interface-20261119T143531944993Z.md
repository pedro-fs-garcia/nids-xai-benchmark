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

A fila de saída do extrator chegou a 7.602 fluxos à espera da escrita, com limite de 10.000.

Causas de emissão: nova conexão TCP depois do encerramento (1.452), varredura do tempo limite (96.170).

Exemplos de fluxos não classificáveis: fluxo 713 (`208.81.233.32-192.168.10.14-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 717 (`100.64.1.132-100.64.0.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 724 (`100.64.17.132-100.64.16.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 736 (`100.64.33.132-100.64.32.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1483 (`63.241.108.104-192.168.10.14-443-49832-6`): Valor não finito em Flow Bytes/s..

## Explicações

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 7,712 ms, e as chamadas de aquecimento levaram 21,442 ms na inferência e 9,498 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 97.554 | 100,00% |
| Selecionados para explicação | 97.554 | 100,00% |
| Com a explicação concluída | 92.503 | 94,82% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 4.7e-16, na escala de probabilidade, contra a tolerância de 1e-09.

### Fila de explicações pendentes

A fila tem limite de 10.000 solicitações. Com ela cheia, a solicitação que chega com a fila cheia é descartada.

| Solicitações | Quantidade |
|---|---:|
| Feitas | 97.554 |
| Aceitas na fila | 92.503 |
| Descartadas com a fila cheia | 5.051 |
| Concluídas | 92.503 |
| Pendentes no fim | 0 |

A fila chegou a 10.001 solicitações pendentes. A última explicação ficou disponível 9.976,627 ms depois da última solicitação.

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
| Tempo de inferência, t2 − t1 | 8,171 | 7,927 | 11,364 | 14,282 | 43,460 |
| Tempo de explicação | 12,413 | 12,864 | 17,318 | 20,756 | 40,423 |
| Latência de classificação, t3 − t0 | 20.773,507 | 14.955,049 | 60.610,400 | 69.670,256 | 71.654,345 |
| Latência de explicação, t4 − t0 | 88.610,711 | 96.864,909 | 172.262,071 | 193.968,867 | 196.793,075 |
| Espera e preparo da entrada, t1 − t0 | 20.765,192 | 14.946,148 | 60.601,268 | 69.662,261 | 71.647,055 |
| Espera na fila de explicações pendentes | 68.232,410 | 62.716,782 | 139.548,779 | 142.688,140 | 143.145,499 |
| Seleção para explicação | 0,001 | 0,001 | 0,002 | 0,003 | 0,169 |
| Escrita nos canais de saída | 0,098 | 0,085 | 0,176 | 0,350 | 12,517 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 884,6 | 371 |
| explicador | 0 | 0 | 1.166,8 | 201 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 384,1 | 4.927 |

A máquina tinha 10.504 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/interface/20261119T143531944993Z/report.json](../training-runs/nids/interface/20261119T143531944993Z/report.json).
