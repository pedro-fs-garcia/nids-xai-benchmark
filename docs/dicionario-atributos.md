# Dicionário de atributos e contrato de entrada

Este documento descreve as 91 colunas dos CSVs do Improved CIC-IDS2017 e define quais delas o classificador recebe. As decisões que ele aplica estão em [decisoes.md](decisoes.md), e os termos seguem o [glossário](glossario.md).

Os significados vêm do código do [CICFlowMeter corrigido](https://github.com/GintsEngelen/CICFlowMeter) no commit `13a061520b` (`BasicFlow.java`, método `dumpFlowBasedFeaturesEx`).

## Contrato de entrada

O classificador recebe 80 atributos por fluxo, na ordem em que aparecem nos CSVs. As 11 colunas restantes ficam fora das entradas.

| Papel | Colunas | Quantidade |
|---|---|---|
| Entrada do classificador | Todas as colunas marcadas como "Entrada" na tabela de colunas | 80 |
| Rótulo | `Label`, `Attempted Category` | 2 |
| Metadado de rastreabilidade | `id`, `Flow ID`, `Src IP`, `Src Port`, `Dst IP`, `Dst Port`, `Timestamp` | 7 |
| Excluído | `Fwd Header Length`, `Bwd Header Length` | 2 |

O valor `inf` em `Flow Bytes/s` e `Flow Packets/s` é substituído por -1 antes da classificação, nos dados de treino e no NIDS.

## Regras dos fluxos

O NIDS forma os fluxos com as mesmas regras do extrator que gerou os CSVs.

- **Identificação.** Um fluxo é identificado por endereço de origem, endereço de destino, porta de origem, porta de destino e protocolo.
- **Sentido.** O sentido de ida é o do primeiro pacote do fluxo. O sentido de volta é o oposto.
- **Encerramento TCP.** Um fluxo TCP fica pronto para encerrar depois de um pacote FIN em cada sentido seguido de um ACK, ou depois de um pacote RST.
- **Tempo limite.** Um fluxo com mais de 120 s desde o primeiro pacote é encerrado, e o pacote seguinte inicia um novo fluxo.
- **Tempo limite de atividade.** Um intervalo maior que 5 s entre pacotes separa um período ativo de um período ocioso. Esse limite só afeta os atributos `Active` e `Idle`.
- **ICMP.** Um pacote ICMP com código e tipo diferentes dos do fluxo inicia um novo fluxo.
- **Emissão.** Durante a leitura, o extrator emite um fluxo quando chega um pacote com o mesmo identificador mais de 120 s depois do primeiro pacote do fluxo, quando chega um SYN depois do encerramento TCP ou quando um pacote ICMP muda o código e o tipo do fluxo. Os demais fluxos são emitidos no fim da captura.
- **Emissão no NIDS.** Além desses casos, o NIDS emite um fluxo quando o relógio da captura passa de 120 s desde o primeiro pacote, sem alterar nenhum atributo ([decisão 8](decisoes.md)).

## Colunas

Os comprimentos de pacote contam os bytes de carga do pacote, sem os cabeçalhos. Os tempos estão em microssegundos (µs). "Ida" e "volta" são os sentidos definidos acima.

Uma rajada é uma sequência de pelo menos 4 pacotes com carga no mesmo sentido, com no máximo 1 s entre pacotes consecutivos.

| Nº | Coluna | Significado | Unidade | Papel |
|---|---|---|---|---|
| 1 | `id` | Número sequencial do registro no arquivo. | — | Metadado |
| 2 | `Flow ID` | Identificador do fluxo, formado por endereços, portas e protocolo. | — | Metadado |
| 3 | `Src IP` | Endereço IP de origem. | — | Metadado |
| 4 | `Src Port` | Porta de origem. | — | Metadado |
| 5 | `Dst IP` | Endereço IP de destino. | — | Metadado |
| 6 | `Dst Port` | Porta de destino. | — | Metadado |
| 7 | `Protocol` | Número do protocolo. Nos CSVs ocorrem 0, 1 (ICMP), 6 (TCP) e 17 (UDP). | — | Entrada |
| 8 | `Timestamp` | Instante do primeiro pacote do fluxo, em UTC. | data e hora | Metadado |
| 9 | `Flow Duration` | Tempo entre o primeiro e o último pacote do fluxo. | µs | Entrada |
| 10 | `Total Fwd Packet` | Número de pacotes de ida. | pacotes | Entrada |
| 11 | `Total Bwd packets` | Número de pacotes de volta. | pacotes | Entrada |
| 12 | `Total Length of Fwd Packet` | Soma dos comprimentos dos pacotes de ida. | bytes | Entrada |
| 13 | `Total Length of Bwd Packet` | Soma dos comprimentos dos pacotes de volta. | bytes | Entrada |
| 14 | `Fwd Packet Length Max` | Maior comprimento entre os pacotes de ida. | bytes | Entrada |
| 15 | `Fwd Packet Length Min` | Menor comprimento entre os pacotes de ida. | bytes | Entrada |
| 16 | `Fwd Packet Length Mean` | Média dos comprimentos dos pacotes de ida. | bytes | Entrada |
| 17 | `Fwd Packet Length Std` | Desvio padrão dos comprimentos dos pacotes de ida. | bytes | Entrada |
| 18 | `Bwd Packet Length Max` | Maior comprimento entre os pacotes de volta. | bytes | Entrada |
| 19 | `Bwd Packet Length Min` | Menor comprimento entre os pacotes de volta. | bytes | Entrada |
| 20 | `Bwd Packet Length Mean` | Média dos comprimentos dos pacotes de volta. | bytes | Entrada |
| 21 | `Bwd Packet Length Std` | Desvio padrão dos comprimentos dos pacotes de volta. | bytes | Entrada |
| 22 | `Flow Bytes/s` | Soma dos comprimentos dos pacotes dividida pela duração do fluxo. Vale `inf` quando a duração é 0. | bytes/s | Entrada |
| 23 | `Flow Packets/s` | Número de pacotes dividido pela duração do fluxo. Vale `inf` quando a duração é 0. | pacotes/s | Entrada |
| 24 | `Flow IAT Mean` | Média dos intervalos entre pacotes consecutivos do fluxo. | µs | Entrada |
| 25 | `Flow IAT Std` | Desvio padrão dos intervalos entre pacotes consecutivos do fluxo. | µs | Entrada |
| 26 | `Flow IAT Max` | Maior intervalo entre pacotes consecutivos do fluxo. | µs | Entrada |
| 27 | `Flow IAT Min` | Menor intervalo entre pacotes consecutivos do fluxo. | µs | Entrada |
| 28 | `Fwd IAT Total` | Soma dos intervalos entre pacotes de ida consecutivos. | µs | Entrada |
| 29 | `Fwd IAT Mean` | Média dos intervalos entre pacotes de ida consecutivos. | µs | Entrada |
| 30 | `Fwd IAT Std` | Desvio padrão dos intervalos entre pacotes de ida consecutivos. | µs | Entrada |
| 31 | `Fwd IAT Max` | Maior intervalo entre pacotes de ida consecutivos. | µs | Entrada |
| 32 | `Fwd IAT Min` | Menor intervalo entre pacotes de ida consecutivos. | µs | Entrada |
| 33 | `Bwd IAT Total` | Soma dos intervalos entre pacotes de volta consecutivos. | µs | Entrada |
| 34 | `Bwd IAT Mean` | Média dos intervalos entre pacotes de volta consecutivos. | µs | Entrada |
| 35 | `Bwd IAT Std` | Desvio padrão dos intervalos entre pacotes de volta consecutivos. | µs | Entrada |
| 36 | `Bwd IAT Max` | Maior intervalo entre pacotes de volta consecutivos. | µs | Entrada |
| 37 | `Bwd IAT Min` | Menor intervalo entre pacotes de volta consecutivos. | µs | Entrada |
| 38 | `Fwd PSH Flags` | Número de pacotes de ida com a flag PSH. | pacotes | Entrada |
| 39 | `Bwd PSH Flags` | Número de pacotes de volta com a flag PSH. | pacotes | Entrada |
| 40 | `Fwd URG Flags` | Número de pacotes de ida com a flag URG. | pacotes | Entrada |
| 41 | `Bwd URG Flags` | Número de pacotes de volta com a flag URG. | pacotes | Entrada |
| 42 | `Fwd RST Flags` | Número de pacotes de ida com a flag RST. | pacotes | Entrada |
| 43 | `Bwd RST Flags` | Número de pacotes de volta com a flag RST. | pacotes | Entrada |
| 44 | `Fwd Header Length` | Soma dos comprimentos de cabeçalho dos pacotes de ida. | bytes | Excluído |
| 45 | `Bwd Header Length` | Soma dos comprimentos de cabeçalho dos pacotes de volta. | bytes | Excluído |
| 46 | `Fwd Packets/s` | Número de pacotes de ida dividido pela duração do fluxo. Vale 0 quando a duração é 0. | pacotes/s | Entrada |
| 47 | `Bwd Packets/s` | Número de pacotes de volta dividido pela duração do fluxo. Vale 0 quando a duração é 0. | pacotes/s | Entrada |
| 48 | `Packet Length Min` | Menor comprimento entre os pacotes do fluxo. | bytes | Entrada |
| 49 | `Packet Length Max` | Maior comprimento entre os pacotes do fluxo. | bytes | Entrada |
| 50 | `Packet Length Mean` | Média dos comprimentos dos pacotes do fluxo. | bytes | Entrada |
| 51 | `Packet Length Std` | Desvio padrão dos comprimentos dos pacotes do fluxo. | bytes | Entrada |
| 52 | `Packet Length Variance` | Variância dos comprimentos dos pacotes do fluxo. | bytes² | Entrada |
| 53 | `FIN Flag Count` | Número de pacotes do fluxo com a flag FIN. | pacotes | Entrada |
| 54 | `SYN Flag Count` | Número de pacotes do fluxo com a flag SYN. | pacotes | Entrada |
| 55 | `RST Flag Count` | Número de pacotes do fluxo com a flag RST. | pacotes | Entrada |
| 56 | `PSH Flag Count` | Número de pacotes do fluxo com a flag PSH. | pacotes | Entrada |
| 57 | `ACK Flag Count` | Número de pacotes do fluxo com a flag ACK. | pacotes | Entrada |
| 58 | `URG Flag Count` | Número de pacotes do fluxo com a flag URG. | pacotes | Entrada |
| 59 | `CWR Flag Count` | Número de pacotes do fluxo com a flag CWR. | pacotes | Entrada |
| 60 | `ECE Flag Count` | Número de pacotes do fluxo com a flag ECE. | pacotes | Entrada |
| 61 | `Down/Up Ratio` | Número de pacotes de volta dividido pelo número de pacotes de ida. | — | Entrada |
| 62 | `Average Packet Size` | Soma dos comprimentos dos pacotes dividida pelo número de pacotes do fluxo. | bytes | Entrada |
| 63 | `Fwd Segment Size Avg` | Soma dos comprimentos dos pacotes de ida dividida pelo número de pacotes de ida. | bytes | Entrada |
| 64 | `Bwd Segment Size Avg` | Soma dos comprimentos dos pacotes de volta dividida pelo número de pacotes de volta. | bytes | Entrada |
| 65 | `Fwd Bytes/Bulk Avg` | Média de bytes de carga por rajada de ida. | bytes | Entrada |
| 66 | `Fwd Packet/Bulk Avg` | Média de pacotes por rajada de ida. | pacotes | Entrada |
| 67 | `Fwd Bulk Rate Avg` | Bytes de carga das rajadas de ida divididos pela duração total dessas rajadas. | bytes/s | Entrada |
| 68 | `Bwd Bytes/Bulk Avg` | Média de bytes de carga por rajada de volta. | bytes | Entrada |
| 69 | `Bwd Packet/Bulk Avg` | Média de pacotes por rajada de volta. | pacotes | Entrada |
| 70 | `Bwd Bulk Rate Avg` | Bytes de carga das rajadas de volta divididos pela duração total dessas rajadas. | bytes/s | Entrada |
| 71 | `Subflow Fwd Packets` | Número de pacotes de ida dividido pelo contador de subfluxos do extrator, em divisão inteira. | pacotes | Entrada |
| 72 | `Subflow Fwd Bytes` | Soma dos comprimentos dos pacotes de ida dividida pelo contador de subfluxos do extrator, em divisão inteira. | bytes | Entrada |
| 73 | `Subflow Bwd Packets` | Número de pacotes de volta dividido pelo contador de subfluxos do extrator, em divisão inteira. | pacotes | Entrada |
| 74 | `Subflow Bwd Bytes` | Soma dos comprimentos dos pacotes de volta dividida pelo contador de subfluxos do extrator, em divisão inteira. | bytes | Entrada |
| 75 | `FWD Init Win Bytes` | Janela TCP anunciada no primeiro pacote de ida. | bytes | Entrada |
| 76 | `Bwd Init Win Bytes` | Janela TCP anunciada no sentido de volta, como registrada pelo extrator. | bytes | Entrada |
| 77 | `Fwd Act Data Pkts` | Número de pacotes de ida com pelo menos 1 byte de carga. | pacotes | Entrada |
| 78 | `Fwd Seg Size Min` | Menor comprimento de cabeçalho entre os pacotes de ida. | bytes | Entrada |
| 79 | `Active Mean` | Média das durações dos períodos ativos do fluxo. | µs | Entrada |
| 80 | `Active Std` | Desvio padrão das durações dos períodos ativos do fluxo. | µs | Entrada |
| 81 | `Active Max` | Maior duração entre os períodos ativos do fluxo. | µs | Entrada |
| 82 | `Active Min` | Menor duração entre os períodos ativos do fluxo. | µs | Entrada |
| 83 | `Idle Mean` | Média das durações dos períodos ociosos do fluxo. | µs | Entrada |
| 84 | `Idle Std` | Desvio padrão das durações dos períodos ociosos do fluxo. | µs | Entrada |
| 85 | `Idle Max` | Maior duração entre os períodos ociosos do fluxo. | µs | Entrada |
| 86 | `Idle Min` | Menor duração entre os períodos ociosos do fluxo. | µs | Entrada |
| 87 | `ICMP Code` | Código ICMP do fluxo. Vale -1 nos fluxos que não são ICMP. | — | Entrada |
| 88 | `ICMP Type` | Tipo ICMP do fluxo. Vale -1 nos fluxos que não são ICMP. | — | Entrada |
| 89 | `Total TCP Flow Time` | Duração acumulada da conexão TCP, somada entre os fluxos em que o tempo limite a dividiu. | µs | Entrada |
| 90 | `Label` | Rótulo original do fluxo. | — | Rótulo |
| 91 | `Attempted Category` | Categoria do rótulo Attempted. Vale -1 nos fluxos que não são Attempted. | — | Rótulo |
