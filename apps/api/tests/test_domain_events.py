from __future__ import annotations

from uuid import UUID

from app import domain_events


def test_emit_domain_event_returns_none_when_store_disabled(monkeypatch):
    monkeypatch.setattr(domain_events, "EVENT_STORE_ENABLED", False)

    assert (
        domain_events.emit_domain_event(
            event_type="TestEvent",
            stream_id="test:1",
            source="test",
            payload={},
            idempotency_key="test:1",
        )
        is None
    )


def test_emit_domain_event_builds_event_envelope(monkeypatch):
    captured = {}

    def fake_append_event(event):
        captured["event"] = event
        return event

    monkeypatch.setattr(domain_events, "EVENT_STORE_ENABLED", True)
    monkeypatch.setattr(domain_events, "append_event", fake_append_event)

    event = domain_events.emit_domain_event(
        event_type="AlertRaised",
        stream_id="alert:1",
        source="test",
        asset_id="rack-1",
        asset_type="rack",
        correlation_id=UUID("00000000-0000-0000-0000-000000000001"),
        payload={"severity": "critical"},
        idempotency_key="alert:1:raised",
    )

    assert event is captured["event"]
    assert event.event_type == "AlertRaised"
    assert event.asset_id == "rack-1"
    assert event.correlation_id == UUID("00000000-0000-0000-0000-000000000001")
