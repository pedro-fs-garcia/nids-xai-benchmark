"""Preparação do PCAP de entrada do NIDS e conferência da extração com os fluxos rotulados."""

import math
from collections import Counter, defaultdict, deque
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from core.flow_extractor import EXTRACTOR_COMMIT, ExtractorBuild, NidsExtractorProcess, parse_timestamp_us
from core.pcap_tools import PcapSummary, PcapTools
from domains.model_training.repository import sha256
from domains.traffic_preparation import reporting
from domains.traffic_preparation.exceptions import TrafficPreparationError
from domains.traffic_preparation.repository import TrafficRepository
from domains.traffic_preparation.schemas import CommandResult

FLOW_KEY = ("Flow ID", "Src IP", "Src Port", "Dst IP", "Dst Port", "Protocol")
EXCLUDED = ("Fwd Header Length", "Bwd Header Length")
CSV_ONLY = ("id", "Attempted Category")
EXAMPLES = 5


def flow_key(row: dict[str, str]) -> tuple[Any, ...]:
    """Identifica um fluxo pela quíntupla, pelo Flow ID e pelo instante do primeiro pacote."""
    return (*(row[column] for column in FLOW_KEY), parse_timestamp_us(row["Timestamp"]))


def match_rows(left: Iterable[dict[str, str]], right: Iterable[dict[str, str]],
               key: Callable[[dict[str, str]], Any] = flow_key
               ) -> tuple[list[tuple[dict[str, str], dict[str, str]]], list[dict[str, str]], list[dict[str, str]]]:
    """Casa linhas com a mesma chave na ordem em que aparecem. Devolve os pares e as sobras de cada lado."""
    buckets: dict[Any, deque[dict[str, str]]] = defaultdict(deque)
    for row in right:
        buckets[key(row)].append(row)
    pairs, only_left = [], []
    for row in left:
        queue = buckets.get(key(row))
        if queue:
            pairs.append((row, queue.popleft()))
        else:
            only_left.append(row)
    only_right = [row for queue in buckets.values() for row in queue]
    return pairs, only_left, only_right


# Valores com fração podem diferir por arredondamento de ponto flutuante entre a extração e o CSV publicado.
# Valores inteiros precisam coincidir exatamente.
RELATIVE_TOLERANCE = 1e-12


def same_value(left: str, right: str) -> bool:
    a, b = float(left), float(right)
    return a == b or (math.isnan(a) and math.isnan(b))


def relative_difference(left: str, right: str) -> float:
    a, b = float(left), float(right)
    if a == b or (math.isnan(a) and math.isnan(b)):
        return 0.0
    if not (math.isfinite(a) and math.isfinite(b)):
        return math.inf
    return abs(a - b) / max(abs(a), abs(b))


def ulps_apart(left: str, right: str) -> float:
    """Distância entre dois valores em unidades do último bit do float64 do maior deles."""
    a, b = float(left), float(right)
    if a == b or (math.isnan(a) and math.isnan(b)):
        return 0.0
    if not (math.isfinite(a) and math.isfinite(b)):
        return math.inf
    return abs(a - b) / math.ulp(max(abs(a), abs(b)))


def compare_attributes(pairs: list[tuple[dict[str, str], dict[str, str]]], names: Iterable[str]) -> dict[str, Any]:
    """Conta, por atributo, as diferenças reais e as que se limitam ao arredondamento de valores com fração."""
    result = {}
    for name in names:
        mismatches, rounding, largest, worst_relative, worst_ulps = 0, 0, 0.0, 0.0, 0.0
        example, rounding_example = None, None
        for left, right in pairs:
            distance = relative_difference(left[name], right[name])
            if distance == 0:
                continue
            case = {"flow_id": left["Flow ID"], "timestamp": left["Timestamp"], "left": left[name], "right": right[name]}
            integral = float(left[name]).is_integer() and float(right[name]).is_integer()
            if not integral and distance <= RELATIVE_TOLERANCE:
                rounding += 1
                worst_relative = max(worst_relative, distance)
                worst_ulps = max(worst_ulps, ulps_apart(left[name], right[name]))
                rounding_example = rounding_example or case
                continue
            mismatches += 1
            difference = abs(float(left[name]) - float(right[name]))
            if math.isfinite(difference) and difference >= largest:
                largest = difference
            example = example or case
        result[name] = {"mismatches": mismatches, "max_abs_difference": largest, "example": example,
                        "rounding_differences": rounding, "max_rounding_relative": worst_relative,
                        "max_rounding_ulps": worst_ulps, "rounding_example": rounding_example}
    return result


