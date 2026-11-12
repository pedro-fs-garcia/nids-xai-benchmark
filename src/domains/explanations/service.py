"""Exemplo, verificação e medição isolada do TreeSHAP nos classificadores do projeto."""

import json
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
from threadpoolctl import threadpool_info, threadpool_limits

from core.process_runner import PythonProcessRunner
from core.tree_explainer import TreeShapExplainer
from core.tree_structure import features_without_split, xgboost_reference_value
from domains.explanations import reporting
from domains.explanations.exceptions import ExplanationError
from domains.explanations.repository import ExplanationRepository
from domains.explanations.schemas import MODELS, CommandResult
from domains.model_artifacts.schemas import LoadedModel

EXPLANATION_CHUNK = 1000
PREDICTION_ATOL = 1e-12


def stratified_sample(original_labels: np.ndarray, size: int, seed: int, minimum: int) -> np.ndarray:
    """Amostra sem reposição, estratificada pelos rótulos originais, com um mínimo por rótulo."""
    labels, counts = np.unique(original_labels, return_counts=True)
    if size > original_labels.size:
        raise ExplanationError("A amostra não pode ser maior que o conjunto.")
    allocation = np.minimum(counts, minimum)
    remaining = size - int(allocation.sum())
    if remaining < 0:
        raise ExplanationError("O mínimo por rótulo excede o tamanho da amostra.")
    capacity = counts - allocation
    share = remaining * capacity / capacity.sum() if capacity.sum() else np.zeros(labels.size)
    allocation = allocation + np.floor(share).astype(np.int64)
    leftover = size - int(allocation.sum())
    # Maior resto primeiro; empates favorecem o menor índice de rótulo.
    for position in np.lexsort((labels, -(share - np.floor(share)))):
        if leftover == 0:
            break
        if allocation[position] < counts[position]:
            allocation[position] += 1
            leftover -= 1
    rng = np.random.default_rng(seed)
    chosen = [rng.choice(np.flatnonzero(original_labels == label), int(amount), replace=False)
              for label, amount in zip(labels, allocation)]
    return np.sort(np.concatenate(chosen)).astype(np.int64)


