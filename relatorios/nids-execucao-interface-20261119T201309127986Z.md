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

A fila de saída do extrator chegou a 1.717 fluxos à espera da escrita, com limite de 10.000.

Causas de emissão: nova conexão TCP depois do encerramento (726), varredura do tempo limite (48.090).

Exemplos de fluxos não classificáveis: fluxo 357 (`208.81.233.32-192.168.10.14-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 364 (`100.64.1.132-100.64.0.1-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 747 (`63.241.108.104-192.168.10.14-443-49832-6`): Valor não finito em Flow Bytes/s.; fluxo 755 (`100.64.6.114-100.64.0.1-443-49832-6`): Valor não finito em Flow Bytes/s.; fluxo 789 (`63.241.108.104-192.168.10.14-80-49856-6`): Valor não finito em Flow Bytes/s..

## Explicações

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 28,629 ms, e as chamadas de aquecimento levaram 25,677 ms na inferência e 12,053 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 48.782 | 100,00% |
| Selecionados para explicação | 48.782 | 100,00% |
| Com a explicação concluída | 48.782 | 100,00% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 6.7e-16, na escala de probabilidade, contra a tolerância de 1e-09.

### Fila de explicações pendentes

A fila tem limite de 10.000 solicitações. Com ela cheia, a solicitação que chega com a fila cheia é descartada.

| Solicitações | Quantidade |
|---|---:|
| Feitas | 48.782 |
| Aceitas na fila | 48.782 |
| Descartadas com a fila cheia | 0 |
| Concluídas | 48.782 |
| Pendentes no fim | 0 |

A fila chegou a 2.059 solicitações pendentes. A última explicação ficou disponível 19,232 ms depois da última solicitação.

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
| Tempo de inferência, t2 − t1 | 6,063 | 6,534 | 8,884 | 11,722 | 29,933 |
| Tempo de explicação | 9,457 | 9,316 | 13,588 | 17,904 | 42,866 |
| Latência de classificação, t3 − t0 | 1.741,193 | 215,146 | 11.066,555 | 12.800,385 | 13.820,102 |
| Latência de explicação, t4 − t0 | 5.661,302 | 1.905,982 | 23.390,988 | 29.409,007 | 30.016,000 |
| Espera e preparo da entrada, t1 − t0 | 1.735,026 | 209,119 | 11.059,998 | 12.793,777 | 13.813,461 |
| Espera na fila de explicações pendentes | 3.910,519 | 1.209,018 | 17.696,064 | 20.071,623 | 20.754,718 |
| Seleção para explicação | 0,001 | 0,001 | 0,002 | 0,002 | 0,023 |
| Escrita nos canais de saída | 0,070 | 0,064 | 0,109 | 0,183 | 14,967 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 330,4 | 283 |
| explicador | 0 | 0 | 469,0 | 201 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 132,8 | 3.364 |

A máquina tinha 10.901 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/interface/20261119T201309127986Z/report.json](../training-runs/nids/interface/20261119T201309127986Z/report.json).
