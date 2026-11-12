"""Relatórios legíveis e figura das execuções do TreeSHAP."""

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

MODEL_NAMES = {"random-forest": "Random Forest", "xgboost": "XGBoost"}
SCALE_NAMES = {"probability": "probabilidade", "log-odds": "log-odds"}
CHECK_NAMES = {
    "feature_order": "Ordem dos atributos",
    "explained_class": "Classe explicada",
    "sum_identity": "Identidade da soma",
    "features_without_split": "Contribuição de atributos sem divisão",
    "reference_value_vs_hessian_weighted_leaves": "Valor de referência contra o cálculo do projeto",
}
TOP_FEATURES = 10
POSITIVE, NEGATIVE, AGGREGATE = "#e34948", "#2a78d6", "#a8a7a1"
SURFACE, TEXT, TEXT_SECONDARY, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"


def render_example(summary: dict[str, Any]) -> str:
    record, selection = summary["record"], summary["selection"]
    features = sorted(summary["features"], key=lambda item: abs(item["contribution"]), reverse=True)
    top, rest = features[:TOP_FEATURES], features[TOP_FEATURES:]
    total_abs = sum(abs(item["contribution"]) for item in features)
    positive = max(features, key=lambda item: item["contribution"])
    negative = min(features, key=lambda item: item["contribution"])
    zero = sum(1 for item in features if item["contribution"] == 0)
    sample = summary["pilot_sample"]
    predicted = "ataque" if summary["predicted_class"] == 1 else "benigno"
    tie = (" Como o número de registros é par, vale o menor dos dois registros centrais na ordem de "
           "probabilidade e de índice." if selection["candidates"] % 2 == 0 else "")
    lines = [
        "# Exemplo de explicação TreeSHAP no Random Forest piloto",
        "",
        "Este documento é um exercício de aprendizado e de integração inicial do TreeSHAP. Ele explica uma "
        "previsão do Random Forest piloto, que não é um dos modelos congelados, para um registro do conjunto de "
        "validação. A configuração do explicador segue a [decisão 7](../docs/decisoes.md), e os termos seguem o "
        "[glossário](../docs/glossario.md).",
        "",
        "## Registro explicado",
        "",
        f"O registro é o de índice {_integer(record['validation_index'])} da validação, com origem no arquivo "
        f"`{record['source_file']}`, `id` {_integer(record['id'])} e rótulo original {record['original_label']}. "
        f"Entre os {_integer(selection['candidates'])} registros {selection['original_label']} da validação que o "
        f"piloto classifica como ataque, ele tem a probabilidade de ataque mediana.{tie}",
        "",
        f"O piloto atribui a esse registro probabilidade de ataque {_decimal(summary['attack_probability'], 6)} e o "
        f"classifica como {predicted}, porque a classe é ataque quando a probabilidade é maior que 0,5.",
        "",
        "## Valor de referência e contribuições",
        "",
        "A saída explicada é a probabilidade de ataque. O valor de referência é "
        f"{_decimal(summary['reference_value'], 6)}. Ele é a média das saídas das folhas de cada árvore, ponderada "
        "pela cobertura do nó. No piloto, a cobertura do nó conta os sorteios da amostra bootstrap de cada árvore. "
        f"Essas amostras são retiradas de uma amostra de treino com {_integer(sample['records'])} registros, dos quais "
        f"{_integer(sample['attack'])} ({_decimal(100 * sample['attack'] / sample['records'], 2)}%) são ataques.",
        "",
        f"As 80 contribuições somam {_decimal(summary['contributions_sum'], 6)}. O valor de referência mais essa soma "
        f"reproduz a probabilidade de ataque com resíduo de {_scientific(summary['sum_identity']['residual'])}, "
        f"abaixo da tolerância de {_scientific(summary['sum_identity']['tolerance'])}. Uma contribuição positiva "
        "eleva a saída em relação ao valor de referência, e uma negativa a reduz. Cada contribuição é o valor de "
        "Shapley do atributo para este registro. Ela descreve o comportamento do modelo, e não uma relação causal "
        "no tráfego.",
        "",
        f"![Contribuições TreeSHAP do registro explicado]({summary['figure']})",
        "",
        "| Atributo | Valor no registro | Contribuição |",
        "|---|---:|---:|",
        *[f"| {item['name']} | {_decimal(item['value'], 4)} | {_signed(item['contribution'])} |" for item in top],
        f"| Demais {len(rest)} atributos | | {_signed(sum(item['contribution'] for item in rest))} |",
        "",
        f"Os {TOP_FEATURES} atributos da tabela concentram "
        f"{_decimal(100 * sum(abs(item['contribution']) for item in top) / total_abs, 1)}% da soma dos valores "
        f"absolutos das contribuições. A maior contribuição positiva é a de {positive['name']} "
        f"({_signed(positive['contribution'])}), e a maior contribuição negativa é a de {negative['name']} "
        f"({_signed(negative['contribution'])}). {zero} atributos têm contribuição zero.",
        "",
        "## Reprodução",
        "",
        "A partir de `src/`, com o ambiente descrito no [README](../src/README.md):",
        "",
        "```bash",
        "python main.py explicar-exemplo",
        "```",
        "",
        f"A configuração está em [{summary['config']}](../{summary['config']}). O registro da execução está em "
        f"[training-runs/tree-shap/exemplo/{summary['run_id']}/report.json]"
        f"(../training-runs/tree-shap/exemplo/{summary['run_id']}/report.json), com as 80 contribuições.",
        "",
    ]
    return "\n".join(lines)


