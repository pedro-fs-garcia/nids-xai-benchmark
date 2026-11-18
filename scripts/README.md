# Scripts

Ferramentas executadas diretamente para produzir um resultado específico. Elas usam o pacote em `src/`, mas não fazem parte dele.

| Script | Uso |
|---|---|
| [inspecionar_cicids2017.py](inspecionar_cicids2017.py) | Inspeção reprodutível dos cinco CSVs diários. O README da raiz descreve a execução. |
| [emular_trecho.py](emular_trecho.py) | Reprodução de um trecho de PCAP em rede emulada, em uma ou mais cópias ao mesmo tempo, capturada pelo NIDS em cada estratégia de explicação. |
| [executar_matriz.py](executar_matriz.py) | Execução dos ensaios de uma matriz, como o piloto ou a campanha, retomando de onde parou. |

Os dois scripts de emulação precisam de root e usam o Python do sistema, que tem o módulo do Mininet. Rode num terminal comum, porque o `sudo` precisa pedir a senha. Os arquivos gerados voltam a pertencer ao usuário que chamou o `sudo`, e nenhum cache de bytecode do root fica no projeto.

**Recursos.** Os pacotes `mininet` e `ethtool`, o ambiente de `src/`, o extrator compilado por `extractor/build.sh` e o `tcpreplay-edit` compilado por [tcpreplay/build.sh](../tcpreplay/README.md). O trecho deve ter sido preparado por `python main.py preparar-pcap` ou `preparar-trecho`. Mais de uma cópia exige um trecho com a lista de endereços IPv4, que só `preparar-trecho` grava.

## Emulação de um trecho

```bash
sudo python3 scripts/emular_trecho.py --modelo random-forest --trecho curto --carga 1 2
sudo python3 scripts/emular_trecho.py --modelo random-forest xgboost --trecho campanha \
    --estrategia sem-xai sincrono-total sincrono-condicional assincrono --criterio probabilidade incerteza --carga 4
```

Cada combinação de modelo, estratégia, critério e carga é um ensaio. Os ensaios rodam em sequência, cada um com a sua rede. `--estrategia` tem o padrão `sem-xai`, e `--criterio` só se aplica ao `sincrono-condicional`, com os limiares fixados em [configs/nids.json](../configs/nids.json). `--carga` é o número de cópias do trecho enviadas ao mesmo tempo, com o padrão 1 ([decisão 15](../docs/decisoes.md)). Um ensaio que falha não interrompe os seguintes.

**Topologia.** Dois hosts em enlace direto, sem switch e sem controlador:

```
h1 (10.255.0.1) h1-eth0 <---- veth ----> h2-eth0 h2 (10.255.0.2)
   tcpreplay-edit, uma cópia por processo   NIDS (captura em modo promíscuo)
```

**Passos.**

