"""Gera arquivos PCAP pequenos, com quadros Ethernet e IPv4, para os testes do extrator e do NIDS."""

import socket
import struct
from dataclasses import dataclass
from pathlib import Path

FIN, SYN, RST, PSH, ACK = 0x01, 0x02, 0x04, 0x08, 0x10
_ETHERNET = bytes.fromhex("020000000002" "020000000001") + struct.pack("!H", 0x0800)


@dataclass(frozen=True)
class Packet:
    timestamp_us: int
    frame: bytes


def tcp(timestamp_us: int, src: str, dst: str, sport: int, dport: int, flags: int,
        payload: int = 0, window: int = 8192) -> Packet:
    header = struct.pack("!HHIIBBHHH", sport, dport, 0, 0, 5 << 4, flags, window, 0, 0)
    return Packet(timestamp_us, _ip(src, dst, 6, header + bytes(payload)))


def udp(timestamp_us: int, src: str, dst: str, sport: int, dport: int, payload: int = 0) -> Packet:
    header = struct.pack("!HHHH", sport, dport, 8 + payload, 0)
    return Packet(timestamp_us, _ip(src, dst, 17, header + bytes(payload)))


def write_pcap(path: Path, packets: list[Packet]) -> Path:
    with path.open("wb") as stream:
        stream.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        for packet in packets:
            seconds, micros = divmod(packet.timestamp_us, 1_000_000)
            stream.write(struct.pack("<IIII", seconds, micros, len(packet.frame), len(packet.frame)))
            stream.write(packet.frame)
    return path


def _ip(src: str, dst: str, protocol: int, payload: bytes) -> bytes:
    header = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(payload), 0, 0, 64, protocol, 0,
                         socket.inet_aton(src), socket.inet_aton(dst))
    checksum = _checksum(header)
    header = header[:10] + struct.pack("!H", checksum) + header[12:]
    return _ETHERNET + header + payload


def _checksum(data: bytes) -> int:
    total = sum(struct.unpack(f"!{len(data) // 2}H", data))
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF
