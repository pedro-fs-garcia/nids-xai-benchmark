import json

import pytest

from domains.campaign.matrix import Cell, append_registry, expand, read_matrix, read_registry, status, validity


def _matrix(**changes):
    matrix = {
        "name": "teste", "segment": "curto", "seed": 7,
        "machine": {"require_mains": True, "max_busy_share": 0.1, "min_available_mib": 1, "window_s": 1,
                    "max_wait_s": 1},
        "max_attempts": 2,
        "blocks": [
            {"label": "a", "models": ["random-forest", "xgboost"], "configurations": ["sem-xai", "assincrono"],
             "loads": [1, 4], "repetitions": 2},
            {"label": "b", "models": ["xgboost"], "configurations": ["sincrono-condicional-incerteza"],
             "loads": [8], "repetitions": 1},
        ],
    }
    matrix.update(changes)
    return matrix


def _write(tmp_path, matrix):
    path = tmp_path / "matriz.json"
    path.write_text(json.dumps(matrix))
    return path


def test_each_repetition_holds_every_combination_in_a_seeded_order(tmp_path):
    cells = expand(read_matrix(_write(tmp_path, _matrix())))
    assert len(cells) == 2 * 2 * 2 * 2 + 1
    first, second = cells[:8], cells[8:16]
    assert {cell.repetition for cell in first} == {1} and {cell.repetition for cell in second} == {2}
    combinations = lambda group: {(c.model, c.configuration, c.load) for c in group}  # noqa: E731
    assert combinations(first) == combinations(second) and len(combinations(first)) == 8
    assert cells == expand(_matrix())
    assert cells[-1] == Cell("b", "xgboost", "sincrono-condicional-incerteza", 8, 1)
    assert cells[-1].strategy == "sincrono-condicional" and cells[-1].criterion == "incerteza"
    assert expand(_matrix(seed=8)) != cells


def test_a_value_not_yet_fixed_refuses_the_matrix(tmp_path):
    matrix = _matrix()
    matrix["blocks"][0]["loads"] = None
    with pytest.raises(ValueError, match="não fixados"):
        read_matrix(_write(tmp_path, matrix))
    matrix["blocks"][0]["loads"] = [1, None]
    with pytest.raises(ValueError, match="não fixados"):
        read_matrix(_write(tmp_path, matrix))
    with pytest.raises(ValueError, match="Configurações"):
        read_matrix(_write(tmp_path, _matrix(blocks=[{**_matrix()["blocks"][0], "configurations": ["outra"]}])))


def _entry(cell, attempt, valid, started=True):
    return {"cell": cell.as_dict(), "attempt": attempt, "result": {"started": started},
            "validity": {"valid": valid, "reasons": [] if valid else ["falhou"]}}


def test_status_resumes_from_the_registry_and_limits_attempts(tmp_path):
    cells = expand(_matrix())
    path = tmp_path / "registro.jsonl"
    append_registry(path, _entry(cells[0], 1, True))
    append_registry(path, _entry(cells[1], 1, False))
    append_registry(path, _entry(cells[2], 1, False))
    append_registry(path, _entry(cells[2], 2, False))
    append_registry(path, _entry(cells[3], 1, False, started=False))
    registry = read_registry(path)
    assert len(registry) == 4 + 1
    situation = status(cells, registry, max_attempts=2)
    assert situation["done"] == [cells[0]] and situation["exhausted"] == [cells[2]]
    pending = dict(situation["pending"])
    assert pending[cells[1]] == 2 and pending[cells[3]] == 1 and len(pending) == len(cells) - 2
    assert status(cells[1:], registry, 2)["unknown_cells"] == [cells[0].id]


def test_drops_are_results_but_a_failed_run_or_a_power_loss_is_not_valid():
    good = {"tcpreplay": {"failed": 0, "exit_code": 0}, "machine": {"mains_online_in_every_sample": True}}
    assert validity({"exit_code": 0}, good, {"passed": True}) == {"valid": True, "reasons": []}
    unplugged = {**good, "machine": {"mains_online_in_every_sample": False}}
    assert not validity({"exit_code": 0}, unplugged, {"passed": True})["valid"]
    assert not validity({"exit_code": 1, "error": "x"}, good, {"passed": True})["valid"]
    assert not validity({"exit_code": 0}, good, None)["valid"]
    assert not validity({"started": False, "exit_code": 1}, None, None)["valid"]
