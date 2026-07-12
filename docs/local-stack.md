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
- PostgreSQL event store
- Grafana
- Prometheus
- React / Vite
- nginx

## Project Flow

1. `apps/api/app/simulator.py` publishes sample telemetry to MQTT topics like `dc/telemetry/rack/rack-a01`.
2. `apps/api/app/ingest.py` subscribes to those topics, normalizes the payload, derives health signals and alarm state, and inserts records into ClickHouse.
3. `apps/api/app/api.py` reads recent telemetry and active alarms from ClickHouse through FastAPI.
4. Grafana queries ClickHouse to show trends, alarm counts, and recent events.
5. The React operator console in `apps/operator-console/` is built with Vite and served from nginx.

## Quick Start

1. Change into the Compose deployment directory:

```bash
cd deploy/compose
```

2. Copy `.env.example` to `.env` and configure the variables as needed.

```bash
cp .env.example .env
```

3. Adjust `FRONTEND_PORT`, `VITE_API_BASE_URL`, or `VITE_GRAFANA_BASE_URL` in `.env` if you want different browser-facing URLs for the React console.
4. Start the containerized stack. Docker Compose will build one Python app image for the API, ingest worker, simulator, alerting worker, and maintenance-model worker, plus a frontend image that builds the React app and serves it from nginx. MQTT, ClickHouse, Prometheus, and Grafana run alongside them:

```bash
docker compose up -d --build
```

The app services map to the scripts that used to run in separate terminals:

- `api`: `uvicorn app.api:app --host 0.0.0.0 --port 8000`
- `ingest`: `python -m app.ingest`
- `simulator`: `python -m app.simulator`
- `alerting`: `python -m app.alerting --interval-seconds ${ALERT_INTERVAL_SECONDS:-30}`
- `maintenance-model`: `python -m app.maintenance_model --interval-seconds ${MAINTENANCE_MODEL_INTERVAL_SECONDS:-300}`
- `frontend`: Vite production build served by nginx on `${FRONTEND_PORT:-5173}`

The API and simulator share a small Docker volume for `SIMULATOR_CONTROL_PATH`, so scenario calls from the API change the telemetry emitted by the simulator container.

5. Generate a bit of API traffic so the monitoring dashboard has data:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/summary
curl "http://localhost:8000/telemetry/recent?limit=10"
```

6. Trigger a temporary simulator scenario from the API:

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

7. Check the running app services:

```bash
docker compose ps
docker compose logs -f api ingest simulator alerting maintenance-model frontend
```

8. For local frontend development outside Docker, run the Vite dev server from the repo root:

```bash
cd apps/operator-console
npm install
npm run dev
```

9. Take alarm actions from the API:

```bash
curl -X POST http://localhost:8000/alerts/repeated_critical_rack_temp:rack-a01/acknowledge \
  -H "Content-Type: application/json" \
  -d '{"actor": "operator", "note": "Investigating in Grafana"}'

curl -X POST http://localhost:8000/alerts/repeated_critical_rack_temp:rack-a01/mute \
  -H "Content-Type: application/json" \
  -d '{"actor": "operator", "note": "Suppress during maintenance", "duration_minutes": 60}'

curl -X POST http://localhost:8000/alerts/repeated_critical_rack_temp:rack-a01/unmute \
  -H "Content-Type: application/json" \
  -d '{"actor": "operator", "note": "Maintenance complete"}'

curl -X POST http://localhost:8000/alerts/repeated_critical_rack_temp:rack-a01/shelve \
  -H "Content-Type: application/json" \
  -d '{"actor": "operator", "note": "Shelve during planned change", "duration_minutes": 120}'

curl -X POST http://localhost:8000/alerts/repeated_critical_rack_temp:rack-a01/unshelve \
  -H "Content-Type: application/json" \
  -d '{"actor": "operator", "note": "Return to active monitoring"}'
