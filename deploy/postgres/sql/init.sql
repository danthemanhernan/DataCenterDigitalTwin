CREATE SCHEMA IF NOT EXISTS event_store;

CREATE TABLE IF NOT EXISTS event_store.events (
    event_id UUID PRIMARY KEY,
    event_type TEXT NOT NULL,
    event_version INTEGER NOT NULL CHECK (event_version >= 1),
    stream_id TEXT NOT NULL,
    stream_version INTEGER NOT NULL CHECK (stream_version >= 1),
    asset_id TEXT,
    asset_type TEXT,
    occurred_at TIMESTAMPTZ NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    correlation_id UUID NOT NULL,
    causation_id UUID,
    scenario_id TEXT,
    source TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key TEXT,
    UNIQUE (stream_id, stream_version)
);

CREATE UNIQUE INDEX IF NOT EXISTS events_idempotency_key_unique
    ON event_store.events (idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS events_recorded_at_idx
    ON event_store.events (recorded_at DESC);

CREATE INDEX IF NOT EXISTS events_asset_idx
    ON event_store.events (asset_type, asset_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS events_correlation_idx
    ON event_store.events (correlation_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS events_scenario_idx
    ON event_store.events (scenario_id, recorded_at DESC)
    WHERE scenario_id IS NOT NULL;

CREATE OR REPLACE FUNCTION event_store.prevent_event_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'event_store.events is append-only';
END;
$$;

DROP TRIGGER IF EXISTS prevent_event_update ON event_store.events;
CREATE TRIGGER prevent_event_update
    BEFORE UPDATE ON event_store.events
    FOR EACH ROW
    EXECUTE FUNCTION event_store.prevent_event_mutation();

DROP TRIGGER IF EXISTS prevent_event_delete ON event_store.events;
CREATE TRIGGER prevent_event_delete
    BEFORE DELETE ON event_store.events
    FOR EACH ROW
    EXECUTE FUNCTION event_store.prevent_event_mutation();
