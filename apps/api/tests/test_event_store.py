from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.event_store import EventEnvelope, event_from_row


def test_event_envelope_serializes_canonical_fields():
    event = EventEnvelope(
        event_id=UUID("00000000-0000-0000-0000-000000000001"),
        event_type="ScenarioStarted",
        event_version=1,
        stream_id="scenario:demand-response-test",
        stream_version=1,
        source="api",
        occurred_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        recorded_at=datetime(2026, 1, 1, 12, 0, 1, tzinfo=UTC),
        correlation_id=UUID("00000000-0000-0000-0000-000000000002"),
        scenario_id="demand-response-test",
        payload={"scenario": "demand_response"},
        metadata={"operator": "api"},
        idempotency_key="demand-response-test:scenario-started",
    )

    serialized = event.as_response()

    assert serialized["event_id"] == "00000000-0000-0000-0000-000000000001"
    assert serialized["event_type"] == "ScenarioStarted"
    assert serialized["stream_id"] == "scenario:demand-response-test"
    assert serialized["stream_version"] == 1
    assert serialized["correlation_id"] == "00000000-0000-0000-0000-000000000002"
    assert serialized["payload"] == {"scenario": "demand_response"}


def test_event_from_row_restores_envelope():
    row = {
        "event_id": UUID("00000000-0000-0000-0000-000000000001"),
        "event_type": "LoadSheddingRequested",
        "event_version": 1,
        "stream_id": "scenario:demand-response-test",
        "stream_version": 4,
        "asset_id": "gpu-cluster-a",
        "asset_type": "compute",
        "occurred_at": datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        "recorded_at": datetime(2026, 1, 1, 12, 0, 1, tzinfo=UTC),
        "correlation_id": UUID("00000000-0000-0000-0000-000000000002"),
        "causation_id": UUID("00000000-0000-0000-0000-000000000003"),
        "scenario_id": "demand-response-test",
        "source": "api",
        "payload": {"shed_target_pct": 40.0},
        "metadata": {"scenario": "demand_response"},
        "idempotency_key": "demand-response-test:load-shedding-requested",
    }

    event = event_from_row(row)

    assert event.event_type == "LoadSheddingRequested"
    assert event.asset_id == "gpu-cluster-a"
    assert event.causation_id == UUID("00000000-0000-0000-0000-000000000003")
    assert event.payload == {"shed_target_pct": 40.0}
