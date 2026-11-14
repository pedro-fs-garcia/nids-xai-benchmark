# tcpreplay da reprodução do tráfego

Esta pasta compila o [tcpreplay](https://github.com/appneta/tcpreplay) 4.6.2, que reproduz os trechos de PCAP na rede emulada ([decisão 10](../docs/decisoes.md)). O binário fica em `tcpreplay/build/` e não é instalado no sistema. O código do tcpreplay não é copiado para o repositório.

## Versão mínima

A emulação exige o tcpreplay 4.6.0 ou mais novo. As versões 4.5.2 e 4.5.3 criam o anel de transmissão (`PACKET_TX_RING`) com quadros de 4.096 bytes sempre que a MTU da interface não cabe numa página de memória. Com esse quadro, o kernel recusa os pacotes acima de 4.064 bytes, e a 4.5.2 para de enviar no primeiro deles. O trecho `validacao` tem 80.958 pacotes acima desse tamanho. A versão 4.6.0 corrige o tamanho do quadro ([issue 1079](https://github.com/appneta/tcpreplay/issues/1079)). O Ubuntu 26.04 distribui a 4.5.2.

## Build

Requer `curl`, `gcc`, `make` e o pacote de desenvolvimento da `libpcap` (`libpcap-dev`).

```bash
tcpreplay/build.sh
```

O script baixa o pacote `tcpreplay-4.6.2.tar.xz` da página de versões do projeto, confere o SHA-256 fixado no próprio script e compila com as opções padrão do `configure`, mais `--disable-shared`. Ele grava em `tcpreplay/build/`, que fica fora do Git:

- `tcpreplay`, o binário usado por [scripts/emular_baixa_carga.py](../scripts/emular_baixa_carga.py);
- `tcpreplay-build.json`, com a versão, o endereço e o hash do pacote, as opções de compilação, o compilador, o hash do binário e a saída de `tcpreplay --version`;
- `configure.log` e `make.log`.

O script da emulação confere o hash do binário com `tcpreplay-build.json` e recusa versões anteriores à 4.6.0.
