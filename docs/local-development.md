# Local Development Guide

This guide covers day-to-day development from the repo root. Use `docs/local-stack.md` when you want the full operational walkthrough for the Docker Compose stack.

## Prerequisites

- Docker Desktop or a compatible Docker engine
- Python 3.11
- uv
- Node.js 22
- npm
- Optional: MQTT Explorer or `mosquitto_sub` for broker inspection

## First-Time Setup

```bash
uv sync --locked
npm --prefix apps/operator-console ci
cp deploy/compose/.env.example deploy/compose/.env
```

The checked-in env example is safe for local development. Change passwords, ports, and browser-facing URLs in `deploy/compose/.env` if needed.

## Start The Full Stack

```bash
docker compose -f deploy/compose/docker-compose.yml --env-file deploy/compose/.env up -d --build
```

Useful URLs:

- Operator console: `http://localhost:5173`
- FastAPI docs: `http://localhost:8000/docs`
- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- MQTT broker: `localhost:1883`
- ClickHouse HTTP: `http://localhost:8123/play`

Check services:

```bash
docker compose -f deploy/compose/docker-compose.yml --env-file deploy/compose/.env ps
docker compose -f deploy/compose/docker-compose.yml --env-file deploy/compose/.env logs --tail=80 api ingest simulator
```

## Run Backend Checks

```bash
uv lock --check
uv sync --locked
uv run --package dc-digital-twin pytest apps/api/tests
uv run --package dc-digital-twin ruff format --check apps/api/app apps/api/tests
uv run --package dc-digital-twin ruff check apps/api/app apps/api/tests
uv run --package dc-digital-twin python -m compileall apps/api/app
uv build --package dc-digital-twin
```

## Run Frontend Checks

```bash
npm --prefix apps/operator-console ci
npm --prefix apps/operator-console run build
```

For frontend-only iteration outside Docker:

```bash
cd apps/operator-console
npm run dev
```

Use `VITE_API_BASE_URL` and `VITE_GRAFANA_BASE_URL` in `apps/operator-console/.env` when the dev server should point somewhere other than the default local stack.

## Trigger A Scenario

```bash
curl -X POST http://localhost:8000/simulator/scenarios/power-outage \
  -H "Content-Type: application/json" \
  --data @examples/simulator-scenarios/power-outage.json
```

Other payloads live under `examples/simulator-scenarios/`.

## Inspect MQTT

MQTT Explorer settings:

- Protocol: `mqtt://`
- Host: `127.0.0.1`
- Port: `1883`
- TLS: off
- WebSocket: off
- Username/password: blank

Subscribe to:

```text
dc/telemetry/#
```

## Reset Local Data

The ClickHouse data volume contains local telemetry history. If the local database is corrupted or you want a fresh run:

```bash
docker compose -f deploy/compose/docker-compose.yml --env-file deploy/compose/.env down
docker volume rm mini-dc-digital-twin_clickhouse_data
docker compose -f deploy/compose/docker-compose.yml --env-file deploy/compose/.env up -d --build
```

This deletes local telemetry and derived tables. It does not remove checked-in schema, dashboards, or source files.
