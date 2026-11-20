# Protocolo experimental

## 1. Termos

Os termos técnicos do desenho experimental têm definição única no [glossário do projeto](glossario.md). Este protocolo usa essas definições sem alterá-las.

## 2. Pergunta e hipótese

**Pergunta de pesquisa.** É viável gerar explicações das decisões de um sistema de detecção de intrusão em rede (NIDS) baseado em aprendizado de máquina, usando o TreeSHAP, no momento da classificação e sem violar as restrições de latência do tráfego?

O TreeSHAP calcula, para cada previsão de um modelo baseado em árvores, a contribuição de cada atributo para essa previsão ([Lundberg et al., 2020](https://doi.org/10.1038/s42256-019-0138-9)). O significado de "viável" neste protocolo está na seção 8.

**Hipótese.** A geração de explicações adiciona custo computacional que varia com a estratégia de explicação e com a carga. As estratégias Síncrono condicional e Assíncrono podem reduzir esse custo, com compromissos diferentes entre latência, uso de recursos e cobertura explicativa.

## 3. Objetivo

Medir a sobrecarga de latência e o uso de recursos que o TreeSHAP adiciona a um NIDS baseado em Random Forest e XGBoost, comparando as quatro estratégias de explicação sob cargas de tráfego controladas.

## 4. Desenho experimental

O experimento cruza três fatores.

- **Estratégia de explicação**, com quatro níveis: Sem XAI, Síncrono total, Síncrono condicional e Assíncrono. XAI é a sigla de inteligência artificial explicável, o conjunto de técnicas que explicam as decisões de um modelo.
- **Classificador**, com dois níveis: Random Forest e XGBoost, ambos congelados antes da campanha.
- **Carga**, com três níveis. O ambiente é emulado em Linux. O Mininet emula a rede, e o `tcpreplay-edit` reproduz o trecho de captura de tráfego (PCAP) da [decisão 16](decisoes.md) na velocidade original. O nível de carga é o número de cópias do trecho reproduzidas ao mesmo tempo, e os três níveis são 1, 2 e 4 cópias ([decisão 15](decisoes.md)).

## 5. Medições

### 5.1 Marcações de tempo

Cada fluxo recebe até cinco marcações de tempo.

- `t0` é o fim da extração de atributos do fluxo.
- `t1` é o início da chamada ao classificador.
- `t2` é o fim da chamada ao classificador.
- `t3` é o momento em que a classificação fica disponível a quem a consome.
- `t4` é o momento em que a explicação fica disponível a quem a consome. Só existe para fluxos explicados.

Nas estratégias síncronas, a classificação e a explicação de um fluxo explicado ficam disponíveis juntas, então `t3` e `t4` coincidem. No modo assíncrono, `t4` é posterior a `t3` e inclui a espera na fila de explicações pendentes.

No NIDS, `t0` é lido no extrator logo depois do cálculo dos atributos do fluxo emitido. A espera do fluxo na fila de saída do extrator fica entre `t0` e `t1`. `t1` e `t2` delimitam a chamada `predict_proba`. `t3` é o retorno da escrita do registro de classificação no canal de saída. Os eventos e o relógio comum estão na [decisão 9](decisoes.md).

`t4` é o retorno da escrita do registro da explicação no canal de saída das explicações. Nas estratégias síncronas, o NIDS escreve o registro da explicação e depois o da classificação, e uma única leitura do relógio, depois das duas escritas, vale por `t3` e `t4`. No modo assíncrono, a solicitação de explicação entra na fila de explicações pendentes depois de `t3`, e o processo explicador lê `t4`. Os eventos estão na [decisão 11](decisoes.md).

### 5.2 Tempos calculados

- O tempo de inferência é `t2 − t1`.
- A latência de classificação é `t3 − t0`.
- A latência de explicação é `t4 − t0`.

Cada latência é resumida pela média e pelos percentis 95 e 99 (p95 e p99). O p95 e o p99 são os valores que 95% e 99% dos fluxos não ultrapassam.

### 5.3 Demais medidas

Cada execução também registra:

- a carga efetiva e a vazão;
- o tempo de CPU e o pico de memória de cada processo do NIDS ([decisão 14](decisoes.md));
- a cobertura explicativa;
- o tamanho da fila de explicações pendentes ao longo da execução, no modo assíncrono;
- os descartes;
- o estado da máquina a cada segundo ([decisão 17](decisoes.md)).

## 6. Controles

Os itens abaixo ficam fixos durante a campanha. O piloto pode variá-los para calibrar.

- Os conjuntos de treino, validação e teste, e o dicionário de atributos, que lista os atributos recebidos pelo classificador com o significado e a unidade de cada um. O conjunto de teste não é usado para escolher estratégia, limiar nem hiperparâmetro.
- Os classificadores congelados.
- A configuração do TreeSHAP, que inclui o tipo de cálculo e o conjunto de referência, quando houver.
- O trecho de tráfego e a troca de endereços de cada cópia ([decisões 15 e 16](decisoes.md)).
- O hardware, as versões de software, o commit do repositório e as sementes de aleatoriedade, registrados em cada execução.
- O estado da máquina. Antes de cada execução, a máquina precisa estar na tomada, ociosa e com memória disponível ([decisão 17](decisoes.md)).

## 7. Repetições

Cada combinação tem 3 repetições ([decisão 18](decisoes.md)).

Cada repetição reúne uma execução de cada combinação, em ordem sorteada com semente fixa. Assim, uma variação lenta da máquina não recai sempre sobre as mesmas combinações.

## 8. Viabilidade operacional

Os resultados valem para as condições do experimento. Eles não implicam equivalência com redes físicas de produção nem garantia de tempo real estrito.

Uma estratégia é viável sob uma carga quando, ao longo de uma execução, atende aos três critérios abaixo.

- O tamanho da fila de explicações pendentes não aumenta de forma contínua até o fim da execução, ou seja, a fila se estabiliza ou esvazia. Este critério só se aplica ao modo assíncrono.
- A proporção de fluxos descartados é 0% ([decisão 20](decisoes.md)).
- A latência de classificação não ultrapassa 1 s no p95 nem 2 s no p99 ([decisão 19](decisoes.md)).

A viabilidade é julgada para cada configuração de explicação, e cada resultado de viabilidade é reportado com a cobertura explicativa da execução ([decisão 21](decisoes.md)).

## 9. Piloto

O piloto define o número de repetições e os valores dos critérios de viabilidade da seção 8, e confirma ou ajusta os limites das filas da [decisão 13](decisoes.md). Para isso, ele realiza três verificações.

1. Verifica se os atributos que o NIDS extrai em tempo real correspondem aos usados no treinamento dos classificadores, incluindo as regras que definem quando um fluxo termina.
2. Verifica se a velocidade de reprodução do tráfego altera os atributos temporais do fluxo, como o tempo entre pacotes. Isso separa esse efeito do custo de processamento do NIDS.
3. Mede, no modo assíncrono, o tempo médio que uma explicação espera na fila antes de ser processada e o tempo que a fila leva para esvaziar depois que o tráfego termina.

A primeira verificação compara cada execução com a leitura do mesmo trecho do arquivo, cópia por cópia (`nids-validar`). A segunda é feita sem rede: o NIDS lê o trecho com os intervalos entre pacotes divididos por 2, 4 e 8, e os fluxos, as previsões e a seleção são comparados com os da leitura original (`nids-efeito-aceleracao`).

As execuções do piloto estão em [configs/piloto-2.json](../configs/piloto-2.json). Elas cobrem as cinco configurações de explicação nos dois classificadores com 4 cópias, a maior carga. Duas combinações do Random Forest, o Sem XAI com 1 cópia e o Síncrono total com 2 cópias, têm três repetições cada, para estimar a variabilidade.

## 10. Matriz e critérios de comparação

A matriz da campanha, em [configs/campanha.json](../configs/campanha.json), cruza os dois classificadores, as configurações de explicação e os três níveis de carga, com 3 repetições ([decisão 18](decisoes.md)). As configurações de explicação são Sem XAI, Síncrono total, Síncrono condicional pelo critério de probabilidade, Síncrono condicional pelo critério de incerteza e Assíncrono ([decisões 12 e 21](decisoes.md)). A matriz tem 90 execuções.

Cada execução fica numa pasta própria. O registro da matriz liga cada combinação de classificador, configuração de explicação, nível de carga e repetição à pasta da execução e ao número da tentativa, e nunca é reescrito.

As métricas principais são:

- a latência de classificação, na média, no p95 e no p99;
- a sobrecarga de latência de cada estratégia, contra a Sem XAI do mesmo classificador e da mesma carga;
- a latência de explicação, na média, no p95 e no p99;
- a cobertura explicativa;
- a proporção de fluxos descartados;
- a viabilidade de cada configuração de explicação sob cada carga, com a cobertura explicativa ao lado (seção 8).

As métricas secundárias são o tempo de inferência, o tempo de explicação, a vazão, a carga efetiva, o tempo de CPU e o pico de memória de cada processo, o tamanho da fila de explicações pendentes, o tempo de esvaziamento da fila e os pacotes descartados na captura.

Um fluxo descartado na fila de saída do extrator entra na proporção de descartes e não tem latência. Uma solicitação de explicação descartada ou pendente deixa o fluxo sem explicação. Esse fluxo entra na latência de classificação e reduz a cobertura explicativa. Descartes, pendências e pacotes perdidos na captura são resultados e não invalidam uma execução.

Cada execução produz as próprias estatísticas. As repetições de uma combinação são resumidas pela mediana, com o mínimo e o máximo.

No piloto e na campanha, uma execução é válida quando termina sem erro, o NIDS passa nas próprias verificações, o `tcpreplay-edit` envia todos os pacotes e a máquina fica na tomada do início ao fim. Uma execução inválida fica registrada com o motivo, e a nova tentativa é outra execução. Cada combinação tem no máximo 2 tentativas ([decisão 22](decisoes.md)).
