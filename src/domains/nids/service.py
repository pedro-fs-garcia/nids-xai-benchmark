"""NIDS: extração, classificação de cada fluxo, explicação conforme a estratégia e registro das marcações de tempo."""

import json
import os
import signal
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

import numpy as np
from threadpoolctl import threadpool_limits

from core.explanation_worker import EXPLANATION_TIMING, ExplanationWorker, explanation_record, read_explanations
from core.flow_extractor import ExtractorBuild, NidsExtractorProcess, parse_timestamp_us
from core.frozen_prediction import FrozenPredictor
from core.instrumentation import monotonic_ns, verify_shared_clock
from core.process_resources import children_usage, memory_available_kib, pin_all_threads, self_usage, thread_affinities
from core.tree_explainer import TreeShapExplainer, explained_output
from domains.explanations.service import summarize
from domains.model_artifacts.service import prepare_flow
from domains.nids import reporting
from domains.nids.comparison import compare
from domains.nids.exceptions import NidsError
from domains.nids.repository import NidsRepository
from domains.nids.schemas import CRITERIA, MODELS, CommandResult
from domains.nids.strategies import (COMPLETED, DROPPED, NOT_SELECTED, REQUESTED, Strategy, build_strategy,
                                     explanation_checks, pending_series, selection_table)
from domains.traffic_preparation.service import compare_attributes, has_nan, match_rows

TIMING = ["seq", "cause", "first_packet_us", "last_packet_us", "capture_clock_us",
          "t0_ns", "t1_ns", "t2_ns", "t3_ns", "prediction", "attack_probability", "error",
          "selected", "selection_start_ns", "selection_end_ns", "delivery_start_ns", "explanation",
          "explanation_requested_ns"]
PROBABILITY_ATOL = 1e-12
# Diferença admitida entre a probabilidade registrada na classificação e a que a saída explicada produz. No
# Random Forest, a saída explicada é a própria probabilidade. No XGBoost, a probabilidade registrada é a sigmoide
# do escore calculada em precisão simples.
OUTPUT_PROBABILITY_ATOL = {"probability": PROBABILITY_ATOL, "log-odds": 1e-6}


@dataclass
class Pipeline:
    """O que o laço de classificação usa em cada fluxo de uma execução."""
    manifest: dict[str, Any]
    estimator: Any
    strategy: Strategy
    explainer: TreeShapExplainer | None
    channel: IO[str]
    explanations: IO[str] | None
    explanation_table: Any
    table: Any = None
    # Processo explicador e fila de explicações pendentes, só no modo assíncrono.
    worker: ExplanationWorker | None = None
    # Na leitura de arquivo, a solicitação espera vaga na fila em vez de ser descartada.
    block_on_full_queue: bool = False


def load_explainer(root: str, data_dir: str, runs_dir: str, reports_dir: str, frozen_run: str, model_name: str,
                   threads: int) -> tuple[Any, dict[str, Any]]:
    """Fábrica do processo explicador. Carrega a cópia verificada do modelo congelado e constrói o explicador."""
    repo = NidsRepository(Path(root), Path(data_dir), Path(runs_dir), Path(reports_dir))
    started = monotonic_ns()
    loaded = repo.load_frozen(Path(frozen_run), model_name)
    load_ns = monotonic_ns() - started
    loaded.estimator.set_params(n_jobs=threads)
    started = monotonic_ns()
    explainer = TreeShapExplainer(loaded.estimator)
    construction_ns = monotonic_ns() - started
    started = monotonic_ns()
    explainer.explain(np.zeros((1, len(loaded.manifest["inputs"])), dtype=np.float64))
    explanation_ns = monotonic_ns() - started

    def explain(vector: np.ndarray) -> tuple[float, np.ndarray]:
        result = explainer.explain(vector)
        return result.reference_value, result.contributions[0]

    return explain, {"model_sha256": loaded.manifest["files"]["model"]["sha256"], "load_ns": load_ns,
                     "explainer_construction_ns": construction_ns, "explanation_ns": explanation_ns}


def processes_on_configured_cpus(cpus: dict[str, Any]) -> bool:
    """Confere que todas as threads do classificador e do explicador e o extrator ficaram nas CPUs configuradas."""
    configured = cpus["configured"]
    checks = [all(set(group) <= set(configured["classifier"]) for group in cpus["classifier"]),
              cpus["extractor"] is None or cpus["extractor"] == sorted(configured["extractor"])]
    if cpus["explainer"] is not None:
        checks.append(all(set(group) <= set(configured["explainer"]) for group in cpus["explainer"]))
    return all(checks)


def warm_up(estimator: Any, strategy: Strategy, features: int) -> tuple[TreeShapExplainer | None, dict[str, Any]]:
    """Constrói o explicador e faz uma chamada de aquecimento de cada operação, antes de a captura abrir.

    O vetor de aquecimento é de zeros e não vem de nenhum conjunto de dados."""
    zeros = np.zeros((1, features), dtype=np.float64)
    explainer, record = None, {"explainer_construction_ns": None, "explanation_ns": None}
    if strategy.explains and strategy.synchronous:
        started = monotonic_ns()
        explainer = TreeShapExplainer(estimator)
        record["explainer_construction_ns"] = monotonic_ns() - started
    started = monotonic_ns()
    estimator.predict_proba(zeros)
    record["inference_ns"] = monotonic_ns() - started
    if explainer is not None:
        started = monotonic_ns()
        explainer.explain(zeros)
        record["explanation_ns"] = monotonic_ns() - started
    return explainer, record


