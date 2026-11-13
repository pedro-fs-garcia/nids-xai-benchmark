"""NIDS de referência: extração, classificação de cada fluxo e registro das marcações de tempo, sem explicações."""

import json
import signal
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from core.flow_extractor import ExtractorBuild, NidsExtractorProcess, parse_timestamp_us
from core.frozen_prediction import FrozenPredictor
from core.instrumentation import monotonic_ns, verify_shared_clock
from domains.explanations.service import summarize
from domains.model_artifacts.service import prepare_flow
from domains.nids import reporting
from domains.nids.exceptions import NidsError
from domains.nids.repository import NidsRepository
from domains.nids.schemas import CommandResult
from domains.traffic_preparation.service import compare_attributes, has_nan, match_rows

TIMING = ["seq", "cause", "first_packet_us", "last_packet_us", "capture_clock_us",
          "t0_ns", "t1_ns", "t2_ns", "t3_ns", "prediction", "attack_probability", "error"]
PROBABILITY_ATOL = 1e-12


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
            segment: str | None = None, ready_file: Path | None = None) -> CommandResult:
        if (pcap is None) == (interface is None) and segment is None:
            raise NidsError("Informe um trecho preparado, um arquivo PCAP ou uma interface.")
        if pcap is not None and interface is not None:
            raise NidsError("Informe um arquivo PCAP ou uma interface, não os dois.")
        config = self.repo.read_config(self.config_path)
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
        build = ExtractorBuild(self.extractor_dir)
        run_dir = self.repo.create_run(kind)
        channel = self.repo.open_channel(run_dir)
        table_stream, table = None, None
        process = NidsExtractorProcess(build, source, config.extractor)
        previous = {sig: signal.signal(sig, lambda *_: process.request_stop()) for sig in (signal.SIGTERM, signal.SIGINT)}
        flows: list[dict[str, Any]] = []
        clock_difference = None
        try:
            for event, payload in process.events():
                if event == "start":
                    clock_difference = verify_shared_clock(payload["monotonic_ns"], config.shared_clock_tolerance_ns)
                    table_stream, table = self.repo.open_table(run_dir, TIMING + payload["header"])
                    if ready_file is not None:
                        self.repo.signal_ready(ready_file, run_dir)
                elif event == "flow":
                    flows.append(self._classify(payload, manifest, estimator, channel, table))
        except BaseException:
            process.kill()
            raise
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
            channel.close()
            if table_stream is not None:
                table_stream.close()
        end = process.end or {}
        summary = self._summary(model_name, kind, source, info, config, loaded, build, run_dir, flows, end,
                                clock_difference, process.start or {})
        if info is not None and kind == "arquivo":
            summary["conference"] = self._conference(info, flows, manifest, estimator)
            summary["passed"] = summary["passed"] and summary["conference"]["passed"]
        self.repo.write_json(run_dir / "report.json", summary)
        report = self.repo.write_report(f"nids-execucao-{kind}-{run_dir.name}.md", reporting.render_run(summary))
        if not summary["passed"]:
            raise NidsError(f"A execução do NIDS não passou nas verificações. Ver {report}.")
        return CommandResult(run_dir, report, summary)

    def _classify(self, flow: Any, manifest: dict[str, Any], estimator: Any, channel: Any, table: Any) -> dict[str, Any]:
        values = flow.values
        record: dict[str, Any] = {"seq": flow.seq, "cause": flow.cause, "first_packet_us": flow.first_packet_us,
                                  "last_packet_us": flow.last_packet_us, "capture_clock_us": flow.capture_clock_us,
                                  "t0_ns": flow.t0_ns, "t1_ns": None, "t2_ns": None, "t3_ns": None,
                                  "prediction": None, "attack_probability": None, "error": None}
        try:
            vector = input_vector(values, manifest)
        except (ValueError, KeyError) as error:
            record["error"] = str(error)
        else:
            t1 = monotonic_ns()
            probability = estimator.predict_proba(vector)[:, 1]
            t2 = monotonic_ns()
            prediction = int(FrozenPredictor.classify(probability)[0])
            channel.write(json.dumps({
                "seq": flow.seq, "flow_id": values["Flow ID"], "src_ip": values["Src IP"],
                "src_port": int(values["Src Port"]), "dst_ip": values["Dst IP"], "dst_port": int(values["Dst Port"]),
                "protocol": int(values["Protocol"]), "timestamp": values["Timestamp"], "prediction": prediction,
                "class": "attack" if prediction else "benign", "attack_probability": float(probability[0]),
            }) + "\n")
            channel.flush()
            t3 = monotonic_ns()
            record.update({"t1_ns": t1, "t2_ns": t2, "t3_ns": t3, "prediction": prediction,
                           "attack_probability": float(probability[0])})
        table.writerow({**record, **values})
        return {**record, "values": values}

    def _summary(self, model_name: str, kind: str, source: dict[str, str], info: dict[str, Any] | None,
                 config: Any, loaded: Any, build: ExtractorBuild, run_dir: Path, flows: list[dict[str, Any]],
                 end: dict[str, Any], clock_difference: int | None, start: dict[str, Any]) -> dict[str, Any]:
        classified = [flow for flow in flows if flow["error"] is None]
        errors = [flow for flow in flows if flow["error"] is not None]
        ordered = all(flow["t0_ns"] <= flow["t1_ns"] <= flow["t2_ns"] <= flow["t3_ns"] for flow in classified)
        checks = {
            "emitted_equals_received": end.get("flows_emitted") == len(flows),
            "received_equals_classified_plus_errors": len(flows) == len(classified) + len(errors),
            "timestamps_ordered": ordered,
            "no_packets_after_emission_in_file_mode": kind != "arquivo" or end.get("packets_after_emission") == 0,
        }
        timings: dict[str, Any] = {}
        if classified:
            t0, t1, t2, t3 = (np.array([flow[key] for flow in classified], dtype=np.int64)
                              for key in ("t0_ns", "t1_ns", "t2_ns", "t3_ns"))
            timings = {"inference_ns": summarize(t2 - t1), "classification_latency_ns": summarize(t3 - t0),
                       "wait_before_inference_ns": summarize(t1 - t0), "delivery_ns": summarize(t3 - t2)}
            span = (int(t3.max()) - int(t0.min())) / 1e9
            timings["classified_per_second"] = len(classified) / span if span > 0 else None
        artifacts = {name: self.repo.artifact(run_dir / name) for name in ("classifications.jsonl", "flows.csv")
                     if (run_dir / name).exists()}
        return {
            "stage": "reference nids", "run_id": run_dir.name, "strategy": "Sem XAI",
            "passed": all(checks.values()), "checks": checks, "model": model_name, "source": {"kind": kind, **source},
            "segment": None if info is None else {key: info[key] for key in (
                "name", "stop", "stop_us", "pcap", "reference", "border_seconds", "manifest", "manifest_sha256")},
            "config": self.repo.relative(config.path), "config_sha256": config.sha256,
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
            "timings": timings, "artifacts": artifacts, "resources": self.repo.resource_usage(),
            "cpu_state": self.repo.cpu_state(), "environment": self.repo.environment(),
        }

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
            "flows_emitted": emitted["flows_emitted"], "flows_received": received["received"],
            "flows_classified": received["classified"], "flows_with_error": received["errors"],
        }
        checks = {
            "tcpreplay_sent_whole_segment": (tcpreplay.get("successful") or 0) + (tcpreplay.get("failed") or 0)
            == counters["segment_packets"],
            "h1_sent_equals_tcpreplay_successful": counters["h1_sent"] == tcpreplay.get("successful"),
            "h2_received_equals_h1_sent": counters["h2_received"] == counters["h1_sent"],
            "no_capture_drops": counters["h2_dropped"] == 0 and counters["pcap_dropped"] == 0
            and counters["pcap_interface_dropped"] == 0,
            "extractor_read_equals_h2_received": counters["extractor_read"] == counters["h2_received"],
            "replay_run_flow_chain": all(replay["checks"].values()),
        }
        run_dir = self.repo.create_run("validacao")
        summary = {
            "stage": "low-load validation", "run_id": run_dir.name, "passed": all(checks.values()),
            "checks": checks, "counters": counters, "model": replay["model"], "segment": original["segment"]["name"],
            "replay_run": self.repo.relative(replay_dir), "file_run": self.repo.relative(file_dir),
            "replay": {key: emulation.get(key) for key in ("topology", "replay_command", "replay_seconds",
                                                           "wait_after_replay_s", "replay_started_utc")},
            "tcpreplay": {key: value for key, value in tcpreplay.items() if key not in ("output", "errors")},
            "flows": {
                "file": len(file_rows), "replay": len(replay_rows), "matched_inside": len(inside),
                "matched_border": len(pairs) - len(inside), "file_only_inside": sum(1 for row in only_file if inside_file(row)),
                "replay_only_inside": sum(1 for row in only_replay if inside_replay(row)),
                "swapped_direction_inside": len(swapped), "replay_offset_us": offset,
                "file_only_examples": [_brief(row) for row in only_file if inside_file(row)][:5],
                "replay_only_examples": [_brief(row) for row in only_replay if inside_replay(row)][:5],
            },
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


TEMPORAL_MARKERS = ("Duration", "IAT", "/s", "Active", "Idle", "Bulk Rate", "TCP Flow Time")
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
        finite = np.isfinite(left) & np.isfinite(right)
        difference = np.abs(left[finite] - right[finite])
        scale = np.maximum(np.abs(left[finite]), 1.0)
        result[name] = {"differing": int(np.count_nonzero(left != right)),
                        "max_abs_difference": float(difference.max()) if difference.size else 0.0,
                        "median_relative_difference": float(np.median(difference / scale)) if difference.size else 0.0}
    return result


def _brief(row: dict[str, str]) -> dict[str, str]:
    return {key: row[key] for key in ("seq", "cause", *FIVE_TUPLE, "Timestamp", "Total Fwd Packet",
                                      "Total Bwd packets")}
