# Execução do NIDS: Assíncrono, XGBoost, interface

A execução passou nas verificações. O NIDS leu a interface `h2-eth0`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o XGBoost congelado, na estratégia Assíncrono. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

O tráfego é o trecho `campanha` da captura de terça-feira, até `2017-07-04T12:30:00Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 15.462.683 |
| Pacotes IPv4 usados na formação dos fluxos | 15.442.609 |
| Pacotes descartados por não serem IPv4 | 20.074 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 169.832 |
| Fluxos descartados na fila de saída do extrator | 0 |
| Fluxos recebidos pelo classificador | 169.832 |
| Fluxos classificados | 168.707 |
| Fluxos não classificáveis | 1.125 |

Estatísticas do libpcap: 29.649.208 pacotes recebidos, 14.186.525 descartados por falta de espaço no buffer e 0 descartados pela interface.

O buffer de captura foi pedido com 256 MiB, e o kernel mapeou 256 MiB.

A fila de saída do extrator chegou a 9.992 fluxos à espera da escrita, com limite de 10.000.

Causas de emissão: nova conexão TCP depois do encerramento (2.800), varredura do tempo limite (167.032).

Exemplos de fluxos não classificáveis: fluxo 1413 (`208.81.233.32-192.168.10.14-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1420 (`100.64.1.132-100.64.0.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1439 (`100.64.17.132-100.64.16.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1451 (`100.64.33.132-100.64.32.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 1479 (`100.64.49.132-100.64.48.1-80-49870-6`): Valor não finito em Flow Bytes/s..

## Explicações

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 37,610 ms, e as chamadas de aquecimento levaram 1,738 ms na inferência e 1,244 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 168.707 | 100,00% |
| Selecionados para explicação | 168.707 | 100,00% |
| Com a explicação concluída | 168.707 | 100,00% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 6.8e-06, na escala de log-odds, contra a tolerância de 0.0001.

### Fila de explicações pendentes

A fila tem limite de 10.000 solicitações. Com ela cheia, a solicitação que chega com a fila cheia é descartada.

| Solicitações | Quantidade |
|---|---:|
| Feitas | 168.707 |
| Aceitas na fila | 168.707 |
| Descartadas com a fila cheia | 0 |
| Concluídas | 168.707 |
| Pendentes no fim | 0 |

A fila chegou a 60 solicitações pendentes. A última explicação ficou disponível 0,924 ms depois da última solicitação.

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
| Tempo de inferência, t2 − t1 | 0,492 | 0,464 | 0,877 | 1,244 | 147,916 |
| Tempo de explicação | 0,870 | 0,813 | 1,480 | 2,238 | 75,508 |
| Latência de classificação, t3 − t0 | 3.886,728 | 180,494 | 22.850,237 | 35.392,149 | 37.308,078 |
| Latência de explicação, t4 − t0 | 3.889,463 | 184,257 | 22.852,009 | 35.394,340 | 37.310,479 |
| Espera e preparo da entrada, t1 − t0 | 3.886,163 | 179,982 | 22.849,745 | 35.391,640 | 37.307,216 |
| Espera na fila de explicações pendentes | 1,736 | 0,818 | 5,721 | 15,081 | 101,669 |
| Seleção para explicação | 0,001 | 0,001 | 0,001 | 0,002 | 0,199 |
| Escrita nos canais de saída | 0,047 | 0,039 | 0,090 | 0,170 | 15,524 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 207,3 | 469 |
| explicador | 0 | 0 | 174,5 | 203 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 2.048,3 | 4.673 |

A máquina tinha 10.387 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/interface/20261117T122202276702Z/report.json](../training-runs/nids/interface/20261117T122202276702Z/report.json).