```

10. Run a local predictive-maintenance cycle from the repo root after telemetry has accumulated:

```bash
uv run --package dc-digital-twin python -m app.maintenance_model --once --hours 24 --window-minutes 30
```

The worker publishes rows into ClickHouse table `dc_twin.maintenance_risk_scores`.

For deterministic sample telemetry, run:

```bash
uv run --package dc-digital-twin python -m app.maintenance_model --once --fixture
```

## Default Endpoints

- API: `http://localhost:8000/docs`
- API metrics: `http://localhost:8000/metrics`
- Simulator scenario state: `http://localhost:8000/simulator/scenario`
- Simulator scenario reset: `DELETE http://localhost:8000/simulator/scenario`
- Simulator scenario catalog: `http://localhost:8000/simulator/scenarios`
- Demand-response scenario trigger: `POST http://localhost:8000/simulator/scenarios/demand-response`
- Recent domain events: `http://localhost:8000/events/recent`
- Alert rules: `http://localhost:8000/alerts/rules`
- Recent alert events: `http://localhost:8000/alerts/recent`
- Alert state: `http://localhost:8000/alerts/{alert_key}/state`
- React console: `http://localhost:5173` by default, or `http://localhost:${FRONTEND_PORT}`
- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- MQTT broker: `localhost:1883`
- ClickHouse HTTP: `http://localhost:8123/play`

## CI/CD and Images

The repository CI is designed to prove that the monorepo can be built and packaged before a branch merges. It checks the uv workspace, Python formatting and linting, Python bytecode compilation, the React production build, and the Docker Compose configuration under `deploy/compose/`.

For local development, Compose builds `mini-dc-app:latest` from `apps/api/` and `mini-dc-frontend:latest` from `apps/operator-console/`. These tags are local Docker images, not files in the repository. They are stored in the Docker image store on the machine that ran `docker compose up --build`.

For shareable deployments, publish immutable tags to a registry such as GitHub Container Registry and deploy those tags instead of relying on every target machine to build from source.

## Notes

- Normal simulator telemetry stays below alarm thresholds so alarms are driven by explicit simulator scenarios rather than background noise.
- The simulated plant assumes 2N redundancy so paired HVAC, UPS, and PDU assets publish comparable metrics for clearer side-by-side graphs.
- The enrichment layer adds site, zone, asset class, severity, and alarm metadata.
- The SQL views are designed to be easy starting points for Grafana panels.
- The repo uses a uv workspace at the root, with the Python package defined in `apps/api/pyproject.toml`.
- ClickHouse automatically applies the SQL files mounted from `deploy/clickhouse/sql/` on first startup of a fresh `clickhouse_data` volume.
- PostgreSQL automatically applies `deploy/postgres/sql/init.sql` on first startup of a fresh `postgres_data` volume, creating the append-only `event_store.events` table.
- Grafana provisions ClickHouse and Prometheus datasources automatically and loads starter dashboards for facility telemetry and API monitoring.
- Grafana also provisions `Mini DC Facility Trends Live`, a copy of the facility dashboard that reads raw telemetry timestamps without minute bucketing so live scenario testing shows every simulator step.
- Trend dashboards now include threshold lines that match the warning and critical alarm rules in `app/logic.py`, and the asset trend dashboard exposes Grafana variables for rack, HVAC, and power asset selection.
- Telemetry trend panels split one query into separate asset series with Grafana transforms, and they use peak-oriented aggregation (`max`, or `min` for UPS battery) to make alarm excursions easier to spot.
- Scenario profiles now progress through staged behavior over their duration instead of jumping directly to a single failure snapshot, making transfer events, recovery ramps, and compensating equipment behavior easier to observe.
- The demand-response profile adds utility price, utility capacity, GPU load, GPU power, load-shed percentage, chilled-water loop, PUE, and power-cost telemetry while reusing the existing ClickHouse telemetry table.
- The demand-response API trigger emits the first durable PostgreSQL domain-event sequence: scenario started, price spike detected, policy evaluated, load shedding requested, and equipment command issued.
- Default Grafana login comes from `.env`, and the provisioned home dashboard is `Mini DC Operations Overview`.
- Grafana runs with anonymous viewer access and `allow_embedding` enabled so the React console can embed the most critical panels directly in the operator workflow.
- FastAPI exposes Prometheus-style metrics at `/metrics`, and Prometheus scrapes the containerized API from `api:8000` for the API monitoring dashboard.
- The simulator checks a local control file each publish loop, so calling a scenario endpoint shifts telemetry into a named failure or maintenance profile for the requested duration.
- Docker Compose builds the frontend as a static Vite bundle and serves it from nginx. Because Vite embeds `VITE_*` values at build time, rebuild the frontend image after changing `VITE_API_BASE_URL` or `VITE_GRAFANA_BASE_URL`.

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
- Acknowledgment records operator intent for the current alert generation. Once a condition has been acknowledged, the next recurrence can emit a fresh alert event instead of being permanently treated as the same open incident.
- Mute actively suppresses new alert events for that `alert_key` until the mute expires or is cleared.
- Shelving behaves like a longer-lived operator suppression state and is intended for maintenance windows or known work where the alert should remain visible in history but stay out of the live signal path.

