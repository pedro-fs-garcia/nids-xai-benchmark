# Scripts

Ferramentas executadas diretamente para produzir um resultado específico. Elas usam o pacote em `src/`, mas não fazem parte dele.

| Script | Uso |
|---|---|
| [inspecionar_cicids2017.py](inspecionar_cicids2017.py) | Inspeção reprodutível dos cinco CSVs diários. O README da raiz descreve a execução. |
| [emular_baixa_carga.py](emular_baixa_carga.py) | Reprodução de um trecho de PCAP em rede emulada, capturada pelo NIDS em cada estratégia de explicação. |

## Emulação em baixa carga

```bash
sudo python3 scripts/emular_baixa_carga.py --modelo random-forest --trecho validacao
sudo python3 scripts/emular_baixa_carga.py --modelo random-forest xgboost --trecho validacao \
    --estrategia sem-xai sincrono-total sincrono-condicional assincrono --criterio probabilidade incerteza
```

O script precisa de root e usa o Python do sistema, que tem o módulo do Mininet. Rode num terminal comum, porque o `sudo` precisa pedir a senha. Os arquivos gerados voltam a pertencer ao usuário que chamou o `sudo`.

Cada combinação de modelo, estratégia e critério é um ensaio. Os ensaios rodam em sequência, cada um com a sua rede. `--estrategia` tem o padrão `sem-xai`, e `--criterio` só se aplica ao `sincrono-condicional`, com os limiares fixados em [configs/nids.json](../configs/nids.json). Um ensaio que falha não interrompe os seguintes.

**Recursos.** Os pacotes `mininet` e `ethtool`, o ambiente de `src/`, o extrator compilado por `extractor/build.sh` e o `tcpreplay` compilado por [tcpreplay/build.sh](../tcpreplay/README.md). O trecho deve ter sido preparado por `python main.py preparar-pcap`.

**Topologia.** Dois hosts em enlace direto, sem switch e sem controlador:

```
h1 (10.255.0.1) h1-eth0 <---- veth ----> h2-eth0 h2 (10.255.0.2)
   tcpreplay                                NIDS (captura em modo promíscuo)
```

**Passos.**

1. Confere o `tcpreplay` compilado, pelo hash do binário e pela versão mínima 4.6.0, e o hash do trecho no manifesto da preparação.
2. Cria a topologia, desativa o IPv6 nos dois hosts, ajusta a MTU ao maior quadro do trecho e desliga as descargas de processamento das interfaces (`ethtool -K … rx tx sg tso gso gro lro off`).
3. Inicia o NIDS em h2 (`python main.py nids-executar --interface h2-eth0 --estrategia …`) e espera a captura abrir. O NIDS fixa as próprias threads, as do extrator e as do processo explicador nas CPUs da configuração ([decisão 14](../docs/decisoes.md)).
4. Lê os contadores das interfaces e executa o `tcpreplay` compilado em h1 (`--intf1=h1-eth0 --multiplier=1 --stats=60`), na velocidade original do trecho, fixo pelo `taskset` na CPU de reprodução da configuração.
5. Espera 120 s mais a margem do relógio ocioso e 15 s de folga, para a varredura emitir os últimos fluxos, e lê de novo os contadores.
6. Encerra o NIDS com SIGTERM e grava `replay.json` na pasta da execução: topologia, interfaces, comandos, versão, CPU e resumo do `tcpreplay`, diferenças dos contadores, estatísticas do libpcap e fluxos emitidos por segundo de reprodução. O extrator tem 30 s para parar depois do pedido. No modo assíncrono, o NIDS ainda espera a fila de explicações pendentes esvaziar, até o tempo máximo de esvaziamento da configuração ([decisão 13](../docs/decisoes.md)). O NIDS tem esses dois prazos mais 180 s para terminar. Se um deles não parar, o processo é encerrado à força, a falha é registrada e o ensaio termina com erro.

O script informa cada etapa no stderr, com o horário, e repassa os relatórios do `tcpreplay` a cada 60 s. O stdout recebe uma linha JSON por ensaio, com a pasta da execução.

Depois do ensaio, a validação compara a execução reproduzida com a execução do mesmo trecho lido do arquivo, com o mesmo modelo e a mesma estratégia:

```bash
cd src
python main.py nids-executar --modelo random-forest --trecho validacao --estrategia assincrono
python main.py nids-validar --reproduzida ../training-runs/nids/interface/<execução> --arquivo ../training-runs/nids/arquivo/<execução>
```

As execuções reproduzidas das quatro estratégias com o mesmo modelo são conferidas juntas por `nids-comparar-estrategias`, descrito em [src/README.md](../src/README.md).