def plot_example(summary: dict[str, Any], path: Path) -> None:
    features = sorted(summary["features"], key=lambda item: abs(item["contribution"]), reverse=True)
    top, rest = features[:TOP_FEATURES], features[TOP_FEATURES:]
    labels = [item["name"] for item in top] + [f"Demais {len(rest)} atributos"]
    values = [item["contribution"] for item in top] + [sum(item["contribution"] for item in rest)]
    labels, values = labels[::-1], values[::-1]
    figure, axis = plt.subplots(figsize=(8, 5.2), dpi=200)
    figure.patch.set_facecolor(SURFACE)
    axis.set_facecolor(SURFACE)
    positions = range(len(values))
    # O primeiro item da lista invertida é o agregado dos demais atributos, que não é um atributo.
    colors = [AGGREGATE if position == 0 else POSITIVE if value > 0 else NEGATIVE
              for position, value in zip(positions, values)]
    axis.barh(positions, values, height=0.55, color=colors, edgecolor=SURFACE, linewidth=2)
    axis.axvline(0, color=TEXT_SECONDARY, linewidth=1)
    span = max(abs(value) for value in values)
    for position, value in zip(positions, values):
        axis.text(value + (0.02 * span if value >= 0 else -0.02 * span), position, _signed(value),
                  va="center", ha="left" if value >= 0 else "right", fontsize=8, color=TEXT)
    axis.set_yticks(list(positions), labels, fontsize=8, color=TEXT)
    axis.set_xlim(-1.35 * span if min(values) < 0 else -0.1 * span, 1.35 * span)
    axis.tick_params(axis="x", labelsize=8, colors=TEXT_SECONDARY)
    axis.xaxis.grid(True, color=GRID, linewidth=0.8)
    axis.set_axisbelow(True)
    for side in ("top", "right", "left"):
        axis.spines[side].set_visible(False)
    axis.spines["bottom"].set_color(GRID)
    axis.set_xlabel("Contribuição para a probabilidade de ataque (vermelho eleva, azul reduz, cinza soma os demais)",
                    fontsize=8, color=TEXT_SECONDARY)
    axis.set_title(
        f"Valor de referência {_decimal(summary['reference_value'], 4)} + soma das contribuições "
        f"{_signed(summary['contributions_sum'], 4)} = P(ataque) {_decimal(summary['attack_probability'], 4)}",
        fontsize=9, color=TEXT, loc="left")
    figure.tight_layout()
    figure.savefig(path, facecolor=SURFACE)
    plt.close(figure)


