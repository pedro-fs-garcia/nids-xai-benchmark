# TG-007: notas sobre erros, métricas e vazamento

## Matriz de confusão e métricas

Usando só versicolor e virginica (as classes que de fato se confundem no Iris; positivo = virginica), a execução de `tg007_metricas_erros.py` deu:

| | Previsto negativo | Previsto positivo |
| --- | --- | --- |
| **Real negativo** | TN=14 | FP=1 |
| **Real positivo** | FN=3 | TP=12 |

- **Falso positivo** (índice 9 do teste): atributos `[5.9, 3.2, 4.8, 1.8]`, era versicolor, o modelo previu virginica com probabilidade 1,0. O modelo "gritou" ataque (virginica) onde não havia — na prática de IDS, isso é um alerta que o analista investiga à toa.
- **Falso negativo** (índice 2 do teste): atributos `[6.1, 2.6, 5.6, 1.4]`, era virginica, o modelo previu versicolor com P(virginica)=0. O modelo deixou passar um caso positivo sem alertar — na prática de IDS, isso é um ataque que não gera alerta nenhum, o pior tipo de erro.
- Precisão 0,923, recall 0,800, F1 0,857, FPR 0,067, ROC AUC 0,867. Recall mais baixo que precisão aqui significa que o modelo deixa passar mais positivos do que inventa; para um IDS, normalmente se prefere o oposto (mais FP, menos FN), porque um ataque não detectado custa mais que um alerta falso.
- A curva ROC amostrada mostra o compromisso: no limiar mais baixo (0,0), FPR=1 e TPR=1 (aceita tudo); no limiar intermediário (1,0), FPR=0,067 e TPR=0,800 — é o ponto que a árvore de profundidade 3 efetivamente usa, porque suas folhas só produzem algumas probabilidades discretas.

## Treino, validação e teste

Esta tarefa não usou um conjunto de validação separado (só treino/teste), porque a profundidade da árvore (3) foi fixada de antemão, sem busca de hiperparâmetro. Se houvesse busca de hiperparâmetro (como no TG-017, que vai comparar configurações de Random Forest), o teste não poderia ser usado para escolher entre elas — precisaria de um terceiro conjunto (validação), e o teste ficaria reservado só para a avaliação final, depois de a configuração estar congelada. Essa separação é exatamente o que a TG-014 vai ter que implementar para o CIC-IDS2017, com o cuidado adicional de grupos de fluxos repetidos (ver abaixo).

## Vazamento de dados: um exemplo medido, não só um aviso

O relatório de inspeção já documentou 22.109 registros do CIC-IDS2017 em grupos com atributos de tráfego idênticos, 14.351 deles cruzando mais de um arquivo ([relatorios/inspecao-cicids2017.md](../relatorios/inspecao-cicids2017.md)). Se a divisão treino/teste ignorar esses grupos, uma cópia pode cair no treino e outra no teste — o modelo "decora" aquele caso em vez de generalizar, e o desempenho medido fica inflado sem que isso seja visível olhando só a acurácia final.

`tg007_vazamento.py` reproduz isso em miniatura: 20 das 100 linhas de versicolor/virginica são duplicadas, e um k-NN(1) é treinado com uma divisão que ignora essa duplicação (como um split ingênuo por linha de CSV) e com uma divisão que respeita os grupos (`GroupShuffleSplit`). Resultado:

- **Linhas de teste cujo par duplicado caiu no treino:** acurácia 1,000 (n=7). Isso é garantido pelo próprio mecanismo do 1-NN — a distância até o par duplicado é zero, então o acerto não depende de o modelo ter aprendido nada sobre a classe, só de o par estar no treino.
- **Linhas de teste sem esse vazamento:** acurácia 0,897 (n=29).
- **Divisão por grupo, sem nenhum par dividido:** acurácia 0,853 (n=34).

A diferença entre 1,000 e as duas estimativas honestas (0,897 e 0,853, próximas entre si) é o tamanho do viés introduzido pelo vazamento neste exemplo — não uma opinião, um número calculado a partir de uma divisão que deliberadamente vaza contra uma que não vaza, no mesmo modelo e nos mesmos dados.

**Implicação direta para o TG:** a TG-014 (separação treino/validação/teste do CIC-IDS2017) precisa impedir que grupos de fluxos repetidos se dividam entre conjuntos, do mesmo jeito que o `GroupShuffleSplit` fez aqui — senão qualquer modelo avaliado nesse conjunto de teste terá desempenho inflado pela mesma razão demonstrada neste exercício.
