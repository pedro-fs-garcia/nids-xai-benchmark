import subprocess
import sys

import numpy as np
import pytest

from core import flow_extractor
from core.flow_extractor import NidsExtractorProcess
from core.frozen_prediction import FrozenPredictor
from core.instrumentation import monotonic_ns, verify_shared_clock
from domains.nids.service import (_endpoints_key, _ordinal_key, _packet_shifts, _temporal, _with_ordinal, input_vector,
                                  replay_checks, run_checks)
from domains.traffic_preparation.service import match_rows

MANIFEST = {
    "inputs": ["Protocol", "Flow Bytes/s", "Flow Packets/s"],
    "preprocessing": {"positive_infinity_columns": ["Flow Bytes/s", "Flow Packets/s"],
                      "positive_infinity_replacement": -1.0},
}


def test_input_vector_follows_the_manifest_order_and_the_training_infinity_rule():
    values = {"Flow Packets/s": "Infinity", "Protocol": "17", "Flow Bytes/s": "120.5", "Label": "NeedManualLabel"}
    assert input_vector(values, MANIFEST).tolist() == [[17.0, 120.5, -1.0]]


@pytest.mark.parametrize("value", ["NaN", "-Infinity"])
def test_input_vector_rejects_values_the_training_data_never_had(value):
    with pytest.raises(ValueError):
        input_vector({"Protocol": "6", "Flow Bytes/s": value, "Flow Packets/s": "1"}, MANIFEST)


def test_class_rule_keeps_ties_benign_and_rejects_invalid_probabilities():
    assert FrozenPredictor.classify(np.array([0.5, 0.500001, 0.0])).tolist() == [0, 1, 0]
    with pytest.raises(ValueError):
        FrozenPredictor.classify(np.array([1.2]))


def test_shared_clock_accepts_a_recent_reading_and_rejects_another_clock():
    assert 0 <= verify_shared_clock(monotonic_ns(), 10**9) <= 10**9
    with pytest.raises(ValueError):
        verify_shared_clock(monotonic_ns() + 10**12, 10**9)
    with pytest.raises(ValueError):
        verify_shared_clock(monotonic_ns() - 10**12, 10**9)


def _flow(seq, first, sport="1000", source="10.0.0.1", destination="10.0.0.2", dport="80"):
    return {"seq": str(seq), "first_packet_us": str(first), "Flow ID": f"{source}-{destination}-{sport}-{dport}-6",
            "Src IP": source, "Src Port": sport, "Dst IP": destination, "Dst Port": dport, "Protocol": "6"}


def test_runs_with_different_clocks_are_matched_by_five_tuple_and_occurrence():
    file_run = _with_ordinal([_flow(1, 100), _flow(2, 400), _flow(3, 200, sport="2000")])
    replay = _with_ordinal([_flow(7, 9_000_400), _flow(5, 9_000_100), _flow(6, 9_000_200, sport="2000")])
    pairs, only_file, only_replay = match_rows(file_run, replay, key=_ordinal_key)
    assert sorted((a["seq"], b["seq"]) for a, b in pairs) == [("1", "5"), ("2", "7"), ("3", "6")]
    assert not only_file and not only_replay


def test_a_flow_seen_in_the_opposite_direction_has_the_same_endpoints():
    forward = _flow(1, 1)
    backward = _flow(2, 1, sport="80", source="10.0.0.2", destination="10.0.0.1", dport="1000")
    assert _endpoints_key(forward) == _endpoints_key(backward)


def test_temporal_attributes_are_those_that_depend_on_capture_instants():
    assert all(_temporal(name) for name in ("Flow Duration", "Fwd IAT Mean", "Flow Bytes/s", "Idle Max",
                                            "Fwd Bulk Rate Avg", "Fwd Bytes/Bulk Avg", "Bwd Packet/Bulk Avg",
                                            "Total TCP Flow Time"))
    assert not any(_temporal(name) for name in ("Total Fwd Packet", "Fwd Packet Length Max", "SYN Flag Count",
                                                "FWD Init Win Bytes", "Subflow Fwd Bytes"))


def _classified(seq, t0, t1, t2, t3, error=None):
    return {"seq": seq, "t0_ns": t0, "t1_ns": t1, "t2_ns": t2, "t3_ns": t3, "error": error}


