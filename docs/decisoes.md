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
- As métricas de detecção vêm do conjunto de teste. A campanha reproduz capturas de dias inteiros, que incluem fluxos do treino, e mede latência e uso de recursos.

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
