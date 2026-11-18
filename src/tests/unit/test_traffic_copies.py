import json
import struct

import pytest

from core.machine_sampler import busy_shares, summarize
from core.pcap_tools import ipv4_endpoints, read_records, write_time_scaled
from core.traffic_copies import COPY_BLOCK, address_map, check_addresses, copy_address, copy_of, pnat_argument
from domains.nids.copies import split_copies
from tests.integration.pcap_factory import ACK, SYN, Packet, tcp, udp, write_pcap

ADDRESSES = ["192.168.10.5", "192.168.10.3", "8.8.8.8"]


def test_each_copy_gets_its_own_addresses_and_the_first_copy_keeps_the_originals():
    assert address_map(ADDRESSES, 1) == {}
    second, third = address_map(ADDRESSES, 2), address_map(ADDRESSES, 3)
    assert second["192.168.10.5"] == "100.64.0.0" and third["192.168.10.5"] == copy_address(0, 3)
    assert len(set(second.values()) | set(third.values()) | set(ADDRESSES)) == 3 * len(ADDRESSES)
    positions = {address: index for index, address in enumerate(ADDRESSES)}
    assert copy_of(third["8.8.8.8"], positions, ADDRESSES) == (3, "8.8.8.8")
    assert copy_of("8.8.8.8", positions, ADDRESSES) == (1, "8.8.8.8")
    assert copy_of("1.1.1.1", positions, ADDRESSES) is None


def test_the_rewrite_argument_lists_one_pair_per_address_in_the_given_order():
    assert pnat_argument(ADDRESSES, 1) is None
    assert pnat_argument(ADDRESSES, 2) == ("--pnat=192.168.10.5/32:100.64.0.0/32,192.168.10.3/32:100.64.0.1/32,"
                                           "8.8.8.8/32:100.64.0.2/32")


def test_addresses_that_collide_with_the_copies_or_overflow_the_block_are_refused():
    with pytest.raises(ValueError, match="bloco das cópias"):
        check_addresses(["100.64.3.1"])
    with pytest.raises(ValueError, match="mais que"):
        check_addresses([f"10.{index // 256}.{index % 256}.1" for index in range(COPY_BLOCK + 1)])


def _row(src, dst, flow_id=None, **values):
    return {"Src IP": src, "Dst IP": dst, "Flow ID": flow_id or f"{src}-{dst}-1000-80-6", **values}


def test_flows_go_back_to_the_original_addresses_of_their_copy():
    second = address_map(ADDRESSES, 2)
    rows = [_row("192.168.10.5", "8.8.8.8", seq="1"),
            _row(second["192.168.10.5"], second["8.8.8.8"], flow_id=f"{second['8.8.8.8']}-{second['192.168.10.5']}"
                 "-80-1000-6", seq="2"),
            _row("8.6.0.1", "8.0.6.4", seq="3"), _row(second["8.8.8.8"], "8.8.8.8", seq="4")]
    groups, unassigned = split_copies(rows, ADDRESSES)
    assert [row["seq"] for row in groups[1]] == ["1"]
    copied = groups[2][0]
    assert (copied["Src IP"], copied["Dst IP"]) == ("192.168.10.5", "8.8.8.8")
    assert copied["Flow ID"] == "8.8.8.8-192.168.10.5-80-1000-6"
    assert [row["seq"] for row in unassigned] == ["3", "4"]


def test_records_and_endpoints_are_read_and_time_scaling_keeps_the_bytes(tmp_path):
    source = write_pcap(tmp_path / "a.pcap", [
        tcp(1_000_000, "10.0.0.1", "10.0.0.2", 1000, 80, SYN),
        udp(1_500_000, "10.0.0.2", "10.0.0.1", 53, 5353, payload=4),
        tcp(3_000_001, "10.0.0.2", "10.0.0.1", 80, 1000, SYN | ACK)])
    records = list(read_records(source))
    endpoints = [ipv4_endpoints(record.data) for record in records]
    assert [(item.src, item.sport, item.protocol) for item in endpoints] == [
        ("10.0.0.1", 1000, 6), ("10.0.0.2", 53, 17), ("10.0.0.2", 80, 6)]
    assert endpoints[0].connection() == endpoints[2].connection()
    target = tmp_path / "x4.pcap"
    assert write_time_scaled(source, target, 4) == 3
    scaled = list(read_records(target))
    assert [record.timestamp_us for record in scaled] == [1_000_000, 1_125_000, 1_500_000]
    assert [record.data for record in scaled] == [record.data for record in records]
    assert ipv4_endpoints(b"\x00" * 12 + struct.pack("!H", 0x0806) + b"\x00" * 28) is None
    assert ipv4_endpoints(Packet(0, b"").frame) is None


def test_the_machine_summary_reports_power_frequency_throttling_and_busy_cpus():
    times_before = {0: (10, 100), 1: (0, 100)}
    times_after = {0: (60, 200), 1: (0, 200)}
    assert busy_shares(times_before, times_after) == {0: 0.5, 1: 0.0}
    sample = lambda online, frequency, throttle, busy: {  # noqa: E731
        "mains_online": online, "frequency_khz": {0: frequency}, "throttle": {0: {"core": throttle, "package": 5}},
        "busy_share": {0: busy}, "memory_kib": {"available": 1000, "swap_free": 10}}
    summary = summarize([sample(True, 1000, 3, 0.1), sample(False, 3000, 7, 0.3)], [0])
    assert summary["samples"] == 2 and summary["mains_online_in_every_sample"] is False
    assert summary["frequency_khz"]["0"] == {"min": 1000, "median": 2000, "max": 3000}
    assert summary["throttle_events"]["0"] == {"core": 4, "package": 0}
    assert json.dumps(summary)
