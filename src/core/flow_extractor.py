"""Adaptador do extrator Java: único módulo que conhece o processo e o formato das suas linhas."""

import hashlib
import json
import os
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

EXTRACTOR_COMMIT = "13a061520b862d605eea746c79ca4033b30d98fc"
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
METADATA = ("Flow ID", "Src IP", "Src Port", "Dst IP", "Dst Port", "Protocol", "Timestamp")


@dataclass(frozen=True)
class ExtractedFlow:
    seq: int
    cause: str
    first_packet_us: int
    last_packet_us: int
    capture_clock_us: int
    t0_ns: int
    values: dict[str, str]


class ExtractorBuild:
    """Verifica e usa os jars produzidos por extractor/build.sh."""

    def __init__(self, build_dir: Path) -> None:
        self.build_dir = build_dir
        record_path = build_dir / "extractor-build.json"
        if not record_path.is_file():
            raise FileNotFoundError(f"Extrator não compilado: execute extractor/build.sh ({record_path}).")
        self.record = json.loads(record_path.read_text(encoding="utf-8"))
        if self.record["extractor_commit"] != EXTRACTOR_COMMIT:
            raise ValueError("O extrator compilado não é o do commit fixado pela decisão 3.")
        for name, expected in self.record["jars"].items():
            if _sha256(build_dir / name) != expected:
                raise ValueError(f"O jar {name} mudou depois do build.")

    def command(self, jar: str, main_class: str, arguments: list[str]) -> tuple[list[str], dict[str, str]]:
        native = self.build_dir / "native"
        environment = {**os.environ, "LD_LIBRARY_PATH": str(native)}
        classpath = f"{self.build_dir / jar}:{self.build_dir / 'lib'}/*"
        return ["java", f"-Djava.library.path={native}", "-cp", classpath, main_class, *arguments], environment

    def run_reference(self, pcap: Path, output_csv: Path) -> dict[str, Any]:
        command, environment = self.command("reference-extractor.jar", "nids.extractor.ReferenceExtractor",
                                            [str(pcap), str(output_csv)])
        result = subprocess.run(command, env=environment, capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError(f"Falha no extrator de referência: {result.stderr.strip() or result.stdout.strip()}")
        return json.loads(result.stdout.strip().splitlines()[-1])


class NidsExtractorProcess:
    """Processo do extrator do NIDS, lido linha a linha. A captura ao vivo para quando a entrada é fechada."""

    def __init__(self, build: ExtractorBuild, source: dict[str, str], options: dict[str, int]) -> None:
        if len(source) != 1 or next(iter(source)) not in ("pcap", "iface"):
            raise ValueError("A fonte do extrator deve ser um arquivo (pcap) ou uma interface (iface).")
        (kind, location), = source.items()
        arguments = [f"--{kind}", location]
        for key, value in options.items():
            arguments += [f"--{key}", str(value)]
        command, environment = build.command("nids-extractor.jar", "nids.extractor.NidsExtractor", arguments)
        self.process = subprocess.Popen(command, env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, bufsize=1)
        self.start: dict[str, Any] | None = None
        self.end: dict[str, Any] | None = None
        self.header: list[str] = []

    def events(self) -> Iterator[tuple[str, Any]]:
        """Devolve ("start", dict), ("flow", ExtractedFlow) e ("end", dict), na ordem do extrator."""
        assert self.process.stdout is not None
        for line in self.process.stdout:
            event = json.loads(line)
            if event["type"] == "start":
                self.start = event
                self.header = event["header"]
                yield "start", event
            elif event["type"] == "flow":
                yield "flow", ExtractedFlow(event["seq"], event["cause"], event["first_packet_us"],
                                            event["last_packet_us"], event["capture_clock_us"], event["t0_ns"],
                                            parse_features(event["features"], self.header))
            elif event["type"] == "end":
                self.end = event
                yield "end", event
        code = self.process.wait()
        if code != 0 or self.end is None:
            stderr = self.process.stderr.read() if self.process.stderr else ""
            raise RuntimeError(f"O extrator terminou com código {code}: {stderr.strip()}")

    def request_stop(self) -> None:
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()

    def kill(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait()


def parse_features(line: str, header: list[str]) -> dict[str, str]:
    values = line.split(",")
    if len(values) != len(header):
        raise ValueError(f"Linha do extrator com {len(values)} campos; o cabeçalho tem {len(header)}.")
    return dict(zip(header, values))


def parse_timestamp_us(text: str) -> int:
    """Converte o Timestamp do extrator e dos CSVs, em UTC, para microssegundos desde a época."""
    moment = datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
    return (moment - _EPOCH) // timedelta(microseconds=1)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
