from collections import Counter
from pathlib import Path

import pytest

from config import get_settings
from core.flow_extractor import ExtractorBuild, NidsExtractorProcess
from core.pcap_tools import PcapTools
from pcap_factory import ACK, FIN, PSH, RST, SYN, tcp, udp, write_pcap

BUILD = get_settings().extractor_build_dir
pytestmark = pytest.mark.skipif(not (BUILD / "extractor-build.json").is_file(),
                                reason="extrator não compilado; execute extractor/build.sh")
START, SECOND = 1_499_169_224_000_000, 1_000_000
A, B, C, D = "192.168.10.5", "192.168.10.3", "192.168.10.9", "205.174.165.73"


@pytest.fixture(scope="module")
def scenario(tmp_path_factory) -> Path:
    """Conexão TCP dividida pelo tempo limite, conexão reaberta depois de FIN, RST e UDP longo."""
    packets = [tcp(START, A, B, 50000, 80, SYN), tcp(START + 100, B, A, 80, 50000, SYN | ACK),
               tcp(START + 200, A, B, 50000, 80, ACK)]
    for step in range(1, 30):
        packets += [tcp(START + step * 10 * SECOND, A, B, 50000, 80, PSH | ACK, payload=100 + step),
                    tcp(START + step * 10 * SECOND + 500, B, A, 80, 50000, ACK)]
    for base in (START + 5 * SECOND, START + 50 * SECOND):
        packets += [tcp(base, C, B, 40000, 443, SYN), tcp(base + 50, B, C, 443, 40000, SYN | ACK),
                    tcp(base + 100, C, B, 40000, 443, ACK), tcp(base + 200, C, B, 40000, 443, PSH | ACK, payload=300),
                    tcp(base + 300, B, C, 443, 40000, FIN | ACK), tcp(base + 400, C, B, 40000, 443, FIN | ACK),
                    tcp(base + 500, B, C, 443, 40000, ACK)]
    packets += [tcp(START + 7 * SECOND, A, D, 41000, 22, SYN), tcp(START + 7 * SECOND + 80, D, A, 22, 41000, RST | ACK)]
    for step in range(7):
        packets += [udp(START + step * 40 * SECOND + 7, C, "8.8.8.8", 5353, 53, payload=40),
                    udp(START + step * 40 * SECOND + 900, "8.8.8.8", C, 53, 5353, payload=90)]
    packets.sort(key=lambda packet: packet.timestamp_us)
    return write_pcap(tmp_path_factory.mktemp("pcap") / "scenario.pcap", packets)


def test_nids_extractor_emits_the_same_flows_as_the_unmodified_extractor(scenario, tmp_path):
    build = ExtractorBuild(BUILD)
    statistics = build.run_reference(scenario, tmp_path / "reference.csv")
    lines = (tmp_path / "reference.csv").read_text().splitlines()
    reference = Counter(line for line in lines[1:] if line != lines[0])
    process = NidsExtractorProcess(build, {"pcap": str(scenario)}, {})
    flows = [payload for event, payload in process.events() if event == "flow"]
    emitted = Counter(",".join(flow.values[name] for name in process.header) for flow in flows)
    assert statistics["packets_valid"] == 91 and emitted == reference and sum(reference.values()) == 8
    assert Counter(flow.cause for flow in flows) == {"timeout_sweep": 6, "tcp_new_connection": 1, "end_of_capture": 1}
    assert process.end["packets_after_emission"] == 0 and process.end["flows_emitted"] == 8


def test_sweep_emits_a_flow_once_its_timeout_has_passed_in_the_capture_clock(scenario):
    process = NidsExtractorProcess(ExtractorBuild(BUILD), {"pcap": str(scenario)}, {})
    for event, payload in process.events():
        if event == "flow" and payload.cause == "timeout_sweep":
            assert payload.capture_clock_us - payload.first_packet_us > 120 * SECOND
            assert payload.last_packet_us - payload.first_packet_us <= 120 * SECOND


def test_tcp_connection_split_by_the_timeout_accumulates_its_duration(scenario):
    process = NidsExtractorProcess(ExtractorBuild(BUILD), {"pcap": str(scenario)}, {})
    totals = sorted(int(payload.values["Total TCP Flow Time"]) for event, payload in process.events()
                    if event == "flow" and payload.values["Src Port"] == "50000")
    assert totals == [120_000_000, 240_000_500, 290_000_500]


def test_pcap_summary_keeps_the_microseconds_of_each_timestamp(tmp_path):
    path = write_pcap(tmp_path / "fraction.pcap", [udp(START + 364_079, A, B, 53, 53), udp(START + 999_999, B, A, 53, 53)])
    summary = PcapTools().summarize(path)
    assert (summary.first_us, summary.last_us) == (START + 364_079, START + 999_999)


def test_pcap_summary_reads_record_headers(scenario):
    summary = PcapTools().summarize(scenario)
    assert summary.packets == 91 and summary.disordered_packets == 0 and summary.link_type == 1
    # O maior quadro é o pacote TCP com 300 bytes de carga: Ethernet, IPv4 e TCP somam 54 bytes de cabeçalho.
    assert summary.first_us == START and summary.max_frame_bytes == 14 + 20 + 20 + 300
