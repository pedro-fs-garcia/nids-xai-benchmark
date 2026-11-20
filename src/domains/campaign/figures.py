"""Figuras dos resultados de uma matriz executada."""

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter  # noqa: E402

from domains.campaign.reporting import _decimal  # noqa: E402
from domains.campaign.results_reporting import CONFIGURATION_ORDER  # noqa: E402

MODELS = ("random-forest", "xgboost")
MODEL_TITLES = {"random-forest": "Random Forest", "xgboost": "XGBoost"}
LABELS = {"sem-xai": "Sem XAI", "sincrono-total": "Síncrono total",
          "sincrono-condicional-probabilidade": "Condicional (probabilidade)",
          "sincrono-condicional-incerteza": "Condicional (incerteza)", "assincrono": "Assíncrono"}
# Cores categóricas em ordem fixa, validadas para daltonismo entre vizinhas, e um marcador por configuração como
# segunda codificação.
COLORS = dict(zip(CONFIGURATION_ORDER, ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4")))
MARKERS = dict(zip(CONFIGURATION_ORDER, ("o", "s", "^", "D", "v")))
SURFACE, TEXT, TEXT_SECONDARY, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"
DPI = 300
WIDTH = 7.5
# Configurações da figura de fluxos pendentes, com a ordem de desenho.
PENDING_CONFIGURATIONS = {"sincrono-total": 1, "assincrono": 2, "sem-xai": 3}
WINDOW_S = 10
# Pontos da distribuição acumulada da latência de classificação de cada execução.
QUANTILES = np.linspace(0.0, 1.0, 1001)


def draw_all(summary: dict[str, Any], series: dict[str, dict[str, Any]], directory: Path, repo: Any) -> dict[str, str]:
    """Desenha as figuras e devolve o caminho de cada uma, relativo à raiz do projeto."""
    directory.mkdir(parents=True, exist_ok=True)
    loads = sorted({row["cell"]["load"] for row in summary["executions"]})
    explaining = [key for key in CONFIGURATION_ORDER if key != "sem-xai"]
    drawn = {
        "classification_latency": _by_load(
            summary, loads, CONFIGURATION_ORDER,
            [("classification_p95_ms", "p95 (ms)", (1000, "limite do p95, 1 s")),
             ("classification_p99_ms", "p99 (ms)", (2000, "limite do p99, 2 s"))],
            directory / "latencia-classificacao.png"),
        "latency_distribution": _distribution(summary, series, loads, directory / "distribuicao-latencia.png"),
        "emitted_per_second": _emitted(summary, series, loads, directory / "fluxos-por-segundo.png"),
        "pending_classification": _pending(summary, series, loads, directory / "pendentes-classificacao.png"),
        "explanation_latency": _by_load(
            summary, loads, explaining,
            [("explanation_latency_p95_ms", "p95 (ms)", None), ("explanation_latency_p99_ms", "p99 (ms)", None)],
            directory / "latencia-explicacao.png"),
        "explanation_queue": _queue(summary, series, loads, directory / "fila-explicacoes.png"),
        "cpu": _by_load(
            summary, loads, CONFIGURATION_ORDER,
            [("cpu_classifier_s", "Classificador (s)", None), ("cpu_explainer_s", "Processo explicador (s)", None),
             ("cpu_extractor_s", "Extrator (s)", None)],
            directory / "cpu-processos.png", log=False),
    }
    return {name: repo.relative(path) for name, path in drawn.items()}


def _by_load(summary: dict[str, Any], loads: list[int], configurations: Any,
             rows: list[tuple[str, str, tuple[float, str] | None]], path: Path, log: bool = True) -> Path:
    """Uma linha por configuração, com a mediana das execuções e o intervalo do mínimo ao máximo, em cada nível de
    carga. Uma linha de painéis por medida e uma coluna por classificador."""
    figure, axes = plt.subplots(len(rows), len(MODELS), figsize=(WIDTH, 2.6 * len(rows) + 0.6), dpi=DPI,
                                sharey="row", squeeze=False)
    figure.patch.set_facecolor(SURFACE)
    positions = np.arange(len(loads))
    for row, (key, label, limit) in enumerate(rows):
        for column, model in enumerate(MODELS):
            axis = axes[row][column]
            _style(axis)
            for index, configuration in enumerate(configurations):
                spreads = [_measure(summary, model, configuration, load, key) for load in loads]
                if all(spread is None for spread in spreads):
                    continue
                offset = (index - (len(configurations) - 1) / 2) * 0.07
                x = [position + offset for position, spread in zip(positions, spreads) if spread]
                kept = [spread for spread in spreads if spread]
                medians = np.array([spread["median"] for spread in kept])
                errors = [medians - [spread["min"] for spread in kept], [spread["max"] for spread in kept] - medians]
                axis.errorbar(x, medians, yerr=errors, color=COLORS[configuration], marker=MARKERS[configuration],
                              markersize=4.5, markeredgecolor=SURFACE, markeredgewidth=0.8, linewidth=1.4,
                              elinewidth=1.0, capsize=0, label=LABELS[configuration])
            if log:
                axis.set_yscale("log")
            axis.yaxis.set_major_formatter(FuncFormatter(_number))
            if limit is not None:
                axis.axhline(limit[0], color=TEXT_SECONDARY, linewidth=0.8, zorder=1)
                axis.text(0.99, limit[0], limit[1], transform=axis.get_yaxis_transform(), ha="right", va="bottom",
                          fontsize=6.5, color=TEXT_SECONDARY)
            axis.set_xticks(positions, [_copies(load) for load in loads])
            axis.set_xlim(-0.4, len(loads) - 0.6)
            if row == 0:
                axis.set_title(MODEL_TITLES[model], fontsize=9, color=TEXT, loc="left")
            if column == 0:
                axis.set_ylabel(label, fontsize=8, color=TEXT_SECONDARY)
    _legend(figure, axes)
    return _save(figure, path)


def _distribution(summary: dict[str, Any], series: dict[str, dict[str, Any]], loads: list[int], path: Path) -> Path:
    """Distribuição acumulada da latência de classificação, uma linha por execução."""
    figure, axes = plt.subplots(len(MODELS), len(loads), figsize=(WIDTH, 5.4), dpi=DPI, sharex=True, sharey=True,
                                squeeze=False)
    figure.patch.set_facecolor(SURFACE)
    for row, model in enumerate(MODELS):
        for column, load in enumerate(loads):
            axis = axes[row][column]
            _style(axis)
            for configuration in CONFIGURATION_ORDER:
                for index, execution in enumerate(_executions(summary, model, configuration, load)):
                    axis.plot(series[execution["cell"]["id"]]["latency_quantiles_ms"], QUANTILES,
                              color=COLORS[configuration], linewidth=1.0,
                              label=LABELS[configuration] if index == 0 else None)
            axis.set_xscale("log")
            axis.xaxis.set_major_locator(FixedLocator([10.0 ** power for power in range(-1, 7)]))
            axis.xaxis.set_major_formatter(FuncFormatter(_latency_label))
            axis.yaxis.set_major_locator(FixedLocator([0, 0.5, 0.95]))
            axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _: _decimal(100 * value, 0) + "%"))
            axis.set_ylim(0, 1.02)
            axis.set_title(f"{MODEL_TITLES[model]}, {_copies(load)}", fontsize=8, color=TEXT, loc="left")
            if row == len(MODELS) - 1:
                axis.set_xlabel("Latência de classificação", fontsize=7.5, color=TEXT_SECONDARY)
            if column == 0:
                axis.set_ylabel("Fluxos classificados", fontsize=7.5, color=TEXT_SECONDARY)
    _legend(figure, axes)
    return _save(figure, path)


