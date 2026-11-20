"""Relatório legível da auditoria de uma matriz de ensaios."""

from collections import Counter
from typing import Any

from domains.campaign.reporting import CONFIGURATION_NAMES, MODEL_NAMES, _integer, _percent

SCOPES = {"todas": "igual em todas", "por classificador": "igual por classificador", "por carga": "igual por carga"}


def render_audit(summary: dict[str, Any]) -> str:
    coverage, exclusions = summary["coverage"], summary["exclusions"]
    lines = [
        f"# Auditoria da matriz `{summary['matrix']}`",
        "",
        "A auditoria confere a matriz prevista contra o registro, a coerência entre cada tentativa registrada e os "
        "registros da execução, o envio de todos os pacotes de cada cópia, o encerramento do extrator a pedido do "
        "NIDS, a integridade e a recontagem dos arquivos brutos de cada execução válida, a validação por cópia feita "
        "pela análise mais recente da matriz e as entradas fixas das execuções válidas. Os termos seguem o "
        "[glossário](../docs/glossario.md).",
        "",
        f"**Resultado.** A auditoria {'aprovou' if summary['passed'] else 'não aprovou'} a matriz. "
        f"{coverage['done']} das {summary['cells']} células têm uma execução válida, "
        f"{len(coverage['exhausted'])} esgotaram as tentativas e {len(coverage['pending'])} estão pendentes. "
        f"O registro tem {summary['attempts']} tentativas, das quais {coverage['not_started']} não começaram. "
        f"A auditoria encontrou {len(summary['problems'])} problemas e {len(summary['pending_checks'])} conferências "
        "pendentes.",
        "",
        "## Problemas",
        "",
        *([f"- {problem}" for problem in summary["problems"]] or ["Nenhum."]),
        "",
        "## Conferências pendentes",
        "",
    ]
    pending = Counter(item.split(": ", 1)[-1] for item in summary["pending_checks"])
    lines += [f"- {check}: {count} execuções." for check, count in sorted(pending.items())] or ["Nenhuma."]
    if summary["analysis"] is None:
        lines += ["", "A matriz ainda não tem análise, e a validação por cópia vem da análise."]
    else:
        lines += ["", f"A validação por cópia vem da análise `{summary['analysis']['run']}`, que cobriu "
                      f"{summary['analysis']['attempts']} tentativas."]
    lines += [
        "",
        "## Exclusões",
        "",
        "Uma tentativa inválida fica registrada com o motivo, e a tentativa seguinte da mesma célula é outra "
        "execução. Uma execução fora do registro foi interrompida antes do fim e não entra na análise.",
        "",
    ]
    if exclusions["invalid"]:
        lines += ["| Célula | Tentativa | Motivo | Tentativa seguinte |", "|---|---:|---|---|"]
        for item in exclusions["invalid"]:
            following = item["replaced_by"]
            lines.append(f"| `{item['cell']}` | {item['attempt']} | {'; '.join(item['reasons'])} | "
                         + ("nenhuma" if following is None else
                            f"{following['attempt']}, {'válida' if following['valid'] else 'inválida'}") + " |")
    else:
        lines.append("Nenhuma tentativa inválida.")
    lines.append("")
    if exclusions["orphans"]:
        lines += ["| Execução fora do registro | Célula | Tentativa | Início da reprodução (UTC) | "
                  "Reprodução terminou |",
                  "|---|---|---:|---|---|"]
        lines += [f"| `{item['run_dir']}` | `{item['cell']}` | {item['attempt']} | {item['replay_started_utc']} | "
                  f"{'sim' if item['replay_finished'] else 'não'} |" for item in exclusions["orphans"]]
    else:
        lines.append("Nenhuma execução fora do registro.")
    if exclusions["exhausted"]:
        lines += ["", "Células sem novas tentativas: " + ", ".join(f"`{cell}`" for cell in exclusions["exhausted"])
                  + "."]
    lines += [
        "",
        "## Perdas na captura",
        "",
        "Uma execução com pacotes perdidos na captura continua válida "
        "([decisão 22](../docs/decisoes.md#22-validade-das-execuções-e-número-de-tentativas)). A validação por cópia "
        "dessa execução reprova, porque exige que nenhum pacote se perca na captura e que o extrator leia todos os "
        "pacotes recebidos pela interface. Quando só essas duas verificações falham e os pacotes perdidos fecham a "
        "diferença entre os recebidos e os lidos, a auditoria registra a reprovação como explicada pela perda, sem "
        "contá-la como problema.",
        "",
    ]
    if summary["capture_loss"]:
        lines += ["| Célula | Tentativa | Pacotes perdidos | Fluxos com entradas diferentes | Previsões diferentes | "
                  "Validação por cópia |", "|---|---:|---:|---:|---:|---|"]
        for item in summary["capture_loss"]:
            validation = item["validation"] or {}
            compared = validation.get("flows_compared")
            different = validation.get("flows_with_different_inputs")
            share = "" if not compared or different is None else f" ({_percent(different / compared)})"
            lines.append(f"| {_cell(item['cell'])} | {item['attempt']} | {_integer(item['capture_lost_packets'])} | "
                         f"{_integer(different)}{share} | {_integer(validation.get('predictions_differing'))} | "
                         f"{validation.get('status', '—')} |")
    else:
        lines.append("Nenhuma execução válida perdeu pacotes na captura.")
    lines += [
        "",
        "## Execuções válidas",
        "",
        "Os fluxos, os selecionados e os explicados vêm da recontagem da tabela por fluxo e da tabela de explicações, "
        "depois da conferência do hash de cada arquivo.",
        "",
        "| Célula | Tentativa | Fluxos | Selecionados | Explicados | Validação por cópia | Problemas |",
        "|---|---:|---:|---:|---:|---|---:|",
    ]
    for trial in summary["trials"]:
        if not trial["valid"]:
            continue
        counted = trial["recount"] or {}
        lines.append(f"| {_cell(trial['cell'])} | {trial['attempt']} | {_integer(counted.get('received'))} | "
                     f"{_integer(counted.get('selected'))} | {_integer(counted.get('completed'))} | "
                     f"{(trial['validation'] or {}).get('status', '—')} | {len(trial['issues']) or 'nenhum'} |")
    inputs = summary["fixed_inputs"]
    lines += [
        "",
        "## Entradas fixas",
        "",
        "| Entrada | Regra | Situação |",
        "|---|---|---|",
        *[f"| `{row['input']}` | {SCOPES[row['scope']]} | "
          f"{'igual' if row['equal'] else str(row['distinct']) + ' valores'} |" for row in inputs["rows"]],
        "",
        "Commits das execuções: " + ", ".join(f"`{commit}`" for commit in inputs["git"]["commits"]) + ".",
        "",
        "Arquivos versionados alterados durante as execuções: "
        + (", ".join(f"`{path}`" for path in inputs["git"]["modified_tracked_files"]) or "nenhum") + ".",
        "",
        "## Reprodução",
        "",
        "```bash",
        f"cd src && python main.py campanha-auditar --matriz ../{summary['matrix_config']}",
        "```",
        "",
        f"O registro dos ensaios está em `{summary['registry']}`, e o da auditoria, em "
        f"`training-runs/nids/auditoria-{summary['matrix']}/{summary['run_id']}/report.json`.",
        "",
    ]
    return "\n".join(lines)


def _cell(cell: dict[str, Any]) -> str:
    return (f"{MODEL_NAMES[cell['model']]}, {CONFIGURATION_NAMES[cell['configuration']]}, {cell['load']}× "
            f"(rep. {cell['repetition']})")
