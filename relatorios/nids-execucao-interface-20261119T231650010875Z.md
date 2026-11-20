# Execução do NIDS: Assíncrono, XGBoost, interface

A execução passou nas verificações. O NIDS leu a interface `h2-eth0`, formou os fluxos com o extrator da [decisão 3](../docs/decisoes.md) e classificou cada fluxo com o XGBoost congelado, na estratégia Assíncrono. Os termos seguem o [glossário](../docs/glossario.md), e as marcações de tempo seguem a seção 5.1 do [protocolo](../docs/protocolo-experimental.md).

O tráfego é o trecho `campanha` da captura de terça-feira, até `2017-07-04T12:30:00Z` (UTC).

## Contadores

| Contador | Valor |
|---|---:|
| Pacotes lidos | 3.706.151 |
| Pacotes IPv4 usados na formação dos fluxos | 3.703.160 |
| Pacotes descartados por não serem IPv4 | 2.991 |
| Pacotes que chegaram a um fluxo já emitido | 0 |
| Fluxos emitidos pelo extrator | 24.413 |
| Fluxos descartados na fila de saída do extrator | 0 |
| Fluxos recebidos pelo classificador | 24.413 |
| Fluxos classificados | 24.396 |
| Fluxos não classificáveis | 17 |

Estatísticas do libpcap: 3.706.151 pacotes recebidos, 0 descartados por falta de espaço no buffer e 0 descartados pela interface.

O buffer de captura foi pedido com 256 MiB, e o kernel mapeou 256 MiB.

A fila de saída do extrator chegou a 29 fluxos à espera da escrita, com limite de 10.000.

Causas de emissão: nova conexão TCP depois do encerramento (363), varredura do tempo limite (24.050).

Exemplos de fluxos não classificáveis: fluxo 181 (`208.81.233.32-192.168.10.14-80-49870-6`): Valor não finito em Flow Bytes/s.; fluxo 376 (`63.241.108.104-192.168.10.14-443-49832-6`): Valor não finito em Flow Bytes/s.; fluxo 396 (`63.241.108.104-192.168.10.14-80-49856-6`): Valor não finito em Flow Bytes/s.; fluxo 957 (`13.107.4.50-192.168.10.14-80-49694-6`): Valor não finito em Flow Bytes/s.; fluxo 4968 (`192.168.10.16-23.96.179.163-52322-443-6`): Valor não finito em Flow Bytes/s..

## Explicações

O TreeSHAP segue a [decisão 7](../docs/decisoes.md). Antes de a captura abrir, a construção do explicador levou 42,492 ms, e as chamadas de aquecimento levaram 10,526 ms na inferência e 3,330 ms na explicação.

| Cobertura explicativa | Fluxos | Proporção dos classificados |
|---|---:|---:|
| Classificados | 24.396 | 100,00% |
| Selecionados para explicação | 24.396 | 100,00% |
| Com a explicação concluída | 24.396 | 100,00% |

A soma do valor de referência com as contribuições difere da saída explicada em no máximo 6.7e-06, na escala de log-odds, contra a tolerância de 0.0001.

### Fila de explicações pendentes

A fila tem limite de 10.000 solicitações. Com ela cheia, a solicitação que chega com a fila cheia é descartada.

| Solicitações | Quantidade |
|---|---:|
| Feitas | 24.396 |
| Aceitas na fila | 24.396 |
| Descartadas com a fila cheia | 0 |
| Concluídas | 24.396 |
| Pendentes no fim | 0 |

A fila chegou a 10 solicitações pendentes. A última explicação ficou disponível 2,494 ms depois da última solicitação.

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
| Tempo de inferência, t2 − t1 | 0,335 | 0,238 | 0,879 | 1,353 | 5,716 |
| Tempo de explicação | 0,544 | 0,391 | 1,538 | 2,224 | 6,356 |
| Latência de classificação, t3 − t0 | 3,894 | 2,412 | 12,068 | 21,700 | 56,768 |
| Latência de explicação, t4 − t0 | 5,231 | 3,588 | 13,831 | 23,453 | 60,557 |
| Espera e preparo da entrada, t1 − t0 | 3,508 | 2,008 | 11,648 | 21,288 | 55,930 |
| Espera na fila de explicações pendentes | 0,723 | 0,475 | 2,464 | 3,632 | 10,244 |
| Seleção para explicação | 0,001 | 0,000 | 0,002 | 0,003 | 0,050 |
| Escrita nos canais de saída | 0,031 | 0,018 | 0,092 | 0,154 | 2,387 |

## Recursos

| Processo | CPUs configuradas | CPUs observadas | CPU usada (s) | Pico de memória (MiB) |
|---|---|---|---:|---:|
| classificador | 2 | 2 | 20,3 | 247 |
| explicador | 0 | 0 | 16,2 | 204 |
| extrator | 4, 5, 6, 7 | 4, 5, 6, 7 | 74,9 | 1.841 |

A máquina tinha 10.264 MiB de memória disponível no início da execução.

O registro da execução está em [training-runs/nids/interface/20261119T231650010875Z/report.json](../training-runs/nids/interface/20261119T231650010875Z/report.json).
