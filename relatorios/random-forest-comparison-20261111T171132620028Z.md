# Seleção e avaliação do Random Forest

Foram comparadas três configurações na mesma amostra de 100.000 registros de treino e no mesmo conjunto de validação. Variaram apenas o número de árvores e a profundidade máxima. A configuração escolhida foi treinada com todo o conjunto de treino antes da avaliação final no teste reservado.

## Comparação na amostra

A amostra é a mesma do primeiro treinamento, com semente 42 e pelo menos um registro de cada rótulo original. Os arquivos sample_indices.npy e sample_origin.npy identificam seus registros. O resultado da configuração de referência foi reutilizado; as outras duas configurações foram treinadas nesta execução.

A alternativa com menos árvores verifica se o número de árvores pode ser reduzido mantendo a qualidade das previsões. A alternativa com menor profundidade verifica o mesmo efeito ao limitar o tamanho das árvores. Todas usam as 80 entradas do [dicionário de atributos](../docs/dicionario-atributos.md), mínimo de dois registros por folha, semente 42 e dois trabalhadores. Não houve normalização, ponderação de classes nem ajuste do limiar.

O critério foi definido antes da comparação: maior F1 na validação. Em caso de empate, menos nós e, depois, menos árvores. F1 é a média harmônica entre precisão e recall. Precisão é a proporção de previsões de ataque corretas; recall é a proporção dos ataques detectados.

| Configuração | Árvores | Profundidade máxima | Nós | Precisão | Recall | F1 | Ajuste (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| reference | 100 | 12 | 20.096 | 0,999828 | 0,996742 | 0,998283 | 32,80 |
| fewer-trees | 50 | 12 | 9.840 | 0,999802 | 0,996518 | 0,998157 | 19,20 |
| shallower-trees | 100 | 8 | 11.948 | 0,999841 | 0,993801 | 0,996812 | 30,25 |

A configuração selecionada foi **reference**. Os tempos correspondem a uma execução por configuração e incluem apenas o ajuste. Servem para descrever o custo observado, sem estabelecer uma comparação estatística de desempenho computacional. O custo do TreeSHAP ainda será medido.

## Treinamento completo e teste reservado

A configuração escolhida foi treinada com os 1.469.983 registros do treino. O ajuste levou 669,53 s. As escolhas foram registradas em selection.json antes desse ajuste. O modelo e seus parâmetros foram salvos antes de abrir os arquivos do teste, com registro em fixed-before-test.json. Os resultados do teste não foram usados para alterar a configuração.

A classe positiva é ataque. O modelo prevê ataque se a probabilidade for maior que 0,5; empates recebem a classe benigno. O mapeamento de rótulos e a separação dos conjuntos seguem as [decisões do desenho experimental](../docs/decisoes.md).

| Métrica | Validação após treino completo | Teste reservado |
|---|---:|---:|
| Acurácia | 0,999352 | 0,999194 |
| Precisão | 0,999894 | 0,999974 |
| Recall | 0,997415 | 0,996676 |
| F1 | 0,998653 | 0,998322 |
| Taxa de falsos positivos | 0,000033 | 0,000008 |
| ROC-AUC | 0,999995 | 0,999999 |

Acurácia é a proporção de previsões corretas. A taxa de falsos positivos é a proporção dos benignos classificada como ataque. ROC-AUC é a área sob a curva que relaciona recall e taxa de falsos positivos ao variar o limiar.

O teste tem 314.993 registros, sendo 239.178 benignos e 75.815 ataques. Sua matriz de confusão é:

| Classe real | Previsto benigno | Previsto ataque |
|---|---:|---:|
| Benigno | 239.176 | 2 |
| Ataque | 252 | 75.563 |

## Erros por rótulo original

A classe benigno predomina nos conjuntos. Por isso, as métricas agregadas são acompanhadas das contagens por rótulo. Para os rótulos de ataque, a última coluna conta ataques detectados; para BENIGN e Attempted, conta falsos positivos.

| Rótulo original | Registros na validação | Previstos ataque na validação | Registros no teste | Previstos ataque no teste |
|---|---:|---:|---:|---:|
| BENIGN | 237.387 | 8 | 237.382 | 2 |
| Botnet | 111 | 72 | 110 | 77 |
| Botnet - Attempted | 608 | 0 | 611 | 0 |
| DDoS | 14.272 | 14.272 | 14.271 | 14.271 |
| DoS GoldenEye | 1.135 | 1.078 | 1.135 | 1.064 |
| DoS GoldenEye - Attempted | 12 | 0 | 12 | 0 |
| DoS Hulk | 23.770 | 23.769 | 23.770 | 23.762 |
| DoS Hulk - Attempted | 87 | 0 | 87 | 0 |
| DoS Slowhttptest | 261 | 258 | 261 | 259 |
| DoS Slowhttptest - Attempted | 505 | 0 | 505 | 0 |
| DoS Slowloris | 579 | 574 | 579 | 576 |
| DoS Slowloris - Attempted | 277 | 0 | 277 | 0 |
| FTP-Patator | 596 | 595 | 596 | 594 |
| FTP-Patator - Attempted | 2 | 0 | 2 | 0 |
| Heartbleed | 2 | 2 | 1 | 1 |
| Infiltration | 6 | 4 | 5 | 3 |
| Infiltration - Attempted | 9 | 0 | 5 | 0 |
| Infiltration - Portscan | 11.949 | 11.881 | 10.118 | 10.018 |
| Portscan | 22.675 | 22.661 | 24.509 | 24.492 |
| SSH-Patator | 444 | 440 | 444 | 434 |
| SSH-Patator - Attempted | 4 | 0 | 4 | 0 |
| Web Attack - Brute Force | 11 | 11 | 11 | 10 |
| Web Attack - Brute Force - Attempted | 194 | 0 | 194 | 0 |
| Web Attack - SQL Injection | 2 | 0 | 2 | 0 |
| Web Attack - SQL Injection - Attempted | 1 | 0 | 1 | 0 |
| Web Attack - XSS | 3 | 3 | 3 | 2 |
| Web Attack - XSS - Attempted | 98 | 0 | 98 | 0 |

Rótulos raros têm poucos exemplos, o que limita a interpretação das taxas por tipo de ataque. A divisão impede entradas idênticas entre conjuntos, mas permite fluxos da mesma conexão em conjuntos diferentes, conforme os limites registrados no desenho experimental. A escolha de configuração foi feita na amostra; somente a escolhida recebeu treinamento completo.

## Artefatos e reprodução

O modelo final tem 100 árvores, profundidade máxima observada 12, 44.322 nós e 22.211 folhas. O pico de memória residente do processo foi 2006,2 MiB (1 MiB = 1.048.576 bytes), considerando comparação, treinamento completo e avaliação.

Os artefatos estão em [training-runs/random-forest-comparison/20261111T171132620028Z/](../training-runs/random-forest-comparison/20261111T171132620028Z/). final/model.joblib contém o modelo e a ordem das entradas. report.json registra todos os parâmetros, as sementes, os hashes e as métricas. Os arquivos de previsões seguem a ordem dos conjuntos derivados.

Versões: Python 3.12.3; numpy 2.5.4, scikit-learn 1.9.1, scipy 1.18.1, joblib 1.6.0.

SHA-256 do manifesto dos dados: `69b1ff4ad68e2465013bc0266324f615b4780092fe4d2fbe0ca53595c423f779`.

A partir de src/, o comando abaixo reproduz a comparação. Ele depende dos dados derivados e dos artefatos do treinamento de referência indicados em configs/random-forest-comparison.json.

```bash
python main.py comparar-rf
```
