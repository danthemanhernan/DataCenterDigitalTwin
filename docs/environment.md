# Environment Variables

The main local stack environment file is `deploy/compose/.env`. Start from `deploy/compose/.env.example` or `examples/local-stack/lab-demo.env.example`.

Frontend-only development can also use `apps/operator-console/.env`, starting from `apps/operator-console/.env.example`.

## MQTT And Simulator

| Variable | Default | Used by | Purpose |
| --- | --- | --- | --- |
| `MQTT_HOST` | `localhost` locally, `mqtt` in Compose app containers | simulator, ingest, API env anchor | MQTT broker hostname. |
| `MQTT_PORT` | `1883` | simulator, ingest, Compose port mapping | MQTT broker port. |
| `MQTT_TOPIC_ROOT` | `dc/telemetry` | simulator, ingest | Root topic for telemetry publish/subscribe. |
| `SIM_INTERVAL_SECONDS` | `2.0` | simulator | Delay between simulator publish loops. |
| `SIMULATOR_CONTROL_PATH` | `/runtime/simulator-control.json` in Compose | API, simulator | Shared scenario-control file path. |

## Ingest

| Variable | Default | Used by | Purpose |
| --- | --- | --- | --- |
| `INGEST_BATCH_SIZE` | `100` | ingest | Number of telemetry rows to buffer before writing to ClickHouse. |
| `INGEST_FLUSH_SECONDS` | `5.0` | ingest | Maximum time to hold buffered telemetry before flushing. |

The ingest batching settings reduce tiny ClickHouse inserts while keeping local telemetry visible quickly.

## ClickHouse

| Variable | Default | Used by | Purpose |
| --- | --- | --- | --- |
| `CLICKHOUSE_HOST` | `localhost` locally, `clickhouse` in Compose app containers | API, ingest, alerting, maintenance model, ClickHouse container env | ClickHouse hostname. |
| `CLICKHOUSE_PORT` | `8123` | API, ingest, alerting, maintenance model, Compose port mapping | ClickHouse HTTP port. |
| `CLICKHOUSE_USER` | `default` | API, ingest, alerting, maintenance model, ClickHouse container env | ClickHouse username. |
| `CLICKHOUSE_PASSWORD` | `password` in examples | API, ingest, alerting, maintenance model, ClickHouse container env | ClickHouse password for local stack. |
| `CLICKHOUSE_DATABASE` | `dc_twin` | API, ingest, alerting, maintenance model, ClickHouse container env | Database name created by the init SQL. |

## API And Frontend

| Variable | Default | Used by | Purpose |
| --- | --- | --- | --- |
| `API_HOST` | `0.0.0.0` | local env convention | Host binding for API runs outside Compose. |
| `API_PORT` | `8000` | Compose port mapping | Host port for FastAPI. |
| `FRONTEND_PORT` | `5173` | Compose port mapping | Host port for the nginx-served operator console. |
| `SITE_NAME` | `DC-SJC-LAB` | telemetry normalization | Site label attached to telemetry rows. |
| `FRONTEND_ORIGINS` | local Vite/nginx origins | FastAPI CORS | Allowed browser origins for API calls. |
| `VITE_API_BASE_URL` | `http://localhost:8000` | frontend build | API URL embedded into the Vite build. |
| `VITE_GRAFANA_BASE_URL` | `http://localhost:3000` | frontend build | Grafana URL embedded into the Vite build. |

Vite embeds `VITE_*` values at build time. Rebuild the frontend image after changing them:

```bash
docker compose -f deploy/compose/docker-compose.yml --env-file deploy/compose/.env up -d --build frontend
```

## Alerting

| Variable | Default | Used by | Purpose |
| --- | --- | --- | --- |
| `ALERT_INTERVAL_SECONDS` | `30` | alerting | Delay between alert evaluation cycles. |

Alert rule thresholds are source-controlled in `apps/api/app/config/alarm_rules.json`.

## Maintenance Model

| Variable | Default | Used by | Purpose |
| --- | --- | --- | --- |
| `MAINTENANCE_MODEL_INTERVAL_SECONDS` | `300` | maintenance-model | Delay between maintenance scoring cycles. |
| `MAINTENANCE_MODEL_LOOKBACK_HOURS` | `24` | maintenance-model | Telemetry history window for model input. |
| `MAINTENANCE_MODEL_WINDOW_MINUTES` | `30` | maintenance-model | Recent scoring window. |
| `MAINTENANCE_MODEL_ROW_LIMIT` | `100000` | maintenance-model | Maximum telemetry rows to fetch per cycle. |

## Grafana

| Variable | Default | Used by | Purpose |
| --- | --- | --- | --- |
| `GRAFANA_ADMIN_USER` | `admin` | Grafana container | Local admin username. |
| `GRAFANA_ADMIN_PASSWORD` | `admin` | Grafana container | Local admin password. |

Grafana also enables anonymous viewer access in Compose so the operator console can embed dashboard panels.

## Source-Control Policy

- Commit `.env.example` files.
- Do not commit real `.env` files.
- Do not put production secrets in examples.
- Keep local-only values in `deploy/compose/.env` or `apps/operator-console/.env`.