def input_vector(values: dict[str, str], manifest: dict[str, Any]) -> np.ndarray:
    """Vetor das entradas na ordem do manifesto, com a regra de infinito do treino."""
    flow = {}
    for name in manifest["inputs"]:
        number = float(values[name])
        flow[name] = "inf" if number == float("inf") and name in manifest["preprocessing"][
            "positive_infinity_columns"] else number
    return prepare_flow(flow, manifest)


class NidsService:
    def __init__(self, repo: NidsRepository, extractor_dir: Path, config_path: Path) -> None:
        self.repo = repo
        self.extractor_dir = extractor_dir
        self.config_path = config_path

    def run(self, model_name: str, pcap: Path | None = None, interface: str | None = None,
            segment: str | None = None, ready_file: Path | None = None,
            strategy_key: str = "sem-xai", criterion: str | None = None) -> CommandResult:
        if (pcap is None) == (interface is None) and segment is None:
            raise NidsError("Informe um trecho preparado, um arquivo PCAP ou uma interface.")
        if pcap is not None and interface is not None:
            raise NidsError("Informe um arquivo PCAP ou uma interface, não os dois.")
        config = self.repo.read_config(self.config_path)
        threshold = None
        if strategy_key == "sincrono-condicional" and criterion is not None:
            threshold = config.selection["thresholds"][criterion][model_name]
            if threshold is None:
                raise NidsError(f"O limiar do critério {criterion} para o {model_name} ainda não foi fixado em "
                                f"{config.path}.")
        strategy = build_strategy(strategy_key, criterion, threshold)
        tree_shap = self.repo.tree_shap(config.tree_shap_config, config.frozen_run)
        info = self.repo.segment(config.preparation_manifest, segment) if segment else None
        if interface is not None:
            source, kind = {"iface": interface}, "interface"
        else:
            path = pcap if pcap is not None else self.repo.root / info["pcap"]["file"]
            source, kind = {"pcap": str(path)}, "arquivo"
        loaded = self.repo.load_frozen(config.frozen_run, model_name)
        manifest = loaded.manifest
        estimator = loaded.estimator
        estimator.set_params(n_jobs=config.classifier_threads)
        cpus = config.resources["cpus"]
        memory_at_start = memory_available_kib()
        # O classificador fica fixo antes de iniciar os outros processos. Cada um deles recebe as próprias CPUs.
        pin_all_threads(cpus["classifier"])
        build = ExtractorBuild(self.extractor_dir)
        run_dir = self.repo.create_run(kind)
        flows: list[dict[str, Any]] = []
        clock_difference = worker_clock_difference = worker_end = extractor_cpus = None
        with threadpool_limits(limits=config.classifier_threads):
            explainer, warmup = warm_up(estimator, strategy, len(manifest["inputs"]))
            pipeline = Pipeline(manifest, estimator, strategy, explainer, self.repo.open_channel(run_dir), None, None,
                                block_on_full_queue=kind == "arquivo")
            streams = [pipeline.channel]
            process = None
            previous: dict[Any, Any] = {}
            try:
                if strategy.explains and strategy.synchronous:
                    pipeline.explanations = self.repo.open_explanations(run_dir)
                    explanation_stream, pipeline.explanation_table = self.repo.open_table(
                        run_dir, EXPLANATION_TIMING, "explanations.csv")
                    streams += [pipeline.explanations, explanation_stream]
                elif strategy.explains:
                    pipeline.worker = ExplanationWorker(
                        load_explainer, (str(self.repo.root), str(self.repo.data_dir), str(self.repo.runs_dir),
                                         str(self.repo.reports_dir), str(config.frozen_run), model_name,
                                         config.classifier_threads),
                        run_dir, config.explanation_queue["limit"], cpus["explainer"], config.classifier_threads)
                    worker_clock_difference = verify_shared_clock(pipeline.worker.ready["monotonic_ns"],
                                                                  config.shared_clock_tolerance_ns)
                    warmup.update({key: pipeline.worker.ready[key] for key in (
                        "explainer_construction_ns", "explanation_ns")})
                    warmup["explainer_process"] = {key: value for key, value in pipeline.worker.ready.items()
                                                   if key != "monotonic_ns"}
                process = NidsExtractorProcess(build, source, config.extractor, cpus["extractor"],
                                               config.resources["extractor_max_heap_mib"])
                previous = {sig: signal.signal(sig, lambda *_: process.request_stop())
                            for sig in (signal.SIGTERM, signal.SIGINT)}
                for event, payload in process.events():
                    if event == "start":
                        clock_difference = verify_shared_clock(payload["monotonic_ns"],
                                                               config.shared_clock_tolerance_ns)
                        extractor_cpus = sorted(os.sched_getaffinity(process.process.pid))
                        table_stream, pipeline.table = self.repo.open_table(run_dir, TIMING + payload["header"])
                        streams.append(table_stream)
                        if ready_file is not None:
                            self.repo.signal_ready(ready_file, run_dir)
                    elif event == "flow":
                        flows.append(self._classify(payload, pipeline))
                if pipeline.worker is not None:
                    worker_end = pipeline.worker.finish(config.explanation_queue["drain_timeout_s"])
            except BaseException:
                if process is not None:
                    process.kill()
                if pipeline.worker is not None:
                    pipeline.worker.kill()
                raise
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
                for stream in streams:
                    stream.close()
        end = process.end or {}
        explanations, unmarked = read_explanations(run_dir) if strategy.explains else ([], 0)
        summary = self._summary(model_name, kind, source, info, config, loaded, build, run_dir, flows, end,
                                clock_difference, process.start or {})
        self._add_explanations(summary, model_name, pipeline, tree_shap, flows, explanations, warmup, worker_end,
                               unmarked)
        summary["shared_clock_difference_explainer_ns"] = worker_clock_difference
        explainer_usage = ((worker_end or {}).get("worker") or {}).get("process")
        summary["resources"] = {
            "classifier_process": self_usage(), "explainer_process": explainer_usage,
            "extractor_process": end.get("process"), "children_total": children_usage(),
            "memory_available_kib_at_start": memory_at_start,
            "cpus": {"configured": cpus, "classifier": thread_affinities(),
                     "explainer": None if explainer_usage is None else explainer_usage["thread_affinities"],
                     "extractor": extractor_cpus},
        }
        summary["checks"]["processes_on_configured_cpus"] = processes_on_configured_cpus(summary["resources"]["cpus"])
        summary["passed"] = all(summary["checks"].values())
        if info is not None and kind == "arquivo":
            summary["conference"] = self._conference(info, flows, manifest, estimator)
            summary["passed"] = summary["passed"] and summary["conference"]["passed"]
        self.repo.write_json(run_dir / "report.json", summary)
        report = self.repo.write_report(f"nids-execucao-{kind}-{run_dir.name}.md", reporting.render_run(summary))
        if not summary["passed"]:
            raise NidsError(f"A execução do NIDS não passou nas verificações. Ver {report}.")
        return CommandResult(run_dir, report, summary)

    def _classify(self, flow: Any, pipeline: Pipeline) -> dict[str, Any]:
        """Classifica um fluxo e, conforme a estratégia, gera a explicação antes de entregar a classificação.

        As quatro estratégias compartilham o caminho até o fim da seleção. Na explicação síncrona, o registro da
        explicação e o da classificação são escritos em seguida, e uma só leitura do relógio vale por t3 e t4."""
        values = flow.values
        record: dict[str, Any] = {"seq": flow.seq, "cause": flow.cause, "first_packet_us": flow.first_packet_us,
                                  "last_packet_us": flow.last_packet_us, "capture_clock_us": flow.capture_clock_us,
                                  "t0_ns": flow.t0_ns, "t1_ns": None, "t2_ns": None, "t3_ns": None,
                                  "prediction": None, "attack_probability": None, "error": None, "selected": None,
                                  "selection_start_ns": None, "selection_end_ns": None, "delivery_start_ns": None,
                                  "explanation": None, "explanation_requested_ns": None}
        try:
            vector = input_vector(values, pipeline.manifest)
        except (ValueError, KeyError) as error:
            record["error"] = str(error)
        else:
            t1 = monotonic_ns()
            probability = pipeline.estimator.predict_proba(vector)[:, 1]
            t2 = monotonic_ns()
            prediction = int(FrozenPredictor.classify(probability)[0])
            attack_probability = float(probability[0])
            selection_start = monotonic_ns()
            selected = pipeline.strategy.select(attack_probability)
            delivery_start = selection_end = monotonic_ns()
            explained = None
            if selected and pipeline.strategy.synchronous:
                result = pipeline.explainer.explain(vector)
                delivery_start = monotonic_ns()
                explained = {"seq": flow.seq, "dequeued_ns": None, "explanation_start_ns": selection_end,
                             "explanation_end_ns": delivery_start}
                pipeline.explanations.write(json.dumps(explanation_record(
                    flow.seq, values["Flow ID"], result.reference_value, result.contributions[0])) + "\n")
                pipeline.explanations.flush()
            pipeline.channel.write(json.dumps({
                "seq": flow.seq, "flow_id": values["Flow ID"], "src_ip": values["Src IP"],
                "src_port": int(values["Src Port"]), "dst_ip": values["Dst IP"], "dst_port": int(values["Dst Port"]),
                "protocol": int(values["Protocol"]), "timestamp": values["Timestamp"], "prediction": prediction,
                "class": "attack" if prediction else "benign", "attack_probability": attack_probability,
            }) + "\n")
            pipeline.channel.flush()
            t3 = monotonic_ns()
            status, requested = (COMPLETED if explained is not None else NOT_SELECTED), None
            if explained is not None:
                pipeline.explanation_table.writerow({**explained, "t4_ns": t3})
            elif selected and pipeline.worker is not None:
                # No modo assíncrono, a solicitação só entra na fila depois de a classificação ficar disponível.
                requested = monotonic_ns()
                accepted = pipeline.worker.submit(flow.seq, values["Flow ID"], vector, pipeline.block_on_full_queue)
                status = REQUESTED if accepted else DROPPED
            record.update({"t1_ns": t1, "t2_ns": t2, "t3_ns": t3, "prediction": prediction,
                           "attack_probability": attack_probability, "selected": int(selected),
                           "selection_start_ns": selection_start, "selection_end_ns": selection_end,
                           "delivery_start_ns": delivery_start, "explanation": status,
                           "explanation_requested_ns": requested})
        pipeline.table.writerow({**record, **values})
        return {**record, "values": values}

    def _summary(self, model_name: str, kind: str, source: dict[str, str], info: dict[str, Any] | None,
                 config: Any, loaded: Any, build: ExtractorBuild, run_dir: Path, flows: list[dict[str, Any]],
                 end: dict[str, Any], clock_difference: int | None, start: dict[str, Any]) -> dict[str, Any]:
        classified = [flow for flow in flows if flow["error"] is None]
        errors = [flow for flow in flows if flow["error"] is not None]
        checks = run_checks(kind, end, flows)
        timings: dict[str, Any] = {}
        if classified:
            t0, t1, t2, t3, selection_start, selection_end, delivery_start = (
                np.array([flow[key] for flow in classified], dtype=np.int64)
                for key in ("t0_ns", "t1_ns", "t2_ns", "t3_ns", "selection_start_ns", "selection_end_ns",
                            "delivery_start_ns"))
            timings = {"inference_ns": summarize(t2 - t1), "classification_latency_ns": summarize(t3 - t0),
                       "wait_before_inference_ns": summarize(t1 - t0),
                       "selection_ns": summarize(selection_end - selection_start),
                       "delivery_ns": summarize(t3 - delivery_start)}
            span = (int(t3.max()) - int(t0.min())) / 1e9
            timings["classified_per_second"] = len(classified) / span if span > 0 else None
        artifacts = {name: self.repo.artifact(run_dir / name)
                     for name in ("classifications.jsonl", "flows.csv", "explanations.jsonl", "explanations.csv")
                     if (run_dir / name).exists()}
        return {
            "stage": "nids run", "run_id": run_dir.name,
            "passed": all(checks.values()), "checks": checks, "model": model_name, "source": {"kind": kind, **source},
            "segment": None if info is None else {key: info[key] for key in (
                "name", "stop", "stop_us", "pcap", "reference", "border_seconds", "manifest", "manifest_sha256")},
            "config": self.repo.relative(config.path), "config_sha256": config.sha256,
            "selection_calibration_run": config.selection["calibration_run"],
            "frozen_run": self.repo.relative(config.frozen_run),
            "model_manifest_sha256": loaded.manifest["files"]["model"]["sha256"],
            "classifier_threads": config.classifier_threads, "extractor_options": config.extractor,
            "extractor_build": build.record, "extractor_start": {key: value for key, value in start.items()
                                                                 if key not in ("header", "type")},
            "extractor_end": {key: value for key, value in end.items() if key != "type"},
            "shared_clock_difference_ns": clock_difference,
            "flows": {"received": len(flows), "classified": len(classified), "errors": len(errors),
                      "by_cause": dict(Counter(flow["cause"] for flow in flows)),
                      "predictions": dict(Counter(str(flow["prediction"]) for flow in classified)),
                      "error_examples": [{"seq": flow["seq"], "flow_id": flow["values"]["Flow ID"],
                                          "error": flow["error"]} for flow in errors[:5]]},
            "timings": timings, "artifacts": artifacts,
            "cpu_state": self.repo.cpu_state(), "environment": self.repo.environment(),
        }

    def _add_explanations(self, summary: dict[str, Any], model_name: str, pipeline: Pipeline, tree_shap: Any,
                          flows: list[dict[str, Any]], explanations: list[dict[str, Any]], warmup: dict[str, Any],
                          worker_end: dict[str, Any] | None = None, unmarked: int = 0) -> None:
        """Acrescenta ao resumo a estratégia, a cobertura explicativa, os tempos e as verificações das explicações."""
        strategy = pipeline.strategy
        classified = {flow["seq"]: flow for flow in flows if flow["error"] is None}
        known = [item for item in explanations if item["seq"] in classified]
        tolerance = tree_shap.tolerances[model_name]["sum_identity"]
        logistic = hasattr(pipeline.estimator, "get_booster")
        residual = probability_difference = None
        if known:
            inputs = np.vstack([input_vector(classified[item["seq"]]["values"], pipeline.manifest) for item in known])
            output = explained_output(pipeline.estimator, inputs)
            explained = np.array([item["reference_value"] + float(np.sum(item["contributions"])) for item in known])
            residual = float(np.max(np.abs(explained - output)))
            # A saída explicada é recalculada das entradas do fluxo. Ela precisa levar à probabilidade registrada.
            recorded = np.array([classified[item["seq"]]["attack_probability"] for item in known])
            probability = 1.0 / (1.0 + np.exp(-output)) if logistic else output
            probability_difference = float(np.max(np.abs(probability - recorded)))
            t0, start, end, t4 = (np.array(values, dtype=np.int64) for values in (
                [classified[item["seq"]]["t0_ns"] for item in known], [item["explanation_start_ns"] for item in known],
                [item["explanation_end_ns"] for item in known], [item["t4_ns"] for item in known]))
            summary["timings"]["explanation_ns"] = summarize(end - start)
            summary["timings"]["explanation_latency_ns"] = summarize(t4 - t0)
        selected = sum(1 for flow in classified.values() if flow["selected"])
        output_atol = OUTPUT_PROBABILITY_ATOL["log-odds" if logistic else "probability"]
        summary["checks"].update(explanation_checks(strategy, flows, explanations, residual, tolerance))
        summary["checks"]["explained_output_matches_classification"] = (
            probability_difference is None or probability_difference <= output_atol)
        summary["checks"]["contributions_cover_every_input"] = all(
            len(item["contributions"]) == len(pipeline.manifest["inputs"]) for item in explanations)
        if worker_end is not None:
            summary["explanation_queue"] = self._queue_summary(classified, known, worker_end, unmarked, summary,
                                                               pipeline.block_on_full_queue)
            ready = warmup["explainer_process"]
            summary["checks"]["explainer_uses_the_same_model"] = (
                ready["model_sha256"] == pipeline.manifest["files"]["model"]["sha256"])
        summary["passed"] = all(summary["checks"].values())
        summary.update({
            "strategy": strategy.name, "strategy_key": strategy.key,
            "selection": None if strategy.criterion is None else {
                "criterion": strategy.criterion, "threshold": strategy.threshold,
                "calibration_run": summary["selection_calibration_run"]},
            "tree_shap_config": self.repo.relative(tree_shap.path), "tree_shap_config_sha256": tree_shap.sha256,
            "explainer": tree_shap.content["explainer"], "warmup": warmup,
            "explanations": {
                "eligible": len(classified), "selected": selected, "completed": len(known),
                "selected_share": selected / len(classified) if classified else None,
                "completed_share": len(known) / len(classified) if classified else None,
                "scale": "log-odds" if logistic else "probability",
                "sum_identity": {"residual": residual, "tolerance": tolerance},
                "explained_output_vs_probability": {"max_difference": probability_difference, "tolerance": output_atol},
            },
        })

    @staticmethod
    def _queue_summary(classified: dict[int, dict[str, Any]], known: list[dict[str, Any]], worker_end: dict[str, Any],
                       unmarked: int, summary: dict[str, Any], blocking: bool) -> dict[str, Any]:
        """Contadores, tamanho, espera e esvaziamento da fila de explicações pendentes, e as suas verificações."""
        requested = {seq: flow["explanation_requested_ns"] for seq, flow in classified.items()
                     if flow["explanation"] == REQUESTED}
        dropped = sum(1 for flow in classified.values() if flow["explanation"] == DROPPED)
        worker = worker_end["worker"] or {}
        killed = worker_end["killed_after_drain_timeout"]
        dequeued = [item["dequeued_ns"] for item in known]
        origin = min((flow["t0_ns"] for flow in classified.values()), default=0)
        last_t4 = max((item["t4_ns"] for item in known), default=None)
        last_request = max(requested.values(), default=None)
        if known:
            wait = np.array([item["dequeued_ns"] - requested[item["seq"]] for item in known], dtype=np.int64)
            summary["timings"]["queue_wait_ns"] = summarize(wait)
        pending = len(requested) - len(known)
        summary["checks"].update({
            "explanation_requests_accounted": (len(requested), dropped) == (worker_end["accepted"], worker_end["dropped"]),
            "explainer_received_every_accepted_request": killed or worker.get("received") == len(requested),
            "explainer_ended_without_error": killed or worker_end["exit_code"] == 0,
            "no_pending_after_normal_end": killed or (pending == 0 and unmarked == 0),
            "no_dropped_request_in_file_mode": not blocking or dropped == 0,
        })
        return {
            "limit": worker_end["limit"], "drain_timeout_s": worker_end["drain_timeout_s"],
            "full_queue_policy": "wait" if blocking else "drop_incoming",
            "requested": len(requested) + dropped, "accepted": len(requested), "dropped": dropped,
            "completed": len(known), "pending": pending, "records_without_marks": unmarked,
            "explainer_received": worker.get("received"), "killed_after_drain_timeout": killed,
            "exit_code": worker_end["exit_code"],
            "size": pending_series(list(requested.values()), dequeued, origin),
            "drain_after_last_request_ns": None if last_t4 is None or last_request is None else last_t4 - last_request,
            "drain_after_end_of_capture_ns": None if worker_end["end_sent_ns"] is None or last_t4 is None
            else max(last_t4 - worker_end["end_sent_ns"], 0),
            "wait_for_explainer_after_end_of_capture_ns": None if worker_end["end_sent_ns"] is None
            else worker_end["finished_ns"] - worker_end["end_sent_ns"],
        }

    def compare_strategies(self, run_dirs: list[Path]) -> CommandResult:
        """Confere que execuções do mesmo modelo e da mesma fonte formam um conjunto comparável das estratégias."""
        reports = [self.repo.read_json(directory / "report.json") for directory in run_dirs]
        if any(report.get("stage") != "nids run" or "strategy_key" not in report for report in reports):
            raise NidsError("Compare execuções de nids-executar que registram a estratégia de explicação.")
        file_mode = all(report["source"]["kind"] == "arquivo" for report in reports)
        explanations = [self.repo.read_explanation_records(report) if file_mode else {} for report in reports]
        flows = [self.repo.read_flow_marks(report) if file_mode else [] for report in reports]
        result = compare(reports, explanations, flows)
        run_dir = self.repo.create_run("comparacao")
        first = reports[0]
        summary = {
            "stage": "strategy comparison", "run_id": run_dir.name, "model": first["model"],
            "source_kind": first["source"]["kind"], "segment": (first["segment"] or {}).get("name"),
            "compared_runs": [self.repo.relative(directory) for directory in run_dirs], **result,
            "environment": self.repo.environment(),
        }
        self.repo.write_json(run_dir / "report.json", summary)
        report = self.repo.write_report(f"nids-estrategias-{run_dir.name}.md", reporting.render_comparison(summary))
        if not summary["passed"]:
            raise NidsError(f"As execuções não formam um conjunto comparável. Ver {report}.")
        return CommandResult(run_dir, report, summary)

    def calibrate_selection(self) -> CommandResult:
        """Mostra, na validação, quantos registros cada critério de seleção escolhe, por limiar da grade."""
        config = self.repo.read_config(self.config_path)
        data = self.repo.validation_split()
        inputs, labels = np.asarray(data.inputs, dtype=np.float64), np.asarray(data.labels)
        grid = config.selection["calibration_grid"]
        models = {}
        for name in MODELS:
            loaded = self.repo.load_frozen(config.frozen_run, name)
            if loaded.manifest["inputs"] != data.manifest["inputs"]:
                raise NidsError(f"A ordem dos atributos do {name} diverge dos dados de validação.")
            loaded.estimator.set_params(n_jobs=config.classifier_threads)
            predictions, probability = FrozenPredictor(loaded.estimator).predict(inputs)
            models[name] = {
                "model_sha256": loaded.manifest["files"]["model"]["sha256"],
                "false_negatives": int(np.count_nonzero((labels == 1) & (predictions == 0))),
                "false_positives": int(np.count_nonzero((labels == 0) & (predictions == 1))),
                "criteria": {criterion: selection_table(criterion, grid[criterion], probability, labels, predictions)
                             for criterion in CRITERIA},
            }
        run_dir = self.repo.create_run("calibracao")
        summary = {
            "stage": "selection calibration", "run_id": run_dir.name,
            "config": self.repo.relative(config.path), "config_sha256": config.sha256,
            "frozen_run": self.repo.relative(config.frozen_run), "data_manifest_sha256": data.manifest_sha256,
            "split": data.name, "test_used": False, "records": int(labels.size),
            "attacks": int(np.count_nonzero(labels == 1)), "benign": int(np.count_nonzero(labels == 0)),
            "grid": grid, "models": models, "environment": self.repo.environment(),
        }
        self.repo.write_json(run_dir / "report.json", summary)
        report = self.repo.write_report(f"selecao-condicional-{run_dir.name}.md", reporting.render_calibration(summary))
        return CommandResult(run_dir, report, summary)

    def _conference(self, info: dict[str, Any], flows: list[dict[str, Any]], manifest: dict[str, Any],
                    estimator: Any) -> dict[str, Any]:
        """Compara os fluxos e as previsões do NIDS com o modelo aplicado à tabela de referência do trecho."""
        reference = self.repo.read_rows(info["reference"])
        border_start = info["stop_us"] - info["border_seconds"] * 1_000_000
        nids_rows = [{**flow["values"], "_flow": flow} for flow in flows]
        pairs, only_reference, only_nids = match_rows(reference, nids_rows)
        inside = [pair for pair in pairs if parse_timestamp_us(pair[0]["Timestamp"]) < border_start]
        attributes = compare_attributes(inside, manifest["inputs"])
        classified = [(row, nids) for row, nids in inside if nids["_flow"]["error"] is None]
        expected_probability = estimator.predict_proba(
            np.vstack([input_vector(row, manifest) for row, _ in classified]))[:, 1] if classified else np.array([])
        observed = np.array([nids["_flow"]["attack_probability"] for _, nids in classified])
        expected = FrozenPredictor.classify(expected_probability) if classified else np.array([])
        predictions = np.array([nids["_flow"]["prediction"] for _, nids in classified])
        mismatched_attributes = sum(item["mismatches"] for item in attributes.values())
        differing_predictions = int(np.count_nonzero(predictions != expected)) if classified else 0
        largest = float(np.max(np.abs(observed - expected_probability))) if classified else 0.0
        inside_reference_only = sum(1 for row in only_reference if parse_timestamp_us(row["Timestamp"]) < border_start)
        nids_only = [row for row in only_nids if parse_timestamp_us(row["Timestamp"]) < border_start]
        inside_nids_only = len(nids_only)
        nids_only_with_nan = sum(1 for row in nids_only if has_nan(row))
        passed = (mismatched_attributes == 0 and differing_predictions == 0 and largest <= PROBABILITY_ATOL
                  and inside_reference_only == 0 and inside_nids_only == nids_only_with_nan)
        return {
            "passed": passed, "reference_flows": len(reference), "matched_inside": len(inside),
            "matched_border": len(pairs) - len(inside), "reference_only_inside": inside_reference_only,
            "nids_only_inside": inside_nids_only, "nids_only_inside_with_nan": nids_only_with_nan,
            "attribute_mismatches": {name: item for name, item in attributes.items() if item["mismatches"]},
            "rounding_differences": sum(item["rounding_differences"] for item in attributes.values()),
            "max_rounding_relative": max((item["max_rounding_relative"] for item in attributes.values()), default=0.0),
            "compared_predictions": len(classified), "differing_predictions": differing_predictions,
            "max_probability_difference": largest, "probability_atol": PROBABILITY_ATOL,
            "labels_of_matched": dict(Counter(row["Label"] for row, _ in inside)),
        }

    def validate(self, replay_dir: Path, file_dir: Path) -> CommandResult:
        """Compara a execução que capturou o trecho reproduzido na rede emulada com a execução do mesmo arquivo."""
        config = self.repo.read_config(self.config_path)
        replay = self.repo.read_json(replay_dir / "report.json")
        original = self.repo.read_json(file_dir / "report.json")
        emulation = self.repo.read_json(replay_dir / "replay.json")
        if replay["source"]["kind"] != "interface" or original["source"]["kind"] != "arquivo":
            raise NidsError("Compare uma execução por interface com uma execução por arquivo.")
        if replay["model"] != original["model"] or replay["segment"]["pcap"] != original["segment"]["pcap"]:
            raise NidsError("As duas execuções devem usar o mesmo modelo e o mesmo trecho.")
        if replay["strategy"] != original["strategy"] or replay.get("selection") != original.get("selection"):
            raise NidsError("As duas execuções devem usar a mesma estratégia de explicação e o mesmo critério.")
        if not original["passed"]:
            raise NidsError("A execução por arquivo precisa ter passado na conferência com a tabela de referência.")
        info = self.repo.segment(config.preparation_manifest, original["segment"]["name"])
        inputs = self.repo.data_manifest()["inputs"]
        file_rows = _with_ordinal(self.repo.read_rows(original["artifacts"]["flows.csv"]))
        replay_rows = _with_ordinal(self.repo.read_rows(replay["artifacts"]["flows.csv"]))
        pairs, only_file, only_replay = match_rows(file_rows, replay_rows, key=_ordinal_key)
        offset = int(np.median([int(r["first_packet_us"]) - int(f["first_packet_us"]) for f, r in pairs])) if pairs else 0
        border_start = info["stop_us"] - info["border_seconds"] * 1_000_000
        inside_file = lambda row: int(row["first_packet_us"]) < border_start  # noqa: E731
        inside_replay = lambda row: int(row["first_packet_us"]) - offset < border_start  # noqa: E731
        inside = [(f, r) for f, r in pairs if inside_file(f)]
        swapped, _, _ = match_rows([row for row in only_file if inside_file(row)],
                                   [row for row in only_replay if inside_replay(row)], key=_endpoints_key)

        exact_names = [name for name in inputs if not _temporal(name)]
        temporal_names = [name for name in inputs if _temporal(name)]
        exact = compare_attributes(inside, exact_names)
        temporal = _temporal_differences(inside, temporal_names)
        exact_equal = [(f, r) for f, r in inside if all(f[name] == r[name] or float(f[name]) == float(r[name])
                                                         for name in exact_names)]
        classified = [(f, r) for f, r in inside if not f["error"] and not r["error"]]
        differing = [(f, r) for f, r in classified if f["prediction"] != r["prediction"]]
        exact_keys = {id(f) for f, _ in exact_equal}
        reference = self.repo.read_rows(info["reference"])
        labelled, _, _ = match_rows(file_rows, reference)
        labels = {id(row): ref["Label"] for row, ref in labelled}

        emitted, received = replay["extractor_end"], replay["flows"]
        tcpreplay, interfaces = emulation["tcpreplay"], emulation["interface_counters"]
        stats = emitted.get("pcap_stats") or {}
        counters = {
            "segment_packets": info["summary"]["packets"],
            "tcpreplay_attempted": tcpreplay.get("attempted_packets"), "tcpreplay_successful": tcpreplay.get("successful"),
            "tcpreplay_failed": tcpreplay.get("failed"), "tcpreplay_truncated": tcpreplay.get("truncated"),
            "h1_sent": interfaces["h1-eth0"]["tx_packets"], "h2_received": interfaces["h2-eth0"]["rx_packets"],
            "h2_dropped": interfaces["h2-eth0"]["rx_dropped"],
            "pcap_received": stats.get("received"), "pcap_dropped": stats.get("dropped"),
            "pcap_interface_dropped": stats.get("interface_dropped"),
            "extractor_read": emitted["packets_read"], "extractor_valid": emitted["packets_valid"],
            "extractor_discarded": emitted["packets_discarded"],
            "file_extractor_read": original["extractor_end"]["packets_read"],
            "file_extractor_valid": original["extractor_end"]["packets_valid"],
            "packets_after_emission": emitted["packets_after_emission"],
            "flows_emitted": emitted["flows_emitted"],
            "flows_dropped_in_extractor_queue": emitted.get("flows_dropped") or 0, "flows_received": received["received"],
            "flows_classified": received["classified"], "flows_with_error": received["errors"],
        }
        checks = replay_checks(counters, replay["checks"])
        seconds = Counter(int(row["t0_ns"]) // 1_000_000_000 for row in replay_rows)
        emission = {"flows": emitted["flows_emitted"],
                    "per_second": emitted["flows_emitted"] / emulation["replay_seconds"],
                    "peak_per_second": max(seconds.values(), default=0)}
        run_dir = self.repo.create_run("validacao")
        summary = {
            "stage": "low-load validation", "run_id": run_dir.name, "passed": all(checks.values()),
            "checks": checks, "counters": counters, "model": replay["model"], "segment": original["segment"]["name"],
            "strategy": replay.get("strategy", "Sem XAI"), "strategy_key": replay.get("strategy_key", "sem-xai"),
            "selection": replay.get("selection"),
            "replay_run": self.repo.relative(replay_dir), "file_run": self.repo.relative(file_dir),
            "replay": {key: emulation.get(key) for key in ("topology", "replay_command", "replay_seconds",
                                                           "wait_after_replay_s", "replay_started_utc",
                                                           "tcpreplay_build")},
            "tcpreplay": {key: value for key, value in tcpreplay.items() if key not in ("output", "errors")},
            "flows": {
                "file": len(file_rows), "replay": len(replay_rows), "matched_inside": len(inside),
                "matched_border": len(pairs) - len(inside), "file_only_inside": sum(1 for row in only_file if inside_file(row)),
                "replay_only_inside": sum(1 for row in only_replay if inside_replay(row)),
                "swapped_direction_inside": len(swapped), "replay_offset_us": offset,
                "file_only_examples": [_brief(row) for row in only_file if inside_file(row)][:5],
                "replay_only_examples": [_brief(row) for row in only_replay if inside_replay(row)][:5],
            },
            "emission": emission, "packet_shifts": _packet_shifts(pairs, inside),
            "exact_attributes": {name: item for name, item in exact.items() if item["mismatches"]},
            "temporal_attributes": temporal, "flows_with_equal_exact_attributes": len(exact_equal),
            "predictions": {
                "compared": len(classified), "differing": len(differing),
                "differing_with_equal_exact_attributes": sum(1 for f, _ in differing if id(f) in exact_keys),
                "examples": [{**_brief(f), "file_probability": f["attack_probability"],
                              "replay_probability": r["attack_probability"]} for f, r in differing[:10]],
            },
            "labels": {"matched_inside": dict(Counter(labels.get(id(f), "sem rótulo") for f, _ in inside)),
                       "file_only_inside": dict(Counter(labels.get(id(row), "sem rótulo")
                                                        for row in only_file if inside_file(row)))},
            "replay_timings": replay["timings"], "environment": self.repo.environment(),
        }
        self.repo.write_json(run_dir / "report.json", summary)
        report = self.repo.write_report(f"nids-validacao-{run_dir.name}.md", reporting.render_validation(summary))
        if not summary["passed"]:
            raise NidsError(f"Algum contador da reprodução não fechou. Ver {report}.")
        return CommandResult(run_dir, report, summary)


def run_checks(kind: str, end: dict[str, Any], flows: list[dict[str, Any]]) -> dict[str, bool]:
    """Verificações de uma execução: cada fluxo emitido chega ao classificador ou é descartado na fila de saída do
    extrator, e as marcações estão em ordem. Os fluxos descartados são as sequências que não chegam."""
    classified = [flow for flow in flows if flow["error"] is None]
    errors = [flow for flow in flows if flow["error"] is not None]
    emitted, dropped = end.get("flows_emitted"), end.get("flows_dropped") or 0
    sequences = [flow["seq"] for flow in flows]
    return {
        "emitted_equals_received_plus_dropped": emitted == len(flows) + dropped
        and len(set(sequences)) == len(sequences) and set(sequences) <= set(range(1, (emitted or 0) + 1)),
        "no_dropped_flow_in_file_mode": kind != "arquivo" or dropped == 0,
        "received_equals_classified_plus_errors": len(flows) == len(classified) + len(errors),
        "timestamps_ordered": all(flow["t0_ns"] <= flow["t1_ns"] <= flow["t2_ns"] <= flow["t3_ns"]
                                  for flow in classified),
        "no_packets_after_emission_in_file_mode": kind != "arquivo" or end.get("packets_after_emission") == 0,
    }


def replay_checks(counters: dict[str, Any], replay_run_checks: dict[str, bool]) -> dict[str, bool]:
    """Cadeia de contadores da reprodução: do tcpreplay à interface de h1, à de h2, ao libpcap e ao extrator."""
    return {
        "tcpreplay_sent_whole_segment": (counters["tcpreplay_successful"] or 0) + (counters["tcpreplay_failed"] or 0)
        == counters["segment_packets"],
        "h1_sent_equals_tcpreplay_successful": counters["h1_sent"] == counters["tcpreplay_successful"],
        "h2_received_equals_h1_sent": counters["h2_received"] == counters["h1_sent"],
        "no_capture_drops": counters["h2_dropped"] == 0 and counters["pcap_dropped"] == 0
        and counters["pcap_interface_dropped"] == 0,
        "extractor_read_equals_h2_received": counters["extractor_read"] == counters["h2_received"],
        "replay_run_flow_chain": all(replay_run_checks.values()),
    }


def _packets(row: dict[str, str]) -> int:
    return int(row["Total Fwd Packet"]) + int(row["Total Bwd packets"])


def _packet_shifts(pairs: list[tuple[dict[str, str], dict[str, str]]],
                   inside: list[tuple[dict[str, str], dict[str, str]]]) -> dict[str, Any]:
    """Conta os fluxos casados com número de pacotes diferente e, entre eles, os de conexões cujo total se conserva.

    Quando o total de pacotes da conexão é igual nas duas execuções, os pacotes só mudaram de fluxo: a reprodução
    desloca os instantes dos pacotes, e um pacote próximo do tempo limite fica no fluxo anterior ou no seguinte."""
    totals: dict[tuple[Any, ...], list[int]] = {}
    for file_row, replay_row in pairs:
        total = totals.setdefault(_endpoints_key(file_row), [0, 0])
        total[0] += _packets(file_row)
        total[1] += _packets(replay_row)
    differing = [(f, r) for f, r in inside if _packets(f) != _packets(r)]
    conserved = [(f, r) for f, r in differing if totals[_endpoints_key(f)][0] == totals[_endpoints_key(f)][1]]
    return {"flows": len(differing), "conserved_in_connection": len(conserved),
            "connections": len({_endpoints_key(f) for f, _ in conserved}),
            "examples": [{"flow_id": f["Flow ID"], "timestamp": f["Timestamp"], "file_packets": _packets(f),
                          "replay_packets": _packets(r)} for f, r in differing[:10]]}


# O extrator reinicia a rajada (bulk) quando dois pacotes com carga ficam mais de 1 s afastados. Por isso os
# atributos de rajada também dependem dos instantes de captura.
TEMPORAL_MARKERS = ("Duration", "IAT", "/s", "Active", "Idle", "Bulk", "TCP Flow Time")
FIVE_TUPLE = ("Flow ID", "Src IP", "Src Port", "Dst IP", "Dst Port", "Protocol")


def _temporal(name: str) -> bool:
    return any(marker in name for marker in TEMPORAL_MARKERS)


def _with_ordinal(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Numera os fluxos de cada quíntupla na ordem do primeiro pacote, para casar execuções com relógios distintos."""
    counts: Counter[tuple[str, ...]] = Counter()
    for row in sorted(rows, key=lambda item: (int(item["first_packet_us"]), int(item["seq"]))):
        key = tuple(row[column] for column in FIVE_TUPLE)
        row["_ordinal"] = str(counts[key])
        counts[key] += 1
    return rows


def _ordinal_key(row: dict[str, str]) -> tuple[str, ...]:
    return (*(row[column] for column in FIVE_TUPLE), row["_ordinal"])


def _endpoints_key(row: dict[str, str]) -> tuple[Any, ...]:
    endpoints = sorted([(row["Src IP"], row["Src Port"]), (row["Dst IP"], row["Dst Port"])])
    return (*endpoints[0], *endpoints[1], row["Protocol"])


def _temporal_differences(pairs: list[tuple[dict[str, str], dict[str, str]]], names: list[str]) -> dict[str, Any]:
    result = {}
    for name in names:
        left = np.array([float(f[name]) for f, _ in pairs])
        right = np.array([float(r[name]) for _, r in pairs])
        finite = np.isfinite(left) & np.isfinite(right) & (left != right)
        difference = np.abs(left[finite] - right[finite])
        scale = np.maximum(np.abs(left[finite]), 1.0)
        result[name] = {"differing": int(np.count_nonzero(left != right)),
                        "max_abs_difference": float(difference.max()) if difference.size else 0.0,
                        "median_relative_difference": float(np.median(difference / scale)) if difference.size else 0.0}
    return result


def _brief(row: dict[str, str]) -> dict[str, str]:
    return {key: row[key] for key in ("seq", "cause", *FIVE_TUPLE, "Timestamp", "Total Fwd Packet",
                                      "Total Bwd packets")}
