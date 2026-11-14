# Extrator de fluxos do NIDS

Esta pasta compila o extrator de fluxos usado pelo NIDS a partir do [CICFlowMeter corrigido](https://github.com/GintsEngelen/CICFlowMeter), no commit `13a061520b` fixado pela [decisão 3](../docs/decisoes.md). O código original não é copiado para o repositório. O build o clona, confere o commit e aplica os patches desta pasta.

## Programas

| Programa | Classes do extrator | Uso |
|---|---|---|
| `ReferenceExtractor` | Sem alteração | Repete a sequência de chamadas de `Cmd.readPcapFile` do extrator: tempos limite de 120 s e 5 s, leitura só de IPv4, um fluxo por linha de CSV. O modo Offline da interface gráfica, que os autores do Improved CIC-IDS2017 usaram para gerar os CSVs, faz a mesma sequência em `ReadPcapFileWorker.readPcapFile`. É a referência da conferência com `tuesday.csv`. |
| `NidsExtractor` | Com os dois patches | Lê de um arquivo PCAP ou de uma interface e emite cada fluxo pela varredura do tempo limite ([decisão 8](../docs/decisoes.md)). Escreve uma linha JSON por evento na saída padrão. Na captura ao vivo, as linhas dos fluxos passam pela fila de saída ([decisão 9](../docs/decisoes.md)). |

Os patches alteram só duas classes:

- [01-flow-emission-sweep.patch](patches/01-flow-emission-sweep.patch): `FlowGenerator` ganha a varredura do tempo limite, a emissão do fim da captura e a causa de cada emissão. As regras de formação dos fluxos não mudam.
- [02-live-capture.patch](patches/02-live-capture.patch): `PacketReader` ganha a abertura de uma interface ao vivo, com o mesmo caminho de leitura dos arquivos, em modo não bloqueante e com buffer de captura de tamanho configurável, e distingue o fim do arquivo de uma leitura sem pacotes. O modo não bloqueante é necessário porque, com TPACKET_V3, a leitura bloqueante da libpcap não retorna numa interface sem pacotes ([decisão 8](../docs/decisoes.md)).

## Build

Requer `git`, Maven, um JDK 8 ou mais novo e a `libpcap` do sistema.

```bash
extractor/build.sh
```

O script grava em `extractor/build/`, que fica fora do Git:

- `reference-extractor.jar` e `nids-extractor.jar`;
- `lib/`, com as dependências do `pom.xml` e o `jnetpcap` 1.4.r1425 do repositório do extrator;
- `native/`, com a `libjnetpcap.so` e um link `libpcap.so` para a `libpcap` do sistema, que a biblioteca procura sem número de versão;
- `extractor-build.json`, com o commit, a versão do Java e os hashes dos jars, dos patches e das dependências.

O `pom.xml` usa as versões do `pom.xml` do commit fixado e deixa de fora o `log4j-core`, porque as classes compiladas só usam a API do `slf4j`. O build foi verificado com o OpenJDK 17, compilando para Java 8.

## Execução

O código Python chama os dois programas pelo adaptador `src/core/flow_extractor.py`. Para executá-los diretamente:

```bash
B=extractor/build
LD_LIBRARY_PATH=$B/native java -Djava.library.path=$B/native -cp "$B/reference-extractor.jar:$B/lib/*" \
    nids.extractor.ReferenceExtractor trecho.pcap fluxos.csv
LD_LIBRARY_PATH=$B/native java -Djava.library.path=$B/native -cp "$B/nids-extractor.jar:$B/lib/*" \
    nids.extractor.NidsExtractor --pcap trecho.pcap
```

Na captura ao vivo, `--iface INTERFACE` substitui `--pcap`, e o processo precisa de permissão de captura. A captura termina quando a entrada padrão é fechada ou recebe a linha `stop`. As opções `--snaplen`, `--read-timeout-ms`, `--idle-margin-us` e `--buffer-bytes` têm os padrões 65535, 100, 2000000 e 268435456. Na captura ao vivo, `--read-timeout-ms` define quanto o kernel espera para entregar um bloco parcial de pacotes, `--buffer-bytes` define o tamanho do buffer de captura da libpcap, e a leitura sem pacotes espera 1 ms antes de tentar de novo.

A opção `--flow-output` escolhe como as linhas dos fluxos chegam à saída padrão. Com `queue`, o padrão da captura ao vivo, a thread que lê os pacotes guarda cada linha na fila de saída, e outra thread a escreve. Com `direct`, o padrão da leitura de arquivo, a mesma thread lê os pacotes e escreve as linhas.

O `NidsExtractor` escreve três tipos de linha:

| Tipo | Conteúdo |
|---|---|
| `start` | Commit, tempos limite, fonte, opções, tamanho do buffer de captura pedido e mapeado pelo kernel, modo de saída dos fluxos, versão do Java, leitura do relógio monotônico e cabeçalho das 89 colunas. |
| `flow` | Sequência, causa da emissão, instantes do primeiro e do último pacote, relógio da captura, `t0` e a linha de atributos. |
| `end` | Pacotes lidos, usados e descartados, pacotes que chegaram a um fluxo já emitido, fluxos por causa, maior tamanho da fila de saída e estatísticas do libpcap. |
