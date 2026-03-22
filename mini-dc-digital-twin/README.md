# Mini DC Digital Twin

A small portfolio project inspired by Niagara-style supervisory control for data centers.

It simulates telemetry from racks, HVAC units, and power equipment, publishes those points to MQTT, normalizes and enriches them in Python, stores them in ClickHouse, and exposes a small FastAPI surface for health and alarm views. Grafana sits on top for trends and alarm dashboards.

## Stack

- Python
- FastAPI
- paho-mqtt
- clickhouse-connect
- Mosquitto MQTT
- ClickHouse
- Grafana
- Prometheus

## Project Flow

1. `app/simulator.py` publishes sample telemetry to MQTT topics like `dc/telemetry/rack/rack-a01`.
2. `app/ingest.py` subscribes to those topics, normalizes the payload, derives health signals and alarm state, and inserts records into ClickHouse.
3. `app/api.py` reads recent telemetry and active alarms from ClickHouse through FastAPI.
4. Grafana queries ClickHouse to show trends, alarm counts, and recent events.

## Quick Start

1. Copy `.env.example` to `.env` and configure the variables as needed.
2. Start infrastructure (Docker Compose will automatically load variables from `.env`):

```bash
docker compose up -d
```

3. Sync the Python environment with `uv` from the workspace root:

```bash
uv sync
```

4. Run the ingest service:

```bash
uv run --package dc-digital-twin python -m app.ingest
```

5. In another terminal, start the API:

```bash
uv run --package dc-digital-twin uvicorn app.api:app --reload --host 0.0.0.0 --port 8000
```

6. In another terminal, start the simulator:

```bash
uv run --package dc-digital-twin python -m app.simulator
```

7. Generate a bit of API traffic so the monitoring dashboard has data:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/summary
curl "http://localhost:8000/telemetry/recent?limit=10"
```

## Default Endpoints

- API: `http://localhost:8000/docs`
- API metrics: `http://localhost:8000/metrics`
- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- MQTT broker: `localhost:1883`
- ClickHouse HTTP: `http://localhost:8123/play`

## Notes

- The simulator intentionally produces both normal and abnormal readings so alarms appear quickly.
- The enrichment layer adds site, zone, asset class, severity, and alarm metadata.
- The SQL views are designed to be easy starting points for Grafana panels.
- The repo uses a uv workspace at the root, with the app defined in `mini-dc-digital-twin/pyproject.toml`.
- ClickHouse automatically applies the SQL files in `sql/` on first startup of a fresh `clickhouse_data` volume.
- Grafana provisions ClickHouse and Prometheus datasources automatically and loads starter dashboards for facility telemetry and API monitoring.
- Default Grafana login comes from `.env`, and the provisioned home dashboard is `Mini DC Operations Overview`.
- FastAPI exposes Prometheus-style metrics at `/metrics`, and Prometheus scrapes the API from `host.docker.internal:8000` for the API monitoring dashboard.
