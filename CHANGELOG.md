# Changelog

All notable changes to this project are tracked here.

This project uses human-readable release notes with semantic version tags. The current version number is aligned with the Python package version in `apps/api/pyproject.toml`.

## v0.1.0 - 2026-07-10

Initial Phase 1 release baseline.

### Added

- Monorepo layout with `apps/api`, `apps/operator-console`, `deploy`, `docs`, and `examples`.
- Local Docker Compose stack for MQTT, ClickHouse, FastAPI, simulator, ingest worker, alerting worker, maintenance model, Prometheus, Grafana, and the React operator console.
- FastAPI backend with telemetry, asset, alerting, simulator-control, scenario, and health endpoints.
- MQTT telemetry simulator and ingest worker for local digital-twin data flow.
- ClickHouse schema, alert tables, views, and Grafana dashboard provisioning.
- React/Vite operator console served by nginx.
- pytest coverage for API helpers, routes, simulator behavior, ingest parsing, alerting logic, maintenance model behavior, and smoke-level imports.
- GitHub Actions CI for Python tests, Ruff format/lint checks, Python package build, frontend build, and Docker Compose config rendering.
- Documentation for architecture, local development, environment variables, Python tooling, CI/CD, screenshots, repository structure, known limitations, and release hygiene.

### Notes

- This release is a local-development and portfolio baseline. It is not a production deployment.
- Docker images are still built locally by Compose. Publishing versioned images to GitHub Container Registry is documented but not automated yet.