def render_validation(summary: dict[str, Any]) -> str:
    sample, models = summary["sample"], summary["models"]
    result = "aprovada" if summary["passed"] else "reprovada"
    lines = [
        "# Verificação do TreeSHAP nos modelos congelados",
        "",
        f"A verificação foi {result}. Ela confere as explicações TreeSHAP dos dois modelos congelados em "
        f"{_integer(sample['records'])} registros da validação. A configuração do explicador segue a "
        "[decisão 7](../docs/decisoes.md), e os termos seguem o [glossário](../docs/glossario.md). "
        "O conjunto de teste não foi usado.",
        "",
        "## Resultado",
        "",
        "| Modelo | Verificação | Resíduo máximo | Tolerância | Resultado |",
        "|---|---|---:|---:|---|",
    ]
    for name, model in models.items():
        for check in model["checks"]:
            residual = _scientific(check["residual"]) if "residual" in check else check.get("detail", "")
            tolerance = _scientific(check["tolerance"]) if "tolerance" in check else ""
            lines.append(f"| {MODEL_NAMES[name]} | {CHECK_NAMES[check['name']]} | {residual} | {tolerance} | "
                         f"{'aprovada' if check['passed'] else 'reprovada'} |")
    lines += [
        "",
        "As tolerâncias são absolutas e foram fixadas na configuração antes da execução. Os resíduos estão na "
        "escala da saída explicada de cada modelo.",
        "",
        "## O que cada verificação compara",
        "",
        "- **Ordem dos atributos.** O número de atributos do classificador e das contribuições é igual ao das 80 "
        "entradas do manifesto de dados, na mesma ordem.",
        "- **Classe explicada.** O classificador tem as classes 0 e 1, nessa ordem, e o explicador devolve as "
        "contribuições da classe 1.",
        "- **Identidade da soma.** O valor de referência mais a soma das contribuições é comparado à saída "
        "explicada de cada registro.",
        "- **Contribuição de atributos sem divisão.** Todo atributo que nenhuma árvore usa em divisão deve ter "
        "contribuição exatamente zero.",
        "- **Valor de referência contra o cálculo do projeto.** No XGBoost, o valor de referência é comparado ao "
        "logit do `base_score` somado à média das folhas de cada árvore, ponderada pela soma das hessianas.",
        "",
        "## Modelos",
        "",
        "| Modelo | Escala | Saída comparada | Valor de referência | Atributos sem divisão |",
        "|---|---|---|---:|---:|",
    ]
    for name, model in models.items():
        lines.append(
            f"| {MODEL_NAMES[name]} | {SCALE_NAMES[model['scale']]} | `{model['output_call']}` | "
            f"{_decimal(model['reference_value'], 7)} | {len(model['features_without_split'])} de 80 |")
    lines += [""]
    if "independent_reference_value" in models.get("xgboost", {}):
        lines += [f"No XGBoost, o cálculo do projeto dá {_decimal(models['xgboost']['independent_reference_value'], 7)}.", ""]
    for name, model in models.items():
        unused = ", ".join(model["features_without_split"]) or "nenhum"
        lines.append(f"- Atributos sem divisão no {MODEL_NAMES[name]}: {unused}.")
    lines += [
        "",
        "## Limites da verificação",
        "",
        "- No XGBoost, as contribuições não são comparadas a `pred_contribs`, porque o `shap` as obtém dessa mesma "
        "chamada ao XGBoost.",
        "- A verificação dos atributos sem divisão só alcança os atributos listados acima.",
        "- A identidade da soma não distingue contribuições trocadas entre atributos. Os valores por atributo são "
        "conferidos nos testes unitários, por força bruta em modelos sintéticos, nas duas implementações.",
        "",
        "## Amostra",
        "",
        f"A amostra tem {_integer(sample['records'])} registros da validação, estratificados pelos rótulos "
        f"originais com semente {sample['seed']}. Cada rótulo entra com pelo menos {sample['minimum_per_label']} "
        "registros, ou com todos os que a validação tiver.",
        "",
        "| Rótulo original | Registros na amostra |",
        "|---|---:|",
        *[f"| {label} | {_integer(count)} |" for label, count in sample["original_labels"].items()],
        "",
        "## Reprodução",
        "",
        "A partir de `src/`, com o ambiente descrito no [README](../src/README.md):",
        "",
        "```bash",
        "python main.py validar-treeshap",
        "```",
        "",
        f"O registro da execução está em [training-runs/tree-shap/validacao/{summary['run_id']}/report.json]"
        f"(../training-runs/tree-shap/validacao/{summary['run_id']}/report.json). Os modelos são os de "
        f"[{summary['frozen_run']}](../{summary['frozen_run']}). As versões usadas foram "
        f"{_versions(summary['environment'])}.",
        "",
    ]
    return "\n".join(lines)