def _emitted(summary: dict[str, Any], series: dict[str, dict[str, Any]], loads: list[int], path: Path) -> Path:
    """Fluxos emitidos a cada segundo, numa execução sem descartes de cada nível de carga."""
    figure, axes = plt.subplots(len(loads), 1, figsize=(WIDTH, 1.5 * len(loads) + 0.5), dpi=DPI, sharex=True,
                                sharey=True, squeeze=False)
    figure.patch.set_facecolor(SURFACE)
    for row, load in enumerate(loads):
        axis = axes[row][0]
        _style(axis)
        execution = _reference_execution(summary, load)
        counts = series[execution["cell"]["id"]]["emitted_per_second"]
        axis.plot(np.arange(len(counts)), counts, color=COLORS["sem-xai"], linewidth=0.8)
        axis.yaxis.set_major_formatter(FuncFormatter(_number))
        axis.set_title(f"{_copies(load)}, {MODEL_TITLES[execution['cell']['model']]}, "
                       f"{LABELS[execution['cell']['configuration']]}, repetição {execution['cell']['repetition']}",
                       fontsize=8, color=TEXT, loc="left")
        axis.set_ylabel("Fluxos/s", fontsize=7.5, color=TEXT_SECONDARY)
    axes[-1][0].set_xlabel("Tempo desde o primeiro fluxo emitido (s)", fontsize=7.5, color=TEXT_SECONDARY)
    figure.tight_layout()
    return _save(figure, path)


