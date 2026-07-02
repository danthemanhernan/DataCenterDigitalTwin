# Repository Structure

DataCenterDigitalTwin is organized as a deployable monorepo. Keep runtime code, deployment configuration, documentation, and examples in separate top-level areas so future phases can add Kubernetes, cloud deployment, and home-lab assets without mixing concerns.

## Top-Level Layout

| Path | Purpose |
| --- | --- |
| `apps/api/` | Python backend package. Contains the FastAPI app, simulator, MQTT ingest worker, alerting worker, predictive-maintenance worker, shared telemetry logic, and JSON configs loaded by those services. |
| `apps/operator-console/` | React/Vite operator console. Built into a static nginx image for Compose and runnable through Vite for local frontend development. |
| `deploy/compose/` | Local Docker Compose entrypoint and environment template. This is the primary local stack launcher. |
| `deploy/clickhouse/` | ClickHouse schema and view initialization SQL mounted by Compose. |
| `deploy/grafana/` | Grafana dashboard JSON and datasource/dashboard provisioning. |
| `deploy/mosquitto/` | Mosquitto broker configuration. |
| `deploy/prometheus/` | Prometheus scrape configuration. |
| `docs/` | Long-lived project documentation, roadmap files, and local operation notes. |
| `examples/` | Copyable sample inputs for API calls and local stack configuration. |

## Backend Boundaries

The Python package lives under `apps/api/app/`. It intentionally keeps one package because the API, simulator, ingest, alerting, and maintenance worker share telemetry schemas, alarm rules, and simulator configuration.

| Module | Boundary |
| --- | --- |
| `api.py` | FastAPI routes, request/response models, metrics middleware, and API-facing serialization. |
| `simulator.py` | MQTT telemetry publisher entrypoint. It selects normal or scenario-driven point generators. |
| `ingest.py` | MQTT subscriber entrypoint. It normalizes telemetry and writes records to ClickHouse. |
| `alerting.py` | Alert rule evaluation, alert persistence, and alert lifecycle state. |
| `maintenance_model.py` | Local predictive-maintenance scoring workflow backed by ClickHouse telemetry. |
| `logic.py` | Shared telemetry generation, scenario control, normalization, alarm evaluation, and timestamp helpers. |
| `config_loader.py` | JSON config loading and config shape adaptation. |
| `config/*.json` | Versioned simulator, metric, topology, scenario, and alarm-rule configuration. |

## Deployment Boundaries

Compose builds local images from `apps/api/` and `apps/operator-console/`. The services mount configuration from `deploy/*`; runtime state stays in Docker volumes or ignored local `.env` files.

Do not place generated runtime data, local Docker volumes, cache directories, frontend build output, or model artifacts in source directories. Add source-controlled examples under `examples/` and keep environment-specific files as ignored copies next to their `.env.example` templates.

## Adding New Repo Areas

- Add a new application under `apps/<name>/` when it has its own build, dependency file, or runtime.
- Add deployable infrastructure under `deploy/<system>/` when it is mounted or consumed by a local or production deployment.
- Add reusable docs under `docs/`, not inside app packages, unless the docs are package-specific API notes.
- Add sample payloads, env variants, or operator walkthrough inputs under `examples/`.
- Avoid reviving the retired `mini-dc-digital-twin/` layout; that path is intentionally ignored for stale local artifacts from the pre-monorepo structure.
