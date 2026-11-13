import numpy as np
import pytest

from core.frozen_prediction import FrozenPredictor
from core.instrumentation import monotonic_ns, verify_shared_clock
from domains.nids.service import _endpoints_key, _ordinal_key, _temporal, _with_ordinal, input_vector
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
                                            "Fwd Bulk Rate Avg", "Total TCP Flow Time"))
    assert not any(_temporal(name) for name in ("Total Fwd Packet", "Fwd Packet Length Max", "SYN Flag Count",
                                                "FWD Init Win Bytes", "Subflow Fwd Bytes"))
