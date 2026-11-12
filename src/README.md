# Ambiente Python (TG-005)

Ambiente virtual para os exercícios de aprendizado de máquina, a preparação dos dados e o treinamento dos classificadores.

## Recriar o ambiente e executar o exemplo

A partir de `src/`:

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py verificar-ambiente
```

Saída esperada:

```
scikit-learn 1.9.1
Exemplo carregado: Iris, 150 amostras, 4 atributos, classes ['setosa', 'versicolor', 'virginica']
```

## Versões instaladas

Geradas com `pip freeze` em 2026-11-12, Python 3.12.3. Ver [requirements.txt](requirements.txt).

| Biblioteca | Versão |
| --- | --- |
| scikit-learn | 1.9.1 |
| numpy | 2.5.4 |
| scipy | 1.18.1 |
| joblib | 1.6.0 |
| threadpoolctl | 3.8.0 |
| cloudpickle | 3.1.2 |
| narwhals | 2.28.0 |
| xgboost-cpu | 3.4.1 |
| shap | 0.54.1 |
| matplotlib | 3.11.2 |

`scikit-learn`, `xgboost-cpu`, `shap` e `matplotlib` são instaladas diretamente. As demais bibliotecas do [requirements.txt](requirements.txt) são dependências delas e ficam fixadas para reproduzir o ambiente inteiro. As versões de `numpy`, `scipy`, `scikit-learn`, `joblib` e `xgboost-cpu` são as exigidas pelos modelos congelados.

## `main.py`

Ponto de entrada dos comandos do projeto. `python main.py verificar-ambiente` importa o scikit-learn e carrega o conjunto Iris (`sklearn.datasets.load_iris`), sem treinar nenhum modelo.

## Preparação dos dados

```bash
python main.py preparar-dados
```

O comando lê os cinco CSVs de `cicids-dataset/`, aplica as decisões 1 a 4 de [docs/decisoes.md](../docs/decisoes.md) e grava em `derived-data/` os conjuntos de treino, validação e teste. Os CSVs originais não são alterados, e o comando falha se algum deles mudar durante a execução.

Cada conjunto tem três arquivos:

| Arquivo | Conteúdo | Tipo |
| --- | --- | --- |
| `X_<conjunto>.npy` | As 80 entradas do classificador, na ordem de [docs/dicionario-atributos.md](../docs/dicionario-atributos.md). | `float64` |
| `y_<conjunto>.npy` | O rótulo binário: 0 para benigno e 1 para ataque. | `int8` |
| `origin_<conjunto>.npy` | O índice do arquivo original, o `id` do registro e o índice do rótulo original. | `int64` |

O `manifest.json` registra os hashes dos CSVs e dos arquivos gerados, a configuração, os nomes das entradas, o mapa dos rótulos originais, as contagens de cada conjunto e o resultado das verificações de independência. Os `.npy` ficam fora do git; o manifesto é versionado.

A execução leva cerca de 2,5 minutos e usa cerca de 2,5 GB de memória. Duas execuções seguidas produzem arquivos idênticos.

## Modelos congelados e inferência

```bash
python main.py congelar-modelos
```

O comando lê [configs/model-freezing.json](../configs/model-freezing.json) e reúne os dois modelos finais em um novo diretório de `training-runs/frozen-models/`. Cada modelo é carregado em um processo Python novo, que compara todas as classificações do teste com as previsões salvas durante a avaliação final. O comando só registra sucesso quando todas as classes coincidem. Também compara as probabilidades com tolerância absoluta de `1e-12` e tolerância relativa zero. Essa tolerância numérica não permite divergências nas classes.

Cada pacote contém `model.joblib`, `manifest.json`, a cópia do manifesto dos dados, os registros de seleção e treinamento, as dependências fixadas em `requirements.txt` e as previsões de referência. O XGBoost também inclui `model.ubj` e `booster-config.json`. O manifesto registra os parâmetros, a ordem dos atributos, o processamento das entradas, as versões e os hashes SHA-256 dos arquivos. O carregamento verifica a integridade dos arquivos e a compatibilidade das versões antes de usar o modelo. `verification.json` registra o processo e o resultado da comparação; o `report.json` na raiz da execução reúne os dois resultados.

Os pacotes verificados estão em [training-runs/frozen-models/20261111T181031847482Z/](../training-runs/frozen-models/20261111T181031847482Z/). Para repetir a verificação do Random Forest a partir de `src/`:

```bash
python main.py verificar-modelo --artifact ../training-runs/frozen-models/20261111T181031847482Z/random-forest
```

Para classificar um fluxo, forneça um objeto JSON com exatamente os 80 nomes de atributos do manifesto e seus valores numéricos. A ordem das chaves no JSON é livre; o carregador monta a entrada na ordem exigida pelo modelo. A representação é `float64`, sem normalização. O valor infinito positivo em `Flow Bytes/s` e `Flow Packets/s` é substituído por `-1`, como na preparação do treino. No JSON, esse valor pode ser representado pela string `"inf"`. Valores ausentes, atributos adicionais e outros valores não finitos são rejeitados. Rótulos, metadados e os dois atributos de comprimento de cabeçalho ficam fora dessa entrada.

O arquivo `example-flow.json` contém os atributos do primeiro registro do teste, cuja origem e previsão constam em `verification.json`. Execute:

```bash
python main.py classificar-fluxo --artifact ../training-runs/frozen-models/20261111T181031847482Z/random-forest --input ../training-runs/frozen-models/20261111T181031847482Z/random-forest/example-flow.json
```

Substitua `random-forest` por `xgboost` nos caminhos para usar o segundo modelo. A resposta contém `prediction` (0 ou 1), `class` (`benign` ou `attack`) e `attack_probability`. A classe é ataque quando a probabilidade é maior que 0,5; o empate é benigno. A inferência individual depende do pacote salvo e do JSON de entrada. A verificação completa também depende de `X_test.npy` e `origin_test.npy` em `derived-data/`, ou no diretório informado por `--data-dir`.

Os arquivos binários `.joblib`, `.ubj` e `.npy` ficam fora do Git e precisam acompanhar os manifestos para usar os pacotes em outro ambiente. O [relatório de verificação](../relatorios/model-freezing-20261111T181031847482Z.md) registra os resultados e os hashes dos modelos.

## Explicações TreeSHAP

Os três comandos abaixo leem [configs/tree-shap.json](../configs/tree-shap.json). O explicador segue a [decisão 7](../docs/decisoes.md): TreeSHAP path-dependent, sem conjunto de referência e sem aproximação. O adaptador em `core/tree_explainer.py` é o único módulo que importa o `shap` e recusa qualquer outra configuração. As explicações usam somente o conjunto de validação; o carregamento recusa o teste.

```bash
python main.py explicar-exemplo
```

Explica um registro da validação com o Random Forest piloto. O registro é o Portscan classificado como ataque com a probabilidade de ataque mediana. O comando grava uma nota e uma figura em `relatorios/treeshap-exemplo-<execução>.md` e `.png`, identificadas como exercício de aprendizado, e o registro da execução em `training-runs/tree-shap/exemplo/`.

```bash
python main.py validar-treeshap
```

Explica uma amostra de 10.000 registros da validação, estratificada pelos rótulos originais, com os dois modelos congelados. Confere a ordem dos atributos, a classe explicada, a identidade `valor de referência + soma das contribuições = saída explicada`, a contribuição zero dos atributos sem divisão e, no XGBoost, o valor de referência. As tolerâncias estão na configuração. O comando grava o resultado de cada verificação em `training-runs/tree-shap/validacao/` e em `relatorios/treeshap-validacao-<execução>.md`, e termina com erro quando alguma verificação é reprovada.

```bash
python main.py medir-treeshap --validacao ../training-runs/tree-shap/validacao/<execução aprovada>
```

Mede o tempo de inferência e o tempo de explicação de 1.000 fluxos da amostra validada, em lotes de 1, 10, 100 e 1.000 fluxos. Cada classificador roda em cinco processos Python novos, fixos na CPU lógica 2, com uma thread. O comando só aceita uma execução de `validar-treeshap` aprovada com a mesma configuração e as mesmas versões, e exige a máquina ligada à tomada. `medir-treeshap-processo` é o comando interno que executa cada repetição. Os tempos de cada chamada ficam em `training-runs/tree-shap/medicao/`, e o resumo, em `relatorios/treeshap-medicao-<execução>.md`. Esses tempos não são latência de classificação nem latência de explicação.

## Primeiro treinamento do Random Forest

```bash
python main.py treinar-rf-piloto
```

O comando extrai uma amostra de 100 mil registros do conjunto de treino, preserva os 27 rótulos originais na amostra e avalia o modelo no conjunto completo de validação. A configuração está em [configs/random-forest-pilot.json](../configs/random-forest-pilot.json). As 100 árvores têm profundidade máxima de 12 e usam dois trabalhadores. Essa configuração serve à avaliação inicial e ainda será comparada a outras.

Cada execução cria um diretório em `training-runs/random-forest-pilot/`. O arquivo `model.joblib` contém o modelo, a ordem das 80 entradas e o mapa das classes. `report.json` registra a configuração completa, as métricas de validação, o tempo de ajuste, o pico de memória do processo, as versões e os hashes dos dados e dos artefatos.

`sample_indices.npy` guarda as posições usadas em `X_train.npy`; `sample_origin.npy` guarda o arquivo de origem, o `id` e o rótulo original dos registros da amostra. `validation_predictions.npy` e `validation_attack_probability.npy` guardam as previsões e as probabilidades de ataque na ordem dos registros da validação. Os arquivos `.npy` e `.joblib` ficam fora do Git.

O relatório legível é gravado em `relatorios/random-forest-pilot-<execução>.md`. A avaliação inicial usa apenas treino e validação; o conjunto de teste fica reservado para a avaliação final.

## Comparação e avaliação final do Random Forest

```bash
python main.py comparar-rf
```

O comando reutiliza a amostra e o resultado do primeiro treinamento e treina somente duas alternativas. A configuração está em [configs/random-forest-comparison.json](../configs/random-forest-comparison.json). O critério é o maior F1 na validação; empates favorecem menos nós e, depois, menos árvores.

A configuração escolhida é treinada com todos os registros do conjunto de treino. O comando grava `selection.json`, salva o modelo final e registra seus parâmetros em `fixed-before-test.json` antes de abrir o teste reservado. Os resultados do teste não alteram a seleção.

Cada execução cria um diretório em `training-runs/random-forest-comparison/`. O modelo fica em `final/model.joblib`, acompanhado das previsões e probabilidades de validação e teste. `report.json` registra métricas, contagens por rótulo original, complexidade das árvores, versões e hashes. O relatório legível fica em `relatorios/random-forest-comparison-<execução>.md`.

A reprodução exige os dados derivados e os arquivos da execução de referência indicados na configuração. Se o primeiro treinamento for refeito, atualize `reference_run` com o diretório gerado.

## Treinamento e avaliação do XGBoost

```bash
python main.py treinar-xgboost
```

O comando compara três configurações na mesma amostra usada pelo Random Forest, usando apenas treino e validação para escolher o maior F1. A configuração está em [configs/xgboost-comparison.json](../configs/xgboost-comparison.json). Somente a escolhida recebe treinamento com todos os 1.469.983 registros do treino. Os parâmetros e o modelo são salvos antes da abertura do teste reservado.

O XGBoost soma os escores das árvores e transforma essa soma, acrescida do escore inicial, em uma probabilidade. O relatório inclui um exemplo que compara o escore com a probabilidade de ataque. A [documentação oficial sobre árvores impulsionadas](https://xgboost.readthedocs.io/en/stable/tutorials/model.html) descreve essa forma de previsão.

Os artefatos ficam em `training-runs/xgboost-comparison/`. O modelo final é salvo em `final/model.joblib` e no formato nativo `final/model.ubj`. `final/booster-config.json` registra a configuração efetiva da biblioteca; `report.json` registra os parâmetros escolhidos, os atributos, as métricas, os hashes e as versões. O relatório legível fica em `relatorios/xgboost-comparison-<execução>.md`.

O ambiente usa o pacote `xgboost-cpu`, destinado ao processamento em CPU, conforme o [guia oficial de instalação](https://xgboost.readthedocs.io/en/stable/install.html#minimal-installation-cpu-only). O treinamento usa o método de histogramas e dois trabalhadores. Não há parada antecipada nem busca extensa de configurações.

## Testes

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Os testes cobrem as regras da preparação dos dados, a amostragem para o treinamento e o cálculo das métricas. Os testes do TreeSHAP usam um Random Forest e um XGBoost sintéticos e comparam as contribuições com o valor de Shapley calculado por força bruta, além da identidade da soma, dos atributos sem divisão e das recusas do adaptador. Os testes de integração verificam arquivos pequenos e o salvamento e carregamento do Random Forest em um diretório temporário.

## TG-006: árvore de decisão e Random Forest no Iris

```bash
python tg006_arvore_random_forest.py
```

Separa treino/teste (70/30, estratificado, semente 42), treina `DecisionTreeClassifier` (profundidade 3) e `RandomForestClassifier` (100 árvores), executa `predict`/`predict_proba` no teste e imprime a árvore rasa em texto (`export_text`). Notas sobre o exercício em [tg006_notas.md](tg006_notas.md).

## TG-007: métricas de erro e vazamento de dados

```bash
python tg007_metricas_erros.py   # matriz de confusão, precisão/recall/F1/FPR/ROC, um FP e um FN concretos
python tg007_vazamento.py        # vazamento por duplicatas: divisão ingênua vs. por grupo
```

Notas e interpretação dos resultados em [tg007_notas.md](tg007_notas.md), incluindo a ligação direta com os 22.109 registros duplicados já documentados em [relatorios/inspecao-cicids2017.md](../relatorios/inspecao-cicids2017.md).