1. Confere o `tcpreplay-edit` compilado, pelo hash do binário, pela versão mínima 4.6.0 e pela edição de pacotes, o hash do trecho e o da lista de endereços no manifesto da preparação.
2. Confere se a máquina está na tomada, ociosa e com memória disponível, e espera até 10 min. Sem isso, o ensaio não começa e é registrado como não iniciado ([decisão 17](../docs/decisoes.md)).
3. Cria a topologia, desativa o IPv6 nos dois hosts, ajusta a MTU ao maior quadro do trecho e desliga as descargas de processamento das interfaces (`ethtool -K … rx tx sg tso gso gro lro off`).
4. Inicia o NIDS em h2 (`python main.py nids-executar --interface h2-eth0 --estrategia …`) e espera a captura abrir. O NIDS fixa as próprias threads, as do extrator e as do processo explicador nas CPUs da configuração ([decisão 14](../docs/decisoes.md)).
5. Inicia a thread que grava o estado da máquina a cada segundo, fixa na última CPU de reprodução.
6. Lê os contadores das interfaces e inicia as cópias em h1, cada uma num processo do `tcpreplay-edit` (`--intf1=h1-eth0 --multiplier=1 --no-flow-stats --stats=60`), na velocidade original, fixo pelo `taskset` numa das CPUs de reprodução, em rodízio. A cópia 1 envia o trecho sem alteração. Cada cópia seguinte recebe `--pnat` com um par /32 por endereço do trecho ([src/core/traffic_copies.py](../src/core/traffic_copies.py)).
7. Espera todas as cópias terminarem, mais 120 s, a margem do relógio ocioso e 15 s de folga, para a varredura emitir os últimos fluxos, e lê de novo os contadores.
8. Encerra o NIDS com SIGTERM e grava, na pasta da execução, `replay.json` e `machine.jsonl`. O `replay.json` tem a topologia, as interfaces, a conferência da máquina antes do ensaio, o commit do repositório, os comandos e o resumo de cada cópia do `tcpreplay-edit`, as somas das cópias, as diferenças dos contadores, as estatísticas do libpcap, os fluxos emitidos por segundo de reprodução e o resumo do estado da máquina. Antes de sair, o extrator entrega os fluxos que restam na fila de saída, no ritmo do classificador, e é encerrado se ficar 30 s sem entregar um. No modo assíncrono, o NIDS ainda espera a fila de explicações pendentes esvaziar, até o tempo máximo de esvaziamento da configuração ([decisão 13](../docs/decisoes.md)). Para terminar, o NIDS tem esses dois prazos, o tempo de entregar a fila de saída cheia a 50 fluxos por segundo, 180 s e mais 60 s por cópia. Se um deles não parar, o processo é encerrado à força, a falha é registrada e o ensaio termina com erro.

O script informa cada etapa no stderr, com o horário, e repassa os relatórios da cópia 1 a cada 60 s. O stdout recebe uma linha JSON por ensaio, com a pasta da execução.

Depois do ensaio, a validação compara a execução reproduzida com a execução do mesmo trecho lido do arquivo, com o mesmo modelo e a mesma estratégia. Com mais de uma cópia, cada cópia é comparada em separado, com os endereços de volta aos originais:

```bash
cd src
python main.py nids-executar --modelo random-forest --trecho campanha --estrategia assincrono
python main.py nids-validar --reproduzida ../training-runs/nids/interface/<execução> --arquivo ../training-runs/nids/arquivo/<execução>
```

As execuções reproduzidas das quatro estratégias com o mesmo modelo são conferidas juntas por `nids-comparar-estrategias`, descrito em [src/README.md](../src/README.md).

## Execução de uma matriz

```bash
sudo python3 scripts/executar_matriz.py --matriz configs/piloto-2.json --ate 07:00
```

A matriz lista blocos de ensaios ([configs/piloto-2.json](../configs/piloto-2.json)). Cada bloco cruza classificadores, configurações de explicação, níveis de carga e repetições. Dentro de um bloco, cada repetição reúne todas as combinações em ordem sorteada com a semente da matriz ([src/domains/campaign/matrix.py](../src/domains/campaign/matrix.py)). Cada ensaio é feito por `emular_trecho.py`, com as condições da máquina da matriz.

O registro fica em `training-runs/matrizes/<nome>/registro.jsonl`, com uma linha por tentativa, e nunca é reescrito. Uma nova chamada com a mesma matriz pula as células já concluídas e repete as inválidas, até o número máximo de tentativas da matriz. Um ensaio inválido fica registrado com o motivo, e a nova tentativa é outro ensaio, em outra pasta. Descartes e pendências não invalidam um ensaio.

Com `--ate`, o executor não começa um ensaio que terminaria depois desse horário. Ele impede a suspensão da máquina com o `systemd-inhibit`, inclusive com a tampa fechada. Um ensaio que não começou porque a máquina não ficou pronta volta para o fim da fila, sem gastar tentativa, e o executor segue tentando até o horário do `--ate`.

Depois dos ensaios, `python main.py matriz-analisar --matriz ../configs/piloto-2.json` valida cada ensaio válido contra a leitura por arquivo correspondente e gera o relatório da matriz em `relatorios/`.