def has_nan(row: dict[str, str]) -> bool:
    """O notebook de rotulagem dos autores descarta com dropna as linhas que têm algum NaN."""
    return any(value == "NaN" for value in row.values())


def _summary_dict(summary: PcapSummary) -> dict[str, Any]:
    return {"packets": summary.packets, "first_packet_us": summary.first_us, "last_packet_us": summary.last_us,
            "max_frame_bytes": summary.max_frame_bytes, "max_captured_bytes": summary.max_captured_bytes,
            "link_type": summary.link_type, "disordered_packets": summary.disordered_packets}


def _flow_brief(row: dict[str, str]) -> dict[str, str]:
    return {column: row[column] for column in (*FLOW_KEY, "Timestamp", "Flow Duration", "Total Fwd Packet",
                                               "Total Bwd packets", "Label") if column in row}


class TrafficPreparationService:
    def __init__(self, repo: TrafficRepository, tools: PcapTools, extractor_dir: Path, config_path: Path) -> None:
        self.repo = repo
        self.tools = tools
        self.extractor_dir = extractor_dir
        self.config_path = config_path

    def prepare(self) -> CommandResult:
        config = self.repo.read_config(self.config_path)
        self.tools.require("pcapfix", "reordercap", "editcap", "capinfos")
        source = config.source
        if not source.file.is_file():
            raise TrafficPreparationError(f"PCAP ausente: {source.file}. Baixe-o do mirror indicado na configuração.")
        if source.file.stat().st_size != source.bytes or sha256(source.file) != source.sha256:
            raise TrafficPreparationError("O PCAP baixado difere do tamanho ou do SHA-256 publicados pelo mirror.")
        flows_csv = self.repo.checked_flows_csv(config)
        output = config.output_dir
        if (output / "manifest.json").exists():
            raise TrafficPreparationError(f"Preparação já existe em {output}. Remova a pasta para refazer.")
        output.mkdir(parents=True, exist_ok=True)

        fixed = output / f"{source.file.stem}-pcapfix.pcap"
        fix = self.tools.pcapfix(source.file, fixed)
        fixed_record = None
        if fix["fixed_file_written"]:
            fixed_record = {"bytes": fixed.stat().st_size, "sha256": sha256(fixed), "retained": False}
        reordered = output / f"{source.file.stem}-reordered.pcap"
        reorder_output = self.tools.reordercap(fixed if fix["fixed_file_written"] else source.file, reordered)
        if fix["fixed_file_written"]:
            fixed.unlink()
        # O arquivo do mirror é pcapng, e o reordercap mantém o formato. O capinfos lê os dois formatos.
        reordered_info = self.tools.capinfos(reordered)
        if reordered_info.get("Strict time order") != "True":
            raise TrafficPreparationError("O reordercap deixou pacotes fora de ordem.")

        stops = {name: _microseconds(moment) for name, moment in config.segments.items()}
        selected: dict[str, list[dict[str, str]]] = {name: [] for name in stops}
        header = self.repo.csv_header(config.flows_csv)
        for row in self.repo.iter_csv(config.flows_csv):
            timestamp = parse_timestamp_us(row["Timestamp"])
            for name, stop in stops.items():
                if timestamp < stop:
                    selected[name].append(row)
        segments = {}
        for name, moment in config.segments.items():
            path = output / f"segment-{name}.pcap"
            self.tools.cut_before(reordered, path, moment)
            summary = self.tools.summarize(path)
            segments[name] = {
                "stop": moment.isoformat().replace("+00:00", "Z"), "stop_us": stops[name],
                "pcap": self.repo.artifact(path), "summary": _summary_dict(summary),
                "reference": self.repo.write_csv(output / f"reference-{name}.csv", header, selected[name]),
                "reference_flows": len(selected[name]),
                "reference_labels": dict(Counter(row["Label"] for row in selected[name])),
            }
        manifest = {
            "stage": "pcap preparation", "config": self.repo.relative(config.path), "config_sha256": config.sha256,
            "source": {"file": self.repo.relative(source.file), "bytes": source.bytes, "sha256": source.sha256,
                       "mirror": source.mirror, "mirror_commit": source.mirror_commit,
                       "path_in_mirror": source.path_in_mirror, "official_md5_checked": False},
            "flows_csv": {"file": self.repo.relative(config.flows_csv), **flows_csv},
            "steps": [
                {"tool": "pcapfix", "result": fix, "output": fixed_record},
                {"tool": "reordercap", "output_text": reorder_output},
            ],
            "source_capinfos": self.tools.capinfos(source.file),
            "reordered": {**self.repo.artifact(reordered), "capinfos": reordered_info,
                          "identical_to_source": sha256(reordered) == source.sha256},
            "segments": segments, "border_seconds": config.border_seconds,
            "tools": self.tools.versions("pcapfix", "reordercap", "editcap"),
            "environment": self.repo.environment(),
        }
        self.repo.write_json(output / "manifest.json", manifest)
        return CommandResult(output / "manifest.json", None, manifest)

    def check_extraction(self, segment: str) -> CommandResult:
        config = self.repo.read_config(self.config_path)
        manifest = self.repo.read_json(config.output_dir / "manifest.json")
        if segment not in manifest["segments"]:
            raise TrafficPreparationError(f"Trecho desconhecido: {segment}.")
        info = manifest["segments"][segment]
        pcap = self.repo.checked(info["pcap"])
        reference_csv = self.repo.checked(info["reference"])
        build = ExtractorBuild(self.extractor_dir)
        run_dir = self.repo.create_run("extracao")
        extracted_csv = run_dir / "extracted.csv"
        statistics = build.run_reference(pcap, extracted_csv)
        header, extracted = self.repo.read_extracted_csv(extracted_csv)
        csv_header = self.repo.csv_header(reference_csv)
        expected_header = [column for column in csv_header if column not in CSV_ONLY]
        reference = list(self.repo.iter_csv(reference_csv))
        inputs = self.repo.data_manifest()["inputs"]

        border_start = info["stop_us"] - config.border_seconds * 1_000_000
        inside = lambda row: parse_timestamp_us(row["Timestamp"]) < border_start  # noqa: E731
        pairs, only_reference, only_extracted = match_rows(reference, extracted)
        inside_pairs = [pair for pair in pairs if inside(pair[0])]
        border_pairs = [pair for pair in pairs if not inside(pair[0])]
        attributes = compare_attributes(inside_pairs, inputs)
        excluded = compare_attributes(inside_pairs, EXCLUDED)
        border_attributes = compare_attributes(border_pairs, inputs)
        unmatched_reference_inside = [row for row in only_reference if inside(row)]
        unmatched_extracted_inside = [row for row in only_extracted if inside(row)]
        dropped_by_labelling = [row for row in unmatched_extracted_inside if has_nan(row)]
        unexplained_extracted_inside = [row for row in unmatched_extracted_inside if not has_nan(row)]
        input_mismatches = sum(item["mismatches"] for item in attributes.values())
        emission = self._emission_equivalence(build, pcap, extracted_csv)
        passed = (header == expected_header and not unmatched_reference_inside and not unexplained_extracted_inside
                  and input_mismatches == 0 and emission["equal"])
        summary = {
            "stage": "flow extraction check", "run_id": run_dir.name, "passed": passed, "segment": segment,
            "config": self.repo.relative(config.path), "preparation_manifest": self.repo.relative(
                config.output_dir / "manifest.json"),
            "pcap": info["pcap"], "reference": info["reference"], "stop": info["stop"],
            "border_seconds": config.border_seconds, "extractor_commit": EXTRACTOR_COMMIT,
            "extractor_build": build.record, "extractor_statistics": statistics,
            "extracted": {**self.repo.artifact(extracted_csv), "flows": len(extracted)},
            "header": {"equal": header == expected_header, "extractor_columns": len(header),
                       "csv_columns_compared": len(expected_header), "csv_only_columns": list(CSV_ONLY),
                       "differences": [[a, b] for a, b in zip(header, expected_header) if a != b]},
            "flows": {
                "reference": len(reference), "extracted": len(extracted),
                "matched_inside": len(inside_pairs), "matched_border": len(border_pairs),
                "reference_only_inside": len(unmatched_reference_inside),
                "reference_only_border": len(only_reference) - len(unmatched_reference_inside),
                "extracted_only_inside": len(unmatched_extracted_inside),
                "extracted_only_inside_with_nan": len(dropped_by_labelling),
                "nan_columns": dict(Counter(name for row in dropped_by_labelling for name, value in row.items()
                                            if value == "NaN")),
                "extracted_with_nan": sum(1 for row in extracted if has_nan(row)),
                "reference_with_nan": sum(1 for row in reference if has_nan(row)),
                "extracted_only_border": len(only_extracted) - len(unmatched_extracted_inside),
            },
            "matched_inside_labels": dict(Counter(pair[0]["Label"] for pair in inside_pairs)),
            "nids_extractor": emission,
            "attributes": attributes, "excluded_attributes": excluded, "relative_tolerance": RELATIVE_TOLERANCE,
            "border_attributes": {name: item for name, item in border_attributes.items() if item["mismatches"]},
            "examples": {
                "reference_only_inside": [_flow_brief(row) for row in unmatched_reference_inside[:EXAMPLES]],
                "extracted_only_inside": [_flow_brief(row) for row in unexplained_extracted_inside[:EXAMPLES]],
                "extracted_only_inside_with_nan": [_flow_brief(row) for row in dropped_by_labelling[:EXAMPLES]],
            },
            "environment": self.repo.environment(),
        }
        self.repo.write_json(run_dir / "report.json", summary)
        report = self.repo.write_report(f"extracao-pcap-{run_dir.name}.md", reporting.render_extraction(summary))
        if not passed:
            raise TrafficPreparationError(f"A extração diverge dos fluxos rotulados. Ver {report}.")
        return CommandResult(run_dir, report, summary)


    def _emission_equivalence(self, build: ExtractorBuild, pcap: Path, reference_csv: Path) -> dict[str, Any]:
        """Compara as linhas do extrator do NIDS, em modo arquivo, com as do extrator de referência."""
        with reference_csv.open(encoding="utf-8") as stream:
            header = stream.readline().rstrip("\n")
            reference = Counter(line.rstrip("\n") for line in stream if line.rstrip("\n") != header)
        process = NidsExtractorProcess(build, {"pcap": str(pcap)}, {})
        nids: Counter[str] = Counter()
        causes: Counter[str] = Counter()
        for event, payload in process.events():
            if event == "flow":
                nids[",".join(payload.values[name] for name in process.header)] += 1
                causes[payload.cause] += 1
        end = process.end or {}
        return {"equal": nids == reference, "reference_lines": sum(reference.values()), "nids_lines": sum(nids.values()),
                "only_reference": sum((reference - nids).values()), "only_nids": sum((nids - reference).values()),
                "by_cause": dict(causes), "packets_after_emission": end.get("packets_after_emission"),
                "packets_read": end.get("packets_read")}


def _microseconds(moment: Any) -> int:
    return parse_timestamp_us(moment.strftime("%Y-%m-%d %H:%M:%S.%f"))
