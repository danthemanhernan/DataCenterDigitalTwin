from __future__ import annotations

from datetime import UTC, datetime

from app import api


class DummyResult:
    def __init__(self, rows=None, named=None):
        self.result_rows = rows or []
        self._named = named or []

    def named_results(self):
        return self._named


class FakeClient:
    def __init__(self, query_results=None, named_results=None):
        self.query_results = list(query_results or [])
        self.named_results = list(named_results or [])
        self.queries = []

    def query(self, sql, parameters=None):
        self.queries.append((sql, parameters))
        rows = self.query_results.pop(0) if self.query_results else []
        named = self.named_results.pop(0) if self.named_results else []
        return DummyResult(rows, named)


def test_serialize_scenario_state_inactive():
    result = api.serialize_scenario_state(None)

    assert result == {"active": False, "scenario": None}


def test_serialize_scenario_state_active_serializes_timestamps():
    scenario = {
        "scenario": "power_outage",
        "activated_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        "expires_at": datetime(2026, 1, 1, 12, 30, 0, tzinfo=UTC),
        "duration_seconds": 1800,
    }

    result = api.serialize_scenario_state(scenario)

    assert result["active"] is True
    assert result["scenario"] == "power_outage"
    assert result["activated_at"] == "2026-01-01T12:00:00+00:00"
    assert result["expires_at"] == "2026-01-01T12:30:00+00:00"
    assert result["duration_seconds"] == 1800


def test_serialize_alert_state_serializes_optional_timestamps():
    alert_state = {
        "alert_key": "alert-1",
        "acknowledged": True,
        "muted": True,
        "muted_until": datetime(2026, 1, 1, 12, 15, 0, tzinfo=UTC),
        "shelved": False,
        "shelved_until": None,
        "last_action": {"action": "mute"},
    }

    result = api.serialize_alert_state(alert_state)

    assert result["alert_key"] == "alert-1"
    assert result["muted_until"] == "2026-01-01T12:15:00+00:00"
    assert result["shelved_until"] is None
    assert result["last_action"]["action"] == "mute"


def test_get_latest_telemetry_by_pair_returns_matching_rows():
    rows = [
        {
            "asset_id": "rack-a01",
            "metric": "rack_temp_c",
            "latest_ts": "ts1",
            "value": 1,
            "unit": "C",
            "status": "normal",
        },
        {
            "asset_id": "rack-a01",
            "metric": "hvac_supply_temp_c",
            "latest_ts": "ts2",
            "value": 2,
            "unit": "C",
            "status": "warning",
        },
    ]
    client = FakeClient(named_results=[rows])
    pairs = {("rack-a01", "rack_temp_c")}

    result = api.get_latest_telemetry_by_pair(client, pairs)

    assert result == {
        ("rack-a01", "rack_temp_c"): {
            "asset_id": "rack-a01",
            "metric": "rack_temp_c",
            "latest_ts": "ts1",
            "value": 1,
            "unit": "C",
            "status": "normal",
            "ts": "ts1",
        }
    }


def test_get_latest_telemetry_by_pair_returns_empty_for_empty_pairs():
    client = FakeClient()

    result = api.get_latest_telemetry_by_pair(client, set())

    assert result == {}


def test_get_alert_lifecycle_by_key_filters_unwanted_alert_keys():
    rows = [
        {"alert_key": "alert-1", "start_ts": "start", "last_event_ts": "last"},
        {"alert_key": "alert-2", "start_ts": "other", "last_event_ts": "other"},
    ]
    client = FakeClient(named_results=[rows])

    result = api.get_alert_lifecycle_by_key(client, {"alert-1"})

    assert result == {"alert-1": rows[0]}


def test_get_latest_acknowledgement_returns_none_when_missing():
    client = FakeClient(named_results=[[]])

    assert api.get_latest_acknowledgement(client, "alert-1") is None


def test_get_latest_acknowledgement_returns_latest_row():
    row = {"ts": "ts", "actor": "api", "note": "ok"}
    client = FakeClient(named_results=[[row]])

    assert api.get_latest_acknowledgement(client, "alert-1") == row


def test_valid_alert_metric_clause_filters_known_metric_asset_pairs():
    clause = api.valid_alert_metric_clause()

    assert "(metric = 'rack_temp_c' AND asset_type = 'rack')" in clause
    assert "(metric = 'hvac_supply_temp_c' AND asset_type = 'hvac')" in clause
    assert "(metric = 'ups_battery_pct' AND asset_type = 'power')" in clause


def test_seconds_between_returns_none_if_missing_values():
    assert api.seconds_between(None, datetime.now(UTC)) is None
    assert api.seconds_between(datetime.now(UTC), None) is None


def test_seconds_between_returns_positive_seconds():
    start = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    end = datetime(2026, 1, 1, 12, 0, 30, tzinfo=UTC)

    assert api.seconds_between(start, end) == 30
