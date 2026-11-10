# Inspeção do Improved CIC-IDS2017

Gerado em 2026-10-28T12:10:09.634056+00:00.

## Resultado

- Leitura integral de **2.099.976 registros**, em cinco CSVs com **91 colunas** de mesmo cabeçalho.
- **27 rótulos textuais**, preservados conforme os arquivos originais.
- **5 registros** com ao menos um atributo numérico de tráfego ausente, não numérico, NaN ou infinito.
- **0 repetições excedentes de linhas completas** e **15.255 repetições excedentes na representação de atributos** definida abaixo.
- **SHA-256, CRC32, tamanho e data de modificação de todas as entradas permaneceram iguais antes e depois da inspeção.**

A inspeção não aplicou limpeza, remoção, reclassificação, amostragem, divisão entre conjuntos ou treinamento. Os arquivos originais permaneceram intactos.

## Pontos que exigem atenção antes do treinamento

- Os cinco registros com problema numérico contêm `inf` tanto em `Flow Bytes/s` quanto em `Flow Packets/s`, totalizando dez células. Suas localizações estão na seção de qualidade dos valores.
- `Fwd Header Length` possui 309 valores negativos, e `Bwd Header Length` possui 472. Esses comprimentos precisam ser conferidos com a implementação do extrator antes de definir seu tratamento. As contagens são por coluna e não representam necessariamente registros distintos.
- Há 11.979 registros com `Attempted Category` diferente de -1. A política de classificação desses registros ainda precisa ser definida.
- A distribuição é desbalanceada. `BENIGN` representa 75,3611% dos registros, enquanto `Heartbleed`, `Web Attack - SQL Injection` e `Web Attack - XSS` possuem, respectivamente, 11, 13 e 18 registros com esses rótulos exatos. Uma avaliação por tipo de ataque exigirá cuidado com essas classes pequenas.
- Há 22.109 registros em grupos com atributos de tráfego iguais, dos quais 14.351 pertencem a grupos presentes em mais de um arquivo. Essas relações precisam ser consideradas na definição dos conjuntos de treino, validação e teste.

## Procedência e integridade

