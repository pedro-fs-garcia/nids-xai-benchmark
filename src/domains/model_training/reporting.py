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