def render_measurement(summary: dict[str, Any]) -> str:
    measurement, models, cpu = summary["measurement"], summary["models"], summary["cpu_state"]
    governors = ", ".join(sorted({value for model in models.values() for value in model["scaling_governor"]}))
    lines = [
        "# Tempos isolados de inferência e de TreeSHAP",
        "",
        "Este relatório mede, fora do NIDS, a duração de chamadas isoladas ao classificador e ao explicador dos "
        "dois modelos congelados. Os tempos medidos são o tempo de inferência e o tempo de explicação, conforme o "
        "[glossário](../docs/glossario.md). Eles não são latência de classificação nem latência de explicação, "
        "porque não incluem a extração de atributos, filas nem a entrega dos resultados. A configuração do "
        "explicador segue a [decisão 7](../docs/decisoes.md).",
        "",
        "## Condições",
        "",
        f"- **Fluxos.** {_integer(measurement['flows'])} registros da validação, sorteados da amostra da "
        f"[execução de verificação aprovada](../{summary['validation_run']}/report.json).",
        f"- **Lotes.** {', '.join(str(size) for size in measurement['batch_sizes'])} fluxos por chamada. O lote 1 "
        "corresponde ao tempo de um fluxo.",
        f"- **Repetições.** {measurement['processes']} processos Python novos por classificador, cada um com "
        f"{measurement['passes']} passagens pelos fluxos depois de uma chamada de aquecimento de cada operação. A "
        "ordem dos classificadores alterna entre repetições.",
        f"- **CPU.** Cada processo fica fixo na CPU lógica {measurement['cpu']} desde o início. O regulador de "
        f"frequência registrado foi `{governors}`. A máquina estava ligada à tomada: "
        f"{'sim' if cpu['mains_power_online'] else 'não'}.",
        "- **Threads.** Os classificadores recebem `n_jobs=1` em memória, e o `threadpoolctl` limita as demais "
        "bibliotecas a uma thread. A razão entre tempo de CPU e tempo de relógio estima as threads ocupadas.",
        "- **Relógio.** `time.perf_counter_ns` mede a chamada ao classificador (`predict_proba`) e a chamada ao "
        "adaptador do explicador.",
        f"- **Ambiente.** {summary['environment']['cpu']}, {_versions(summary['environment'])}.",
        "",
        "No XGBoost, o `shap` delega o TreeSHAP ao próprio XGBoost, e o tempo de explicação inclui a construção de "
        "uma `DMatrix` a cada chamada. No Random Forest, o cálculo é feito pela extensão C do `shap`. A diferença "
        "entre os classificadores inclui a diferença entre as implementações.",
        "",
    ]
    for name, model in models.items():
        lines += [
            f"## {MODEL_NAMES[name]}",
            "",
            "| Operação | Lote | Chamadas | Mediana (ms) | p95 (ms) | p99 (ms) | Média (ms) | Média por fluxo (ms) | CPU/relógio |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for size, batch in model["batches"].items():
            for operation, label in (("inference", "Inferência"), ("explanation", "Explicação")):
                values = batch[operation]
                call = values["call_ns"]
                lines.append(
                    f"| {label} | {size} | {_integer(call['count'])} | {_ms(call['median'])} | {_ms(call['p95'])} | "
                    f"{_ms(call['p99'])} | {_ms(call['mean'])} | {_ms(values['per_flow_mean_ns'])} | "
                    f"{_decimal(values['cpu_to_wall_ratio'], 2)} |")
        first = model["batches"][str(measurement["batch_sizes"][0])]
        lines += [
            "",
            f"Medianas por processo no lote {measurement['batch_sizes'][0]}, em ms: inferência "
            f"{', '.join(_ms(value) for value in first['inference']['process_medians_ns'])}; explicação "
            f"{', '.join(_ms(value) for value in first['explanation']['process_medians_ns'])}.",
            "",
            "| Etapa por processo | Mediana entre processos (ms) | Mínimo (ms) | Máximo (ms) |",
            "|---|---:|---:|---:|",
            _stage_row("Carregamento verificado do modelo", model["load_ns"]),
            _stage_row("Construção do explicador", model["construction_ns"]),
            _stage_row("Aquecimento da inferência", [value["inference"] for value in model["warmup_ns"]]),
            _stage_row("Aquecimento da explicação", [value["explanation"] for value in model["warmup_ns"]]),
            "",
            f"Threads configuradas no classificador: {', '.join(str(v) for v in model['configured_threads'])}. "
            f"Threads do processo ao fim da medição: {', '.join(str(v) for v in model['os_threads'])}. "
            "Bibliotecas sob o `threadpoolctl`: "
            f"{'; '.join(f'{pool['internal_api']} ({pool['num_threads']})' for pool in model['threadpools']) or 'nenhuma'}.",
            "",
        ]
    lines += [
        "## Reprodução",
        "",
        "A partir de `src/`, com o ambiente descrito no [README](../src/README.md) e a máquina ligada à tomada:",
        "",
        "```bash",
        f"python main.py medir-treeshap --validacao ../{summary['validation_run']}",
        "```",
        "",
        f"O registro da execução, com os tempos de cada chamada, está em "
        f"[training-runs/tree-shap/medicao/{summary['run_id']}/](../training-runs/tree-shap/medicao/{summary['run_id']}/).",
        "",
    ]
    return "\n".join(lines)


def _stage_row(label: str, values: list[int]) -> str:
    ordered = sorted(values)
    middle = len(ordered) // 2
    median = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    return f"| {label} | {_ms(median)} | {_ms(ordered[0])} | {_ms(ordered[-1])} |"


def _versions(environment: dict[str, Any]) -> str:
    libraries = environment["libraries"]
    return f"Python {environment['python']}, " + ", ".join(f"{name} {libraries[name]}" for name in sorted(libraries))


def _integer(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _decimal(value: float, digits: int) -> str:
    return f"{value:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _signed(value: float, digits: int = 4) -> str:
    return ("+" if value > 0 else "") + _decimal(value, digits).replace("-", "−")


def _ms(nanoseconds: float) -> str:
    return _decimal(nanoseconds / 1e6, 3)


def _scientific(value: float) -> str:
    if value == 0:
        return "0"
    mantissa, exponent = f"{value:.1e}".split("e")
    superscript = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")
    return f"{mantissa.replace('.', ',')} × 10{str(int(exponent)).translate(superscript)}"