def _pending(summary: dict[str, Any], series: dict[str, dict[str, Any]], loads: list[int], path: Path) -> Path:
    """Maior número de fluxos pendentes de classificação a cada janela, na repetição 1 do Sem XAI, do Síncrono
    total e do Assíncrono. A linha do Sem XAI fica por cima das outras."""
    figure, axes = plt.subplots(len(MODELS), len(loads), figsize=(WIDTH, 5.4), dpi=DPI, sharex=True, sharey=True,
                                squeeze=False)
    figure.patch.set_facecolor(SURFACE)
    largest = 1
    for row, model in enumerate(MODELS):
        for column, load in enumerate(loads):
            axis = axes[row][column]
            _style(axis)
            for configuration in [key for key in CONFIGURATION_ORDER if key in PENDING_CONFIGURATIONS]:
                executions = _executions(summary, model, configuration, load)
                if not executions:
                    continue
                windows, values = _windows(series[executions[0]["cell"]["id"]]["pending_classification"])
                largest = max(largest, int(values.max()))
                axis.step(windows, values, where="post", color=COLORS[configuration], linewidth=1.0,
                          label=LABELS[configuration], zorder=PENDING_CONFIGURATIONS[configuration])
            axis.set_yscale("symlog", linthresh=1)
            axis.yaxis.set_major_formatter(FuncFormatter(_number))
            axis.set_title(f"{MODEL_TITLES[model]}, {_copies(load)}", fontsize=8, color=TEXT, loc="left")
            if row == len(MODELS) - 1:
                axis.set_xlabel("Tempo desde o primeiro fluxo emitido (s)", fontsize=7.5, color=TEXT_SECONDARY)
            if column == 0:
                axis.set_ylabel(f"Fluxos pendentes, maior em {WINDOW_S} s", fontsize=7.5, color=TEXT_SECONDARY)
    axes[0][0].set_ylim(0, largest * 2)
    _legend(figure, axes)
    return _save(figure, path)


def _windows(points: list[list[int]]) -> tuple[np.ndarray, np.ndarray]:
    """Maior valor de cada janela de WINDOW_S segundos que tem alguma leitura, a partir do maior de cada segundo."""
    seconds, values = np.array(points).T
    windows = seconds // WINDOW_S
    starts = np.unique(windows)
    return starts * WINDOW_S, np.array([values[windows == start].max() for start in starts])


