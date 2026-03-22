# Grafana Dashboard Notes

Use the provisioned ClickHouse datasource named `ClickHouse` against database `dc_twin`.

## Provisioned Dashboards

- `Mini DC Operations Overview`
- `Mini DC Facility Trends`
- `Mini DC Asset Metric Trends`

## Suggested Panels

- Active alarms table from `v_active_alarms` sorted by latest timestamp
- Rack temperature trend from `v_metric_1m` filtered to `metric = 'rack_temp_c'`
- Rack power trend from `v_metric_1m` filtered to `metric = 'rack_kw'`
- HVAC supply and return temperature comparison
- UPS load and battery status gauges
- Alarm count by severity over the last 15 minutes

## Suggested Variables

- `site`
- `zone`
- `asset_type`
- `asset_id`
- `metric`
- `rack_asset`
- `hvac_asset`
- `power_asset`

## Example Query

```sql
SELECT
  minute_bucket AS time,
  asset_id,
  avg_value
FROM dc_twin.v_metric_1m
WHERE metric = 'rack_temp_c'
ORDER BY time ASC
```

## Alarm Styling

- `warning` as amber
- `critical` as red
- `normal` as green when used in state timeline panels
- Trend dashboards should use dashed threshold lines that match `app/logic.py` alarm rules.
- Trend panels should apply the `Partition by values` transform on `asset_id` and `Prepare time series` so one query cleanly splits into per-asset lines.
- Use `max(value)` for high-is-bad metrics and `min(value)` for low-battery trends so the graph reflects alarm-driving excursions.
