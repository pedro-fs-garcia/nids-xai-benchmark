# Glossário de termos do protocolo experimental

Definição canônica dos termos técnicos usados no desenho experimental deste TG. Qualquer documento do projeto (protocolo, artigo, relatórios) deve usar exatamente estas definições, sem redefinir o termo nem usá-lo com outro sentido.

| Termo | Definição | Fonte |
|---|---|---|
| Fluxo | Agregado dos pacotes trocados entre um par de endereços e portas dentro de uma janela de tempo, segundo as regras do extrator de atributos usado. O NIDS classifica cada fluxo e, conforme a estratégia, explica essa classificação pela contribuição de cada atributo. | Sharafaldin, Lashkari e Ghorbani (2018), [transcrição local](bibliography/toward-generating-intrusion-model.md) |
| Classificador | Modelo que atribui uma classe a cada fluxo a partir de seus atributos. Random Forest e XGBoost são os classificadores do trabalho. | Definição local |
| Estratégia de explicação | Regra que define quais fluxos são explicados e se a entrega da classificação espera pela explicação. As estratégias são Sem XAI, Síncrono total, Síncrono condicional e Assíncrono. | Definição local |
| Sem XAI | Estratégia de explicação em que a classificação é disponibilizada sem gerar explicação. É a referência da sobrecarga de latência das demais estratégias. | Definição local |
| Síncrono total | Estratégia de explicação em que a explicação de todos os fluxos é gerada antes de a classificação ser disponibilizada. | Definição local |
| Síncrono condicional | Estratégia de explicação em que a explicação é gerada antes de a classificação ser disponibilizada, só para os fluxos que atendem a um critério de seleção calibrado no conjunto de validação. | Definição local |
| Assíncrono (modo assíncrono) | Estratégia de explicação em que a classificação é disponibilizada de imediato e a explicação é processada depois, sem bloquear a entrega da classificação. | Definição local |
| Execução | Reprodução de tráfego com carga, estratégia de explicação, classificador e duração fixos, na qual se registram as variáveis dependentes de cada fluxo processado. | Princípio geral em Kalibera e Jones (2013), [KAR](https://kar.kent.ac.uk/33611/) |
| Repetição | Execução independente das demais, nas mesmas condições (mesma estratégia, classificador e carga), realizada apenas para estimar a variabilidade do resultado. | Princípio geral em Kalibera e Jones (2013) |
| Carga (de tráfego) | Número de fluxos oferecidos ao sistema por segundo durante uma execução. | Definição local |
| Campanha experimental | Conjunto de execuções, com suas repetições, que cobre todas as combinações de estratégia, classificador e carga. Seus resultados são reportados como resposta à pergunta de pesquisa. | Definição local |
| Piloto | Etapa anterior à campanha, em escala reduzida, que serve apenas para calibrar os parâmetros da campanha antes de congelá-los. Seus resultados não entram na resposta à pergunta de pesquisa. | Definição local |
| Modelo congelado | Modelo cujos parâmetros aprendidos, hiperparâmetros, ordem de atributos e versões de biblioteca ficam fixos durante toda a campanha. Só é considerado congelado quando, carregado em um processo novo, produz exatamente as mesmas previsões. | Definição local |
| Fila de explicações pendentes | Estrutura exclusiva do modo assíncrono que retém os fluxos já classificados até que suas explicações sejam processadas. | Definição local |
| Cobertura explicativa | Em uma execução, a proporção dos fluxos classificados selecionados para explicação e a proporção dos que tiveram a explicação concluída. | Definição local |
| Tempo de inferência | Duração da chamada ao classificador para classificar um fluxo. | Definição local |
| Latência de classificação | Tempo entre o fim da extração de atributos de um fluxo e o momento em que sua classificação fica disponível a quem a consome. Nas estratégias síncronas, inclui a geração da explicação dos fluxos explicados. | Definição local |
| Latência de explicação | Tempo entre o fim da extração de atributos de um fluxo e o momento em que sua explicação fica disponível a quem a consome. No modo assíncrono, inclui a espera na fila de explicações pendentes. | Definição local |
| Vazão | Número de fluxos classificados por segundo. | Definição local |
| Descarte | Fluxo que o NIDS não classifica por falta de capacidade, ou explicação que não é gerada porque a fila de explicações pendentes atingiu seu limite. | Definição local |
| Sobrecarga (overhead) de latência | Diferença entre a latência de classificação com uma estratégia de explicação ativa e a latência na estratégia "Sem XAI", sob a mesma carga e o mesmo classificador. | Definição local |
