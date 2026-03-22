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
