# Reprodução do experimento

Este guia refaz o experimento a partir dos dados públicos do CIC-IDS2017, na ordem em que as etapas dependem umas das outras. As decisões citadas estão em [decisoes.md](decisoes.md), e os termos seguem o [glossário](glossario.md). O [src/README.md](../src/README.md) e o [scripts/README.md](../scripts/README.md) descrevem cada comando em detalhe.

## O que fica fora do repositório

O repositório guarda o código, as configurações, os manifestos com os hashes das entradas e dos arquivos gerados, os relatórios de cada etapa e o registro de cada matriz de ensaios. De cada execução do NIDS, ele guarda o `report.json` e, na rede emulada, o `replay.json`. Os arquivos da tabela abaixo não são publicados, e as etapas deste guia os geram de novo.

| Arquivos | Pasta | Origem |
|---|---|---|
| CSVs do Improved CIC-IDS2017 e PCAP de terça-feira do CIC-IDS2017 | `cicids-dataset/` | [Dados de entrada](#dados-de-entrada) |
| Conjuntos de treino, validação e teste (`.npy`) | `derived-data/` | `preparar-dados` |
| Trechos de PCAP e tabelas de referência | `derived-data/pcap/` | `preparar-pcap` e `preparar-trecho` |
| Modelos (`.joblib` e `.ubj`) e previsões (`.npy`) | `training-runs/` | Treino e congelamento dos classificadores |
| Registros brutos das execuções do NIDS (`.csv` e `.jsonl`) | `training-runs/nids/` | `nids-executar` e `scripts/emular_trecho.py` |
| Extrator e tcpreplay compilados | `extractor/build/` e `tcpreplay/build/` | `build.sh` de cada pasta |

Na máquina da campanha, `cicids-dataset/` ocupa 12 GB, `derived-data/` ocupa 21 GB e `training-runs/` ocupa 18 GB.

## Máquina

A campanha rodou num Intel Core i5-1334U com 12 CPUs lógicas, no Ubuntu 26.04 com o kernel Linux 7.0.0-43 e o Python 3.12.3 ([análise da campanha](../training-runs/nids/analise-campanha/20261120T120722710408Z/report.json)).

As CPUs de cada processo ficam em `resources.cpus` de [configs/nids.json](../configs/nids.json) ([decisão 14](decisoes.md#14-orçamento-de-cpu-e-de-memória)). A reprodução do tráfego usa as CPUs lógicas 8 a 11, e uma máquina com menos de 12 CPUs lógicas exige outra distribuição nesse campo. A máquina fica na tomada durante as medições ([decisão 17](decisoes.md#17-estado-da-máquina-durante-os-ensaios)). As latências dependem da máquina, e uma campanha em outra máquina mede outros valores.

## Dependências

Do sistema:

- Python 3.12, com o módulo `venv`. O experimento usou o 3.12.3.
- `git`, Maven, um JDK 8 ou mais novo e a `libpcap`, para compilar o extrator ([extractor/README.md](../extractor/README.md)). O build foi verificado com o OpenJDK 17.
- `curl`, `gcc`, `make` e `libpcap-dev`, para compilar o tcpreplay 4.6.2 ([tcpreplay/README.md](../tcpreplay/README.md)).
- `pcapfix`, `reordercap`, `editcap` e `capinfos`, para preparar o PCAP. A preparação do experimento registrou o pcapfix 1.1.7 e o Wireshark 4.2.2 no [manifesto](../derived-data/pcap/tuesday/manifest.json).
- `mininet`, `ethtool` e `sudo`, para a rede emulada ([scripts/README.md](../scripts/README.md)).

Os comandos abaixo criam o ambiente Python em `src/venv`, onde `scripts/emular_trecho.py` procura o Python do NIDS, e rodam os testes. O [requirements.txt](../src/requirements.txt) fixa a versão de cada biblioteca, e o `requirements-dev.txt` acrescenta o pytest.

```bash
cd src
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest
```

Na raiz do repositório, os dois scripts abaixo compilam o extrator e o tcpreplay.

```bash
extractor/build.sh
tcpreplay/build.sh
```

Sete testes do extrator só rodam depois desse build. Os jars gravam o instante da compilação, e o `tcpreplay-edit` grava o caminho da pasta em que foi compilado. Por isso, os hashes dos jars de outra compilação, e o do `tcpreplay-edit` compilado em outra pasta, diferem dos registrados nas execuções da campanha.

## Dados de entrada

O Improved CIC-IDS2017 está na [página dos autores](https://intrusion-detection.distrinet-research.be/CNS2022/Dataset_Download.html). O arquivo `CICIDS2017_improved.zip` traz os cinco CSVs, que vão para `cicids-dataset/`. O tamanho e o SHA-256 do arquivo e de cada CSV estão no [relatório da inspeção](../relatorios/inspecao-cicids2017.md).

```bash
unzip CICIDS2017_improved.zip -d cicids-dataset
sha256sum cicids-dataset/*.csv
```

O NIDS lê o `Tuesday-WorkingHours.pcap` do CIC-IDS2017 ([decisão 10](decisoes.md#10-tráfego-de-entrada-e-emulação-da-rede)), com 11 GB. O mirror, o commit, o caminho, o tamanho e o SHA-256 do arquivo estão em [configs/pcap-preparation.json](../configs/pcap-preparation.json), e `preparar-pcap` confere o tamanho e o hash antes de usá-lo.

```bash
mkdir -p cicids-dataset/pcap
curl -L -o cicids-dataset/pcap/Tuesday-WorkingHours.pcap \
  https://huggingface.co/datasets/bencorn/CICIDS2017/resolve/811c007f08d693a8a8b4226c197c138391806ce6/pcaps/Tuesday-WorkingHours.pcap
```

Os arquivos ficam dentro de `cicids-dataset/`, e não num link simbólico para fora do repositório. O `preparar-pcap` grava no manifesto o caminho real de cada arquivo em relação ao repositório e termina com erro quando esse caminho fica fora dele.

A [página do CIC-IDS2017](https://www.unb.ca/cic/datasets/ids-2017.html) pede que os trabalhos que usam o conjunto citem Sharafaldin, Habibi Lashkari e Ghorbani (2018).

## Etapas

Os comandos `python main.py` rodam em `src/`, com o ambiente ativado.

### Configurações que apontam para execuções

Os comandos de treino, de explicação e do NIDS gravam cada execução numa pasta nova, cujo nome é o instante UTC em que ela foi criada, como `20261111T171132620028Z`. Algumas configurações apontam para as pastas do experimento original. Depois de cada comando da tabela, o campo indicado recebe a pasta nova, antes do comando seguinte.

| Comando | Pasta nova | Campo |
|---|---|---|
| `treinar-rf-piloto` | `training-runs/random-forest-pilot/<execução>` | `reference_run` de `configs/random-forest-comparison.json` e de `configs/xgboost-comparison.json`, e `pilot_run` de `configs/tree-shap.json` |
| `comparar-rf` | `training-runs/random-forest-comparison/<execução>` | `models.random-forest` de `configs/model-freezing.json` |
| `treinar-xgboost` | `training-runs/xgboost-comparison/<execução>` | `models.xgboost` de `configs/model-freezing.json` |
| `congelar-modelos` | `training-runs/frozen-models/<execução>` | `frozen_run` de `configs/tree-shap.json` e de `configs/nids.json` |
| `calibrar-selecao` | `training-runs/nids/calibracao/<execução>` | `selection.calibration_run` de `configs/nids.json` |

### 1. Dados

```bash
python main.py preparar-dados
git diff ../derived-data/manifest.json
```

O comando aplica as decisões 1 a 4 aos cinco CSVs e grava os conjuntos de treino, validação e teste em `derived-data/`. O manifesto tem os hashes dos CSVs e dos conjuntos, e o `git diff` mostra o que mudou em relação ao manifesto do experimento.

### 2. Classificadores

```bash
python main.py treinar-rf-piloto
python main.py comparar-rf
python main.py treinar-xgboost
python main.py congelar-modelos
```

`comparar-rf` e `treinar-xgboost` escolhem a configuração de cada classificador na validação e avaliam a escolhida no teste. `congelar-modelos` confere que cada modelo, carregado num processo novo, repete as previsões do teste. O SHA-256 de cada modelo do experimento está em `training-runs/frozen-models/20261111T181031847482Z/<classificador>/manifest.json`.

### 3. TreeSHAP

```bash
python main.py validar-treeshap
python main.py medir-treeshap --validacao ../training-runs/tree-shap/validacao/<execução>
```

`validar-treeshap` confere as explicações de 10.000 registros da validação com os dois modelos congelados. `medir-treeshap` aceita só uma validação aprovada, exige a máquina na tomada e mede o tempo de inferência e o tempo de explicação fora do NIDS.

### 4. Critérios de seleção

```bash
python main.py calibrar-selecao
```

Os limiares dos dois critérios de seleção estão em `selection.thresholds` de `configs/nids.json` ([decisão 12](decisoes.md#12-critérios-de-seleção-do-síncrono-condicional)). A calibração refaz, no conjunto de validação, a tabela usada para escolhê-los.

### 5. Tráfego

```bash
rm ../derived-data/pcap/tuesday/manifest.json
python main.py preparar-pcap
python main.py conferir-extracao --trecho validacao
rm ../derived-data/pcap/tuesday-campanha/manifest.json
python main.py preparar-trecho --config ../configs/pcap-campanha.json
python main.py conferir-extracao --config ../configs/pcap-campanha.json --trecho campanha
git diff ../derived-data/pcap
```

`preparar-pcap` e `preparar-trecho` recusam uma pasta que já tem `manifest.json`, e os manifestos do experimento estão no repositório. Por isso, cada um vem depois do `rm` do seu manifesto.

`preparar-pcap` corrige e ordena o PCAP inteiro e corta os trechos `dev` e `validacao`, em `derived-data/pcap/tuesday/`. `preparar-trecho` corta, de um trecho já preparado, o trecho da campanha ([decisão 16](decisoes.md#16-tráfego-do-piloto-e-da-campanha)). `conferir-extracao` compara os fluxos extraídos de cada trecho com os de `tuesday.csv` e termina com erro se alguma conferência falhar. Os manifestos dos trechos são versionados, e o `git diff` mostra o que mudou neles.

### 6. Leituras por arquivo

A validação de cada execução da campanha a compara com a leitura do mesmo trecho pelo NIDS, direto do arquivo e sem rede, com o mesmo classificador e a mesma configuração de explicação. As dez leituras abaixo precisam existir antes da análise da campanha.

```bash
for modelo in random-forest xgboost; do
  python main.py nids-executar --modelo $modelo --trecho campanha --estrategia sem-xai
  python main.py nids-executar --modelo $modelo --trecho campanha --estrategia sincrono-total
  python main.py nids-executar --modelo $modelo --trecho campanha --estrategia sincrono-condicional --criterio probabilidade
  python main.py nids-executar --modelo $modelo --trecho campanha --estrategia sincrono-condicional --criterio incerteza
  python main.py nids-executar --modelo $modelo --trecho campanha --estrategia assincrono
done
```

### 7. Campanha

O registro de uma matriz fica em `training-runs/matrizes/<nome>/registro.jsonl`, e o executor pula as células já concluídas nele. O registro da campanha original está no repositório, com as 90 células concluídas. Por isso, uma nova campanha usa uma cópia de `configs/campanha.json` com outro valor em `name`. Os comandos abaixo rodam na raiz do repositório, num terminal comum, porque o `sudo` pede a senha.

```bash
sed 's/"name": "campanha"/"name": "campanha-reproducao"/' configs/campanha.json > configs/campanha-reproducao.json
sudo python3 scripts/executar_matriz.py --matriz configs/campanha-reproducao.json
```

As 90 execuções da campanha original levaram de 22,5 a 23,9 min cada, cerca de 34 h no total ([registro](../training-runs/matrizes/campanha/registro.jsonl)). Com `--ate 07:00`, o executor não começa uma execução que terminaria depois desse horário, e a mesma chamada, repetida, continua de onde parou. Antes de cada execução, o executor espera a máquina atender às condições do bloco `machine` da matriz ([decisão 17](decisoes.md#17-estado-da-máquina-durante-os-ensaios)).

### 8. Validação, auditoria e resultados

```bash
python main.py matriz-analisar --matriz ../configs/campanha-reproducao.json
python main.py campanha-auditar --matriz ../configs/campanha-reproducao.json
python main.py campanha-resultados --matriz ../configs/campanha-reproducao.json
```

`matriz-analisar` valida cada execução válida contra a leitura por arquivo correspondente. `campanha-auditar` confere o registro, os arquivos brutos e as validações. `campanha-resultados` exige uma auditoria aprovada, recalcula as medidas dos registros brutos e aplica as regras das decisões 23 a 27.

## O que se repete

Num clone limpo, na máquina da campanha, com o Python 3.12.16 e o Wireshark 4.6.4, as etapas 1 a 6 levaram cerca de 1 h 30 min e repetiram o experimento nestes pontos.

- Os conjuntos de treino, validação e teste e os trechos de PCAP saíram com os mesmos hashes. Nos manifestos, mudaram só os caminhos, as versões do Python e das ferramentas, os nomes de dois campos da saída do `capinfos`, a plataforma, o tempo, a memória e o hash do manifesto de base.
- Os dois `model.joblib` saíram com os mesmos hashes, e as métricas de validação e de teste e a tabela da calibração foram as mesmas.
- As dez leituras por arquivo do trecho da campanha deram arquivos de classificações e de explicações idênticos aos do experimento.

Mudaram os tempos medidos, como os do custo isolado do TreeSHAP, e 467 das 314.993 probabilidades de ataque do Random Forest no teste, em no máximo 2,2 × 10⁻¹⁶, sem mudar nenhuma classificação. Essa conferência não cobre as etapas 7 e 8, que exigem `sudo` e cerca de 34 h.

## Resultados do experimento original

| Etapa | Relatório | Registro |
|---|---|---|
| Inspeção dos CSVs | [inspecao-cicids2017.md](../relatorios/inspecao-cicids2017.md) | [inspecao-cicids2017.json](../relatorios/inspecao-cicids2017.json) |
| Random Forest | [random-forest-comparison-20261111T171132620028Z.md](../relatorios/random-forest-comparison-20261111T171132620028Z.md) | `training-runs/random-forest-comparison/20261111T171132620028Z/` |
| XGBoost | [xgboost-comparison-20261111T175006216484Z.md](../relatorios/xgboost-comparison-20261111T175006216484Z.md) | `training-runs/xgboost-comparison/20261111T175006216484Z/` |
| Modelos congelados | [model-freezing-20261111T181031847482Z.md](../relatorios/model-freezing-20261111T181031847482Z.md) | `training-runs/frozen-models/20261111T181031847482Z/` |
| Validação do TreeSHAP | [treeshap-validacao-20261112T111512985729Z.md](../relatorios/treeshap-validacao-20261112T111512985729Z.md) | `training-runs/tree-shap/validacao/20261112T111512985729Z/` |
| Custo isolado do TreeSHAP | [treeshap-medicao-20261112T113136395550Z.md](../relatorios/treeshap-medicao-20261112T113136395550Z.md) | `training-runs/tree-shap/medicao/20261112T113136395550Z/` |
| Calibração dos critérios de seleção | [selecao-condicional-20261114T204351398308Z.md](../relatorios/selecao-condicional-20261114T204351398308Z.md) | `training-runs/nids/calibracao/20261114T204351398308Z/` |
| Extração do trecho da campanha | [extracao-pcap-20261115T192306992011Z.md](../relatorios/extracao-pcap-20261115T192306992011Z.md) | `training-runs/traffic/extracao/` |
| Análise da campanha | [campanha-20261120T120722710408Z.md](../relatorios/campanha-20261120T120722710408Z.md) | `training-runs/nids/analise-campanha/20261120T120722710408Z/` |
| Auditoria da campanha | [campanha-auditoria-20261120T125714303006Z.md](../relatorios/campanha-auditoria-20261120T125714303006Z.md) | `training-runs/nids/auditoria-campanha/20261120T125714303006Z/` |
| Resultados da campanha | [campanha-resultados-20261120T173808263579Z.md](../relatorios/campanha-resultados-20261120T173808263579Z.md) | `training-runs/nids/resultados-campanha/20261120T173808263579Z/` |

As 90 execuções da campanha rodaram no commit `4558a3be71a791309db44c71a1fd6c9a25ae6642` ([auditoria](../relatorios/campanha-auditoria-20261120T125714303006Z.md)). Depois dele, o código mudou só nos comandos da auditoria e dos resultados. As entradas fixas de cada execução, com os hashes do modelo, do trecho, dos jars do extrator e do `tcpreplay-edit`, estão no `report.json` e no `replay.json` da execução, em `training-runs/nids/interface/`.
