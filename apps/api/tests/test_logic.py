from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.logic import (
    determine_alarm,
    generate_demand_response_points,
    generate_power_outage_points,
    interpolate_profile,
    normalize_message,
    parse_timestamp,
    scenario_progress,
)


def test_parse_timestamp_with_naive_datetime_assigns_utc():
    value = datetime(2026, 1, 1, 12, 30, 0)
    result = parse_timestamp(value)

    assert result.tzinfo == UTC
    assert result.isoformat() == "2026-01-01T12:30:00+00:00"


def test_parse_timestamp_with_z_string_parses_utc():
    result = parse_timestamp("2026-01-01T12:30:00Z")

    assert result.tzinfo == UTC
    assert result.isoformat() == "2026-01-01T12:30:00+00:00"


def test_parse_timestamp_with_offset_string_converts_to_utc():
    result = parse_timestamp("2026-01-01T08:30:00-04:00")

    assert result.tzinfo == UTC
    assert result.isoformat() == "2026-01-01T12:30:00+00:00"


def test_parse_timestamp_raises_for_unsupported_type():
    with pytest.raises(TypeError):
        parse_timestamp(123)


def test_determine_alarm_for_normal_metric():
    assert determine_alarm("rack_temp_c", 31.9) == ("normal", "")
    assert determine_alarm("rack_temp_c", 32.0) == ("warning", "Rack inlet temperature high")
    assert determine_alarm("rack_temp_c", 38.0) == ("critical", "Rack inlet temperature high")


def test_determine_alarm_for_inverse_metric():
    assert determine_alarm("ups_battery_pct", 35.0) == ("normal", "")
    assert determine_alarm("ups_battery_pct", 30.0) == ("warning", "UPS battery low")
    assert determine_alarm("ups_battery_pct", 20.0) == ("critical", "UPS battery low")


def test_determine_alarm_for_demand_response_metric():
    assert determine_alarm("utility_price_usd_mwh", 399.9) == ("normal", "")
    assert determine_alarm("utility_price_usd_mwh", 400.0) == ("warning", "Utility price spike active")
    assert determine_alarm("utility_price_usd_mwh", 700.0) == ("critical", "Utility price spike active")
    assert determine_alarm("shed_load_pct", 20.0) == ("warning", "Demand-response load shedding active")


def test_scenario_progress_returns_zero_when_no_scenario():
    assert scenario_progress(None) == 0.0


def test_scenario_progress_computes_fractional_progress():
    scenario = {
        "activated_at": "2026-01-01T12:00:00Z",
        "expires_at": "2026-01-01T13:00:00Z",
    }
    ts = datetime(2026, 1, 1, 12, 30, 0, tzinfo=UTC)

    assert scenario_progress(scenario, ts) == 0.5


def test_scenario_progress_caps_at_one():
    scenario = {
        "activated_at": "2026-01-01T12:00:00Z",
        "expires_at": "2026-01-01T13:00:00Z",
    }
    ts = datetime(2026, 1, 1, 14, 0, 0, tzinfo=UTC)

    assert scenario_progress(scenario, ts) == 1.0


def test_interpolate_profile_raises_for_empty_points():
    with pytest.raises(ValueError):
        interpolate_profile([], 0.5)


def test_interpolate_profile_returns_first_point_before_start():
    points = [(0.0, 10.0), (0.5, 20.0), (1.0, 40.0)]

    assert interpolate_profile(points, -0.1) == 10.0
    assert interpolate_profile(points, 0.0) == 10.0


def test_interpolate_profile_linearly_interpolates_between_points():
    points = [(0.0, 10.0), (0.5, 20.0), (1.0, 40.0)]

    assert interpolate_profile(points, 0.25) == 15.0
    assert interpolate_profile(points, 0.75) == 30.0


def test_interpolate_profile_returns_last_point_after_end():
    points = [(0.0, 10.0), (0.5, 20.0), (1.0, 40.0)]

    assert interpolate_profile(points, 1.5) == 40.0


def test_power_outage_points_include_new_baseline_categories():
    scenario = {
        "activated_at": "2026-01-01T12:00:00Z",
        "expires_at": "2026-01-01T12:01:00Z",
    }

    points = generate_power_outage_points(scenario)
    point_keys = {(point["asset_type"], point["asset_id"], point["metric"]) for point in points}

    assert ("utility", "utility-grid", "utility_price_usd_mwh") in point_keys
    assert ("compute", "gpu-cluster-a", "gpu_load_pct") in point_keys
    assert ("kpi", "facility", "pue") in point_keys


def test_demand_response_points_show_load_shedding_mid_event(monkeypatch):
    now = datetime(2026, 1, 1, 12, 0, 30, tzinfo=UTC)
    scenario = {
        "activated_at": "2026-01-01T12:00:00Z",
        "expires_at": "2026-01-01T12:01:00Z",
    }
    monkeypatch.setattr("app.logic.utc_now", lambda: now)

    points = generate_demand_response_points(scenario)
    by_metric = {point["metric"]: point for point in points}

    assert by_metric["utility_price_usd_mwh"]["value"] >= 700.0
    assert by_metric["shed_load_pct"]["value"] >= 35.0
    assert by_metric["gpu_power_kw"]["value"] < 800.0


def test_normalize_message_populates_expected_fields():
    topic = "dc/telemetry/rack/rack-a01"
    payload = {
        "metric": "rack_temp_c",
        "value": 39.0,
        "unit": "C",
        "quality": "good",
        "ts": datetime(2026, 1, 1, 12, 30, 0, tzinfo=UTC),
    }

    normalized = normalize_message(topic, payload)

    assert normalized["asset_type"] == "rack"
    assert normalized["asset_id"] == "rack-a01"
    assert normalized["metric"] == "rack_temp_c"
    assert normalized["value"] == 39.0
    assert normalized["status"] == "critical"
    assert normalized["alarm_text"] == "Rack inlet temperature high"
    assert normalized["zone"] == "white-space-1"
    assert normalized["unit"] == "C"
    assert normalized["quality"] == "good"
    assert normalized["ts"] == payload["ts"]
    assert normalized["severity_score"] == 100
