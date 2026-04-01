# Mini DC Digital Twin

A small portfolio project inspired by Niagara-style supervisory control for data centers.

It simulates telemetry from racks, HVAC units, and power equipment, publishes those points to MQTT, normalizes and enriches them in Python, stores them in ClickHouse, and exposes a small FastAPI surface for health and alarm views. Grafana sits on top for trends and alarm dashboards.

The simulated topology assumes a simple 2N redundant layout with two representative racks, two matching HVAC units, two UPS units, and two PDUs.

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

8. Trigger a temporary simulator scenario from the API:

```bash
curl -X POST http://localhost:8000/simulator/scenarios/power-outage \
  -H "Content-Type: application/json" \
  -d '{"duration_seconds": 30}'
```

Other built-in scenarios:

```bash
curl -X POST http://localhost:8000/simulator/scenarios/cooling-degradation \
  -H "Content-Type: application/json" \
  -d '{"duration_seconds": 45}'

curl -X POST http://localhost:8000/simulator/scenarios/load-transfer \
  -H "Content-Type: application/json" \
  -d '{"duration_seconds": 45}'
```

9. Run the Python alerting pipeline:

```bash
uv run --package dc-digital-twin python -m app.alerting --once
uv run --package dc-digital-twin python -m app.alerting --interval-seconds 30
```

## Default Endpoints

- API: `http://localhost:8000/docs`
- API metrics: `http://localhost:8000/metrics`
- Simulator scenario state: `http://localhost:8000/simulator/scenario`
- Simulator scenario catalog: `http://localhost:8000/simulator/scenarios`
- Alert rules: `http://localhost:8000/alerts/rules`
- Recent alert events: `http://localhost:8000/alerts/recent`
- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- MQTT broker: `localhost:1883`
- ClickHouse HTTP: `http://localhost:8123/play`

## Notes

- Normal simulator telemetry stays below alarm thresholds so alarms are driven by explicit simulator scenarios rather than background noise.
- The simulated plant assumes 2N redundancy so paired HVAC, UPS, and PDU assets publish comparable metrics for clearer side-by-side graphs.
- The enrichment layer adds site, zone, asset class, severity, and alarm metadata.
- The SQL views are designed to be easy starting points for Grafana panels.
- The repo uses a uv workspace at the root, with the app defined in `mini-dc-digital-twin/pyproject.toml`.
- ClickHouse automatically applies the SQL files in `sql/` on first startup of a fresh `clickhouse_data` volume.
- Grafana provisions ClickHouse and Prometheus datasources automatically and loads starter dashboards for facility telemetry and API monitoring.
- Grafana also provisions `Mini DC Facility Trends Live`, a copy of the facility dashboard that reads raw telemetry timestamps without minute bucketing so live scenario testing shows every simulator step.
- Trend dashboards now include threshold lines that match the warning and critical alarm rules in `app/logic.py`, and the asset trend dashboard exposes Grafana variables for rack, HVAC, and power asset selection.
- Telemetry trend panels split one query into separate asset series with Grafana transforms, and they use peak-oriented aggregation (`max`, or `min` for UPS battery) to make alarm excursions easier to spot.
- Scenario profiles now progress through staged behavior over their duration instead of jumping directly to a single failure snapshot, making transfer events, recovery ramps, and compensating equipment behavior easier to observe.
- Default Grafana login comes from `.env`, and the provisioned home dashboard is `Mini DC Operations Overview`.
- FastAPI exposes Prometheus-style metrics at `/metrics`, and Prometheus scrapes the API from `host.docker.internal:8000` for the API monitoring dashboard.
- The simulator checks a local control file each publish loop, so calling a scenario endpoint shifts telemetry into a named failure or maintenance profile for the requested duration.

## Alerting Pipeline

The alerting pipeline is intentionally a small Python polling worker instead of Airflow.

Choice justification:
- The current project only needs one lightweight recurring job, so a simple loop-based worker is easier to run and reason about than introducing a scheduler, metadata database, and DAG management overhead.
- ClickHouse is already the source of truth for telemetry, so storing alert events there keeps the architecture small and makes alerts queryable from both the API and Grafana.
- The worker creates and uses an `alert_events` table directly, which means existing local environments can start alerting without waiting for a separate migration tool.
- Airflow can be added later if the project grows into multiple dependent jobs, backfills, or more complex orchestration needs.

The current rules focus on clear operator signals:
- repeated critical rack temperature in the last 5 minutes
- sustained high HVAC supply temperature in the last 5 minutes
- sustained low UPS battery in the last 10 minutes

Operational notes:
- Normal simulation should stay quiet, so scenario-driven telemetry is the main way to generate alert events.
- Use `--once` for quick checks and continuous mode for dashboard-driven demos.
