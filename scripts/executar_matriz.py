#!/usr/bin/env python3
"""Executa os ensaios de uma matriz (piloto ou campanha) na rede emulada, retomando de onde parou.

Executar com sudo e o Python do sistema, que tem o módulo do Mininet:

    sudo python3 scripts/executar_matriz.py --matriz configs/piloto-2.json --ate 07:00

A matriz lista os blocos de ensaios (src/domains/campaign/matrix.py). Cada célula é uma combinação de classificador,
configuração de explicação, nível de carga e repetição, e cada ensaio é feito por scripts/emular_trecho.py. O registro
da matriz fica em training-runs/matrizes/<nome>/registro.jsonl, com uma linha por tentativa, e nunca é reescrito.
Uma nova chamada com a mesma matriz pula as células já concluídas e repete as que falharam, até o número máximo de
tentativas. Um ensaio que falha fica registrado com o motivo, e a nova tentativa é outro ensaio, em outra pasta.

Com --ate, o executor não começa um ensaio que terminaria depois desse horário. O executor impede a suspensão da
máquina enquanto roda, com o systemd-inhibit. Um ensaio que não começou porque a máquina não ficou pronta volta
para o fim da fila, sem gastar tentativa, e o executor segue tentando até o horário do --ate.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS))

from emular_trecho import (FLOW_TIMEOUT_S, REPORT_PER_COPY_S, REPORT_S, ROOT, SETTLE_S, load_context, log,  # noqa: E402
                           run_trial_safely, sudo_owner)

from domains.campaign.matrix import append_registry, expand, read_matrix, read_registry, status, validity  # noqa: E402

INHIBITED = "MATRIZ_SEM_SUSPENSAO"


def main() -> int:
    arguments = parse_arguments()
    owner = sudo_owner()
    if owner is None:
        return 2
    if os.environ.get(INHIBITED) != "1":
        # O systemd-inhibit mantém a máquina acordada enquanto o executor roda, inclusive com a tampa fechada.
        os.environ[INHIBITED] = "1"
        os.execvp("systemd-inhibit", ["systemd-inhibit", "--what=sleep:idle:handle-lid-switch",
                                      "--who=nids-xai-benchmark", "--why=Ensaios do experimento", "--mode=block",
                                      sys.executable, *sys.argv])
    matrix_path = arguments.matriz.resolve()
    try:
        matrix = read_matrix(matrix_path)
        context = load_context(matrix["segment"], owner)
    except (OSError, ValueError, KeyError) as error:
        print(f"Não foi possível preparar a matriz: {error}", file=sys.stderr)
        return 1
    folder = ROOT / "training-runs" / "matrizes" / matrix["name"]
    folder.mkdir(parents=True, exist_ok=True)
    registry_path = folder / "registro.jsonl"
    cells = expand(matrix)
    situation = status(cells, read_registry(registry_path), matrix["max_attempts"])
    if situation["unknown_cells"]:
        print(f"O registro tem células fora da matriz: {situation['unknown_cells'][:5]}. Use outro nome de matriz.",
              file=sys.stderr)
        return 1
    queue = list(situation["pending"])
    replay_s = (context.segment["summary"]["last_packet_us"] - context.segment["summary"]["first_packet_us"]) / 1e6
    log(f"Matriz {matrix['name']}: {len(cells)} células, {len(situation['done'])} concluídas, "
        f"{len(situation['exhausted'])} sem novas tentativas e {len(queue)} a executar, cerca de "
        f"{sum(estimate_s(replay_s, cell.load) for cell, _ in queue) / 3600:.1f} h.")
    deadline = stop_time(arguments.ate) if arguments.ate else None
    while queue:
        cell, attempt = queue.pop(0)
        expected = estimate_s(replay_s, cell.load)
        if deadline is not None and datetime.now() + timedelta(seconds=expected) > deadline:
            log(f"O próximo ensaio terminaria depois de {arguments.ate}. A matriz para aqui, com {len(queue) + 1} "
                "ensaios a executar.")
            break
        log(f"Ensaio {cell.id}, tentativa {attempt}. Previsão de {expected / 60:.0f} min.")
        started = datetime.now(timezone.utc).isoformat()
        result = run_trial_safely(context, cell.model, cell.strategy, cell.criterion, cell.load, matrix["machine"],
                                  {**cell.as_dict(), "attempt": attempt, "matrix": matrix["name"]})
        replay, report = read_run(result.get("run_dir"))
        entry = {"cell": cell.as_dict(), "attempt": attempt, "started_utc": started,
                 "finished_utc": datetime.now(timezone.utc).isoformat(), "result": result,
                 "validity": validity(result, replay, report), "matrix": str(matrix_path.relative_to(ROOT))}
        append_registry(registry_path, entry)
        for path in (registry_path, folder, folder.parent):
            os.chown(path, *owner)
        print(json.dumps({"cell": cell.id, "attempt": attempt, "run_dir": result.get("run_dir"),
                          "valid": entry["validity"]["valid"], "reasons": entry["validity"]["reasons"]},
                         ensure_ascii=False), flush=True)
        if not result.get("started", True):
            # O ensaio volta para o fim da fila, sem gastar tentativa. O executor só para no horário do --ate.
            log("A máquina não ficou pronta. O ensaio volta para o fim da fila.")
            queue.append((cell, attempt))
            continue
        if not entry["validity"]["valid"]:
            log("Ensaio inválido: " + "; ".join(entry["validity"]["reasons"]) + ".")
            if attempt < matrix["max_attempts"]:
                queue.append((cell, attempt + 1))
    final = status(cells, read_registry(registry_path), matrix["max_attempts"])
    log(f"Matriz {matrix['name']}: {len(final['done'])} de {len(cells)} células concluídas, "
        f"{len(final['exhausted'])} sem novas tentativas e {len(final['pending'])} pendentes.")
    return 0 if not final["pending"] and not final["exhausted"] else 1


def estimate_s(replay_s: float, copies: int) -> float:
    """Duração prevista de um ensaio: reprodução, espera da varredura, encerramento e verificações."""
    return replay_s + FLOW_TIMEOUT_S + 2 + SETTLE_S + 60 + REPORT_S + REPORT_PER_COPY_S * copies


def stop_time(text: str) -> datetime:
    """Próxima ocorrência do horário dado, hoje ou amanhã."""
    hour, minute = (int(part) for part in text.split(":"))
    now = datetime.now()
    moment = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return moment if moment > now else moment + timedelta(days=1)


def read_run(run_dir: str | None) -> tuple[dict | None, dict | None]:
    if not run_dir or run_dir == "None":
        return None, None
    folder = Path(run_dir)
    loaded = []
    for name in ("replay.json", "report.json"):
        path = folder / name
        loaded.append(json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None)
    return loaded[0], loaded[1]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--matriz", type=Path, required=True, help="Configuração da matriz, em configs/.")
    parser.add_argument("--ate", help="Horário, no formato HH:MM, depois do qual nenhum ensaio deve terminar.")
    arguments = parser.parse_args()
    if arguments.ate is not None:
        try:
            stop_time(arguments.ate)
        except ValueError:
            parser.error("--ate deve estar no formato HH:MM.")
    return arguments


if __name__ == "__main__":
    sys.exit(main())
