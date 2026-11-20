# Decisões do desenho experimental

Decisões tomadas para o experimento. Elas valem para todos os documentos e para todo o código do projeto. Os termos seguem o [glossário](glossario.md).

## 1. Alvo de classificação e rótulos

### Decisão

A classificação é binária. Um fluxo é **ataque** quando exibe comportamento malicioso e **benigno** caso contrário.

Na prática, o comportamento malicioso é o indicado pelos rótulos do Improved CIC-IDS2017, atribuídos por Liu et al. (2022):

- `BENIGN` é benigno.
- Todo rótulo com o sufixo `- Attempted` é benigno. Esses são exatamente os registros com `Attempted Category` diferente de -1.
- Todos os demais rótulos são ataque, incluindo `DoS Hulk`.

Os CSVs originais não são alterados. O mapeamento se aplica aos dados derivados.

### Justificativa

- O classificador recebe apenas os atributos do fluxo. A intenção do atacante não está nesses atributos, então o rótulo deve depender do que o fluxo contém.
- O TreeSHAP explica cada classificação pela contribuição dos atributos. Um fluxo sem comportamento malicioso rotulado como ataque levaria a explicação a atribuir "ataque" a atributos que não o contêm.
- A documentação do Improved CIC-IDS2017 define um fluxo Attempted como aquele que "was intended to be part of the attack" mas "does not exhibit any malicious behaviour". Ela recomenda "When in doubt, we recommend to relabel all 'Attempted' flows as Benign" e proíbe tratar esses fluxos como classe própria ([Datasets Download](https://intrusion-detection.distrinet-research.be/CNS2022/Dataset_Download.html)).
- A classificação por tipo de ataque teria classes com poucos registros para dividir entre treino, validação e teste: Heartbleed (11), Web Attack - SQL Injection (13), Web Attack - XSS (18) e Infiltration (36).
- A métrica ROC-AUC, prevista na proposta, é definida para o caso binário, e o TreeSHAP tem uma única saída a explicar.

Sobre o DoS Hulk, a documentação do Improved CIC-IDS2017 afirma que "the entirety of this attack should strictly speaking be labelled as Attempted with category 5 - Attack Implemented Incorrectly". Em seguida, justifica a manutenção do rótulo de ataque: "since this large volume of traffic still looks anomalous, we opted to keep the default label of DoS Hulk" ([CIC-IDS 2017](https://intrusion-detection.distrinet-research.be/CNS2022/CICIDS2017.html)). Este trabalho mantém os 158.468 registros `DoS Hulk` como ataque pelo mesmo motivo: o grande volume desse tráfego continua anômalo.

### Efeito nos dados

| Classe | Registros | Proporção |
|---|---|---|
| Benigno | 1.594.545 | 75,93% |
| Ataque | 505.431 | 24,07% |
| Total | 2.099.976 | 100% |

### Mapa de rótulos

| Rótulo original | Registros | Classe |
|---|---|---|
| BENIGN | 1.582.566 | Benigno |
| Portscan | 159.066 | Ataque |
| DoS Hulk | 158.468 | Ataque |
| DDoS | 95.144 | Ataque |
| Infiltration - Portscan | 71.767 | Ataque |
| DoS GoldenEye | 7.567 | Ataque |
| Botnet - Attempted | 4.067 | Benigno |
| FTP-Patator | 3.972 | Ataque |
| DoS Slowloris | 3.859 | Ataque |
| DoS Slowhttptest - Attempted | 3.368 | Benigno |
| SSH-Patator | 2.961 | Ataque |
| DoS Slowloris - Attempted | 1.847 | Benigno |
| DoS Slowhttptest | 1.740 | Ataque |
| Web Attack - Brute Force - Attempted | 1.292 | Benigno |
| Botnet | 736 | Ataque |
| Web Attack - XSS - Attempted | 655 | Benigno |
| DoS Hulk - Attempted | 581 | Benigno |
| DoS GoldenEye - Attempted | 80 | Benigno |
| Web Attack - Brute Force | 73 | Ataque |
| Infiltration - Attempted | 45 | Benigno |
| Infiltration | 36 | Ataque |
| SSH-Patator - Attempted | 27 | Benigno |
| Web Attack - XSS | 18 | Ataque |
| Web Attack - SQL Injection | 13 | Ataque |
| FTP-Patator - Attempted | 12 | Benigno |
| Heartbleed | 11 | Ataque |
| Web Attack - SQL Injection - Attempted | 5 | Benigno |

As contagens vêm do [relatório de inspeção](../relatorios/inspecao-cicids2017.md).

## 2. Valores infinitos e comprimentos de cabeçalho

### Decisão

- Nos dados derivados, o valor `inf` de `Flow Bytes/s` e `Flow Packets/s` é substituído por -1.
- `Fwd Header Length` e `Bwd Header Length` não fazem parte das entradas do classificador.

Os CSVs originais não são alterados.

### Diagnóstico dos infinitos

- Os 5 registros com `inf` são os únicos do dataset com `Flow Duration` igual a 0. As duas taxas dividem pela duração do fluxo.
- Os 5 são BENIGN, UDP na porta 137, com 2 pacotes de ida e nenhum de volta.
- A versão do [CICFlowMeter corrigido](https://github.com/GintsEngelen/CICFlowMeter) que gerou o dataset divide pela duração sem verificar se ela é 0. As versões a partir do commit `9caefd056f` gravam -1 nas duas taxas nesse caso (`BasicFlow.java`, método `dumpFlowBasedFeaturesEx`).

### Diagnóstico dos comprimentos de cabeçalho

- O CICFlowMeter corrigido soma os comprimentos de cabeçalho em variáveis `long`, sem estouro.
- O notebook de rotulagem do Improved CIC-IDS2017 converte as duas colunas com `astype('int16')` ([`CNS2022_Code`](https://github.com/GintsEngelen/CNS2022_Code), `Labelling/CICIDS2017_labelling_fixed_CICFlowMeter.ipynb`). Todo valor acima de 32.767 dá a volta e vira outro número, negativo ou positivo.
- Nenhum valor das duas colunas passa de 32.748. No entanto, 338 sentidos de ida e 523 de volta são fluxos TCP com 1.639 pacotes ou mais. Como cada cabeçalho TCP tem no mínimo 20 bytes, a soma nesses fluxos passa de 32.767.
- O NIDS em operação calcula a soma correta. Com os atributos mantidos, os fluxos longos teriam no treino valores diferentes dos encontrados em operação.

| Registros | Quantidade |
|---|---|
| Com valor negativo | 593 |
| Com valor certamente errado | 690 |
| Com valor possivelmente errado | até 2.051 (0,1%) |

Os registros com valor negativo incluem 3 dos 11 registros de Heartbleed.

### Outros valores negativos

`ICMP Code` e `ICMP Type` valem -1 nos 2.099.373 fluxos que não são ICMP, e `Attempted Category` vale -1 nos fluxos que não são Attempted. Esses valores indicam que o campo não se aplica e não são erros.

### Justificativa

- O valor -1 é o que as versões posteriores do CICFlowMeter corrigido gravam para fluxos de duração 0, e nenhuma taxa válida é negativa. A substituição mantém os 5 registros.
- O extrator adotado para o NIDS (decisão 3) produz `inf` nesses fluxos. Por isso o NIDS aplica a mesma substituição antes da classificação.
- Os valores errados de cabeçalho não podem ser identificados em todos os registros afetados. Excluir os registros possivelmente afetados descartaria sistematicamente os fluxos longos, incluindo 3 dos 11 registros de Heartbleed. Retirar os dois atributos elimina a divergência entre treino e operação sem descartar registros.

### Efeito nos dados

- Nenhum registro é excluído.
- 5 registros passam a ter -1 em `Flow Bytes/s` e `Flow Packets/s`.
- As entradas do classificador perdem dois atributos.

## 3. Extrator e entradas do classificador

### Decisão

- O NIDS extrai os atributos com o [CICFlowMeter corrigido](https://github.com/GintsEngelen/CICFlowMeter) no commit `13a061520b`, com tempo limite de fluxo de 120 s e tempo limite de atividade de 5 s.
- O classificador recebe 80 atributos. `Dst Port` fica fora das entradas.
- `id`, `Flow ID`, `Src IP`, `Src Port`, `Dst IP`, `Dst Port` e `Timestamp` são metadados de rastreabilidade. `Label` e `Attempted Category` são rótulos. Nenhuma dessas colunas é entrada.

O [dicionário de atributos](dicionario-atributos.md) lista o significado, a unidade e o papel de cada coluna, e as regras de formação dos fluxos.

### Justificativa

- As versões do extrator entre os commits `e3bb9ce18d` e `13a061520b` produzem as 88 colunas de atributos dos CSVs, com os mesmos nomes e na mesma ordem. O commit `13a061520b` é o último anterior à data dos CSVs no arquivo do dataset, 2023-04-27. A documentação do dataset não informa a versão usada.
- A versão atual do extrator calcula atributos diferentes dos do treino. Ela renomeia `Total TCP Flow Time`, acrescenta 5 atributos, inverte o sentido do fluxo quando o primeiro pacote é SYN-ACK e altera o cálculo dos atributos de subfluxo e de `Bwd Init Win Bytes`.
- No CIC-IDS2017, vários ataques usam uma porta de destino fixa. Com `Dst Port` nas entradas, o classificador poderia aprender a porta em vez do comportamento do fluxo, e as explicações apontariam para a porta. Bertoli et al. (2020) removeram as portas para eliminar "qualquer imposição do _setup_ utilizado para obtenção dos dados" ([transcrição local](bibliography/abordagem-fim-a-fim-para-uso-de-aprendizado-de-maquina.md)).
- Os endereços IP identificam as máquinas do ambiente em que o dataset foi gerado, e `Timestamp` identifica o dia e a hora de cada ataque. Com essas colunas nas entradas, o classificador aprenderia o cenário do dataset.

### Efeito nos dados

| Papel | Colunas |
|---|---|
| Entrada do classificador | 80 |
| Metadado de rastreabilidade | 7 |
| Rótulo | 2 |
| Excluído pela decisão 2 | 2 |
| Total | 91 |

## 4. Separação entre treino, validação e teste

### Decisão

- A unidade de agrupamento é o conjunto de registros com as 80 entradas idênticas. Cada grupo fica inteiro em um único conjunto.
- Os registros são divididos em 70% para treino, 15% para validação e 15% para teste.
- A divisão é estratificada pelos 27 rótulos originais e usa uma semente de aleatoriedade fixa.
- Os registros de grupos com rótulos binários diferentes mantêm seus rótulos.

### Procedimento

1. Aplicar as decisões 1, 2 e 3 aos registros dos cinco CSVs.
2. Agrupar os registros que têm as 80 entradas idênticas.
3. Atribuir a cada grupo um rótulo de estratificação, que é o rótulo original mais frequente entre seus registros.
4. Distribuir os grupos entre treino, validação e teste, de forma estratificada pelo rótulo de estratificação.

Como os grupos são indivisíveis, as proporções obtidas são aproximadas. A preparação dos dados registra as proporções obtidas e a semente.

### Verificações de independência

A preparação dos dados só é válida quando as quatro verificações abaixo passam.

- Nenhum vetor de 80 entradas aparece em mais de um conjunto.
- Cada registro pertence a exatamente um conjunto, e os três conjuntos somam 2.099.976 registros.
- Cada um dos 27 rótulos originais aparece nos três conjuntos.
- A proporção de benignos e de ataques é registrada para cada conjunto.

### Uso dos conjuntos

- O treino ajusta os classificadores.
- A validação escolhe os hiperparâmetros e calibra o critério de seleção da estratégia Síncrono condicional.
- O teste só é usado na avaliação final, depois que os classificadores estão congelados. Ele não é usado para escolher atributos, hiperparâmetros, limiares nem estratégias.
- As métricas de detecção vêm do conjunto de teste. O piloto e a campanha reproduzem o trecho da [decisão 16](#16-tráfego-do-piloto-e-da-campanha), que inclui fluxos do treino, e medem latência e uso de recursos.

### Justificativa

- 447.899 registros (21,33%) pertencem a 63.136 grupos de registros com as 80 entradas idênticas, e 281.406 deles estão em grupos que cruzam dias. O rótulo Portscan tem 159.066 registros e 1.683 vetores de entrada distintos. Uma divisão por registro colocaria cópias dos registros de treino no teste e inflaria o desempenho medido.
- O agrupamento por `Flow ID` mantém as conexões juntas, mas deixa registros idênticos de conexões diferentes em conjuntos diferentes.
- O agrupamento pelas duas relações ao mesmo tempo é inviável. Três componentes concentram 792.425 registros (38%), e cada componente teria que ficar inteiro em um conjunto.
- A divisão por dia é inviável. A segunda-feira não tem ataques, e cada tipo de ataque ocorre em um ou dois dias.
- A estratificação pelos rótulos originais garante que cada tipo de ataque apareça nos três conjuntos, o que a estratificação pelo rótulo binário não garante.

| Dia | Benigno | Ataque |
|---|---|---|
| Segunda | 371.624 | 0 |
| Terça | 315.145 | 6.933 |
| Quarta | 324.996 | 171.645 |
| Quinta | 290.169 | 71.907 |
| Sexta | 292.611 | 254.946 |

### Limites

- Fluxos da mesma conexão podem ficar em conjuntos diferentes. 1.245.681 registros (59,32%) compartilham o `Flow ID` com outro registro.
- Os 11 registros de Heartbleed pertencem a uma única conexão, dividida pelo tempo limite de 120 s. O desempenho medido nesse rótulo é otimista.
- 14 grupos, com 2.678 registros, têm entradas idênticas e rótulos binários diferentes: 2.639 Portscan, 24 Infiltration - Portscan e 15 BENIGN. Nenhum classificador separa esses registros.

## 5. Configuração do Random Forest

### Decisão

O Random Forest usa 100 árvores, profundidade máxima de 12, mínimo de dois registros por folha, critério de Gini e `max_features="sqrt"`. O treinamento usa `bootstrap=True`, semente 42 e dois trabalhadores. Não há ponderação de classes nem normalização das entradas.

A configuração é escolhida pelo maior F1 na validação. Empates favorecem a floresta com menos nós e, depois, menos árvores. A comparação usa a mesma amostra de 100 mil registros para três configurações. Somente a escolhida recebe treinamento com todos os 1.469.983 registros do treino. O limiar de classificação permanece fixo: ataque quando a probabilidade for maior que 0,5; benigno nos demais casos.

As escolhas são registradas antes do treinamento completo e da abertura do teste reservado. O teste avalia o modelo escolhido e não participa da seleção.

### Justificativa

| Árvores | Profundidade máxima | F1 na validação, após treino na amostra |
|---|---|---|
| 100 | 12 | 0,998283 |
| 50 | 12 | 0,998157 |
| 100 | 8 | 0,996812 |

A configuração com 100 árvores e profundidade 12 obteve o maior F1. A alternativa com 50 árvores reduziu o número de nós, mas teve 279 erros na validação, contra 260 da configuração escolhida. A alternativa com profundidade 8 teve 482 erros. A diferença entre as duas primeiras configurações é pequena; a comparação não estabelece significância estatística nem mede o custo das explicações.

Os parâmetros completos e as medições estão em [selection.json](../training-runs/random-forest-comparison/20261111T171132620028Z/selection.json). A configuração da comparação está em [configs/random-forest-comparison.json](../configs/random-forest-comparison.json).

## 6. Configuração do XGBoost

### Decisão

O XGBoost usa 100 árvores, profundidade máxima de 6 e taxa de aprendizagem 0,1. A função objetivo é `binary:logistic`, que produz a probabilidade de ataque. O treinamento usa `booster="gbtree"`, método de histogramas em CPU, semente 42 e dois trabalhadores. As proporções de registros e atributos usados em cada árvore são 1,0. Não há ponderação adicional de classes, normalização das entradas nem parada antecipada.

A seleção segue o mesmo critério do Random Forest: maior F1 na validação, com desempate pelo menor número de nós e, depois, de árvores. As três configurações usam os mesmos 100 mil registros da amostra do Random Forest. As métricas do Random Forest não participam da escolha do XGBoost.

A configuração escolhida recebe treinamento com todos os 1.469.983 registros do treino. O modelo e seus parâmetros são salvos antes de abrir o teste. O limiar permanece fixo em probabilidade maior que 0,5 para ataque. O resultado do teste não altera a configuração.

### Justificativa

| Árvores | Profundidade máxima | Taxa de aprendizagem | F1 na validação, após treino na amostra |
|---|---|---|---|
| 100 | 6 | 0,1 | 0,999103 |
| 50 | 6 | 0,1 | 0,998496 |
| 100 | 4 | 0,1 | 0,998759 |

A configuração com 100 árvores e profundidade 6 obteve o maior F1 e 136 erros na validação, contra 228 com 50 árvores e 188 com profundidade 4. Essa comparação curta sustenta a escolha entre as três configurações avaliadas. Ela não estabelece significância estatística nem mede o custo de gerar explicações.

Os demais parâmetros e a configuração efetiva da biblioteca estão nos artefatos da execução. O [relatório de avaliação](../relatorios/xgboost-comparison-20261111T175006216484Z.md) apresenta as métricas de validação e teste, a matriz de confusão e as contagens por rótulo. A comparação é definida em [configs/xgboost-comparison.json](../configs/xgboost-comparison.json).

## 7. Configuração do TreeSHAP

### Decisão

- O TreeSHAP usa a perturbação path-dependent, sem conjunto de referência e sem aproximação. Na biblioteca `shap` 0.54.1, isso corresponde a `feature_perturbation="tree_path_dependent"` na construção do explicador e a `approximate=False` na chamada de `shap_values`.
- Os termos path-dependent e interventional são os de Lundberg et al. (2020) ([transcrição local](bibliography/from-local-explanations-to-global-understanding-with-explainable-ai-for-trees.md)). Na biblioteca `shap`, eles correspondem aos valores `"tree_path_dependent"` e `"interventional"` de `feature_perturbation`.
- Os valores de Shapley são calculados exatamente para a função de valor definida pela cobertura do nó. Essa função aproxima a expectativa interventional, que só o cálculo com conjunto de referência obtém exatamente (Lundberg et al., 2020, Methods, "TreeExplainer with path dependent feature perturbation"). Nos documentos, "exato" qualifica o cálculo dos valores de Shapley, e não a expectativa.
- No Random Forest, a saída explicada é a probabilidade de ataque. O explicador usa `model_output="raw"` e a classe 1. A saída bruta da classe 1 é a média, entre as árvores, da proporção de ataques na folha alcançada, que é o valor de `predict_proba` para a classe 1.
- No XGBoost, a saída explicada é o escore anterior à sigmoide, na escala de log-odds, também com `model_output="raw"`. A classe continua a vir da probabilidade, pelo limiar da decisão 6.
- O valor de referência é a saída esperada desse cálculo, e não um conjunto de dados.

### Justificativa

- O custo do cálculo interventional cresce linearmente com o número de amostras do conjunto de referência (Lundberg et al., 2020, Methods, "TreeExplainer with interventional feature perturbation"). Esse número seria um parâmetro arbitrário a mais e mudaria a sobrecarga de latência medida. A mesma subseção do artigo dá dois limites diferentes para esse custo, O(TLDN) e O(TRL), e por isso esta decisão não reproduz a fórmula.
- O custo do cálculo path-dependent, O(TLD²), não depende de conjunto de referência. O cálculo dispensa esse conjunto porque usa a cobertura do nó guardada no próprio modelo (Methods, "TreeExplainer with path dependent feature perturbation").
- O cálculo path-dependent explica a saída bruta das árvores. No `shap` 0.54.1, ele só aceita `model_output="raw"`, e `model_output="probability"` exige o cálculo interventional. Segundo Lundberg et al. (2020), não há forma simples de ajustar os valores de Shapley a uma transformação não linear da saída, e o cálculo dessas transformações percorre cada amostra do conjunto de referência (Methods, "TreeExplainer with interventional feature perturbation"). Por isso, o XGBoost é explicado na escala de log-odds, e não de probabilidade.

### Consequências

- As contribuições do Random Forest ficam na escala de probabilidade, e as do XGBoost na escala de log-odds. As magnitudes das contribuições não são comparáveis entre os dois classificadores.
- A implementação que calcula as contribuições difere entre os classificadores. No Random Forest, o cálculo é feito pela extensão C do `shap`. No XGBoost, o `shap` 0.54.1 delega o cálculo ao TreeSHAP do próprio XGBoost, por `Booster.predict(..., pred_contribs=True, approx_contribs=False)`. A diferença de custo do TreeSHAP entre os classificadores inclui a diferença entre as implementações.

### Cobertura do nó nos dois classificadores

Lundberg et al. (2020, Methods, "TreeExplainer with path dependent feature perturbation") definem a cobertura do nó como o número de registros que chegam ao nó. Cada biblioteca a calcula de um modo.

- No Random Forest, o `shap` 0.54.1 usa `tree_.weighted_n_node_samples` como cobertura do nó (`shap/explainers/_tree.py`, classe `SingleTree`). No scikit-learn 1.9.1, o treino com `bootstrap=True` dá a cada registro, como peso na árvore, o número de vezes em que ele foi sorteado (`sklearn/ensemble/_forest.py`, função `_parallel_build_trees`). Na primeira árvore do Random Forest congelado, a raiz tem cobertura 1.469.983, igual ao número de sorteios, e recebe 929.107 registros distintos.
- No XGBoost, a documentação define que "cover is the sum of second order gradient in each node" ([referência de `xgb.plot.tree`, XGBoost 3.4.0](https://xgboost.readthedocs.io/en/stable/r_docs/R-package/docs/reference/xgb.plot.tree.html)). Em `binary:logistic`, a hessiana de cada registro vale p(1 − p). Na primeira árvore do XGBoost congelado, a raiz tem cobertura 268.646,3, igual a n·p₀(1 − p₀) com n = 1.469.983 e p₀ = 0,24068305, o `base_score` do modelo.
- No XGBoost congelado, o valor de referência devolvido por `pred_contribs` vale −1,3696141. O logit do `base_score` somado à média das folhas de cada árvore, ponderada pela soma das hessianas, vale −1,3696140.

Por isso, o valor de referência não é a saída média sobre o treino em nenhum dos dois classificadores.

## 8. Emissão dos fluxos no NIDS

### Decisão

- O NIDS emite um fluxo quando o relógio da captura passa de 120 s desde o primeiro pacote do fluxo. Essa emissão se chama varredura do tempo limite.
- O relógio da captura é o instante do último pacote lido. Quando a leitura fica sem pacotes, ele avança com o relógio do sistema menos uma margem de 2 s, para que os fluxos sejam emitidos mesmo sem tráfego novo. Ele nunca volta atrás.
- O NIDS mantém as emissões que o extrator já faz durante a leitura: a chegada de um SYN depois do encerramento TCP e a mudança de código e tipo ICMP. No fim da captura, emite os fluxos restantes.
- As regras de formação dos fluxos não mudam. O fluxo emitido pela varredura continua guardado até o pacote seguinte do mesmo identificador, para que o fluxo seguinte da mesma conexão TCP herde o sentido e a duração acumulada (`Total TCP Flow Time`), como no extrator original.
- Na captura ao vivo, a leitura de pacotes usa o modo não bloqueante da libpcap. Quando não há pacotes, o extrator avança o relógio da captura, executa a varredura e espera 1 ms antes de ler de novo.
- O buffer de captura da libpcap, que guarda os pacotes ainda não lidos pelo extrator, tem 256 MiB.
- A implementação é o patch [extractor/patches/01-flow-emission-sweep.patch](../extractor/patches/01-flow-emission-sweep.patch), aplicado sobre o commit `13a061520b` da decisão 3. O modo não bloqueante e o tamanho do buffer de captura estão em [extractor/patches/02-live-capture.patch](../extractor/patches/02-live-capture.patch).

### Justificativa

- O extrator só emite um fluxo durante a leitura quando chega outro pacote com o mesmo identificador, nos casos acima. Os demais fluxos saem no fim da captura (`FlowGenerator.addPacket` e `Cmd.readPcapFile`). Numa captura contínua, a maioria dos fluxos não seria classificada até o fim.
- Depois de 120 s desde o primeiro pacote, as regras do extrator já não aceitam pacotes no fluxo: o pacote seguinte inicia um fluxo novo. Emitir nesse instante não altera nenhum atributo, e os fluxos do NIDS ficam iguais aos fluxos que geraram os dados de treino.
- Emitir logo depois do encerramento TCP alteraria os fluxos. O extrator original acrescenta ao fluxo encerrado os pacotes que chegam depois do encerramento, até um SYN.
- Com TPACKET_V3, a libpcap bloqueia no `poll()` sem limite de tempo quando o tempo limite de leitura é positivo e deixa o kernel acordar a leitura, o que só acontece quando há pacotes (`pcap-linux.c`, `set_poll_timeout`, libpcap 1.10.6). Numa interface sem pacotes, a leitura bloqueante não retorna. A varredura do tempo limite e o pedido de parada nunca seriam atendidos depois do último pacote. No modo não bloqueante, a leitura retorna 0 na hora, e o tempo limite de 100 ms passa a definir só quanto o kernel espera para entregar um bloco parcial de pacotes. Um ensaio com a leitura bloqueante travou depois do fim da reprodução por esse motivo.
- O buffer de captura padrão da libpcap tem 2 MiB. Ele comporta cerca de 170 ms do maior volume do trecho `validacao`, de 12,2 MB num segundo, e uma pausa do extrator dessa ordem faz o kernel descartar pacotes. Com 256 MiB, o buffer comporta cerca de 20 s desse volume. Num ensaio com o buffer padrão, o libpcap descartou 11.448 dos 3.954.069 pacotes do trecho com o XGBoost, que classifica um fluxo em menos de 1 ms.

### Consequências

- A classificação de um fluxo fica disponível até cerca de 120 s depois do seu primeiro pacote. Essa espera ocorre antes de `t0` e não entra na latência de classificação, que começa em `t0`.
- Na captura ao vivo, um pacote atrasado pode chegar a um fluxo que a varredura já emitiu. O extrator conta esses pacotes, e cada execução os registra.
- O extrator recebe os pacotes até 100 ms depois de eles chegarem à interface, pelo bloco parcial do kernel. Esse atraso ocorre antes de `t0` e não entra na latência de classificação.
- Um pacote espera no buffer de captura enquanto o extrator não o lê. Essa espera também ocorre antes de `t0`. Cada execução registra os pacotes que o libpcap descartou por falta de espaço no buffer.
- A libpcap reduz o buffer, sem acusar erro, quando o kernel não consegue reservar o tamanho pedido (`pcap-linux.c`, `create_ring`, libpcap 1.10.6). Cada execução registra o tamanho pedido e o tamanho que o kernel mapeou no processo do extrator.

## 9. Marcações de tempo e relógio do NIDS

### Decisão

- O extrator e o classificador rodam em dois processos ligados por um pipe, uma linha por fluxo emitido.
- Na captura ao vivo, o extrator guarda a linha de cada fluxo emitido na fila de saída, uma fila em memória com o limite da [decisão 13](#13-limites-das-filas-e-política-de-descarte), e uma thread própria escreve as linhas no pipe. A thread que lê os pacotes não espera o classificador. Na leitura de arquivo, a mesma thread lê os pacotes e escreve as linhas.
- `t0` é lido no extrator Java, logo depois do cálculo dos atributos do fluxo emitido (`dumpFlowBasedFeaturesEx`) e antes de a linha entrar na fila de saída ou ser escrita no pipe.
- `t1` e `t2` são lidos imediatamente antes e depois da chamada `predict_proba` de um fluxo. O intervalo inclui só a chamada ao classificador.
- `t3` é o retorno da escrita do registro de classificação no canal de saída do NIDS, depois da passagem do registro ao sistema operacional, sem `fsync`. O canal de saída é o arquivo `classifications.jsonl` da execução, com uma linha por fluxo.
- Os quatro instantes vêm do relógio monotônico do Linux (`CLOCK_MONOTONIC`): `System.nanoTime()` no Java e `time.monotonic_ns()` no Python. Cada execução confere essa base comum. A diferença entre a leitura do extrator na abertura e a leitura do classificador ao recebê-la deve ficar entre 0 e 1 s, ou a execução falha.
- O classificador usa uma thread, como na medição isolada do TreeSHAP. As CPUs de cada processo estão na [decisão 14](#14-orçamento-de-cpu-e-de-memória).

### Justificativa

- O protocolo define `t3` como o momento em que a classificação fica disponível a quem a consome. A escrita no canal de saída torna o registro visível a outro processo e custa o mesmo nas quatro estratégias.
- O relógio monotônico não sofre os ajustes do relógio de parede. Os dois processos rodam na mesma máquina e leem o mesmo relógio, então as diferenças entre marcações de processos distintos têm significado.
- Entre `t0` e `t1` ficam a espera na fila de saída, a passagem pelo pipe e a montagem do vetor de entradas. Essa espera faz parte da latência de classificação.
- Quando a thread que lê os pacotes também escreve os fluxos, um pipe cheio interrompe a leitura, e o buffer de captura transborda. O pipe comporta cerca de 90 fluxos. No trecho `validacao`, a varredura emite mais de 200 fluxos em alguns segundos, e o Random Forest leva de 8 a 14 ms por fluxo, na média de cada ensaio. Num ensaio desse trecho com a escrita direta e o Random Forest, o libpcap descartou 413.628 dos 3.954.069 pacotes.
- Na leitura de arquivo não há captura a perder. A escrita direta limita a memória do extrator, que lê o arquivo mais rápido do que o classificador consome os fluxos.
- Cada execução registra o maior tamanho que a fila de saída atingiu.

## 10. Tráfego de entrada e emulação da rede

### Decisão

- **PCAP.** O tráfego de entrada é o `Tuesday-WorkingHours.pcap` do CIC-IDS2017, com 11.048.283.608 bytes e SHA-256 `080c2250154c5a174c03660ed0f75a3858d41a27511ba716e780d7bcb1ec4c57`. O arquivo vem do mirror não oficial [bencorn/CICIDS2017](https://huggingface.co/datasets/bencorn/CICIDS2017), no commit `811c007f08d693a8a8b4226c197c138391806ce6`, porque o servidor do CIC estava em manutenção. O MD5 oficial não foi conferido. A validade do arquivo se apoia na equivalência entre os fluxos extraídos e os de `tuesday.csv`.
- **Equivalência com `tuesday.csv`.** Os fluxos extraídos de um trecho equivalem aos do CSV quando as entradas inteiras coincidem exatamente e as entradas com fração diferem no máximo 10⁻¹² em valor relativo. Ficam fora da comparação os fluxos que começam nos últimos 120 s do trecho, que o corte interrompe, e os fluxos extraídos com algum `NaN`, que o CSV não tem.
- **Fluxos não classificáveis.** O NIDS não entrega ao classificador um fluxo com algum valor de entrada que os dados de treino não têm, como `NaN`. Ele registra o motivo e conta esses fluxos em cada execução. O tráfego não é alterado para retirá-los.
- **Preparação.** O arquivo inteiro passa pelo `pcapfix` e depois pelo `reordercap`, como os autores do Improved CIC-IDS2017 descrevem no [CNS2022_Code](https://github.com/GintsEngelen/CNS2022_Code). O arquivo do mirror está no formato pcapng, apesar da extensão `.pcap`, e o `reordercap` mantém esse formato. Os trechos são cortados com o `editcap` a partir do início da captura e gravados como PCAP clássico, sem alterar os bytes nem os instantes dos pacotes: `dev` até 11:58:44 UTC e `validacao` até 12:30:00 UTC. A configuração está em [configs/pcap-preparation.json](../configs/pcap-preparation.json).
- **Extrator.** O NIDS compila o pacote `cic.cs.unb.ca.jnetpcap` do commit da decisão 3 com o JDK 17, para Java 8, e usa o `jnetpcap` 1.4.r1425 incluído no repositório do extrator. A captura ao vivo usa o mesmo caminho de leitura de pacotes da leitura de arquivo, com o patch [extractor/patches/02-live-capture.patch](../extractor/patches/02-live-capture.patch).
- **Emulação.** O Mininet cria dois hosts em enlace direto, sem switch. O host h1 envia o trecho, ou as cópias do trecho da [decisão 15](#15-carga-por-sobreposição-de-cópias), na velocidade original com o `tcpreplay-edit` 4.6.2, compilado por [tcpreplay/build.sh](../tcpreplay/README.md) a partir do pacote da versão publicado pelo projeto. O host h2 executa o NIDS, que captura a interface em modo promíscuo. As descargas de processamento das placas virtuais (`ethtool -K`) ficam desligadas, a MTU acompanha o maior quadro do trecho e o IPv6 fica desativado nos dois hosts.

### Justificativa

- O MD5 publicado pelo CIC confirmaria que o arquivo do mirror é o original, mas o servidor do CIC estava fora do ar, e o trabalho não pode depender da sua volta. A equivalência com `tuesday.csv` mostra a propriedade de que o experimento depende: nos trechos conferidos, o arquivo produz os mesmos fluxos dos dados de treino.
- Os CSVs do Improved CIC-IDS2017 foram gerados a partir dos PCAPs depois do `pcapfix` e do `reordercap`. Repetir a preparação é a condição para que os fluxos do NIDS correspondam aos do treino.
- As entradas com fração do CSV diferem das extraídas nos últimos algarismos, com diferença relativa de no máximo 6 × 10⁻¹⁵ nos trechos conferidos. O notebook de rotulagem dos autores lê e regrava os CSVs com o pandas. A origem exata dessas diferenças não foi confirmada.
- Um fluxo de um único pacote não tem intervalo entre pacotes, e seus atributos de intervalo ficam `NaN`. O notebook de rotulagem dos autores descarta as linhas com `NaN` (`dropna`), então os modelos não foram treinados com esses fluxos. No trecho `validacao`, eles são 22 de 32.108 fluxos.
- Retirar os fluxos não classificáveis exigiria alterar o PCAP. Contá-los em cada execução mostra quanto do tráfego o NIDS deixa sem classificação.
- O caminho de leitura da captura ao vivo do extrator original (`TrafficFlowWorker`) difere do que gerou os CSVs e não trata ICMP.
- As descargas de processamento juntariam segmentos TCP em quadros maiores antes da captura, e os atributos de tamanho deixariam de corresponder aos do PCAP. O IPv6 desativado impede que os hosts emitam pacotes próprios durante a captura.
- O PCAP tem quadros maiores que 1.500 bytes, de até 24.874 bytes no trecho `validacao`, e a MTU precisa comportá-los para que o enlace os entregue inteiros. As versões 4.5.2 e 4.5.3 do `tcpreplay` não enviam os quadros acima de 4.064 bytes quando a MTU passa de uma página de memória. A versão 4.6.0 corrige esse defeito, e o Ubuntu 26.04 distribui a 4.5.2.

## 11. Estratégias de explicação no NIDS

### Decisão

- As quatro estratégias compartilham o caminho de classificação até `t2`. Depois de `t2`, o NIDS decide se o fluxo é selecionado para explicação. Conforme a estratégia, ele gera a explicação antes de entregar a classificação ou encaminha a solicitação de explicação ao processo explicador.
- O canal de saída das explicações é o arquivo `explanations.jsonl` da execução, com um registro por fluxo explicado. O registro tem o número de sequência e o `Flow ID` do fluxo, o valor de referência e as 80 contribuições, na ordem das entradas do manifesto do modelo congelado. O registro de classificação tem o mesmo formato nas quatro estratégias.
- Cada fluxo classificado registra o início e o fim da seleção. Cada fluxo explicado registra o início e o fim da chamada ao explicador, que delimitam o tempo de explicação, e `t4`.
- Nas estratégias síncronas, o NIDS escreve o registro da explicação e, em seguida, o da classificação. Uma única leitura do relógio, depois das duas escritas, vale por `t3` e `t4`.
- No modo assíncrono, a solicitação de explicação entra na fila de explicações pendentes depois de `t3`. O processo explicador retira a solicitação, gera a explicação, escreve o registro e lê `t4`. Ele também registra o instante da retirada.
- O classificador inicia o processo explicador antes de a captura abrir. O processo explicador carrega a própria cópia verificada do modelo congelado e constrói o próprio explicador. A diferença entre a leitura do relógio monotônico que ele envia quando fica pronto e a leitura do classificador ao recebê-la deve ficar entre 0 e 1 s, como na decisão 9.
- Antes de a captura abrir, o NIDS constrói o explicador e faz uma chamada de aquecimento da inferência e outra da explicação, com um vetor de zeros que não vem de nenhum conjunto de dados. Esses tempos ficam registrados à parte.

### Justificativa

- Com o mesmo caminho até `t2`, a diferença de latência entre as estratégias vem só do que cada uma faz depois da classificação. Na leitura de arquivo, o registro de classificação sai idêntico nas quatro estratégias, o que confirma que a explicação não altera a classificação.
- O protocolo define que, nas estratégias síncronas, a classificação e a explicação de um fluxo explicado ficam disponíveis juntas. A leitura única do relógio depois das duas escritas faz `t3` e `t4` coincidirem.
- Um processo separado não divide com o classificador o interpretador Python nem a CPU ([decisão 14](#14-orçamento-de-cpu-e-de-memória)). Uma thread no mesmo processo disputaria com a classificação o bloqueio global do interpretador.
- A construção do explicador ocorre uma vez por execução e não pertence à latência de nenhum fluxo. A primeira chamada de cada operação é mais lenta que as seguintes. Na medição isolada do TreeSHAP, a chamada de aquecimento da inferência do XGBoost levou 0,559 ms, contra a mediana de 0,167 ms das chamadas seguintes ([medição](../relatorios/treeshap-medicao-20261112T113136395550Z.md)).

### Consequências

- As marcações das explicações ficam em `explanations.csv`, separadas dos registros do canal de saída das explicações. Cada execução confere que cada registro de explicação corresponde a um fluxo classificado e que o valor de referência somado às contribuições reproduz a saída explicada do fluxo, nas tolerâncias de [configs/tree-shap.json](../configs/tree-shap.json).
- No modo assíncrono, a fila de explicações pendentes usa uma thread do próprio classificador para enviar as solicitações ao processo explicador. Esse envio ocorre depois de `t3` e atrasa o fluxo seguinte, que registra o atraso entre `t0` e `t1`.

## 12. Critérios de seleção do Síncrono condicional

### Decisão

- O Síncrono condicional tem dois critérios de seleção, aplicados à probabilidade de ataque que o classificador já calculou para o fluxo.
  - Pelo critério de probabilidade, o fluxo é selecionado quando a probabilidade de ataque é maior ou igual ao limiar.
  - Pelo critério de incerteza, o fluxo é selecionado quando a distância entre a probabilidade de ataque e 0,5 é menor ou igual ao limiar.
- Cada critério tem um limiar por classificador, fixado com a tabela de calibração do conjunto de validação. O comando `calibrar-selecao` produz essa tabela. Para cada limiar de uma grade, ela mostra quantos registros da validação o critério seleciona, no total, entre os ataques, entre os benignos e entre os erros de classificação.
- O limiar do critério de probabilidade é 0,5, e o do critério de incerteza é 0,4, nos dois classificadores. O critério de incerteza seleciona, então, os fluxos com probabilidade de ataque entre 0,1 e 0,9.
- Os limiares ficam em [configs/nids.json](../configs/nids.json), com a execução de calibração que os sustenta.
- O conjunto de teste não participa da calibração.

### Justificativa

- A proposta do trabalho prevê a seleção por limiares de probabilidade e de incerteza.
- Os dois critérios selecionam fluxos diferentes. Na validação, o critério de probabilidade seleciona de 23,9% a 24,1% dos 315.000 registros com limiares de 0,1 a 0,9, nos dois classificadores, e quase todos os registros selecionados são ataques. O critério de incerteza com limiar 0,4 seleciona 0,21% dos registros no Random Forest e 0,04% no XGBoost. Esses registros contêm 187 dos 204 erros de classificação do Random Forest e 15 dos 32 do XGBoost ([calibração](../relatorios/selecao-condicional-20261114T204351398308Z.md)).
- O limiar 0,5 coincide com o limiar de classificação. O critério de probabilidade explica os fluxos classificados como ataque e os de probabilidade igual a 0,5, que são classificados como benignos. Na validação, nenhum registro tem probabilidade igual a 0,5, e o critério seleciona exatamente os 75.628 registros que o Random Forest classifica como ataque e os 75.804 que o XGBoost classifica como ataque.
- Acima de 0,4, a seleção por incerteza cresce depressa no Random Forest. Com o limiar 0,45, ela passaria a 0,31% dos registros, e com 0,49, a 4,33%.
- A seleção usa a probabilidade já calculada e não chama o classificador de novo. Cada execução registra o tempo da seleção.
- A [decisão 4](#4-separação-entre-treino-validação-e-teste) reserva a validação para calibrar o critério de seleção.

## 13. Limites das filas e política de descarte

### Decisão

- A fila de saída do extrator comporta 10.000 fluxos. Um fluxo emitido com a fila cheia é descartado e contado. Os fluxos descartados são os números de sequência que não chegam ao classificador.
- A fila de explicações pendentes comporta 10.000 solicitações de explicação. Uma solicitação que encontra a fila cheia é descartada e contada. A classificação desse fluxo já foi entregue, e a explicação não é gerada.
- Na leitura de arquivo, o extrator escreve os fluxos diretamente no pipe ([decisão 9](#9-marcações-de-tempo-e-relógio-do-nids)), e a solicitação de explicação espera vaga na fila em vez de ser descartada.
- Depois do último fluxo, o classificador envia ao processo explicador a marca de fim, e o processo explicador esvazia a fila. O tempo máximo de esvaziamento é de 300 s. Passado esse tempo, o processo explicador é encerrado, e as solicitações que restaram ficam pendentes.
- Os dois limites e o tempo máximo de esvaziamento ficam em [configs/nids.json](../configs/nids.json).

### Justificativa

- Uma fila sem limite cresce enquanto o consumidor for mais lento que a chegada, até esgotar a memória. Com o limite, a falta de capacidade aparece como descarte contado, e a proporção de descartes é um dos critérios de viabilidade do [protocolo](protocolo-experimental.md) (seção 8).
- Descartar o item que chega mantém a fila na ordem de chegada e não altera as solicitações já aceitas.
- No modo assíncrono, a classificação não espera a explicação. O descarte da solicitação mantém essa propriedade quando a fila está cheia.
- Na leitura de arquivo não há captura a perder. A espera por vaga completa a execução e permite comparar as explicações das estratégias fluxo a fluxo.
- Na medição isolada, o Random Forest gera uma explicação em 7,4 ms, em média. A fila de explicações cheia leva cerca de 74 s para esvaziar, dentro do tempo máximo de 300 s. Uma linha da fila de saída do extrator tem cerca de 1 kB, e a fila cheia ocupa cerca de 10 MB do heap do extrator. Nos ensaios a 1× do trecho `validacao`, a fila de saída do extrator chegou a 392 fluxos.
- No piloto, as filas só atingiram o limite em execuções do Random Forest com 4 cópias, que já ultrapassam o limite da [decisão 19](#19-limite-da-latência-de-classificação) ([análise do piloto](../relatorios/piloto-2-20261118T101010406495Z.md)). No Síncrono total, a fila de saída do extrator descartou 23.204 fluxos, e no Assíncrono, a fila de explicações pendentes descartou 5.319 solicitações. Um limite maior trocaria esses descartes por mais latência.
- Nas execuções sem saturação, a maior fila de saída do extrator teve 769 fluxos, e a maior fila de explicações pendentes, 32 solicitações. O limite de 10.000 fica mais de 13 vezes acima da maior delas.
- Nas duas execuções do Assíncrono do piloto, o processo explicador concluiu todas as solicitações aceitas antes do tempo máximo de esvaziamento. A última explicação ficou disponível 2 ms depois da última solicitação no XGBoost ([execução](../relatorios/nids-execucao-interface-20261117T224639963550Z.md)) e 10,4 s depois no Random Forest ([execução](../relatorios/nids-execucao-interface-20261117T230929822226Z.md)), bem abaixo dos 300 s.

### Consequências

- Cada execução registra os fluxos descartados na fila de saída do extrator e as solicitações de explicação feitas, aceitas, descartadas, concluídas e pendentes. Ela confere que os fluxos emitidos somam os recebidos e os descartados e que o processo explicador retirou da fila todas as solicitações aceitas.
- O tamanho da fila de explicações pendentes ao longo da execução é reconstruído dos instantes de solicitação e de retirada, sem medição no caminho da classificação.

## 14. Orçamento de CPU e de memória

### Decisão

- O classificador roda na CPU lógica 2, o processo explicador na 0 e o extrator nas CPUs 4 a 7. As cópias do `tcpreplay-edit` ocupam as CPUs 8 a 11, uma CPU por cópia, em rodízio. A thread que lê o estado da máquina ([decisão 17](#17-estado-da-máquina-durante-os-ensaios)) fica na CPU 11. As CPUs 1 e 3 ficam sem processo do experimento.
- Todas as threads de cada processo ficam fixas nas suas CPUs. O classificador fixa as próprias threads no início da execução. O extrator e as cópias do `tcpreplay-edit` são fixados antes de começar, e o processo explicador fixa as próprias threads ao iniciar. Cada execução registra as CPUs observadas de cada processo e confere que elas são as configuradas.
- O classificador e o processo explicador usam uma thread cada, com `n_jobs=1` e `threadpool_limits(1)`.
- O heap máximo do extrator é de 4.096 MiB.
- A JVM do extrator roda com `-Dnio.mx=1073741824`, `-Dnio.ms=1073741824` e `-XX:+ExplicitGCInvokesConcurrent` ([configs/nids.json](../configs/nids.json)). As duas primeiras opções sobem de 64 MiB para 1 GiB os limites da memória nativa da jNetPcap. A terceira faz cada chamada de `System.gc()` iniciar uma coleta concorrente, sem parar a JVM.
- Cada execução registra o tempo de CPU e o pico de memória residente de cada processo, em separado, e a memória disponível na máquina no início. O classificador é medido do início ao fim da captura, sem a carga do modelo nem as verificações feitas depois. O processo explicador é medido do fim da carga do modelo ao fim do atendimento das solicitações. O extrator é medido do início ao fim do processo.

### Justificativa

- O processador da máquina, um Intel Core i5-1334U, tem dois núcleos de desempenho, nas CPUs lógicas 0 a 3, e oito núcleos de eficiência, nas CPUs 4 a 11 (`/sys/devices/cpu_core/cpus` e `/sys/devices/cpu_atom/cpus`). As CPUs 0 e 1 pertencem ao mesmo núcleo físico, assim como as CPUs 2 e 3.
- O classificador e o processo explicador ficam em núcleos de desempenho diferentes, com as CPUs irmãs vazias. Assim, o processo explicador não toma CPU do classificador, e nenhum dos dois divide um núcleo físico. A medição isolada do TreeSHAP também usou a CPU 2.
- O extrator usa pouca CPU na captura em velocidade original. No ensaio do trecho `validacao` com o Random Forest, ele usou 231 s de CPU em 2.188 s de reprodução. Quatro núcleos de eficiência comportam o extrator e as threads da JVM.
- As cópias do `tcpreplay-edit` ficam fora das CPUs do NIDS para que o envio dos pacotes não dispute CPU com a captura e a classificação.
- O pico de memória do classificador inclui a carga do modelo e as verificações feitas depois da captura, que crescem com o número de fluxos. Zerar o pico no início da captura (`/proc/self/clear_refs`) e lê-lo no fim deixa só a memória da classificação.
- Sem limite explícito, a JVM 17 reserva para o heap até 25% da memória física, 3.792 MiB nesta máquina. O limite fixo torna o extrator independente da memória da máquina. Nos ensaios do trecho `validacao`, o pico de memória residente do extrator foi de 2.119 MiB.
- A jNetPcap copia cada pacote lido para a memória nativa (`new PcapPacket(hdr, buf)`, em `PacketReader`) e libera a cópia quando o coletor de lixo descarta o objeto Java correspondente. Quando a memória nativa ocupada passa do limite brando, ela chama `System.gc()`. Quando passa do limite máximo, ela chama `System.gc()` e espera a liberação por até 15 s (`DisposableGC`, `OUT_OF_MEMORY_TIMEOUT`). Com os limites padrão, de 64 MiB, cada chamada faz o G1 da JVM 17 parar o extrator inteiro, inclusive a leitura dos pacotes.
- Lendo o trecho `campanha` do arquivo nas CPUs do extrator, a JVM sem as três opções fez 123 pausas completas, que somaram 36,4 s, e a leitura levou 78 s. Com as opções, ela não fez pausa completa, as pausas somaram 0,9 s, a maior durou 52 ms, e a leitura levou 27 s. Os 24.413 fluxos emitidos foram idênticos nas duas leituras.
- Sem as opções, o extrator chegou a ficar 15 s sem ler pacotes na rede emulada, e o buffer de captura, de 256 MiB, transbordava a partir de 2 cópias do trecho. Com as opções, as execuções do XGBoost sem explicação com 2 e 4 cópias não perderam pacotes, e cada cópia casou fluxo a fluxo com a leitura do arquivo ([2 cópias](../relatorios/nids-validacao-20261117T151302791243Z.md), [4 cópias](../relatorios/nids-validacao-20261117T151328708255Z.md)).

### Consequências

- O modo assíncrono usa um núcleo de desempenho a mais que as outras estratégias. A comparação entre as estratégias registra a CPU usada por cada processo.
- Os núcleos de eficiência são mais lentos que os de desempenho. Um atraso do extrator aparece nos descartes do libpcap, que cada execução registra.
- O extrator pode ocupar até 1 GiB de memória nativa além do heap.
- O gerador de fluxos guarda os pacotes de cada fluxo e mantém cada fluxo emitido até chegar outro pacote com a mesma chave. Por isso, o heap ocupado cresce com o número de cópias. Com 4 cópias, ele terminou em 3.696 MiB depois da última coleta, de 4.096 MiB. Com mais cópias, o heap se esgota, e as pausas do coletor voltam a parar a leitura dos pacotes. A carga fica limitada a 4 cópias ([decisão 15](#15-carga-por-sobreposição-de-cópias)).

## 15. Carga por sobreposição de cópias

### Decisão

- O nível de carga de uma execução é o número de cópias do trecho que o host h1 envia ao mesmo tempo, todas na velocidade original e iniciadas juntas.
- A cópia 1 é o trecho sem alteração. Cada cópia seguinte troca cada endereço IPv4 do trecho por um endereço reservado a ela no bloco 100.64.0.0/10, com 4.096 endereços por cópia, e mantém o restante de cada pacote. A troca usa a opção `--pnat` do `tcpreplay-edit`, com um par /32 por endereço do trecho ([src/core/traffic_copies.py](../src/core/traffic_copies.py)).
- A lista dos endereços IPv4 do trecho, ordenada pelo número de pacotes, fica no manifesto do trecho. A posição de cada endereço na lista define o endereço que o substitui em cada cópia.
- Cada cópia é um processo do `tcpreplay-edit`, com `--no-flow-stats`, fixo numa das CPUs de reprodução ([decisão 14](#14-orçamento-de-cpu-e-de-memória)).
- A validação de uma execução atribui cada fluxo à cópia dos seus endereços, volta os endereços aos originais e compara cada cópia com a leitura do trecho do arquivo. Os fluxos que o extrator forma de quadros que não são IPv4 ficam sem cópia e fora da comparação.
- Antes do piloto, uma cópia gravada pelo `tcprewrite`, com a mesma troca e a mesma biblioteca de edição, é lida do arquivo e comparada fluxo a fluxo com o trecho original (`nids-conferir-copia`).
- O piloto e a campanha usam três níveis de carga, de 1, 2 e 4 cópias.

### Justificativa

- Acelerar a reprodução encurta os intervalos entre pacotes. Os atributos temporais mudam, e os tempos limite do extrator passam a formar outros fluxos, então as previsões e a seleção do Síncrono condicional deixam de ser comparáveis entre as cargas. Lido com os intervalos entre pacotes divididos por 2, o trecho `campanha` forma 22.993 fluxos, contra 24.413 na leitura original. Dos 22.992 fluxos casados, 1.867 mudam a contagem, o tamanho ou as flags, e só 8 mantêm os atributos temporais. A seleção do Random Forest pelo critério de incerteza passa de 32 para 757 fluxos, e, com os intervalos divididos por 8, para 1.147 ([medição](../relatorios/nids-aceleracao-20261116T102343628819Z.md)).
- Com as cópias, cada fluxo de cada cópia tem as mesmas entradas do fluxo correspondente do trecho, e a carga cresce sem mudar o que o classificador recebe. Lida do arquivo, a cópia 16 do trecho `campanha` produziu os 24.413 fluxos do trecho, com as 80 entradas e as previsões idênticas ([conferência](../relatorios/nids-copia-20261115T193223330810Z.md)). Na rede emulada, com 2 cópias do trecho `curto`, cada cópia casou fluxo a fluxo com a leitura do arquivo, sem fluxo de um lado só ([validação](../relatorios/nids-validacao-20261116T102237656054Z.md)).
- A opção `--seed` do `tcpreplay` troca os endereços por `(ip ^ semente) - (ip & semente)` (`randomize_ipv4_addr`, em `edit_packet.c`). Essa conta leva endereços diferentes ao mesmo endereço, e fluxos de cópias diferentes se juntariam.
- O bloco 100.64.0.0/10 é reservado ao endereçamento compartilhado de provedores (RFC 6598) e não aparece no trecho. A preparação confere isso. O bloco comporta 1.024 cópias de 4.096 endereços, e o trecho `campanha` tem 1.661 endereços IPv4.
- O `tcpreplay-edit` percorre os pares em ordem a cada pacote. Com a lista ordenada pelo número de pacotes, os endereços mais frequentes são encontrados primeiro.
- Sem `--no-flow-stats`, o `tcpreplay` mantém uma tabela de fluxos própria a cada pacote, só para o relatório, e avisa em cada quadro que não consegue decodificar.
- Até 4 cópias, o NIDS captura o trecho sem perder pacotes. Acima disso, o heap do extrator se esgota ([decisão 14](#14-orçamento-de-cpu-e-de-memória)).
- O Random Forest satura dentro desses níveis. No Síncrono total, ele classifica cerca de 84 fluxos por segundo. Com 2 cópias do trecho `campanha`, o extrator emite até 508 fluxos num segundo, e 186 segundos passam de 84 fluxos.
- Uma explicação do XGBoost custa 0,43 ms em média, contra 7,4 ms no Random Forest ([medição](../relatorios/treeshap-medicao-20261112T113136395550Z.md)). Com até 4 cópias, o XGBoost deve atender o tráfego em todas as estratégias. A campanha mede o custo do TreeSHAP no XGBoost abaixo da saturação, e não o ponto em que ele satura.

### Consequências

- As cópias começam juntas, e as rajadas de emissão de fluxos coincidem. O pico de carga cresce na mesma proporção da média.
- Os quadros que não são IPv4, como o ARP, e os pacotes IPv6 chegam uma vez por cópia, sem troca. O extrator junta os quadros ARP de todas as cópias nos mesmos fluxos, 10 dos 24.413 fluxos do trecho `campanha`, e não forma fluxos IPv6.

## 16. Tráfego do piloto e da campanha

### Decisão

- O piloto e a campanha reproduzem o trecho `campanha`, da captura de terça-feira de 12:10:00 a 12:30:00 UTC, cortado do trecho `validacao` da [decisão 10](#10-tráfego-de-entrada-e-emulação-da-rede) sem alterar bytes nem instantes ([configs/pcap-campanha.json](../configs/pcap-campanha.json)).
- O corte grava um manifesto próprio, com o PCAP, a tabela de referência, as conexões que já tinham pacotes antes do início e a lista de endereços IPv4 do trecho. A tabela de referência tem os fluxos de `tuesday.csv` que começam dentro do trecho.
- Os fluxos das conexões anteriores ao início ficam fora da equivalência com `tuesday.csv` e da conferência da leitura por arquivo, e cada conferência os conta. Eles continuam na carga e na classificação.
- O trecho `curto`, de 12:10:00 a 12:15:00 UTC, serve aos ensaios de conferência das cópias, fora do piloto e da campanha ([configs/pcap-curto.json](../configs/pcap-curto.json)).

### Justificativa

- A terça-feira tem cerca de 8 h de tráfego. Com 70 a 90 execuções, um dia inteiro por execução ocuparia a máquina por semanas.
- Os 20 minutos do trecho `campanha` têm 3.706.151 pacotes, 94% dos pacotes do trecho `validacao`, que começa no início da captura. Eles também têm todos os 689 fluxos de ataque do trecho `validacao`, de FTP-Patator, e os 12 fluxos de FTP-Patator - Attempted, benignos pela [decisão 1](#1-alvo-de-classificação-e-rótulos). Cada execução leva cerca de 25 min.
- Um trecho que começa no meio da captura tem conexões em andamento. O primeiro fluxo de cada uma começa no meio da conexão, e os seguintes herdam outro sentido e outra duração acumulada ([decisão 8](#8-emissão-dos-fluxos-no-nids)), então não correspondem aos fluxos do CSV. No trecho `campanha`, são 1.582 conexões e 3.024 dos 24.413 fluxos do NIDS.
- As conexões anteriores ao início vêm dos pacotes IPv4 lidos antes de 12:10:00 e dos fluxos do CSV anteriores a esse instante. O extrator também forma fluxos de quadros que não são IPv4, com endereços tirados de outros campos, como o fluxo `8.6.0.1-8.0.6.4` dos quadros ARP, e só o CSV mostra que esses fluxos já existiam antes do início.
- Fora da borda e das conexões anteriores ao início, os 19.438 fluxos extraídos do trecho `campanha` têm as 80 entradas iguais às do CSV, e os 11 que só a extração tem têm algum `NaN` ([conferência](../relatorios/extracao-pcap-20261115T192306992011Z.md)).

## 17. Estado da máquina durante os ensaios

### Decisão

- Antes de cada ensaio na rede emulada, o script de emulação confere, numa janela de 10 s, se a máquina está na tomada, se a ocupação média das CPUs fica em até 25% e se há pelo menos 3.072 MiB de memória disponível. Sem isso, ele repete a conferência a cada 30 s por até 10 min. Se a máquina não ficar pronta, o ensaio não começa e fica registrado como não iniciado. O executor da matriz põe esse ensaio no fim da fila, sem gastar tentativa, e segue até o horário de parada.
- A ocupação da CPU durante o ensaio não interrompe nem invalida o ensaio. Ela fica registrada, e a análise mostra se algum ensaio sofreu interferência.
- Durante o ensaio, uma thread do script, fixa na CPU 11, grava a cada segundo a fonte de energia, a frequência e as contagens de limitação térmica de cada CPU, a ocupação de cada CPU, a memória disponível e o swap livre, no arquivo `machine.jsonl` da execução.
- Cada ensaio registra o commit do repositório e os arquivos versionados com alterações.
- O executor da matriz impede a suspensão da máquina com o `systemd-inhibit`, inclusive com a tampa fechada.
- O piloto e a campanha rodam com o perfil de energia `power-saver` do `power-profiles-daemon`.
- Os limites da conferência ficam na configuração de cada matriz ([configs/piloto-2.json](../configs/piloto-2.json)). O piloto confirma ou ajusta esses valores.

### Justificativa

- Em ensaios do trecho `validacao` com o notebook na bateria e em uso, a mediana do tempo de inferência do Random Forest subiu de 3,6 ms para 9,1 ms no Síncrono condicional e de 4,3 ms para 11,5 ms no Assíncrono, contra os mesmos ensaios repetidos na tomada e com a máquina ociosa.
- O registro de cada segundo mostra depois se a frequência caiu, se houve limitação térmica ou se outro programa ocupou as CPUs irmãs do classificador e do processo explicador.
- A ocupação da máquina sem os ensaios varia com os serviços em segundo plano. Com o navegador e os containers de outros projetos abertos, ela ficou em 12% e 19% em duas janelas de 10 s. Um limite de 10% deixaria ensaios sem começar por oscilações do segundo plano, e o de 25% ainda barra o uso ativo da máquina por outro trabalho.
- O perfil de energia muda a frequência das CPUs e, com ela, o tempo de inferência e a carga em que o classificador satura. Os limites das decisões [13](#13-limites-das-filas-e-política-de-descarte), [19](#19-limite-da-latência-de-classificação) e [20](#20-limiar-de-fluxos-descartados) vieram de execuções nesse perfil. O perfil gravado em `/var/lib/power-profiles-daemon/state.ini` é `power-saver` e não muda desde 10 de setembro de 2026, antes do piloto. As execuções não registram o perfil.

## 18. Número de repetições

### Decisão

- Cada combinação de classificador, configuração de explicação e nível de carga tem 3 repetições na campanha. Com 2 classificadores, 5 configurações de explicação e 3 níveis de carga, a campanha tem 90 execuções.

### Justificativa

- No piloto, três repetições do Random Forest no Sem XAI com 1 cópia e no Síncrono total com 2 cópias tiveram amplitude, relativa à mediana, de 3,3% e 4,1% na média do tempo de inferência, de 11,9% e 16,9% no p95 da latência de classificação e de 26,2% e 15,3% no p99 ([análise do piloto](../relatorios/piloto-2-20261118T101010406495Z.md)).
- Essa variação é pequena perto da diferença entre estratégias. No mesmo piloto, o p95 da latência de classificação do XGBoost com 4 cópias foi de 54 ms no Sem XAI e de 714 ms no Síncrono total.
- Cada execução do piloto levou cerca de 23 min, e as 90 execuções somam cerca de 34 h.

## 19. Limite da latência de classificação

### Decisão

- Pelo critério de latência da viabilidade, a latência de classificação de uma execução não ultrapassa 1 s no p95 nem 2 s no p99.

### Justificativa

- No piloto, as execuções se dividiram em dois grupos ([análise do piloto](../relatorios/piloto-2-20261118T101010406495Z.md)). Nas que não saturaram, o p99 da latência de classificação ficou em até 1,3 s. São as do XGBoost com 4 cópias, em todas as estratégias, e as do Random Forest no Sem XAI com 1 cópia. Nas saturadas, o p95 passou de 29 s, e a fila de saída do extrator passou de 2.600 fluxos. São as do Random Forest no Síncrono total a partir de 2 cópias e as do Random Forest em todas as estratégias com 4 cópias.
- Os limites de 1 s e 2 s ficam entre os dois grupos e são os menores valores inteiros, em segundos, que mantêm viáveis todas as execuções sem saturação. Entre elas, a de maior latência foi a do XGBoost no Síncrono total com 4 cópias, com p95 de 714 ms e p99 de 1,3 s.

## 20. Limiar de fluxos descartados

### Decisão

- Pelo critério de descartes da viabilidade, a proporção de fluxos descartados na fila de saída do extrator é 0%. Uma estratégia só é viável sob uma carga se o NIDS classifica todos os fluxos da execução.

### Justificativa

- No piloto, só a execução do Random Forest no Síncrono total com 4 cópias descartou fluxos, 23.204, ou 23,8% ([análise do piloto](../relatorios/piloto-2-20261118T101010406495Z.md)). Ela também ultrapassou o limite da [decisão 19](#19-limite-da-latência-de-classificação), com p95 de 200 s. Todas as outras execuções descartaram 0%, então uma tolerância maior não mudaria a viabilidade de nenhuma delas.

## 21. Configurações de explicação da campanha

### Decisão

- A matriz da campanha tem cinco configurações de explicação, Sem XAI, Síncrono total, Síncrono condicional pelo critério de probabilidade, Síncrono condicional pelo critério de incerteza e Assíncrono. Os dois critérios do Síncrono condicional usam os limiares da [decisão 12](#12-critérios-de-seleção-do-síncrono-condicional).
- A viabilidade é julgada para cada configuração de explicação, e cada resultado de viabilidade é reportado com a cobertura explicativa da execução.

### Justificativa

- As configurações vão de cobertura explicativa total a quase nula. No piloto, com 4 cópias, o Síncrono total e o Assíncrono do XGBoost explicaram 100% dos fluxos, o critério de probabilidade explicou 2,8%, e o de incerteza, 0,1% ([análise do piloto](../relatorios/piloto-2-20261118T101010406495Z.md)).
- O critério de incerteza seleciona os fluxos em que o classificador está em dúvida, e esses fluxos concentram os erros de classificação. Na validação, ele selecionou 0,21% dos registros no Random Forest, com 187 dos 204 erros, e 0,04% no XGBoost, com 15 dos 32 erros ([decisão 12](#12-critérios-de-seleção-do-síncrono-condicional)).
- Os critérios de viabilidade da seção 8 do [protocolo](protocolo-experimental.md) não incluem a cobertura. Uma configuração que explica poucos fluxos atende a eles com pouco custo, então só a viabilidade com a cobertura ao lado compara as configurações.
- Com 4 cópias, o critério de incerteza explicou 117 fluxos no XGBoost e 133 no Random Forest. Com 1 cópia, a expectativa é de cerca de um quarto disso, e o p99 da latência de explicação fica perto do maior valor da amostra. Cada execução registra o número de fluxos explicados.

## 22. Validade das execuções e número de tentativas

### Decisão

- Uma execução do piloto ou da campanha é válida quando termina sem erro, o NIDS passa nas próprias verificações, o `tcpreplay-edit` envia todos os pacotes e a máquina fica na tomada do início ao fim.
- Os descartes de fluxos e de solicitações de explicação, as solicitações pendentes, os pacotes perdidos na captura e a ocupação das CPUs durante a execução não invalidam uma execução.
- A validação por cópia de uma execução com pacotes perdidos na captura reprova, porque exige que nenhum pacote se perca na captura e que o extrator leia todos os pacotes recebidos pela interface. A auditoria registra essa reprovação como explicada pela perda quando nenhuma outra verificação da validação falha e os pacotes lidos pelo extrator, somados aos perdidos no buffer de captura, fecham com os recebidos pela interface.
- Cada combinação de classificador, configuração de explicação, nível de carga e repetição tem no máximo 2 tentativas. Uma execução inválida fica registrada com o motivo, e a nova tentativa é outra execução. A combinação com 2 tentativas inválidas fica registrada como esgotada.
- O número máximo de tentativas fica no campo `max_attempts` da configuração de cada matriz.

### Justificativa

- Os critérios de validade detectam falhas da execução, da geração do tráfego e da máquina. Os descartes e as pendências são resultados da carga, e a ocupação das CPUs fica registrada e aparece na análise ([decisão 17](#17-estado-da-máquina-durante-os-ensaios)).
- No piloto, as 16 execuções foram válidas na primeira tentativa ([análise do piloto](../relatorios/piloto-2-20261118T101010406495Z.md)). A segunda tentativa cobre uma falha isolada. Uma combinação que falha duas vezes indica um problema que a auditoria precisa mostrar.
- Na campanha, a execução do XGBoost no Síncrono condicional pelo critério de probabilidade com 4 cópias, repetição 1, perdeu na captura 10.231 dos 14.824.604 pacotes, 0,07%. Dos 88.767 fluxos casados com a leitura por arquivo, 1.042 (1,2%) ficaram com entradas diferentes, e 20 tiveram previsão diferente ([auditoria](../relatorios/campanha-auditoria-20261120T125714303006Z.md)). Nas outras 14 execuções do XGBoost com 4 cópias, sem perda na captura, de 4 a 10 fluxos tiveram previsão diferente ([análise da campanha](../relatorios/campanha-20261120T120722710408Z.md)). A perda fica registrada na execução e aparece na auditoria, como os descartes nas filas.
