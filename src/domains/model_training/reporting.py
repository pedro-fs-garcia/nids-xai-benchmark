"""Relatório legível produzido a partir das medidas do treinamento."""

from typing import Any


def render_pilot_report(summary: dict[str, Any]) -> str:
    config = summary["configuration"]
    metrics = summary["validation"]["metrics"]
    matrix = metrics["confusion_matrix"]
    resources = summary["resources"]
    complexity = summary["complexity"]
    lines = [
        "# Treinamento preliminar do Random Forest",
        "",
        f"O modelo foi treinado com {_integer(summary['sample']['records'])} registros do conjunto de treino "
        f"e avaliado nos {_integer(summary['validation']['records'])} registros do conjunto de validação. "
        "Esta avaliação orienta a escolha da configuração do classificador. O conjunto de teste permanece reservado.",
        "",
        "## Dados e configuração",
        "",
        "A amostra foi extraída sem reposição e de forma proporcional aos rótulos originais. "
        "Cada rótulo recebeu pelo menos um registro. Os arquivos sample_indices.npy e sample_origin.npy "
        "identificam, respectivamente, as posições no treino e a origem dos registros usados.",
        "",
        f"A amostragem usou a semente {config['sample_seed']}. O modelo recebeu as 80 entradas "
        "do [dicionário de atributos](../docs/dicionario-atributos.md), sem seleção adicional nem normalização. "
        "Os rótulos seguem o [mapeamento binário aprovado](../docs/decisoes.md).",
        "",
        "| Parâmetro | Valor |",
        "|---|---|",
    ]
    for key, value in config["model"].items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend([
        "",
        "O tamanho da amostra reduz o custo desta primeira execução. O número de árvores, "
        "o limite de profundidade e o mínimo de registros por folha limitam a complexidade. "
        "Esta configuração ainda será comparada a outras.",
        "",
        "## Avaliação na validação",
        "",
        "A classe positiva é ataque. A previsão é ataque quando a probabilidade fornecida pelo modelo "
        "é maior que 0,5; empates recebem a classe benigno. O limiar não foi ajustado nesta avaliação.",
        "",
        "| Classe real | Previsto benigno | Previsto ataque |",
        "|---|---:|---:|",
        f"| Benigno | {_integer(matrix['tn'])} | {_integer(matrix['fp'])} |",
        f"| Ataque | {_integer(matrix['fn'])} | {_integer(matrix['tp'])} |",
        "",
        "Precisão é a parcela das previsões de ataque que corresponde a ataques. Recall é a parcela "
        "dos ataques identificada pelo modelo. F1 é a média harmônica entre precisão e recall. "
        "A taxa de falsos positivos é a parcela dos registros benignos classificada como ataque. "
        "ROC-AUC é a área sob a curva que relaciona recall e taxa de falsos positivos ao variar o limiar.",
        "",
        "| Métrica | Valor |",
        "|---|---:|",
        f"| Acurácia | {_decimal(metrics['accuracy'])} |",
        f"| Precisão | {_decimal(metrics['precision'])} |",
        f"| Recall | {_decimal(metrics['recall'])} |",
        f"| F1 | {_decimal(metrics['f1'])} |",
        f"| Taxa de falsos positivos | {_decimal(metrics['false_positive_rate'])} |",
        f"| ROC-AUC | {_decimal(metrics['roc_auc'])} |",
        "",
        "A tabela abaixo mostra as previsões por rótulo original. Para os rótulos de ataque, "
        "a coluna final conta os ataques detectados. Para BENIGN e Attempted, ela conta falsos positivos.",
        "",
        "| Rótulo original | Registros na amostra | Registros na validação | Previstos como ataque na validação |",
        "|---|---:|---:|---:|",
    ])
    for label, info in summary["validation"]["by_original_label"].items():
        lines.append(
            f"| {label} | {_integer(summary['sample']['original_labels'][label])} | "
            f"{_integer(info['records'])} | {_integer(info['predicted_attack'])} |"
        )
    undetected = [
        f"{label} ({info['records']} registros)"
        for label, info in summary["validation"]["by_original_label"].items()
        if info["class"] == "attack" and info["records"] > 0 and info["predicted_attack"] == 0
    ]
    if undetected:
        lines.extend([
            "",
            "O modelo não detectou nenhum ataque dos seguintes rótulos na validação: "
            + "; ".join(undetected) + ". O resultado agregado deve ser lido junto dessas contagens.",
        ])
    lines.extend([
        "",
        "## Custo e complexidade",
        "",
        f"O ajuste do modelo levou {_decimal(resources['fit_seconds'], 3)} s. A avaliação de toda a validação, "
        f"incluindo o cálculo das métricas, levou {_decimal(resources['validation_seconds'], 3)} s. "
        "Esses tempos descrevem processamento em lote e não medem a latência do NIDS.",
        "",
        f"O pico de memória residente do processo foi {_decimal(resources['peak_process_memory_mib'], 1)} MiB "
        "(1 MiB = 1.048.576 bytes). A medida inclui leitura, verificações, treinamento e avaliação; "
        "não isola a memória do ajuste. O tempo total do comando foi "
        f"{_decimal(resources['elapsed_seconds'], 3)} s até a geração do relatório.",
        "",
        f"As {complexity['trees']} árvores têm profundidade máxima {complexity['depth_max']}, "
        f"{_integer(complexity['nodes_total'])} nós e {_integer(complexity['leaves_total'])} folhas ao todo.",
        "",
        f"Máquina: {summary['environment']['cpu']}; "
        f"{summary['environment']['logical_cpus']} processadores lógicos. "
        f"Sistema: {summary['environment']['platform']}. Python {summary['environment']['python']}.",
        "",
        "Versões: " + ", ".join(f"{name} {v}" for name, v in summary['environment']['libraries'].items()) + ".",
        "",
        "## Reprodução e artefatos",
        "",
        "A partir de `src/`, execute:",
        "",
        "```bash",
        "python main.py treinar-rf-piloto",
        "```",
        "",
        f"Os artefatos desta execução estão em [training-runs/random-forest-pilot/{summary['run_id']}/]"
        f"(../training-runs/random-forest-pilot/{summary['run_id']}/). "
        "O arquivo report.json registra os parâmetros completos, os hashes dos arquivos e a ordem das entradas. "
        "O modelo está em model.joblib. As previsões e probabilidades da validação estão em arquivos NumPy, "
        "na ordem dos registros de X_validation.npy.",
        "",
        f"SHA-256 do manifesto dos dados: `{summary['data_manifest_sha256']}`.",
        "",
        "## Alcance da avaliação",
        "",
        "Os resultados se referem a uma única configuração, treinada em uma amostra. "
        "A seleção do Random Forest final exige comparar configurações usando treino e validação. "
        "Os rótulos raros têm poucos exemplos e suas contagens devem acompanhar qualquer interpretação. "
        "Fluxos da mesma conexão podem ocorrer no treino e na validação, conforme os limites registrados "
        "na decisão de separação dos dados.",
        "",
    ])
    return "\n".join(lines)


