"""Adaptador das ferramentas externas de PCAP (pcapfix, reordercap, editcap, capinfos) e leitura dos registros."""

import shutil
import socket
import struct
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Número mágico do PCAP clássico: ordem dos bytes e divisor que converte a fração do segundo em microssegundos.
_MAGIC = {
    b"\xd4\xc3\xb2\xa1": ("<", 1), b"\xa1\xb2\xc3\xd4": (">", 1),
    b"\x4d\x3c\xb2\xa1": ("<", 1_000), b"\xa1\xb2\x3c\x4d": (">", 1_000),
}


ETHERNET = 1
_VLAN = (0x8100, 0x88A8)
_TCP, _UDP = 6, 17


@dataclass(frozen=True)
class PcapRecord:
    """Registro de um PCAP clássico: instante em microssegundos, cabeçalho de 16 bytes e bytes capturados."""
    timestamp_us: int
    header: bytes
    data: bytes


@dataclass(frozen=True)
class Endpoints:
    """Endereços IPv4, protocolo e portas de um pacote. As portas são 0 fora de TCP e UDP e nos fragmentos que
    não são o primeiro."""
    src: str
    dst: str
    protocol: int
    sport: int
    dport: int

    def connection(self) -> tuple[str, int, str, int, int]:
        """Identifica a conexão sem o sentido: as duas pontas em ordem e o protocolo."""
        first, second = sorted([(self.src, self.sport), (self.dst, self.dport)])
        return (*first, *second, self.protocol)


def read_header(path: Path) -> tuple[bytes, str, int, int]:
    """Cabeçalho global de um PCAP clássico, ordem dos bytes, divisor da fração do segundo e tipo de enlace."""
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:4] not in _MAGIC:
        raise ValueError(f"{path} não é um PCAP clássico.")
    order, divisor = _MAGIC[header[:4]]
    return header, order, divisor, struct.unpack(order + "I", header[20:24])[0]


def read_records(path: Path) -> Iterator[PcapRecord]:
    """Registros de um PCAP clássico, na ordem do arquivo."""
    _, order, divisor, _ = read_header(path)
    record = struct.Struct(order + "IIII")
    with path.open("rb") as stream:
        stream.seek(24)
        while chunk := stream.read(16):
            if len(chunk) < 16:
                raise ValueError(f"Registro truncado em {path}.")
            seconds, fraction, captured, _ = record.unpack(chunk)
            data = stream.read(captured)
            if len(data) < captured:
                raise ValueError(f"Registro truncado em {path}.")
            yield PcapRecord(seconds * 1_000_000 + fraction // divisor, chunk, data)


def ipv4_endpoints(frame: bytes, link_type: int = ETHERNET) -> Endpoints | None:
    """Endereços, protocolo e portas de um quadro Ethernet com IPv4. Outros quadros devolvem None."""
    if link_type != ETHERNET or len(frame) < 14:
        return None
    offset, ether_type = 14, struct.unpack_from("!H", frame, 12)[0]
    while ether_type in _VLAN and len(frame) >= offset + 4:
        ether_type = struct.unpack_from("!H", frame, offset + 2)[0]
        offset += 4
    if ether_type != 0x0800 or len(frame) < offset + 20 or frame[offset] >> 4 != 4:
        return None
    length = (frame[offset] & 0x0F) * 4
    protocol = frame[offset + 9]
    fragment = struct.unpack_from("!H", frame, offset + 6)[0] & 0x1FFF
    src = socket.inet_ntoa(frame[offset + 12:offset + 16])
    dst = socket.inet_ntoa(frame[offset + 16:offset + 20])
    sport = dport = 0
    if protocol in (_TCP, _UDP) and fragment == 0 and len(frame) >= offset + length + 4:
        sport, dport = struct.unpack_from("!HH", frame, offset + length)
    return Endpoints(src, dst, protocol, sport, dport)


def write_time_scaled(source: Path, target: Path, factor: float) -> int:
    """Grava o PCAP com os intervalos entre pacotes divididos pelo fator, a partir do primeiro pacote.

    É o tráfego que a reprodução acelerada entregaria, sem atraso de envio nem de captura. Os bytes dos pacotes não
    mudam. Os instantes ficam em microssegundos, arredondados para baixo, e a ordem dos pacotes se mantém."""
    header, order, divisor, _ = read_header(source)
    if divisor != 1:
        raise ValueError(f"{source} tem instantes em nanossegundos.")
    record = struct.Struct(order + "IIII")
    first = None
    written = 0
    with target.open("wb") as stream:
        stream.write(header)
        for item in read_records(source):
            first = item.timestamp_us if first is None else first
            scaled = first + int((item.timestamp_us - first) / factor)
            _, _, captured, original = record.unpack(item.header)
            stream.write(record.pack(scaled // 1_000_000, scaled % 1_000_000, captured, original))
            stream.write(item.data)
            written += 1
    return written


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
