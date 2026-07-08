from __future__ import annotations

from datetime import UTC, datetime

from app import ingest


class FakeClient:
    def __init__(self):
        self.inserted = []

    def insert(self, table, data, column_names):
        self.inserted.append({"table": table, "data": data, "column_names": column_names})


class FixedClock:
    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def __call__(self):
        if self.index >= len(self.values):
            return self.values[-1]
        value = self.values[self.index]
        self.index += 1
        return value


def test_telemetry_values_preserves_column_order():
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
        "alarm_text": "",
        "severity_score": 0,
        "quality": "good",
    }

    assert ingest.telemetry_values(row) == [
        row["ts"],
        row["site"],
        row["zone"],
        row["asset_type"],
        row["asset_id"],
        row["metric"],
        row["value"],
        row["unit"],
        row["status"],
        row["alarm_text"],
        row["severity_score"],
        row["quality"],
    ]


def test_insert_telemetry_does_nothing_for_empty_rows():
    client = FakeClient()

    ingest.insert_telemetry(client, [])

    assert client.inserted == []


def test_telemetry_buffer_flushes_when_batch_size_reached(monkeypatch):
    client = FakeClient()
    buffer = ingest.TelemetryBuffer(client, batch_size=2, flush_seconds=1000.0)
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
        "alarm_text": "",
        "severity_score": 0,
        "quality": "good",
    }

    assert buffer.add(row) == 0
    assert buffer.add(row) == 2
    assert client.inserted[0]["table"] == "telemetry_raw"
    assert len(buffer.rows) == 0


def test_telemetry_buffer_flushes_by_time(monkeypatch):
    clock = FixedClock([0.0, 0.0, 5.1])
    monkeypatch.setattr(ingest.time, "monotonic", clock)
    client = FakeClient()
    buffer = ingest.TelemetryBuffer(client, batch_size=100, flush_seconds=5.0)
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
        "alarm_text": "",
        "severity_score": 0,
        "quality": "good",
    }

    buffer.add(row)
    assert buffer.add(row) == 2
    assert client.inserted[0]["table"] == "telemetry_raw"


def test_flush_returns_zero_when_no_rows(monkeypatch):
    monkeypatch.setattr(ingest.time, "monotonic", lambda: 0.0)
    client = FakeClient()
    buffer = ingest.TelemetryBuffer(client, batch_size=2, flush_seconds=1000.0)

    assert buffer.flush() == 0
