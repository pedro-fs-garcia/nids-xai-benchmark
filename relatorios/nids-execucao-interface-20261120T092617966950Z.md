# Execução do NIDS: Assíncrono, Random Forest, interface

A execução passou nas verificações. O NIDS leu a interface `h2-eth0`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o Random Forest congelado, na estratégia Assíncrono. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

O tráfego é o trecho `campanha` da captura de terça-feira, até `2017-07-04T12:30:00Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 7.412.302 |
| Pacotes IPv4 usados na formação dos fluxos | 7.406.320 |
| Pacotes descartados por não serem IPv4 | 5.982 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 48.816 |
| Fluxos descartados na fila de saída do extrator | 0 |
| Fluxos recebidos pelo classificador | 48.816 |
| Fluxos classificados | 48.782 |
| Fluxos não classificáveis | 34 |

Estatísticas do libpcap: 7.412.302 pacotes recebidos, 0 descartados por falta de espaço no buffer e 0 descartados pela interface.

O buffer de captura foi pedido com 256 MiB, e o kernel mapeou 256 MiB.

A fila de saída do extrator chegou a 1.406 fluxos à espera da escrita, com limite de 10.000.

Causas de emissão: nova conexão TCP depois do encerramento (726), varredura do tempo limite (48.090).

Exemplos de fluxos não classificáveis: fluxo 357 (`208.81.233.32-192.168.10.14-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 364 (`100.64.1.132-100.64.0.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 747 (`63.241.108.104-192.168.10.14-443-49832-6`): Valor não finito em Flow Bytes/s.; fluxo 754 (`100.64.6.114-100.64.0.1-443-49832-6`): Valor não finito em Flow Bytes/s.; fluxo 789 (`63.241.108.104-192.168.10.14-80-49856-6`): Valor não finito em Flow Bytes/s..

## Explicações

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 8,423 ms, e as chamadas de aquecimento levaram 4,351 ms na inferência e 10,916 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 48.782 | 100,00% |
| Selecionados para explicação | 48.782 | 100,00% |
| Com a explicação concluída | 48.782 | 100,00% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 5.6e-16, na escala de probabilidade, contra a tolerância de 1e-09.

### Fila de explicações pendentes

A fila tem limite de 10.000 solicitações. Com ela cheia, a solicitação que chega com a fila cheia é descartada.

| Solicitações | Quantidade |
|---|---:|
| Feitas | 48.782 |
| Aceitas na fila | 48.782 |
| Descartadas com a fila cheia | 0 |
| Concluídas | 48.782 |
| Pendentes no fim | 0 |

A fila chegou a 1.869 solicitações pendentes. A última explicação ficou disponível 12,479 ms depois da última solicitação.

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
| Tempo de inferência, t2 − t1 | 5,197 | 5,481 | 7,654 | 9,813 | 30,977 |
| Tempo de explicação | 8,264 | 8,002 | 11,613 | 15,125 | 33,079 |
| Latência de classificação, t3 − t0 | 1.080,877 | 102,473 | 7.147,539 | 8.847,382 | 9.972,401 |
| Latência de explicação, t4 − t0 | 3.805,652 | 1.089,796 | 17.626,770 | 22.043,569 | 22.827,338 |
| Espera e preparo da entrada, t1 − t0 | 1.075,605 | 97,576 | 7.141,666 | 8.840,682 | 9.966,636 |
| Espera na fila de explicações pendentes | 2.716,415 | 706,419 | 12.407,999 | 14.872,944 | 15.273,443 |
| Seleção para explicação | 0,001 | 0,001 | 0,001 | 0,002 | 0,008 |
| Escrita nos canais de saída | 0,051 | 0,047 | 0,081 | 0,133 | 10,948 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 282,5 | 284 |
| explicador | 0 | 0 | 408,6 | 201 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 121,7 | 3.564 |

A máquina tinha 11.672 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/interface/20261120T092617966950Z/report.json](../training-runs/nids/interface/20261120T092617966950Z/report.json).
