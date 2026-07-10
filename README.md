# DataCenterDigitalTwin

[![CI](https://github.com/danthemanhernan/DataCenterDigitalTwin/actions/workflows/ci.yml/badge.svg)](https://github.com/danthemanhernan/DataCenterDigitalTwin/actions/workflows/ci.yml)

DataCenterDigitalTwin is a local AI data center digital twin for practicing supervisory controls, industrial telemetry, observability, alerting, and operator workflow design.

It simulates rack, HVAC, UPS, and PDU telemetry; publishes points through MQTT; normalizes and stores telemetry in ClickHouse; exposes a FastAPI surface; evaluates alert rules; runs a lightweight maintenance-risk model; and presents the system through Grafana dashboards and a React operator console.

## Quick Start

```bash
cp deploy/compose/.env.example deploy/compose/.env
docker compose -f deploy/compose/docker-compose.yml --env-file deploy/compose/.env up -d --build
```

Open:

- Operator console: `http://localhost:5173`
- FastAPI docs: `http://localhost:8000/docs`
- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- MQTT broker: `localhost:1883`

## Documentation

- [Master roadmap](docs/roadmap/MASTER_ROADMAP.md)
- [Phase 1 roadmap](docs/roadmap/phase-1-production.md)
- [Architecture overview](docs/architecture.md)
- [Interactive architecture map](docs/architecture-map.html)
- [Local development guide](docs/local-development.md)
- [Local stack operations](docs/local-stack.md)
- [Environment variables](docs/environment.md)
- [Repository structure](docs/repository-structure.md)
- [Python tooling](docs/python-tooling.md)
- [CI/CD foundation](docs/ci-cd.md)
- [Release hygiene](docs/release-hygiene.md)
- [Known limitations](docs/known-limitations.md)
- [Screenshots](docs/screenshots.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)

The repo is organized as a deployable monorepo:

- `apps/api/`: Python FastAPI services, simulator, ingest worker, alerting worker, and maintenance model.
- `apps/operator-console/`: React/Vite operator console served by nginx in Docker.
- `deploy/compose/`: Docker Compose entrypoint and environment example.
- `deploy/clickhouse/`, `deploy/grafana/`, `deploy/prometheus/`, `deploy/mosquitto/`: service configuration mounted by Compose.
- `docs/local-stack.md`: local stack operation notes and endpoint details.
- `docs/repository-structure.md`: module and ownership boundaries for the monorepo.
- `docs/python-tooling.md`: uv, Ruff, dependency, and type-checking plan for the Python backend.
- `docs/ci-cd.md`: GitHub Actions workflow explanation and local parity commands.
- `docs/release-hygiene.md`: release tags, GitHub Releases, GHCR concepts, and license review.
- `docs/known-limitations.md`: current runtime, security, data, observability, and deployment constraints.
- `docs/architecture.md`: service boundaries and data flow.
- `docs/architecture-map.html`: visual architecture map with platform icons and owned-service symbols.
- `docs/local-development.md`: day-to-day development commands.
- `docs/environment.md`: environment variable reference.
- `docs/screenshots.md`: sample UI screenshots and recapture notes.
- `examples/`: sample environment files and API request payloads for local demos.

## CI/CD

GitHub Actions validates pull requests and pushes to `main` with the same gates used locally: uv lock/sync, pytest, Ruff formatting and linting, Python package build, frontend install/build, and Docker Compose configuration rendering.

Docker Compose currently builds local images named `mini-dc-app:latest` and `mini-dc-frontend:latest` from this checkout. Those images live in the local Docker image store on the machine that ran the build. The next deployment step is publishing versioned images to an artifact registry such as GitHub Container Registry, then updating Compose or a deployment manifest to pull those immutable tags.
