# Protocolo experimental

## 1. Termos

Os termos técnicos do desenho experimental têm definição única no [glossário do projeto](../docs/glossario.md). Este protocolo usa essas definições sem alterá-las.

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
- **Carga**, com níveis definidos pelo piloto (seção 9). O ambiente é emulado em Linux. O Mininet emula a rede e o tcpreplay reproduz capturas de tráfego (PCAP) em taxa controlada.

## 5. Medições

### 5.1 Marcações de tempo

Cada fluxo recebe até cinco marcações de tempo.

- `t0` é o fim da extração de atributos do fluxo.
- `t1` é o início da chamada ao classificador.
- `t2` é o fim da chamada ao classificador.
- `t3` é o momento em que a classificação fica disponível a quem a consome.
- `t4` é o momento em que a explicação fica disponível a quem a consome. Só existe para fluxos explicados.

Nas estratégias síncronas, a classificação e a explicação de um fluxo explicado ficam disponíveis juntas, então `t3` e `t4` coincidem. No modo assíncrono, `t4` é posterior a `t3` e inclui a espera na fila de explicações pendentes.

### 5.2 Tempos calculados

- O tempo de inferência é `t2 − t1`.
- A latência de classificação é `t3 − t0`.
- A latência de explicação é `t4 − t0`.

Cada latência é resumida pela média e pelos percentis 95 e 99 (p95 e p99). O p95 e o p99 são os valores que 95% e 99% dos fluxos não ultrapassam.

### 5.3 Demais medidas

Cada execução também registra:

- a vazão;
- o uso de CPU e de memória pelo processo do NIDS;
- a cobertura explicativa;
- o tamanho da fila de explicações pendentes ao longo da execução, no modo assíncrono;
- os descartes.

## 6. Controles

Os itens abaixo ficam fixos durante a campanha. O piloto pode variá-los para calibrar.

- Os conjuntos de treino, validação e teste, e o dicionário de atributos, que lista os atributos recebidos pelo classificador com o significado e a unidade de cada um. O conjunto de teste não é usado para escolher estratégia, limiar nem hiperparâmetro.
- Os classificadores congelados.
- A configuração do TreeSHAP, que inclui o tipo de cálculo e o conjunto de referência, quando houver.
- O hardware, as versões de software e as sementes de aleatoriedade, registrados em cada execução.

## 7. Repetições

O piloto define o número de repetições por combinação, a partir da variabilidade observada nos resultados. Esse número ainda não foi fixado.

## 8. Viabilidade operacional

Os resultados valem para as condições do experimento. Eles não implicam equivalência com redes físicas de produção nem garantia de tempo real estrito.

Uma estratégia é viável sob uma carga quando, ao longo de uma execução, atende aos três critérios abaixo.

- O tamanho da fila de explicações pendentes não aumenta de forma contínua até o fim da execução, ou seja, a fila se estabiliza ou esvazia. Este critério só se aplica ao modo assíncrono.
- A proporção de fluxos descartados não ultrapassa um limiar.
- A latência de classificação, no p95 e no p99, não ultrapassa um limite.

O piloto define os valores do limiar e do limite.

## 9. Piloto

O piloto define os níveis de carga, o número de repetições e os valores dos critérios de viabilidade da seção 8. Para isso, ele realiza três verificações.

1. Verifica se os atributos que o NIDS extrai em tempo real correspondem aos usados no treinamento dos classificadores, incluindo as regras que definem quando um fluxo termina.
2. Verifica se a velocidade de reprodução do tráfego altera os atributos temporais do fluxo, como o tempo entre pacotes. Isso separa esse efeito do custo de processamento do NIDS.
3. Mede, no modo assíncrono, o tempo médio que uma explicação espera na fila antes de ser processada e o tempo que a fila leva para esvaziar depois que o tráfego termina.

## 10. Decisões em aberto

As decisões já tomadas estão em [docs/decisoes.md](../docs/decisoes.md). As decisões abaixo ainda não foram tomadas.

- Política de emissão dos fluxos no NIDS. O extrator só emite um fluxo encerrado quando chega outro pacote com o mesmo identificador ou quando a captura termina, e esse atraso afeta o instante `t0`.
- Critério de seleção da estratégia Síncrono condicional, que inclui a grandeza avaliada (probabilidade ou incerteza), o limiar e a forma de calibração no conjunto de validação.
- Limites das filas e política de descarte.
- Níveis de carga, número de repetições e valores dos critérios de viabilidade, todos definidos pelo piloto.
