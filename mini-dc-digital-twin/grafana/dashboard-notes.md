# Grafana Dashboard Notes

Use the provisioned ClickHouse datasource named `ClickHouse` against database `dc_twin`.

## Provisioned Dashboards

- `Mini DC Operations Overview`
- `Mini DC Facility Trends`

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
