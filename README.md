# DataCenterDigitalTwin

[![CI](https://github.com/danthemanhernan/DataCenterDigitalTwin/actions/workflows/ci.yml/badge.svg)](https://github.com/danthemanhernan/DataCenterDigitalTwin/actions/workflows/ci.yml)

Test project for mocking a digital twin for a data center and using it as a playground for testing data analysis methods.

The repo is organized as a deployable monorepo:

- `apps/api/`: Python FastAPI services, simulator, ingest worker, alerting worker, and maintenance model.
- `apps/operator-console/`: React/Vite operator console served by nginx in Docker.
- `deploy/compose/`: Docker Compose entrypoint and environment example.
- `deploy/clickhouse/`, `deploy/grafana/`, `deploy/prometheus/`, `deploy/mosquitto/`: service configuration mounted by Compose.
- `docs/local-stack.md`: local stack operation notes and endpoint details.
- `docs/repository-structure.md`: module and ownership boundaries for the monorepo.
- `docs/python-tooling.md`: uv, Ruff, dependency, and type-checking plan for the Python backend.
- `docs/ci-cd.md`: GitHub Actions workflow explanation and local parity commands.
- `examples/`: sample environment files and API request payloads for local demos.

```bash
cd deploy/compose
cp .env.example .env
docker compose up -d --build
```

## CI/CD

GitHub Actions validates pull requests and pushes to `main` with the same gates used locally: uv lock/sync, Ruff formatting and linting, Python compile checks, frontend install/build, and Docker Compose configuration rendering.

Docker Compose currently builds local images named `mini-dc-app:latest` and `mini-dc-frontend:latest` from this checkout. Those images live in the local Docker image store on the machine that ran the build. The next deployment step is publishing versioned images to an artifact registry such as GitHub Container Registry, then updating Compose or a deployment manifest to pull those immutable tags.

See `docs/local-stack.md` for endpoint details and local development notes.

See `docs/repository-structure.md` for the repo layout, module boundaries, and guidance on where new apps, deployment files, docs, and examples should go.

See `docs/python-tooling.md` for the Python workspace, dependency, Ruff, and type-checking plan.

See `docs/ci-cd.md` for the GitHub Actions workflow, job breakdown, caching behavior, and local parity commands.
