from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

load_dotenv()


EVENT_STORE_ENABLED = os.getenv("EVENT_STORE_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
EVENT_STORE_HOST = os.getenv("EVENT_STORE_HOST", "localhost")
EVENT_STORE_PORT = int(os.getenv("EVENT_STORE_PORT", "5432"))
EVENT_STORE_USER = os.getenv("EVENT_STORE_USER", "dc_twin")
EVENT_STORE_PASSWORD = os.getenv("EVENT_STORE_PASSWORD", "")
EVENT_STORE_DATABASE = os.getenv("EVENT_STORE_DATABASE", "dc_twin_events")


class EventStoreDisabledError(RuntimeError):
    pass


class EventStoreConcurrencyError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


def coerce_uuid(value: UUID | str | None) -> UUID:
    if value is None:
        return uuid4()
    if isinstance(value, UUID):
        return value
    return UUID(value)


@dataclass(frozen=True)
class EventEnvelope:
    event_type: str
    stream_id: str
    source: str
    payload: dict[str, Any]
    event_id: UUID = field(default_factory=uuid4)
    event_version: int = 1
    stream_version: int | None = None
    asset_id: str | None = None
    asset_type: str | None = None
    occurred_at: datetime = field(default_factory=utc_now)
    recorded_at: datetime | None = None
    correlation_id: UUID = field(default_factory=uuid4)
    causation_id: UUID | None = None
    scenario_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None

    def with_stream_version(self, stream_version: int, recorded_at: datetime | None = None) -> EventEnvelope:
        return EventEnvelope(
            event_type=self.event_type,
            stream_id=self.stream_id,
            source=self.source,
            payload=self.payload,
            event_id=self.event_id,
            event_version=self.event_version,
            stream_version=stream_version,
            asset_id=self.asset_id,
            asset_type=self.asset_type,
            occurred_at=self.occurred_at,
            recorded_at=recorded_at or self.recorded_at or utc_now(),
            correlation_id=self.correlation_id,
            causation_id=self.causation_id,
            scenario_id=self.scenario_id,
            metadata=self.metadata,
            idempotency_key=self.idempotency_key,
        )

    def as_response(self) -> dict[str, Any]:
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "event_version": self.event_version,
            "stream_id": self.stream_id,
            "stream_version": self.stream_version,
            "asset_id": self.asset_id,
            "asset_type": self.asset_type,
            "occurred_at": self.occurred_at.isoformat(),
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
            "correlation_id": str(self.correlation_id),
            "causation_id": str(self.causation_id) if self.causation_id else None,
            "scenario_id": self.scenario_id,
            "source": self.source,
            "payload": self.payload,
            "metadata": self.metadata,
            "idempotency_key": self.idempotency_key,
        }


def postgres_dsn() -> str:
    return (
        f"host={EVENT_STORE_HOST} port={EVENT_STORE_PORT} dbname={EVENT_STORE_DATABASE} "
        f"user={EVENT_STORE_USER} password={EVENT_STORE_PASSWORD}"
    )


def get_connection():
    if not EVENT_STORE_ENABLED:
        raise EventStoreDisabledError("Event store is disabled")
    return psycopg.connect(postgres_dsn(), row_factory=dict_row)


class PostgresEventWriter:
    def __init__(self, connection_factory=get_connection):
        self.connection_factory = connection_factory

    def append(
        self,
        event: EventEnvelope,
        expected_stream_version: int | None = None,
    ) -> EventEnvelope:
        with self.connection_factory() as connection, connection.transaction():
            stream_version = event.stream_version
            if stream_version is None:
                stream_version = self._next_stream_version(connection, event.stream_id, expected_stream_version)

            recorded_event = event.with_stream_version(stream_version)
            return self._insert(connection, recorded_event)

    @staticmethod
    def _next_stream_version(connection: Any, stream_id: str, expected_stream_version: int | None) -> int:
        result = connection.execute(
            """
            SELECT COALESCE(MAX(stream_version), 0) AS current_version
            FROM event_store.events
            WHERE stream_id = %s
            """,
            (stream_id,),
        ).fetchone()
        current_version = int(result["current_version"])

        if expected_stream_version is not None and current_version != expected_stream_version:
            raise EventStoreConcurrencyError(
                f"Expected stream {stream_id!r} at version {expected_stream_version}, found {current_version}"
            )

        return current_version + 1

    @staticmethod
    def _insert(connection: Any, event: EventEnvelope) -> EventEnvelope:
        result = connection.execute(
            """
            INSERT INTO event_store.events (
                event_id,
                event_type,
                event_version,
                stream_id,
                stream_version,
                asset_id,
                asset_type,
                occurred_at,
                recorded_at,
                correlation_id,
                causation_id,
                scenario_id,
                source,
                payload,
                metadata,
                idempotency_key
            )
            VALUES (
                %(event_id)s,
                %(event_type)s,
                %(event_version)s,
                %(stream_id)s,
                %(stream_version)s,
                %(asset_id)s,
                %(asset_type)s,
                %(occurred_at)s,
                %(recorded_at)s,
                %(correlation_id)s,
                %(causation_id)s,
                %(scenario_id)s,
                %(source)s,
                %(payload)s,
                %(metadata)s,
                %(idempotency_key)s
            )
            ON CONFLICT (idempotency_key)
            WHERE idempotency_key IS NOT NULL
            DO NOTHING
            RETURNING *
            """,
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "event_version": event.event_version,
                "stream_id": event.stream_id,
                "stream_version": event.stream_version,
                "asset_id": event.asset_id,
                "asset_type": event.asset_type,
                "occurred_at": event.occurred_at,
                "recorded_at": event.recorded_at,
                "correlation_id": event.correlation_id,
                "causation_id": event.causation_id,
                "scenario_id": event.scenario_id,
                "source": event.source,
                "payload": Jsonb(event.payload),
                "metadata": Jsonb(event.metadata),
                "idempotency_key": event.idempotency_key,
            },
        ).fetchone()

        if result is None and event.idempotency_key:
            result = connection.execute(
                """
                SELECT *
                FROM event_store.events
                WHERE idempotency_key = %s
                """,
                (event.idempotency_key,),
            ).fetchone()

        if result is None:
            raise EventStoreConcurrencyError(
                f"Event insert for stream {event.stream_id!r} at version {event.stream_version} did not complete"
            )

        return event_from_row(result)


def event_from_row(row: dict[str, Any]) -> EventEnvelope:
    payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
    metadata = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
    return EventEnvelope(
        event_id=coerce_uuid(row["event_id"]),
        event_type=row["event_type"],
        event_version=row["event_version"],
        stream_id=row["stream_id"],
        stream_version=row["stream_version"],
        asset_id=row["asset_id"],
        asset_type=row["asset_type"],
        occurred_at=row["occurred_at"],
        recorded_at=row["recorded_at"],
        correlation_id=coerce_uuid(row["correlation_id"]),
        causation_id=coerce_uuid(row["causation_id"]) if row["causation_id"] else None,
        scenario_id=row["scenario_id"],
        source=row["source"],
        payload=payload,
        metadata=metadata,
        idempotency_key=row["idempotency_key"],
    )


def append_event(event: EventEnvelope, expected_stream_version: int | None = None) -> EventEnvelope:
    return PostgresEventWriter().append(event, expected_stream_version=expected_stream_version)


def list_recent_events(limit: int = 50) -> list[EventEnvelope]:
    if not EVENT_STORE_ENABLED:
        return []

    with get_connection() as connection:
        result = connection.execute(
            """
            SELECT *
            FROM event_store.events
            ORDER BY recorded_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        return [event_from_row(row) for row in result.fetchall()]
