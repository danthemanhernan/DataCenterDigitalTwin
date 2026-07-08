from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app import maintenance_model


class DummyResult:
    def __init__(self, named=None):
        self._named = named or []

    def named_results(self):
        return self._named


class FakeClient:
    def __init__(self, named_results=None):
        self.named_results = list(named_results or [])
        self.queries = []
        self.commands = []

    def query(self, sql, parameters=None):
        self.queries.append((sql, parameters))
        named = self.named_results.pop(0) if self.named_results else []
        return DummyResult(named)

    def command(self, sql):
        self.commands.append(sql)


def test_fetch_telemetry_returns_points_from_client():
    row = {
        "ts": datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        "site": "DC",
        "zone": "zone-a",
        "asset_type": "rack",
        "asset_id": "rack-1",
        "metric": "rack_temp_c",
        "value": 24.0,
        "unit": "C",
        "status": "normal",
    }
    client = FakeClient(named_results=[[row]])

    points = maintenance_model.fetch_telemetry(client, hours=1, limit=10)

    assert len(points) == 1
    assert points[0].asset_id == "rack-1"
    assert points[0].metric == "rack_temp_c"
    assert client.queries[0][1]["limit"] == 10


def test_normalize_ts_converts_naive_datetime_to_utc():
    value = datetime(2026, 1, 1, 12, 0, 0)

    assert maintenance_model.normalize_ts(value) == datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_normalize_ts_parses_z_string():
    value = "2026-01-01T12:00:00Z"

    assert maintenance_model.normalize_ts(value) == datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_row_to_point_uses_status_when_provided():
    row = {
        "ts": datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        "site": "DC",
        "zone": "zone-a",
        "asset_type": "rack",
        "asset_id": "rack-1",
        "metric": "rack_temp_c",
        "value": 24.0,
        "unit": "C",
        "status": "normal",
    }

    point = maintenance_model.row_to_point(row)

    assert point.asset_type == "rack"
    assert point.value == 24.0
    assert point.status == "normal"


def test_build_training_dataset_filters_by_window(monkeypatch):
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    points = [
        maintenance_model.TelemetryPoint(
            ts=now - timedelta(minutes=10),
            site="DC",
            zone="zone-a",
            asset_type="rack",
            asset_id="rack-1",
            metric="rack_temp_c",
            value=24.0,
            unit="C",
            status="normal",
        ),
        maintenance_model.TelemetryPoint(
            ts=now - timedelta(minutes=2),
            site="DC",
            zone="zone-a",
            asset_type="rack",
            asset_id="rack-1",
            metric="rack_temp_c",
            value=25.0,
            unit="C",
            status="normal",
        ),
    ]
    monkeypatch.setattr(maintenance_model, "utc_now", lambda: now)

    dataset = maintenance_model.build_training_dataset(points, window_minutes=5)

    assert len(dataset) == 1
    assert dataset[0]["sample_count"] == 1


def test_slope_per_hour_returns_zero_for_short_series():
    point = maintenance_model.TelemetryPoint(
        ts=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        site="DC",
        zone="zone-a",
        asset_type="rack",
        asset_id="rack-1",
        metric="rack_temp_c",
        value=24.0,
        unit="C",
        status="normal",
    )

    assert maintenance_model.slope_per_hour([point]) == 0.0


def test_metric_zscore_returns_zero_for_missing_metric():
    model = {}

    assert maintenance_model.metric_zscore("rack_temp_c", 30.0, model) == 0.0


def test_clamp_bounds_value():
    assert maintenance_model.clamp(10.0, 0.0, 5.0) == 5.0
    assert maintenance_model.clamp(-1.0, 0.0, 5.0) == 0.0
    assert maintenance_model.clamp(3.0, 0.0, 5.0) == 3.0
