# Scripts

Ferramentas executadas diretamente para produzir um resultado específico. Elas usam o pacote em `src/`, mas não fazem parte dele.

| Script | Uso |
|---|---|
| [inspecionar_cicids2017.py](inspecionar_cicids2017.py) | Inspeção reprodutível dos cinco CSVs diários. O README da raiz descreve a execução. |
| [emular_baixa_carga.py](emular_baixa_carga.py) | Reprodução de um trecho de PCAP em rede emulada, capturada pelo NIDS de referência. |

## Emulação em baixa carga

```bash
sudo python3 scripts/emular_baixa_carga.py --modelo random-forest --trecho validacao
```

O script precisa de root e usa o Python do sistema, que tem o módulo do Mininet. Rode num terminal comum: o `sudo` precisa pedir a senha. Os arquivos gerados voltam a pertencer ao usuário que chamou o `sudo`.

**Recursos.** Os pacotes `mininet`, `tcpreplay` e `ethtool`, o ambiente de `src/` e o extrator compilado por `extractor/build.sh`. O trecho deve ter sido preparado por `python main.py preparar-pcap`.

**Topologia.** Dois hosts em enlace direto, sem switch e sem controlador:

```
h1 (10.255.0.1) h1-eth0 <---- veth ----> h2-eth0 h2 (10.255.0.2)
   tcpreplay                                NIDS (captura em modo promíscuo)
```

**Passos.**

1. Confere o hash do trecho no manifesto da preparação.
2. Cria a topologia, desativa o IPv6 nos dois hosts, ajusta a MTU ao maior quadro do trecho e desliga as descargas de processamento das interfaces (`ethtool -K … rx tx sg tso gso gro lro off`).
3. Inicia o NIDS em h2 (`python main.py nids-executar --interface h2-eth0`) e espera a captura abrir.
4. Lê os contadores das interfaces e executa `tcpreplay --intf1=h1-eth0 --multiplier=1 --stats=60` em h1, na velocidade original do trecho.
5. Espera 120 s mais a margem do relógio ocioso e 15 s de folga, para a varredura emitir os últimos fluxos, e lê de novo os contadores.
6. Encerra o NIDS com SIGTERM e grava `replay.json` na pasta da execução: topologia, interfaces, comandos, resumo do `tcpreplay` e diferenças dos contadores.

O script informa cada etapa no stderr, com o horário, e repassa os relatórios do `tcpreplay` a cada 60 s. O stdout recebe só a linha JSON final, com a pasta da execução.

Depois do ensaio, a validação compara a execução reproduzida com a execução do mesmo trecho lido do arquivo:

```bash
cd src
python main.py nids-executar --modelo random-forest --trecho validacao
python main.py nids-validar --reproduzida ../training-runs/nids/interface/<execução> --arquivo ../training-runs/nids/arquivo/<execução>
```
