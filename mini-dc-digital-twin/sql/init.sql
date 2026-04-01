CREATE DATABASE IF NOT EXISTS dc_twin;

CREATE TABLE IF NOT EXISTS dc_twin.telemetry_raw
(
    ts DateTime64(3, 'UTC'),
    site LowCardinality(String),
    zone LowCardinality(String),
    asset_type LowCardinality(String),
    asset_id String,
    metric LowCardinality(String),
    value Float64,
    unit LowCardinality(String),
    status LowCardinality(String),
    alarm_text String,
    severity_score UInt8,
    quality LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY (asset_type, asset_id, metric, ts);

CREATE TABLE IF NOT EXISTS dc_twin.alert_events
(
    ts DateTime64(3, 'UTC'),
    alert_key String,
    rule_name LowCardinality(String),
    site LowCardinality(String),
    zone LowCardinality(String),
    asset_type LowCardinality(String),
    asset_id String,
    severity LowCardinality(String),
    status LowCardinality(String),
    metric LowCardinality(String),
    message String,
    current_value Float64,
    threshold_value Float64,
    observation_count UInt16,
    window_minutes UInt8,
    source LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY (rule_name, asset_id, ts);

CREATE TABLE IF NOT EXISTS dc_twin.alert_actions
(
    ts DateTime64(3, 'UTC'),
    alert_key String,
    action LowCardinality(String),
    actor String,
    note String,
    muted_until Nullable(DateTime64(3, 'UTC'))
)
ENGINE = MergeTree
ORDER BY (alert_key, ts);
