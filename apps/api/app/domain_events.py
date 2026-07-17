from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from .event_store import EVENT_STORE_ENABLED, EventEnvelope, append_event


def emit_domain_event(
    *,
    event_type: str,
    stream_id: str,
    source: str,
    payload: dict[str, Any],
    idempotency_key: str,
    asset_id: str | None = None,
    asset_type: str | None = None,
    correlation_id: UUID | None = None,
    causation_id: UUID | None = None,
    scenario_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> EventEnvelope | None:
    if not EVENT_STORE_ENABLED:
        return None

    return append_event(
        EventEnvelope(
            event_type=event_type,
            stream_id=stream_id,
            source=source,
            payload=payload,
            idempotency_key=idempotency_key,
            asset_id=asset_id,
            asset_type=asset_type,
            correlation_id=correlation_id or uuid4(),
            causation_id=causation_id,
            scenario_id=scenario_id,
            metadata=metadata or {},
            occurred_at=occurred_at or datetime.now(UTC),
        )
    )