def _queue(summary: dict[str, Any], series: dict[str, dict[str, Any]], loads: list[int], path: Path) -> Path:
    """Maior tamanho da fila de explicações pendentes em cada segundo, nas 3 execuções do Assíncrono."""
    figure, axes = plt.subplots(len(MODELS), len(loads), figsize=(WIDTH, 5.0), dpi=DPI, sharex=True, squeeze=False)
    figure.patch.set_facecolor(SURFACE)
    for row, model in enumerate(MODELS):
        for column, load in enumerate(loads):
            axis = axes[row][column]
            _style(axis)
            executions = _executions(summary, model, "assincrono", load)
            largest = 0
            for execution in executions:
                points = np.array(series[execution["cell"]["id"]]["queue"])
                largest = max(largest, int(points[:, 1].max()))
                axis.step(points[:, 0], points[:, 1], where="post", color=COLORS["assincrono"], linewidth=0.8)
            limit = executions[0]["queue"]["limit"] if executions else None
            if limit is not None and largest > limit / 2:
                axis.axhline(limit, color=TEXT_SECONDARY, linewidth=0.8, zorder=1)
                axis.text(0.99, limit, f"limite, {_number(limit, None)}", transform=axis.get_yaxis_transform(),
                          ha="right", va="bottom", fontsize=6.5, color=TEXT_SECONDARY)
            axis.yaxis.set_major_formatter(FuncFormatter(_number))
            axis.set_ylim(bottom=0)
            axis.set_title(f"{MODEL_TITLES[model]}, {_copies(load)}", fontsize=8, color=TEXT, loc="left")
            if row == len(MODELS) - 1:
                axis.set_xlabel("Tempo desde o primeiro fluxo emitido (s)", fontsize=7.5, color=TEXT_SECONDARY)
            if column == 0:
                axis.set_ylabel("Solicitações na fila", fontsize=7.5, color=TEXT_SECONDARY)
    figure.tight_layout()
    return _save(figure, path)


def _measure(summary: dict[str, Any], model: str, configuration: str, load: int, key: str) -> dict[str, Any] | None:
    for item in summary["combinations"]:
        if (item["model"], item["configuration"], item["load"]) == (model, configuration, load):
            return item["measures"].get(key)
    return None


def _executions(summary: dict[str, Any], model: str, configuration: str, load: int) -> list[dict[str, Any]]:
    found = [row for row in summary["executions"]
             if (row["cell"]["model"], row["cell"]["configuration"], row["cell"]["load"]) == (model, configuration,
                                                                                               load)]
    return sorted(found, key=lambda row: row["cell"]["repetition"])


def _reference_execution(summary: dict[str, Any], load: int) -> dict[str, Any]:
    """A execução do XGBoost sem explicação na repetição 1, que não descarta fluxos, ou a primeira sem descartes."""
    candidates = _executions(summary, "xgboost", "sem-xai", load) or [
        row for row in summary["executions"] if row["cell"]["load"] == load]
    clean = [row for row in candidates if not row["flows"]["dropped"]]
    return (clean or candidates)[0]


def _style(axis: Any) -> None:
    axis.set_facecolor(SURFACE)
    axis.grid(True, color=GRID, linewidth=0.6)
    axis.set_axisbelow(True)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axis.spines[side].set_color(AXIS)
    axis.tick_params(labelsize=7, colors=TEXT_SECONDARY)


def _legend(figure: Any, axes: Any) -> None:
    entries: dict[str, Any] = {}
    for axis in np.ravel(axes):
        for handle, label in zip(*axis.get_legend_handles_labels()):
            entries.setdefault(label, handle)
    figure.legend(list(entries.values()), list(entries), loc="upper center", ncol=len(entries), fontsize=7,
                  frameon=False, labelcolor=TEXT)
    figure.tight_layout(rect=(0, 0, 1, 0.95))


def _save(figure: Any, path: Path) -> Path:
    figure.savefig(path, facecolor=SURFACE)
    plt.close(figure)
    return path


def _copies(load: int) -> str:
    return f"{load} {'cópia' if load == 1 else 'cópias'}"


def _latency_label(value: float, _: Any) -> str:
    """Rótulo de uma década de latência em milissegundos, só nas décadas de 1 ms, 100 ms e 10 s."""
    labels = {1.0: "1 ms", 100.0: "100 ms", 10_000.0: "10 s"}
    return labels.get(value, "")


def _number(value: float, _: Any) -> str:
    if value == 0:
        return "0"
    return _decimal(value, 0 if abs(value) >= 1 else 1 if abs(value) >= 0.1 else 2)
