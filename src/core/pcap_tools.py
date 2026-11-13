"""Adaptador das ferramentas externas de PCAP (pcapfix, reordercap, editcap, capinfos) e leitura dos cabeçalhos."""

import shutil
import struct
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Número mágico do PCAP clássico: ordem dos bytes e divisor que converte a fração do segundo em microssegundos.
_MAGIC = {
    b"\xd4\xc3\xb2\xa1": ("<", 1), b"\xa1\xb2\xc3\xd4": (">", 1),
    b"\x4d\x3c\xb2\xa1": ("<", 1_000), b"\xa1\xb2\x3c\x4d": (">", 1_000),
}


@dataclass(frozen=True)
class PcapSummary:
    packets: int
    first_us: int | None
    last_us: int | None
    max_frame_bytes: int
    max_captured_bytes: int
    link_type: int
    disordered_packets: int


class PcapTools:
    def require(self, *tools: str) -> None:
        missing = [tool for tool in tools if shutil.which(tool) is None]
        if missing:
            raise FileNotFoundError(f"Ferramentas ausentes: {', '.join(missing)}.")

    def versions(self, *tools: str) -> dict[str, str]:
        versions = {}
        for tool in tools:
            result = subprocess.run([tool, "--version" if tool != "pcapfix" else "-h"],
                                    capture_output=True, text=True, check=False)
            text = (result.stdout or result.stderr).strip().splitlines()
            versions[tool] = text[0] if text else "desconhecida"
        return versions

    def pcapfix(self, source: Path, target: Path) -> dict[str, object]:
        """Corrige o arquivo. O pcapfix só grava a saída quando encontra algo a corrigir."""
        result = subprocess.run(["pcapfix", "-o", str(target), str(source)], capture_output=True, text=True, check=False)
        return {"exit_code": result.returncode, "output": (result.stdout + result.stderr).strip(),
                "fixed_file_written": target.exists()}

    def reordercap(self, source: Path, target: Path) -> str:
        result = subprocess.run(["reordercap", str(source), str(target)], capture_output=True, text=True, check=True)
        return (result.stdout + result.stderr).strip()

    def cut_before(self, source: Path, target: Path, stop: datetime) -> None:
        """Copia os pacotes anteriores ao instante dado, em UTC."""
        if stop.tzinfo is None:
            raise ValueError("O instante de corte deve ter fuso horário.")
        stamp = stop.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
        subprocess.run(["editcap", "-F", "pcap", "-B", stamp, str(source), str(target)],
                       capture_output=True, text=True, check=True)

    def capinfos(self, path: Path) -> dict[str, str]:
        """Resumo do capinfos, que lê PCAP e pcapng: tipo, contagem de pacotes, instantes e ordem cronológica."""
        result = subprocess.run(["capinfos", "-M", "-K", "-t", "-E", "-c", "-s", "-a", "-e", "-o", str(path)],
                                capture_output=True, text=True, check=True)
        info = {}
        for line in result.stdout.splitlines():
            key, separator, value = line.partition(":")
            if separator:
                info[key.strip()] = value.strip()
        return info

    def summarize(self, path: Path) -> PcapSummary:
        """Lê os cabeçalhos de registro de um PCAP clássico, sem interpretar os pacotes."""
        with path.open("rb") as stream:
            header = stream.read(24)
            if len(header) != 24 or header[:4] not in _MAGIC:
                raise ValueError(f"{path} não é um PCAP clássico.")
            order, divisor = _MAGIC[header[:4]]
            link_type = struct.unpack(order + "I", header[20:24])[0]
            record = struct.Struct(order + "IIII")
            packets = disordered = max_frame = max_captured = 0
            first = last = previous = None
            while chunk := stream.read(16):
                if len(chunk) < 16:
                    raise ValueError(f"Registro truncado em {path}.")
                seconds, fraction, captured, original = record.unpack(chunk)
                stream.seek(captured, 1)
                timestamp = seconds * 1_000_000 + fraction // divisor
                if previous is not None and timestamp < previous:
                    disordered += 1
                previous = timestamp if previous is None else max(previous, timestamp)
                first = timestamp if first is None else first
                last = timestamp
                packets += 1
                max_frame = max(max_frame, original)
                max_captured = max(max_captured, captured)
        return PcapSummary(packets, first, last, max_frame, max_captured, link_type, disordered)