def select_example(original_labels: np.ndarray, predictions: np.ndarray, probabilities: np.ndarray,
                   label_index: int, predicted_class: int) -> tuple[int, int]:
    """Registro de probabilidade mediana entre os do rótulo e da classe prevista dados."""
    candidates = np.flatnonzero((original_labels == label_index) & (predictions == predicted_class))
    if not candidates.size:
        raise ExplanationError("Nenhum registro atende ao critério do exemplo.")
    ordered = candidates[np.lexsort((candidates, probabilities[candidates]))]
    # Com número par de candidatos, vale o menor dos dois registros centrais.
    return int(ordered[(ordered.size - 1) // 2]), int(candidates.size)


def measurement_flows(sample: np.ndarray, flows: int, seed: int) -> np.ndarray:
    return np.sort(np.random.default_rng(seed).choice(sample, flows, replace=False)).astype(np.int64)


def summarize(values: np.ndarray) -> dict[str, float | int]:
    values = np.asarray(values, dtype=np.float64)
    return {
        "count": int(values.size), "mean": float(values.mean()), "median": float(np.median(values)),
        "p95": float(np.percentile(values, 95)), "p99": float(np.percentile(values, 99)),
        "min": float(values.min()), "max": float(values.max()),
    }


def configured_threads(estimator: Any) -> int:
    if hasattr(estimator, "get_booster"):
        return int(json.loads(estimator.get_booster().save_config())["learner"]["generic_param"]["nthread"])
    return int(estimator.n_jobs)


class ExplanationService:
    def __init__(self, repo: ExplanationRepository, runner: PythonProcessRunner, config_path: Path) -> None:
        self.repo = repo
        self.runner = runner
        self.config_path = config_path

    def explain_example(self) -> CommandResult:
        config = self.repo.read_config(self.config_path)
        data = self.repo.load_split("validation")
        pilot = self.repo.load_pilot(config.pilot_run, data)
        label_index = _label_index(data.manifest, config.example_label)
        index, candidates = select_example(np.asarray(data.origin[:, 2]), pilot.predictions,
                                           pilot.probabilities, label_index, config.example_class)
        inputs = np.array(data.inputs[index:index + 1], dtype=np.float64)
        probability = float(pilot.estimator.predict_proba(inputs)[0, 1])
        if abs(probability - float(pilot.probabilities[index])) > PREDICTION_ATOL:
            raise ExplanationError("A probabilidade recalculada diverge da previsão salva do piloto.")
        result = TreeShapExplainer(pilot.estimator).explain(inputs)
        contributions = result.contributions[0]
        tolerance = config.tolerances["random-forest"]["sum_identity"]
        residual = abs(result.reference_value + float(contributions.sum()) - probability)
        run_dir = self.repo.create_run("exemplo")
        figure = f"treeshap-exemplo-{run_dir.name}.png"
        origin = data.origin[index]
        summary = {
            "stage": "learning example", "run_id": run_dir.name,
            "config": self.repo.relative(config.path), "config_sha256": config.sha256,
            "pilot_run": self.repo.relative(config.pilot_run),
            "pilot_model_sha256": pilot.report["artifacts"]["model"]["sha256"],
            "pilot_sample": {key: pilot.report["sample"][key] for key in ("records", "benign", "attack")},
            "data_manifest_sha256": data.manifest_sha256, "split": data.name, "test_used": False,
            "selection": {"original_label": config.example_label, "predicted_class": config.example_class,
                          "candidates": candidates},
            "record": {"validation_index": index, "source_file": data.manifest["sources"][int(origin[0])]["file"],
                       "id": int(origin[1]), "original_label": config.example_label, "label": int(data.labels[index])},
            "attack_probability": probability, "predicted_class": int(probability > 0.5),
            "reference_value": result.reference_value, "contributions_sum": float(contributions.sum()),
            "sum_identity": {"residual": residual, "tolerance": tolerance, "passed": residual <= tolerance},
            "features": [{"name": name, "value": float(value), "contribution": float(contribution)}
                         for name, value, contribution in zip(data.manifest["inputs"], inputs[0], contributions)],
            "figure": figure, "environment": self.repo.environment(),
        }
        self.repo.write_json(run_dir / "report.json", summary)
        if not summary["sum_identity"]["passed"]:
            raise ExplanationError(f"Resíduo da identidade acima da tolerância: {residual}. Ver {run_dir}.")
        reporting.plot_example(summary, self.repo.report_path(figure))
        path = self.repo.write_report(f"treeshap-exemplo-{run_dir.name}.md", reporting.render_example(summary))
        return CommandResult(run_dir, path, summary)

    def validate(self) -> CommandResult:
        config = self.repo.read_config(self.config_path)
        data = self.repo.load_split("validation")
        original = np.asarray(data.origin[:, 2])
        sample = stratified_sample(original, config.sample.size, config.sample.seed, config.sample.minimum_per_label)
        run_dir = self.repo.create_run("validacao")
        inputs = np.array(data.inputs[sample], dtype=np.float64)
        names = [label["label"] for label in data.manifest["original_labels"]]
        labels, counts = np.unique(original[sample], return_counts=True)
        models = {}
        for name in MODELS:
            loaded = self.repo.load_frozen(config.frozen_run, name, data)
            models[name] = self._validate_model(name, loaded, inputs, config.tolerances[name], run_dir,
                                                config.frozen_run)
        passed = all(check["passed"] for model in models.values() for check in model["checks"])
        summary = {
            "stage": "tree-shap validation", "run_id": run_dir.name, "passed": passed,
            "config": self.repo.relative(config.path), "config_sha256": config.sha256,
            "explainer": config.content["explainer"], "frozen_run": self.repo.relative(config.frozen_run),
            "data_manifest_sha256": data.manifest_sha256, "split": data.name, "test_used": False,
            "sample": {**config.content["validation_sample"], "records": int(sample.size),
                       "indices": self.repo.save_array(run_dir, "validation_sample_indices", sample),
                       "original_labels": {names[int(label)]: int(count) for label, count in zip(labels, counts)}},
            "models": models, "environment": self.repo.environment(),
        }
        self.repo.write_json(run_dir / "report.json", summary)
        path = self.repo.write_report(f"treeshap-validacao-{run_dir.name}.md", reporting.render_validation(summary))
        if not passed:
            raise ExplanationError(f"Verificação reprovada. Resíduos registrados em {run_dir} e {path}.")
        return CommandResult(run_dir, path, summary)

    def _validate_model(self, name: str, loaded: LoadedModel, inputs: np.ndarray, tolerances: dict[str, float],
                        run_dir: Path, frozen_run: Path) -> dict[str, Any]:
        estimator = loaded.estimator
        features = len(loaded.manifest["inputs"])
        explainer = TreeShapExplainer(estimator)
        contributions = np.empty_like(inputs)
        references = set()
        started = time.perf_counter()
        for start in range(0, len(inputs), EXPLANATION_CHUNK):
            result = explainer.explain(inputs[start:start + EXPLANATION_CHUNK])
            contributions[start:start + EXPLANATION_CHUNK] = result.contributions
            references.add(result.reference_value)
        elapsed = time.perf_counter() - started
        if len(references) != 1:
            raise ExplanationError(f"O valor de referência de {name} variou entre chamadas.")
        reference = references.pop()
        if name == "random-forest":
            output = estimator.predict_proba(inputs)[:, 1]
            scale, output_call = "probability", "predict_proba(X)[:, 1]"
        else:
            output = estimator.predict(inputs, output_margin=True).astype(np.float64)
            scale, output_call = "log-odds", "predict(X, output_margin=True)"
        unused = features_without_split(estimator)
        order = estimator.n_features_in_ == features and contributions.shape[1] == features
        if name == "xgboost":
            order = order and estimator.get_booster().num_features() == features
        classes = [int(label) for label in estimator.classes_]
        checks = [
            {"name": "feature_order", "passed": bool(order),
             "detail": f"{features} atributos na ordem do manifesto de dados"},
            {"name": "explained_class", "passed": classes == [0, 1], "detail": f"classes {classes}; classe explicada 1"},
            _check("sum_identity", float(np.max(np.abs(reference + contributions.sum(1) - output))),
                   tolerances["sum_identity"]),
            _check("features_without_split", float(np.max(np.abs(contributions[:, unused]))) if unused else 0.0, 0.0),
        ]
        extra: dict[str, Any] = {}
        if name == "xgboost":
            independent = xgboost_reference_value(estimator.get_booster())
            checks.append(_check("reference_value_vs_hessian_weighted_leaves", abs(reference - independent),
                                 tolerances["reference_value"]))
            extra = {"independent_reference_value": independent}
        return {
            "manifest_sha256": self.repo.frozen_manifest_hash(frozen_run, name),
            "model_sha256": loaded.manifest["files"]["model"]["sha256"],
            "scale": scale, "output_call": output_call, "reference_value": reference,
            "construction_reference_value": explainer.construction_reference_value,
            "features_without_split": [loaded.manifest["inputs"][index] for index in unused],
            "explanation_seconds": elapsed, "checks": checks,
            "contributions": self.repo.save_array(run_dir, f"{name}_contributions", contributions),
            **extra,
        }

    def measure(self, validation_run: Path) -> CommandResult:
        config = self.repo.read_config(self.config_path)
        validation = self.repo.read_json(validation_run / "report.json")
        environment = self.repo.environment()
        if validation.get("passed") is not True:
            raise ExplanationError("A medição exige uma execução aprovada de validar-treeshap.")
        if validation["config_sha256"] != config.sha256 or validation["frozen_run"] != self.repo.relative(config.frozen_run):
            raise ExplanationError("A execução de validação usou outra configuração ou outros modelos.")
        if (validation["environment"]["libraries"] != environment["libraries"]
                or validation["environment"]["python"] != environment["python"]):
            raise ExplanationError("A execução de validação usou outras versões de biblioteca.")
        measurement = config.measurement
        cpu = self.repo.cpu_state()
        if measurement.cpu not in cpu["affinity"]:
            raise ExplanationError(f"A CPU lógica {measurement.cpu} não está disponível para o processo.")
        if measurement.require_mains_power and cpu["mains_power_online"] is not True:
            raise ExplanationError("A medição exige a máquina ligada à tomada.")
        data = self.repo.load_split("validation")
        if validation["data_manifest_sha256"] != data.manifest_sha256:
            raise ExplanationError("A execução de validação usou outro manifesto de dados.")
        sample = self.repo.load_array(validation_run, validation["sample"]["indices"])
        indices = measurement_flows(sample, measurement.flows, config.sample.seed)
        run_dir = self.repo.create_run("medicao")
        plan = {
            "config": config.content, "config_sha256": config.sha256,
            "validation_run": self.repo.relative(validation_run), "frozen_run": self.repo.relative(config.frozen_run),
            "flow_indices": self.repo.save_array(run_dir, "flow_indices", indices),
            "flows": self.repo.save_array(run_dir, "flows", np.ascontiguousarray(data.inputs[indices], dtype=np.float64)),
        }
        self.repo.write_json(run_dir / "plan.json", plan)
        processes: list[dict[str, Any]] = []
        for repetition in range(measurement.processes):
            # A ordem dos classificadores alterna entre repetições.
            for name in MODELS if repetition % 2 == 0 else MODELS[::-1]:
                result = self.runner.run(["medir-treeshap-processo", "--run-dir", str(run_dir), "--modelo", name,
                                          "--repeticao", str(repetition)], cpus=[measurement.cpu])
                if result["pid"] == os.getpid():
                    raise ExplanationError("Cada repetição deve ocorrer em um processo novo.")
                result["record"] = self.repo.write_json(run_dir / f"process-{name}-{repetition}.json", result)
                processes.append(result)
        summary = {
            "stage": "isolated tree-shap timing", "run_id": run_dir.name,
            "config": self.repo.relative(config.path), "config_sha256": config.sha256,
            "validation_run": plan["validation_run"], "frozen_run": plan["frozen_run"],
            "data_manifest_sha256": data.manifest_sha256, "split": data.name, "test_used": False,
            "measurement": config.content["measurement"], "parent_pid": os.getpid(), "cpu_state": cpu,
            "models": {name: _aggregate([p for p in processes if p["model"] == name], measurement.batch_sizes)
                       for name in MODELS},
            "processes": [{key: p[key] for key in ("model", "repetition", "pid", "order", "record")} for p in processes],
            "environment": environment,
        }
        self.repo.write_json(run_dir / "report.json", summary)
        path = self.repo.write_report(f"treeshap-medicao-{run_dir.name}.md", reporting.render_measurement(summary))
        return CommandResult(run_dir, path, summary)

    def measure_process(self, run_dir: Path, name: str, repetition: int) -> dict[str, Any]:
        plan = self.repo.read_json(run_dir / "plan.json")
        measurement = plan["config"]["measurement"]
        affinity = sorted(os.sched_getaffinity(0))
        if affinity != [measurement["cpu"]]:
            raise ExplanationError(f"O processo deve estar fixo na CPU lógica {measurement['cpu']}; está em {affinity}.")
        flows = self.repo.load_array(run_dir, plan["flows"])
        data = self.repo.load_split("validation")
        with threadpool_limits(limits=measurement["threads"]):
            started = time.perf_counter_ns()
            loaded = self.repo.load_frozen(self.repo.root / plan["frozen_run"], name, data)
            load_ns = time.perf_counter_ns() - started
            estimator = loaded.estimator
            estimator.set_params(n_jobs=measurement["threads"])
            threads = configured_threads(estimator)
            if threads != measurement["threads"]:
                raise ExplanationError(f"O classificador {name} ficou com {threads} threads configuradas.")
            started = time.perf_counter_ns()
            explainer = TreeShapExplainer(estimator)
            construction_ns = time.perf_counter_ns() - started
            warmup = {"inference": _timed(lambda: estimator.predict_proba(flows[:1]))[0],
                      "explanation": _timed(lambda: explainer.explain(flows[:1]))[0]}
            durations: dict[str, dict[str, list[int]]] = {}
            cpu_ns: dict[str, dict[str, int]] = {}
            for size in measurement["batch_sizes"]:
                durations[str(size)] = {"inference": [], "explanation": []}
                cpu_ns[str(size)] = {"inference": 0, "explanation": 0}
            for _ in range(measurement["passes"]):
                for size in measurement["batch_sizes"]:
                    for start in range(0, len(flows), size):
                        batch = flows[start:start + size]
                        for operation, call in (("inference", lambda: estimator.predict_proba(batch)),
                                                ("explanation", lambda: explainer.explain(batch))):
                            wall, cpu = _timed(call)
                            durations[str(size)][operation].append(wall)
                            cpu_ns[str(size)][operation] += cpu
            pools = [{key: pool[key] for key in ("user_api", "internal_api", "num_threads")} for pool in threadpool_info()]
        return {
            "pid": os.getpid(), "model": name, "repetition": repetition,
            "order": MODELS.index(name) if repetition % 2 == 0 else MODELS[::-1].index(name),
            "affinity": affinity, "cpu_state": self.repo.cpu_state(), "configured_threads": threads,
            "os_threads": len(os.listdir("/proc/self/task")), "threadpools": pools,
            "load_ns": load_ns, "construction_ns": construction_ns, "warmup_ns": warmup,
            "durations_ns": durations, "cpu_ns": cpu_ns, "environment": self.repo.environment(),
        }


def _check(name: str, residual: float, tolerance: float) -> dict[str, Any]:
    return {"name": name, "residual": residual, "tolerance": tolerance, "passed": residual <= tolerance}


def _label_index(manifest: dict[str, Any], label: str) -> int:
    matches = [item["index"] for item in manifest["original_labels"] if item["label"] == label]
    if len(matches) != 1:
        raise ExplanationError(f"Rótulo original desconhecido: {label}")
    return int(matches[0])


def _timed(call: Any) -> tuple[int, int]:
    wall, cpu = time.perf_counter_ns(), time.process_time_ns()
    call()
    return time.perf_counter_ns() - wall, time.process_time_ns() - cpu


def _aggregate(processes: list[dict[str, Any]], batch_sizes: tuple[int, ...]) -> dict[str, Any]:
    batches: dict[str, Any] = {}
    for size in batch_sizes:
        key = str(size)
        batches[key] = {}
        for operation in ("inference", "explanation"):
            values = np.concatenate([np.asarray(p["durations_ns"][key][operation], dtype=np.float64) for p in processes])
            wall = float(values.sum())
            cpu = float(sum(p["cpu_ns"][key][operation] for p in processes))
            batches[key][operation] = {
                "call_ns": summarize(values), "per_flow_mean_ns": float(values.mean() / size),
                "process_medians_ns": [float(np.median(p["durations_ns"][key][operation])) for p in processes],
                "cpu_to_wall_ratio": cpu / wall if wall else None,
            }
    return {
        "processes": len(processes),
        "load_ns": [p["load_ns"] for p in processes],
        "construction_ns": [p["construction_ns"] for p in processes],
        "warmup_ns": [p["warmup_ns"] for p in processes],
        "configured_threads": sorted({p["configured_threads"] for p in processes}),
        "os_threads": sorted({p["os_threads"] for p in processes}),
        "threadpools": processes[0]["threadpools"] if processes else [],
        "affinity": sorted({cpu for p in processes for cpu in p["affinity"]}),
        "scaling_governor": sorted({value for p in processes for value in p["cpu_state"]["scaling_governor"].values()
                                    if value is not None}),
        "mains_power_online": sorted({str(p["cpu_state"]["mains_power_online"]) for p in processes}),
        "batches": batches,
    }
