import math

import pytest

from core.flow_extractor import parse_features, parse_timestamp_us
from domains.traffic_preparation.service import compare_attributes, flow_key, match_rows, same_value, ulps_apart


def _row(flow_id="10.0.0.1-10.0.0.2-1000-80-6", timestamp="2017-07-04 11:53:44.000001", **values):
    source, destination, sport, dport, protocol = flow_id.split("-")
    return {"Flow ID": flow_id, "Src IP": source, "Src Port": sport, "Dst IP": destination, "Dst Port": dport,
            "Protocol": protocol, "Timestamp": timestamp, **values}


def test_timestamps_with_and_without_fraction_are_the_same_instant():
    assert parse_timestamp_us("2017-07-04 11:53:44") == parse_timestamp_us("2017-07-04 11:53:44.000000")
    assert parse_timestamp_us("2017-07-04 11:53:44.001") - parse_timestamp_us("2017-07-04 11:53:44") == 1000
    assert flow_key(_row(timestamp="2017-07-04 11:53:44.1")) == flow_key(_row(timestamp="2017-07-04 11:53:44.100000"))


def test_rows_with_the_same_key_are_paired_in_order_and_leftovers_are_reported():
    left = [_row(value="a"), _row(value="b"), _row(flow_id="10.0.0.3-10.0.0.2-5-53-17", value="c")]
    right = [_row(value="x"), _row(timestamp="2017-07-04 12:00:00", value="y"), _row(value="z")]
    pairs, only_left, only_right = match_rows(left, right)
    assert [(a["value"], b["value"]) for a, b in pairs] == [("a", "x"), ("b", "z")]
    assert [row["value"] for row in only_left] == ["c"]
    assert [row["value"] for row in only_right] == ["y"]


def test_values_compare_as_numbers_including_infinity_and_nan():
    assert same_value("40", "40.0") and same_value("Infinity", "inf") and same_value("NaN", "nan")
    assert not same_value("1.0", "1.0000000001")


def test_attribute_comparison_counts_mismatches_and_keeps_an_example():
    pairs = [(_row(A="1.0", B="2"), _row(A="1", B="3")), (_row(A="5", B="2"), _row(A="5", B="2.5"))]
    result = compare_attributes(pairs, ["A", "B"])
    assert result["A"]["mismatches"] == 0 and result["A"]["example"] is None
    assert result["B"]["mismatches"] == 2 and math.isclose(result["B"]["max_abs_difference"], 1.0)
    assert result["B"]["example"]["left"] == "2"


def test_extractor_line_must_have_one_value_per_header_column():
    assert parse_features("a,b,c", ["x", "y", "z"]) == {"x": "a", "y": "b", "z": "c"}
    with pytest.raises(ValueError):
        parse_features("a,b", ["x", "y", "z"])


def test_fractional_values_may_differ_by_rounding_but_integers_must_match():
    assert ulps_apart("14988137.233276444", "1.4988137233276445E7") == 1
    assert ulps_apart("1", "1") == 0 and ulps_apart("inf", "1") == math.inf
    pairs = [(_row(A="0.1110730328071751"), _row(A="0.11107303280717519")), (_row(A="5"), _row(A="6")),
             (_row(A="100000000000000"), _row(A="100000000000001"))]
    result = compare_attributes(pairs, ["A"])["A"]
    assert result["rounding_differences"] == 1 and result["max_rounding_ulps"] == 6
    assert result["mismatches"] == 2 and result["example"]["left"] == "5"
