CREATE VIEW IF NOT EXISTS dc_twin.v_active_alarms AS
SELECT
    ts,
    site,
    zone,
    asset_type,
    asset_id,
    metric,
    value,
    unit,
    status,
    alarm_text,
    severity_score
FROM dc_twin.telemetry_raw
WHERE status IN ('warning', 'critical');

CREATE VIEW IF NOT EXISTS dc_twin.v_metric_1m AS
SELECT
    toStartOfMinute(ts) AS minute_bucket,
    site,
    zone,
    asset_type,
    asset_id,
    metric,
    avg(value) AS avg_value,
    max(value) AS max_value,
    any(unit) AS unit,
    max(severity_score) AS peak_severity
FROM dc_twin.telemetry_raw
GROUP BY minute_bucket, site, zone, asset_type, asset_id, metric;

CREATE VIEW IF NOT EXISTS dc_twin.v_recent_alerts AS
SELECT
    ts,
    alert_key,
    rule_name,
    site,
    zone,
    asset_type,
    asset_id,
    severity,
    status,
    metric,
    message,
    current_value,
    threshold_value,
    observation_count,
    window_minutes,
    source
FROM dc_twin.alert_events;

CREATE VIEW IF NOT EXISTS dc_twin.v_alert_actions AS
SELECT
    ts,
    alert_key,
    action,
    actor,
    note,
    muted_until
FROM dc_twin.alert_actions;