A estrutura dos arquivos é compatível com o Improved CIC-IDS2017 associado ao trabalho de Liu e colaboradores, publicado no IEEE CNS 2022. Esta inspeção local não autentica a origem do download. [Documentação dos autores](https://intrusion-detection.distrinet-research.be/CNS2022/index.html).

| Arquivo | Bytes | SHA-256 | Igual depois |
| --- | --- | --- | --- |
| monday.csv | 207.875.155 | `51fe5dc962626efb4ae70dce0303072fb780da0932822b651202ee9c2fbc1aff` | Sim |
| tuesday.csv | 178.397.720 | `e2a0a5b631dfc6b455cc9f9a88b944110637d70a7f74171473925f76f38b6b0c` | Sim |
| wednesday.csv | 291.290.505 | `bf46c5f3c792e8817381f724511229569606918eaf07ac986d7a2592b6341bc2` | Sim |
| thursday.csv | 189.519.159 | `78a4d11eaf473d099e30e71ddb01e0f38218e844c0a9cdd36602145d674af482` | Sim |
| friday.csv | 285.188.226 | `ebd499e6f23bd59f9cb81bec28178491b02b925fa5640a24215c9437d79482d0` | Sim |
| CICIDS2017_improved.zip | 343.549.013 | `97fdb91d339e2d8cf5627f981b831e5e7e400b981c58181c451a38fd03c48883` | Sim |

| CSV extraído | Tamanho e CRC32 correspondem ao diretório do ZIP |
| --- | --- |
| friday.csv | Sim |
| monday.csv | Sim |
| thursday.csv | Sim |
| tuesday.csv | Sim |
| wednesday.csv | Sim |


## Volume e estrutura por arquivo

Registros são entradas retornadas pelo leitor CSV, descontado o cabeçalho inicial. Registros estruturados têm o número esperado de campos e não repetem o cabeçalho.

| Arquivo | Registros | Estruturados | Campos incorretos | Linhas vazias | Cabeçalhos repetidos | Bytes |
| --- | --- | --- | --- | --- | --- | --- |
| monday.csv | 371.624 | 371.624 | 0 | 0 | 0 | 207.875.155 |
| tuesday.csv | 322.078 | 322.078 | 0 | 0 | 0 | 178.397.720 |
| wednesday.csv | 496.641 | 496.641 | 0 | 0 | 0 | 291.290.505 |
| thursday.csv | 362.076 | 362.076 | 0 | 0 | 0 | 189.519.159 |
| friday.csv | 547.557 | 547.557 | 0 | 0 | 0 | 285.188.226 |


## Distribuição dos rótulos

Valores originais de `Label`, sem agrupamento ou renomeação.

| Rótulo | Segunda | Terça | Quarta | Quinta | Sexta | Total | Proporção |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BENIGN | 371.624 | 315.106 | 319.120 | 288.172 | 288.544 | 1.582.566 | 75,3611% |
| Portscan | 0 | 0 | 0 | 0 | 159.066 | 159.066 | 7,5747% |
| DoS Hulk | 0 | 0 | 158.468 | 0 | 0 | 158.468 | 7,5462% |
| DDoS | 0 | 0 | 0 | 0 | 95.144 | 95.144 | 4,5307% |
| Infiltration - Portscan | 0 | 0 | 0 | 71.767 | 0 | 71.767 | 3,4175% |
| DoS GoldenEye | 0 | 0 | 7.567 | 0 | 0 | 7.567 | 0,3603% |
| Botnet - Attempted | 0 | 0 | 0 | 0 | 4.067 | 4.067 | 0,1937% |
| FTP-Patator | 0 | 3.972 | 0 | 0 | 0 | 3.972 | 0,1891% |
| DoS Slowloris | 0 | 0 | 3.859 | 0 | 0 | 3.859 | 0,1838% |
| DoS Slowhttptest - Attempted | 0 | 0 | 3.368 | 0 | 0 | 3.368 | 0,1604% |
| SSH-Patator | 0 | 2.961 | 0 | 0 | 0 | 2.961 | 0,1410% |
| DoS Slowloris - Attempted | 0 | 0 | 1.847 | 0 | 0 | 1.847 | 0,0880% |
| DoS Slowhttptest | 0 | 0 | 1.740 | 0 | 0 | 1.740 | 0,0829% |
| Web Attack - Brute Force - Attempted | 0 | 0 | 0 | 1.292 | 0 | 1.292 | 0,0615% |
| Botnet | 0 | 0 | 0 | 0 | 736 | 736 | 0,0350% |
| Web Attack - XSS - Attempted | 0 | 0 | 0 | 655 | 0 | 655 | 0,0312% |
| DoS Hulk - Attempted | 0 | 0 | 581 | 0 | 0 | 581 | 0,0277% |
| DoS GoldenEye - Attempted | 0 | 0 | 80 | 0 | 0 | 80 | 0,0038% |
| Web Attack - Brute Force | 0 | 0 | 0 | 73 | 0 | 73 | 0,0035% |
| Infiltration - Attempted | 0 | 0 | 0 | 45 | 0 | 45 | 0,0021% |
| Infiltration | 0 | 0 | 0 | 36 | 0 | 36 | 0,0017% |
| SSH-Patator - Attempted | 0 | 27 | 0 | 0 | 0 | 27 | 0,0013% |
| Web Attack - XSS | 0 | 0 | 0 | 18 | 0 | 18 | 0,0009% |
| Web Attack - SQL Injection | 0 | 0 | 0 | 13 | 0 | 13 | 0,0006% |
| FTP-Patator - Attempted | 0 | 12 | 0 | 0 | 0 | 12 | 0,0006% |
| Heartbleed | 0 | 0 | 11 | 0 | 0 | 11 | 0,0005% |
| Web Attack - SQL Injection - Attempted | 0 | 0 | 0 | 5 | 0 | 5 | 0,0002% |

A divisão entre treino, validação e teste deve considerar classes por dia, repetições e relações entre fluxos. Separar por dias pode deixar classes ausentes do treinamento; sortear linhas pode distribuir registros repetidos entre conjuntos.

## Categorias Attempted

`Label` e `Attempted Category` são campos de anotação e devem ficar fora das entradas preditivas. A política para as categorias Attempted continua aberta. Os autores orientam seu tratamento conforme o objetivo da análise e recomendam que não sejam utilizadas como classes adicionais. [Orientações dos autores](https://intrusion-detection.distrinet-research.be/CNS2022/Dataset_Download.html).

| Attempted Category original | Registros |
| --- | --- |
| -1 | 2.087.997 |
| 0 | 4.845 |
| 1 | 4.067 |
| 2 | 23 |
| 3 | 27 |
| 4 | 75 |
| 5 | 138 |
| 6 | 2.804 |

| Rótulo original | Categoria diferente de -1 | Registros |
| --- | --- | --- |
| Botnet - Attempted | 1 | 4.067 |
| DoS GoldenEye - Attempted | 0 | 80 |
| DoS Hulk - Attempted | 0 | 579 |
| DoS Hulk - Attempted | 4 | 2 |
| DoS Slowhttptest - Attempted | 0 | 563 |
| DoS Slowhttptest - Attempted | 4 | 1 |
| DoS Slowhttptest - Attempted | 6 | 2.804 |
| DoS Slowloris - Attempted | 0 | 1.705 |
| DoS Slowloris - Attempted | 2 | 3 |
| DoS Slowloris - Attempted | 4 | 1 |
| DoS Slowloris - Attempted | 5 | 138 |
| FTP-Patator - Attempted | 0 | 10 |
| FTP-Patator - Attempted | 2 | 2 |
| Infiltration - Attempted | 0 | 42 |
| Infiltration - Attempted | 2 | 3 |
| SSH-Patator - Attempted | 3 | 27 |
| Web Attack - Brute Force - Attempted | 0 | 1.214 |
| Web Attack - Brute Force - Attempted | 2 | 7 |
| Web Attack - Brute Force - Attempted | 4 | 71 |
| Web Attack - SQL Injection - Attempted | 0 | 1 |
| Web Attack - SQL Injection - Attempted | 2 | 4 |
| Web Attack - XSS - Attempted | 0 | 651 |
| Web Attack - XSS - Attempted | 2 | 4 |


## Qualidade dos valores

Problemas numéricos incluem ausentes, NaN, infinitos e valores não numéricos. As contagens por registro representam a união dos problemas, sem contar um registro várias vezes.

| Arquivo | Registros com problema numérico, incluindo id e categoria | Registros com problema nos atributos de tráfego | Timestamps inválidos | Células vazias | Células com espaços nas extremidades |
| --- | --- | --- | --- | --- | --- |
| monday.csv | 3 | 3 | 0 | 0 | 0 |
| tuesday.csv | 0 | 0 | 0 | 0 | 0 |
| wednesday.csv | 1 | 1 | 0 | 0 | 0 |
| thursday.csv | 1 | 1 | 0 | 0 | 0 |
| friday.csv | 0 | 0 | 0 | 0 | 0 |

| Coluna | Ausentes | NaN | +Infinito | -Infinito | Não numéricos |
| --- | --- | --- | --- | --- | --- |
| Flow Bytes/s | 0 | 0 | 5 | 0 | 0 |
| Flow Packets/s | 0 | 0 | 5 | 0 | 0 |

| Arquivo | Linha física, incluindo cabeçalho | Coluna | Valor | Problema |
| --- | --- | --- | --- | --- |
| monday.csv | 106.985 | Flow Bytes/s | `inf` | positive_infinity |
| monday.csv | 114.892 | Flow Bytes/s | `inf` | positive_infinity |
| monday.csv | 121.884 | Flow Bytes/s | `inf` | positive_infinity |
| wednesday.csv | 465.857 | Flow Bytes/s | `inf` | positive_infinity |
| thursday.csv | 12.014 | Flow Bytes/s | `inf` | positive_infinity |
| monday.csv | 106.985 | Flow Packets/s | `inf` | positive_infinity |
| monday.csv | 114.892 | Flow Packets/s | `inf` | positive_infinity |
| monday.csv | 121.884 | Flow Packets/s | `inf` | positive_infinity |
| wednesday.csv | 465.857 | Flow Packets/s | `inf` | positive_infinity |
| thursday.csv | 12.014 | Flow Packets/s | `inf` | positive_infinity |


## Valores negativos e colunas constantes

Valores negativos foram contabilizados sem classificação automática como erro. Anotações e valores sentinela exigem interpretação própria; valores negativos em durações ou contagens requerem investigação. Nenhuma coluna foi excluída.

| Coluna | Negativos | Mínimo finito | Máximo finito |
| --- | --- | --- | --- |
| Fwd Header Length | 309 | -32.708 | 32.748 |
| Bwd Header Length | 472 | -32.764 | 32.680 |
| ICMP Code | 2.099.373 | -1 | 10 |
| ICMP Type | 2.099.373 | -1 | 11 |
| Attempted Category | 2.087.997 | -1 | 6 |

| Coluna constante entre valores finitos | Valor | Finitos | Não finitos ou ausentes |
| --- | --- | --- | --- |
| Nenhuma | — | — | — |

A constância descreve a população inspecionada. A seleção futura de atributos deve ser ajustada somente com o treinamento.

## Duplicações

A comparação utiliza os valores textuais lidos pelo parser CSV, serializados em JSON e agrupados por SHA-256. Diferenças como `1` e `1.0` geram assinaturas distintas. A linha completa inclui todas as 91 colunas. A representação diagnóstica de tráfego possui 84 atributos e exclui `id`, `Flow ID`, `Src IP`, `Dst IP`, `Timestamp`, `Label` e `Attempted Category`. Portas e protocolo são mantidos. A seleção final de atributos permanece aberta.

| Medida | Linhas completas | Atributos de tráfego |
| --- | --- | --- |
| Registros comparados | 2.099.976 | 2.099.976 |
| Assinaturas distintas | 2.099.976 | 2.084.721 |
| Grupos repetidos | 0 | 6.854 |
| Repetições excedentes, descontada uma ocorrência por grupo | 0 | 15.255 |
| Registros em grupos repetidos | 0 | 22.109 |
| Maior grupo | 1 | 980 |
| Grupos em mais de um arquivo | 0 | 3.028 |
| Registros em grupos presentes em mais de um arquivo | 0 | 14.351 |
| Grupos com mais de um rótulo textual | 0 | 1 |
| Registros em grupos com mais de um rótulo textual | 0 | 2 |

| Arquivo | Repetições excedentes de linhas completas dentro do arquivo | Repetições excedentes de atributos dentro do arquivo |
| --- | --- | --- |
| monday.csv | 0 | 1.438 |
| tuesday.csv | 0 | 1.412 |
| wednesday.csv | 0 | 1.489 |
| thursday.csv | 0 | 4.653 |
| friday.csv | 0 | 1.548 |

Fluxos legítimos distintos podem ter atributos iguais. Rótulos diferentes nessa projeção podem decorrer da perda de contexto ao excluir endereços e horários. Os grupos sinalizam pontos de investigação e não provam, por si sós, erros de rotulagem. Nenhuma repetição foi removida.
| Assinatura SHA-256 | Registros | Rótulos e contagens | Localizações de exemplo |
| --- | --- | --- | --- |
| `1978a68878545bb9bb3d485218a2c19f29fc5e2541b05c779c101f0337de6cca` | 2 | Portscan (1), Infiltration - Portscan (1) | friday.csv, linha 321757, thursday.csv, linha 230651 |


## Cobertura temporal

Extremos de `Timestamp`, interpretados como ISO 8601 sem conversão de fuso. São horários de início registrados para os fluxos, não necessariamente o início efetivo dos ataques ou o horário dos últimos pacotes.

| Arquivo | Menor Timestamp | Maior Timestamp |
| --- | --- | --- |
| monday.csv | 2017-07-03 11:55:58.598308 | 2017-07-03 20:01:34.352593 |
| tuesday.csv | 2017-07-04 11:53:44.398274 | 2017-07-04 20:00:30.041663 |
| wednesday.csv | 2017-07-05 11:42:42.084372 | 2017-07-05 20:10:14.557249 |
| thursday.csv | 2017-07-06 11:59:00.490140 | 2017-07-06 20:04:36.513760 |
| friday.csv | 2017-07-07 11:59:50.315195 | 2017-07-07 20:02:40.977798 |


## Próximas decisões

- Definir a tarefa de classificação e o destino das categorias Attempted.
- Selecionar atributos compatíveis com o extrator do NIDS, preservando metadados para rastreabilidade.
- Investigar os valores inválidos e as repetições antes de estabelecer regras de tratamento.
- Definir a separação entre treino, validação e teste com base nas classes por dia e nas relações entre fluxos.
- Ajustar eventuais transformações somente com o treinamento e salvar os resultados em arquivos derivados separados.

## Método e reprodução

- Python 3.12.3, biblioteca padrão e GNU sort. Nenhuma dependência adicional foi instalada.
- Leitura sequencial, sem carregar todos os CSVs em memória. Assinaturas intermediárias foram ordenadas em disco temporário e removidas ao final.
- Ausentes numéricos incluem campos vazios, NA, N/A, null e None, sem distinção de maiúsculas e minúsculas. NaN é contado separadamente.
- Estatísticas numéricas utilizam valores finitos convertidos para float64 durante a inspeção. As assinaturas utilizam os textos originais dos campos.
- Tempo total da inspeção e verificação de integridade: 257.989 segundos. Este tempo não mede inferência nem TreeSHAP.
- SHA-256 do script executado: `cac17aa240f7140d91e62a988f88a848506ead5bedda2b4e11a4ce253f4a0061`.

Executar a partir da raiz do projeto.

```bash
python3 scripts/inspecionar_cicids2017.py
```

Os detalhes por arquivo e coluna, as combinações de categorias e rótulos e os hashes antes e depois estão em [inspecao-cicids2017.json](inspecao-cicids2017.json).

## Estatísticas numéricas por coluna

| Coluna | Finitos | Ausentes | NaN | +Infinito | -Infinito | Não numéricos | Zeros | Negativos | Mínimo finito | Máximo finito |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| id | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 547.557 |
| Src Port | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 2.113 | 0 | 0 | 65.535 |
| Dst Port | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 2.113 | 0 | 0 | 65.529 |
| Protocol | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.510 | 0 | 0 | 17 |
| Flow Duration | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 119.999.998 |
| Total Fwd Packet | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 33 | 0 | 0 | 219.759 |
| Total Bwd packets | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 55.069 | 0 | 0 | 291.922 |
| Total Length of Fwd Packet | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 306.391 | 0 | 0 | 12.870.252 |
| Total Length of Bwd Packet | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 331.914 | 0 | 0 | 655.452.323 |
| Fwd Packet Length Max | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 306.391 | 0 | 0 | 24.820 |
| Fwd Packet Length Min | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.095.798 | 0 | 0 | 1.472 |
| Fwd Packet Length Mean | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 306.391 | 0 | 0 | 5775.5 |
| Fwd Packet Length Std | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.267.213 | 0 | 0 | 7116.541297564128 |
| Bwd Packet Length Max | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 331.914 | 0 | 0 | 19.530 |
| Bwd Packet Length Min | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.108.156 | 0 | 0 | 1.983 |
| Bwd Packet Length Mean | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 331.914 | 0 | 0 | 4370.686524002315 |
| Bwd Packet Length Std | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.278.141 | 0 | 0 | 6715.738331213727 |
| Flow Bytes/s | 2.099.971 | 0 | 0 | 5 | 0 | 0 | 302.248 | 0 | 0 | 253.000.000 |
| Flow Packets/s | 2.099.971 | 0 | 0 | 5 | 0 | 0 | 0 | 0 | 0.0250000895836543 | 3.000.000 |
| Flow IAT Mean | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 69.000.029 |
| Flow IAT Std | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 492.711 | 0 | 0 | 84819214.85657084 |
| Flow IAT Max | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 119.999.735 |
| Flow IAT Min | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 81.243 | 0 | 0 | 69.000.029 |
| Fwd IAT Total | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 465.748 | 0 | 0 | 119.999.998 |
| Fwd IAT Mean | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 465.748 | 0 | 0 | 119.999.570 |
| Fwd IAT Std | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.168.321 | 0 | 0 | 83228041.45824479 |
| Fwd IAT Max | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 465.748 | 0 | 0 | 119.999.869 |
| Fwd IAT Min | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 504.665 | 0 | 0 | 119.999.570 |
| Bwd IAT Total | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 517.195 | 0 | 0 | 119.999.992 |
| Bwd IAT Mean | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 517.195 | 0 | 0 | 119.976.977 |
| Bwd IAT Std | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.270.754 | 0 | 0 | 84620454.91855389 |
| Bwd IAT Max | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 517.195 | 0 | 0 | 119.991.381 |
| Bwd IAT Min | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 528.557 | 0 | 0 | 119.976.977 |
| Fwd PSH Flags | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.310.129 | 0 | 0 | 5.520 |
| Bwd PSH Flags | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.321.609 | 0 | 0 | 9.761 |
| Fwd URG Flags | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 2.099.883 | 0 | 0 | 16 |
| Bwd URG Flags | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 2.099.975 | 0 | 0 | 2 |
| Fwd RST Flags | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.729.784 | 0 | 0 | 190 |
| Bwd RST Flags | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.842.041 | 0 | 0 | 12 |
| Fwd Header Length | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 2.146 | 309 | -32.708 | 32.748 |
| Bwd Header Length | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 55.174 | 472 | -32.764 | 32.680 |
| Fwd Packets/s | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 38 | 0 | 0 | 2.000.000 |
| Bwd Packets/s | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 55.069 | 0 | 0 | 2.000.000 |
| Packet Length Min | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.098.789 | 0 | 0 | 1.408 |
| Packet Length Max | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 302.248 | 0 | 0 | 24.820 |
| Packet Length Mean | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 302.248 | 0 | 0 | 2125.666666666667 |
| Packet Length Std | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 355.621 | 0 | 0 | 4693.160684645995 |
| Packet Length Variance | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 355.621 | 0 | 0 | 22025757.211906865 |
| FIN Flag Count | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.330.133 | 0 | 0 | 60 |
| SYN Flag Count | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.065.688 | 0 | 0 | 52 |
| RST Flag Count | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.489.320 | 0 | 0 | 190 |
| PSH Flag Count | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.306.029 | 0 | 0 | 9.861 |
| ACK Flag Count | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.038.656 | 0 | 0 | 511.681 |
| URG Flag Count | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 2.099.882 | 0 | 0 | 16 |
| CWR Flag Count | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 2.099.212 | 0 | 0 | 23 |
| ECE Flag Count | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 2.099.290 | 0 | 0 | 14 |
| Down/Up Ratio | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 55.102 | 0 | 0 | 16.928571428571427 |
| Average Packet Size | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 302.248 | 0 | 0 | 2125.6666666666665 |
| Fwd Segment Size Avg | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 306.391 | 0 | 0 | 5775.5 |
| Bwd Segment Size Avg | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 331.914 | 0 | 0 | 4370.6865240023135 |
| Fwd Bytes/Bulk Avg | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 2.012.997 | 0 | 0 | 1.827.185 |
| Fwd Packet/Bulk Avg | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 2.012.997 | 0 | 0 | 3.812 |
| Fwd Bulk Rate Avg | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 2.012.997 | 0 | 0 | 974.000.000 |
| Bwd Bytes/Bulk Avg | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.808.329 | 0 | 0 | 156.761.876 |
| Bwd Packet/Bulk Avg | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.808.329 | 0 | 0 | 58.270 |
| Bwd Bulk Rate Avg | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.808.329 | 0 | 0 | 1.369.000.000 |
| Subflow Fwd Packets | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 2.044.907 | 0 | 0 | 1 |
| Subflow Fwd Bytes | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 311.868 | 0 | 0 | 1.777 |
| Subflow Bwd Packets | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 2.099.943 | 0 | 0 | 1 |
| Subflow Bwd Bytes | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 333.378 | 0 | 0 | 2.090 |
| FWD Init Win Bytes | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.010.839 | 0 | 0 | 65.535 |
| Bwd Init Win Bytes | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.281.130 | 0 | 0 | 65.535 |
| Fwd Act Data Pkts | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 582.827 | 0 | 0 | 9.130 |
| Fwd Seg Size Min | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 9.368 | 0 | 0 | 44 |
| Active Mean | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.639.754 | 0 | 0 | 110.097.488 |
| Active Std | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.884.805 | 0 | 0 | 74154397.74458432 |
| Active Max | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.639.754 | 0 | 0 | 110.097.488 |
| Active Min | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.639.754 | 0 | 0 | 110.097.488 |
| Idle Mean | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.632.894 | 0 | 0 | 119.999.735 |
| Idle Std | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.879.586 | 0 | 0 | 76914831.60257196 |
| Idle Max | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.632.894 | 0 | 0 | 119.999.735 |
| Idle Min | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.632.894 | 0 | 0 | 119.999.735 |
| ICMP Code | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 117 | 2.099.373 | -1 | 10 |
| ICMP Type | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 41 | 2.099.373 | -1 | 11 |
| Total TCP Flow Time | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 1.001.205 | 0 | 0 | 30.290.439.669 |
| Attempted Category | 2.099.976 | 0 | 0 | 0 | 0 | 0 | 4.845 | 2.087.997 | -1 | 6 |