def test_run_checks_pass_when_every_emitted_flow_arrives_with_ordered_marks():
    flows = [_classified(1, 10, 20, 30, 40), _classified(2, 15, 40, 50, 60),
             _classified(3, 18, None, None, None, error="Valor não finito em Flow Bytes/s.")]
    checks = run_checks("interface", {"flows_emitted": 3, "packets_after_emission": 7}, flows)
    assert all(checks.values())


def test_run_checks_fail_on_a_lost_flow_on_unordered_marks_and_on_a_late_packet_in_file_mode():
    flows = [_classified(1, 10, 20, 30, 40), _classified(2, 15, 14, 50, 60)]
    checks = run_checks("arquivo", {"flows_emitted": 3, "packets_after_emission": 1}, flows)
    assert not checks["emitted_equals_received"] and not checks["timestamps_ordered"]
    assert not checks["no_packets_after_emission_in_file_mode"] and checks["received_equals_classified_plus_errors"]


COUNTERS = {"segment_packets": 100, "tcpreplay_successful": 100, "tcpreplay_failed": 0, "h1_sent": 100,
            "h2_received": 100, "h2_dropped": 0, "pcap_dropped": 0, "pcap_interface_dropped": 0, "extractor_read": 100}


def test_replay_checks_pass_when_every_packet_goes_from_tcpreplay_to_the_extractor():
    assert all(replay_checks(COUNTERS, {"emitted_equals_received": True}).values())


@pytest.mark.parametrize("change, failed", [
    ({"tcpreplay_successful": 90}, {"tcpreplay_sent_whole_segment", "h1_sent_equals_tcpreplay_successful"}),
    ({"h2_received": 99}, {"h2_received_equals_h1_sent", "extractor_read_equals_h2_received"}),
    ({"pcap_dropped": 4, "extractor_read": 96}, {"no_capture_drops", "extractor_read_equals_h2_received"}),
])
def test_replay_checks_point_to_the_stage_that_lost_packets(change, failed):
    checks = replay_checks({**COUNTERS, **change}, {"emitted_equals_received": True})
    assert {name for name, passed in checks.items() if not passed} == failed


def test_replay_checks_fail_when_the_replay_run_lost_a_flow():
    assert not replay_checks(COUNTERS, {"emitted_equals_received": False})["replay_run_flow_chain"]


def _counted(seq, first, forward, backward, sport="1000"):
    return {**_flow(seq, first, sport=sport), "Total Fwd Packet": str(forward), "Total Bwd packets": str(backward),
            "Timestamp": "2017-07-04 12:00:00"}


def test_packets_that_move_to_the_next_flow_of_a_connection_are_told_apart_from_lost_packets():
    file_run = [_counted(1, 100, 50, 60), _counted(2, 200, 30, 40), _counted(3, 150, 5, 5, sport="2000")]
    replay = [_counted(1, 100, 51, 61), _counted(2, 200, 29, 39), _counted(3, 150, 5, 3, sport="2000")]
    pairs = list(zip(file_run, replay))
    shifts = _packet_shifts(pairs, pairs)
    assert (shifts["flows"], shifts["conserved_in_connection"], shifts["connections"]) == (3, 2, 1)


def test_extractor_that_ignores_the_stop_request_is_killed_and_the_run_fails(monkeypatch):
    monkeypatch.setattr(flow_extractor, "STOP_TIMEOUT_S", 0.3)
    extractor = NidsExtractorProcess.__new__(NidsExtractorProcess)
    extractor.process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    extractor.start = extractor.end = extractor._watchdog = None
    extractor.header, extractor.killed_after_stop_timeout = [], False
    extractor.request_stop()
    with pytest.raises(RuntimeError, match="não parou"):
        list(extractor.events())
    assert extractor.process.poll() is not None


def test_extractor_that_stops_when_asked_is_not_killed(monkeypatch):
    monkeypatch.setattr(flow_extractor, "STOP_TIMEOUT_S", 5.0)
    extractor = NidsExtractorProcess.__new__(NidsExtractorProcess)
    script = ("import json, sys\nprint(json.dumps({'type': 'start', 'header': ['a']}), flush=True)\n"
              "sys.stdin.read()\nprint(json.dumps({'type': 'end', 'flows_emitted': 0}), flush=True)")
    extractor.process = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    extractor.start = extractor.end = extractor._watchdog = None
    extractor.header, extractor.killed_after_stop_timeout = [], False
    extractor.request_stop()
    assert [event for event, _ in extractor.events()] == ["start", "end"]
    assert not extractor.killed_after_stop_timeout
