# Ambiente Python (TG-005)

Ambiente virtual isolado para os exercícios de Machine Learning (TG-006, TG-007) antes de trabalhar com os CSVs do CIC-IDS2017.

## Recriar o ambiente e executar o exemplo

A partir de `src/`:

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Saída esperada:

```
scikit-learn 1.9.1
Exemplo carregado: Iris, 150 amostras, 4 atributos, classes ['setosa', 'versicolor', 'virginica']
```

## Versões instaladas

Geradas com `pip freeze` em 2026-11-10, Python 3.12.3. Ver [requirements.txt](requirements.txt).

| Biblioteca | Versão |
| --- | --- |
| scikit-learn | 1.9.1 |
| numpy | 2.5.4 |
| scipy | 1.18.1 |
| joblib | 1.6.0 |
| threadpoolctl | 3.8.0 |
| cloudpickle | 3.1.2 |
| narwhals | 2.28.0 |

`numpy`, `scipy`, `joblib`, `threadpoolctl`, `cloudpickle` e `narwhals` são dependências do scikit-learn, não instaladas diretamente.

## `main.py`

Importa o scikit-learn e carrega o conjunto Iris (`sklearn.datasets.load_iris`), sem treinar nenhum modelo — isso é tarefa da TG-006.

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
