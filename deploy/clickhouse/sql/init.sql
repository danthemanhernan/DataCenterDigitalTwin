CREATE DATABASE IF NOT EXISTS dc_twin;

CREATE TABLE IF NOT EXISTS dc_twin.telemetry_raw
(
    ts DateTime64(3, 'UTC'),
    ingested_at DateTime64(3, 'UTC'),
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
    quality LowCardinality(String),
    source LowCardinality(String),
    source_topic String
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
    muted_until Nullable(DateTime64(3, 'UTC')),
    shelved_until Nullable(DateTime64(3, 'UTC'))
)
ENGINE = MergeTree
ORDER BY (alert_key, ts);

CREATE TABLE IF NOT EXISTS dc_twin.maintenance_risk_scores
(
    ts DateTime64(3, 'UTC'),
    model_version LowCardinality(String),
    source LowCardinality(String),
    lookback_hours UInt16,
    window_minutes UInt16,
    telemetry_rows UInt32,
    site LowCardinality(String),
    zone LowCardinality(String),
    asset_type LowCardinality(String),
    asset_id String,
    metric LowCardinality(String),
    sample_count UInt32,
    avg_value Float64,
    min_value Float64,
    max_value Float64,
    latest_value Float64,
    slope_per_hour Float64,
    warning_or_critical_ratio Float64,
    critical_ratio Float64,
    baseline_mean Float64,
    baseline_stddev Float64,
    baseline_samples UInt32,
    anomaly_zscore Float64,
    trend_component Float64,
    maintenance_risk_score Float64,
    risk_band LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY (asset_type, asset_id, metric, ts);