## React Operations Frontend

The React console lives in `apps/operator-console/` and complements Grafana rather than replacing it.

Choice justification:
- React plus Vite keeps the first frontend iteration lightweight and local-development friendly without introducing a large UI framework stack.
- The console embeds a few high-value Grafana panels instead of rebuilding every chart from scratch, which keeps the work focused on operator workflow, alarm handling, and scenario control.
- FastAPI remains the source of truth for scenario commands and alert actions, so the frontend stays thin and interactive while the backend owns state transitions.
- Shelving was added to the alert model because the frontend needs a practical suppression action that is distinct from acknowledgment and more durable than a short mute.

Design notes:
- The visual direction is dark-forward, minimal, and intentionally product-like, with restrained red accents inspired by Tesla’s branding language.
- The alarm list is filterable by severity, state, and asset search so the operator can quickly narrow focus during a scenario.
- Alarm actions now require an operator confirmation modal with name and note before the UI will acknowledge, mute, or shelve anything.
- The console also includes an `Acknowledge all active` action, which uses one operator and note to acknowledge each currently active alarm once, deduped by `alert_key`.
- Embedded Grafana panels use `d-solo` URLs against provisioned dashboards, so the console benefits from the existing observability work instead of duplicating it.

## Predictive Maintenance Modeling

The first predictive-maintenance workflow lives in `apps/api/app/maintenance_model.py` and trains a metric-level anomaly baseline from ClickHouse telemetry history, then scores the latest asset windows into ClickHouse.

Choice justification:
- A mean/std anomaly baseline was chosen over logistic regression or random forest because the simulator does not yet produce real labeled failure outcomes or maintenance work orders. Treating abnormal level, persistence, and adverse trend as a weak maintenance-risk signal is more honest than inventing labels.
- The implementation uses only the existing Python dependencies and the existing ClickHouse telemetry table, keeping the experiment reproducible without adding scikit-learn, notebooks, model serving, or orchestration.
- Maintenance scores are persisted to `dc_twin.maintenance_risk_scores` so they can be queried by the API, Grafana, or future operator-console views.
- A `--fixture` mode is included only for smoke testing the model code path without a running stack; normal runs extract project telemetry from ClickHouse.

Model assumptions:
- Normal telemetry is used to estimate each metric baseline.
- Higher values are treated as riskier for thermal, power, and load metrics.
- `ups_battery_pct` is inverted, so lower values are treated as riskier.
- Recent windows are scored using latest anomaly z-score, warning or critical persistence, critical persistence, and a capped adverse trend component.

Operational notes:
- Generate telemetry first with the simulator, then run the worker from the workspace root with `uv run --package dc-digital-twin python -m app.maintenance_model --once`.
- Triggering `cooling-degradation` or `power-outage` before the run should push HVAC or UPS metrics higher in the ranked report.
- The `maintenance_risk_scores` table is the durable output for operators and dashboards.
