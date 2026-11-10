# TG-006: notas sobre o exercício

## Atributos e rótulo

No Iris, `X` são os atributos: quatro medidas numéricas da flor (comprimento e largura da sépala e da pétala). `y` é o rótulo: a espécie (0, 1 ou 2), o que o modelo deve prever. `X` descreve a amostra; `y` é a resposta que falta quando o modelo é usado em produção.

## Criar o modelo vs. treinar vs. usar o modelo treinado

Essas são três etapas distintas, não sinônimos:

- **Criar o modelo** (`DecisionTreeClassifier(max_depth=3)`, `RandomForestClassifier(n_estimators=100)`) só define os hiperparâmetros: que tipo de modelo, quão complexo. O objeto criado ainda não aprendeu nada dos dados; não tem regras de decisão nem valores internos ajustados.
- **Treinar** (`fit(X_train, y_train)`) é a etapa em que o algoritmo aprende, a partir dos dados de treino, os valores internos do modelo: os limiares de corte em cada nó da árvore (ex.: `petal length <= 2.45`) ou, no caso do Random Forest, a estrutura de cada uma das 100 árvores do conjunto. É só depois do `fit` que o modelo passa a ter uma regra de decisão concreta.
- **Usar o modelo treinado** (`predict(X_test)`, `predict_proba(X_test)`) aplica essa regra já fixada a dados novos. Não há aprendizado nessa etapa: o modelo não muda ao prever; apenas percorre a estrutura que já tem para chegar a uma saída. `predict` devolve a classe escolhida; `predict_proba` devolve a distribuição de probabilidade entre as classes antes dessa escolha.

Resumindo: criar define a forma do modelo, treinar preenche essa forma com o que os dados ensinam, usar aplica o que foi aprendido sem alterá-lo.

## Falso positivo e falso negativo (preparação para a TG-007)

Esta tarefa não pede matriz de confusão, mas a avaliação em dados separados já aparece: a acurácia foi calculada em `X_test`, que não participou do `fit`. Isso evita medir o modelo nos mesmos dados em que ele aprendeu, o que inflaria artificialmente o desempenho.

## Observação sobre o resultado obtido

Na execução registrada (semente fixa 42, 30% para teste), a árvore rasa (profundidade 3) teve acurácia de 0,978 e o Random Forest teve 0,889 — a árvore saiu melhor que a floresta nesta divisão específica. Isso não significa que uma árvore rasa seja geralmente melhor que um Random Forest: o Iris é um conjunto pequeno e bem separado, e o resultado depende da divisão treino/teste sorteada. Essa variação é parte do que a TG-007 cobre ao tratar validação e métricas com mais cuidado; aqui ela só está registrada, sem conclusão quanto a qual modelo é melhor em geral.