def _integer(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _decimal(value: float, digits: int = 6) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def render_forest_comparison_report(summary: dict[str, Any]) -> str:
    selection = summary["selection"]
    final = summary["final"]
    candidates = selection["candidates"]
    xgboost = summary.get("algorithm") == "xgboost"
    title = "XGBoost" if xgboost else "Random Forest"
    kind = "xgboost-comparison" if xgboost else "random-forest-comparison"
    command = "treinar-xgboost" if xgboost else "comparar-rf"
    sample_use = (
        "As três configurações do XGBoost foram treinadas nesta execução. A referência do Random Forest "
        "fornece apenas a amostra, sem usar suas métricas para escolher o XGBoost."
        if xgboost else
        "O resultado da configuração de referência foi reutilizado; as outras duas configurações foram treinadas nesta execução."
    )
    parameters_description = (
        "taxa de aprendizagem 0,1, semente 42 e dois trabalhadores. O método hist agrupa valores dos "
        "atributos em intervalos para construir os cortes das árvores e executa em CPU. "
        "Não houve normalização, ponderação de classes, parada antecipada nem ajuste do limiar. "
        "A taxa de aprendizagem limita a contribuição de cada árvore "
        "([parâmetros do XGBoost](https://xgboost.readthedocs.io/en/stable/parameter.html))."
        if xgboost else
        "mínimo de dois registros por folha, semente 42 e dois trabalhadores. "
        "Não houve normalização, ponderação de classes nem ajuste do limiar."
    )
    explanation = []
    if xgboost:
        example = summary["prediction_example"]
        explanation = [
            "## Como o modelo produz a previsão",
            "",
            "O XGBoost constrói as árvores em sequência. Cada árvore ajusta a previsão do conjunto "
            "já construído. Na classificação binária, o modelo soma os escores das árvores ao escore inicial "
            "e transforma o resultado em uma probabilidade pela função logística, "
            "P(ataque) = 1 / (1 + exp(−s)), em que s é o escore total "
            "([Introduction to Boosted Trees](https://xgboost.readthedocs.io/en/stable/tutorials/model.html)).",
            "",
            f"No primeiro registro da validação, o modelo final produziu o escore "
            f"{_decimal(example['score'])}. A função logística fornece {_decimal(example['logistic_of_score'])}, "
            f"e predict_proba retorna {_decimal(example['probability'])}. "
            f"A previsão binária foi {example['prediction']}, sendo 0 benigno e 1 ataque. "
            "O arquivo report.json registra a origem desse exemplo.",
            "",
        ]
    lines = [
        f"# Seleção e avaliação do {title}",
        "",
        f"Foram comparadas três configurações na mesma amostra de {_integer(summary['sample_records'])} "
        "registros de treino e no mesmo conjunto de validação. Variaram apenas o número de árvores "
        "e a profundidade máxima. A configuração escolhida foi treinada com todo o conjunto de treino "
        "antes da avaliação final no teste reservado.",
        "",
        *explanation,
        "## Comparação na amostra",
        "",
        f"A amostra é a mesma do primeiro treinamento, com semente {summary['sample_seed']} e pelo menos "
        "um registro de cada rótulo original. Os arquivos sample_indices.npy e sample_origin.npy "
        "identificam seus registros. " + sample_use,
        "",
        "A alternativa com menos árvores verifica se o número de árvores pode ser reduzido mantendo "
        "a qualidade das previsões. A alternativa com menor profundidade verifica o mesmo efeito "
        "ao limitar o tamanho das árvores. Todas usam as 80 entradas do "
        "[dicionário de atributos](../docs/dicionario-atributos.md), " + parameters_description,
        "",
        "O critério foi definido antes da comparação: maior F1 na validação. Em caso de empate, "
        "menos nós e, depois, menos árvores. F1 é a média harmônica entre precisão e recall. "
        "Precisão é a proporção de previsões de ataque corretas; recall é a proporção dos ataques detectados.",
        "",
        "| Configuração | Árvores | Profundidade máxima | Nós | Precisão | Recall | F1 | Ajuste (s) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for entry in candidates:
        model, metrics, complexity = entry["parameters"], entry["metrics"], entry["complexity"]
        lines.append(
            f"| {entry['name']} | {model['n_estimators']} | {model['max_depth']} | "
            f"{_integer(complexity['nodes_total'])} | {_decimal(metrics['precision'])} | "
            f"{_decimal(metrics['recall'])} | {_decimal(metrics['f1'])} | {_decimal(entry['fit_seconds'], 2)} |"
        )
    lines.extend([
        "",
        f"A configuração selecionada foi **{selection['selected']}**. Os tempos correspondem a uma execução "
        "por configuração e incluem apenas o ajuste. Servem para descrever o custo observado, sem "
        "estabelecer uma comparação estatística de desempenho computacional. O custo do TreeSHAP ainda será medido.",
        "",
        "## Treinamento completo e teste reservado",
        "",
        f"A configuração escolhida foi treinada com os {_integer(final['training_records'])} registros "
        f"do treino. O ajuste levou {_decimal(final['fit_seconds'], 2)} s. "
        "As escolhas foram registradas em selection.json antes desse ajuste. O modelo e seus parâmetros "
        "foram salvos antes de abrir os arquivos do teste, com registro em fixed-before-test.json. "
        "Os resultados do teste não foram usados para alterar a configuração.",
        "",
        "A classe positiva é ataque. O modelo prevê ataque se a probabilidade for maior que 0,5; "
        "empates recebem a classe benigno. O mapeamento de rótulos e a separação dos conjuntos seguem "
        "as [decisões do desenho experimental](../docs/decisoes.md).",
        "",
        "| Métrica | Validação após treino completo | Teste reservado |",
        "|---|---:|---:|",
    ])
    titles = {
        "accuracy": "Acurácia", "precision": "Precisão", "recall": "Recall", "f1": "F1",
        "false_positive_rate": "Taxa de falsos positivos", "roc_auc": "ROC-AUC",
    }
    for key, title in titles.items():
        lines.append(f"| {title} | {_decimal(final['validation']['metrics'][key])} | {_decimal(final['test']['metrics'][key])} |")
    test = final["test"]
    matrix = test["metrics"]["confusion_matrix"]
    lines.extend([
        "",
        "Acurácia é a proporção de previsões corretas. A taxa de falsos positivos é a proporção "
        "dos benignos classificada como ataque. ROC-AUC é a área sob a curva que relaciona recall e "
        "taxa de falsos positivos ao variar o limiar.",
        "",
        f"O teste tem {_integer(test['records'])} registros, sendo {_integer(test['benign'])} benignos "
        f"e {_integer(test['attack'])} ataques. Sua matriz de confusão é:",
        "",
        "| Classe real | Previsto benigno | Previsto ataque |",
        "|---|---:|---:|",
        f"| Benigno | {_integer(matrix['tn'])} | {_integer(matrix['fp'])} |",
        f"| Ataque | {_integer(matrix['fn'])} | {_integer(matrix['tp'])} |",
        "",
        "## Erros por rótulo original",
        "",
        "A classe benigno predomina nos conjuntos. Por isso, as métricas agregadas são acompanhadas "
        "das contagens por rótulo. Para os rótulos de ataque, a última coluna conta ataques detectados; "
        "para BENIGN e Attempted, conta falsos positivos.",
        "",
        "| Rótulo original | Registros na validação | Previstos ataque na validação | Registros no teste | Previstos ataque no teste |",
        "|---|---:|---:|---:|---:|",
    ])
    for label, info in test["by_original_label"].items():
        val = final["validation"]["by_original_label"][label]
        lines.append(
            f"| {label} | {_integer(val['records'])} | {_integer(val['predicted_attack'])} | "
            f"{_integer(info['records'])} | {_integer(info['predicted_attack'])} |"
        )
    complexity = final["complexity"]
    lines.extend([
        "",
        "Rótulos raros têm poucos exemplos, o que limita a interpretação das taxas por tipo de ataque. "
        "A divisão impede entradas idênticas entre conjuntos, mas permite fluxos da mesma conexão "
        "em conjuntos diferentes, conforme os limites registrados no desenho experimental. "
        "A escolha de configuração foi feita na amostra; somente a escolhida recebeu treinamento completo.",
        "",
        "## Artefatos e reprodução",
        "",
        f"O modelo final tem {complexity['trees']} árvores, profundidade máxima observada "
        f"{complexity['depth_max']}, {_integer(complexity['nodes_total'])} nós e "
        f"{_integer(complexity['leaves_total'])} folhas. O pico de memória residente do processo "
        f"foi {_decimal(summary['resources']['peak_process_memory_mib'], 1)} MiB "
        "(1 MiB = 1.048.576 bytes), considerando comparação, treinamento completo e avaliação.",
        "",
        f"Os artefatos estão em [training-runs/{kind}/{summary['run_id']}/]"
        f"(../training-runs/{kind}/{summary['run_id']}/). "
        "final/model.joblib contém o modelo e a ordem das entradas. report.json registra todos os parâmetros, "
        "as sementes, os hashes e as métricas. Os arquivos de previsões seguem a ordem dos conjuntos derivados.",
        "",
        "Versões: Python " + summary["environment"]["python"] + "; "
        + ", ".join(f"{name} {value}" for name, value in summary["environment"]["libraries"].items()) + ".",
        "",
        f"SHA-256 do manifesto dos dados: `{summary['data_manifest_sha256']}`.",
        "",
        "A partir de src/, o comando abaixo reproduz a comparação. Ele depende dos dados derivados "
        f"e dos artefatos do treinamento de referência indicados em configs/{kind}.json.",
        "",
        "```bash",
        f"python main.py {command}",
        "```",
        "",
    ])
    if xgboost:
        lines.extend([
            "O modelo também está salvo no formato nativo em final/model.ubj. "
            "final/booster-config.json registra a configuração efetiva do XGBoost, incluindo seus padrões.",
            "",
        ])
    return "\n".join(lines)
