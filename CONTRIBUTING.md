# Contributing

This repository is currently maintained as a portfolio and learning project. Contributions should keep the local stack understandable, reproducible, and easy to operate from a clean checkout.

## Development Flow

1. Create a branch from `main`.
2. Keep changes scoped to one concern.
3. Update docs when behavior, commands, environment variables, ports, or architecture change.
4. Run the local validation commands before opening a pull request.
5. Open a pull request and wait for GitHub Actions to pass before merging.

## Local Validation

Run the same checks that CI runs:

```bash
uv lock --check
uv sync --locked
uv run --package dc-digital-twin pytest apps/api/tests
uv run --package dc-digital-twin ruff format --check apps/api/app apps/api/tests
uv run --package dc-digital-twin ruff check apps/api/app apps/api/tests
uv run --package dc-digital-twin python -m compileall apps/api/app
uv build --package dc-digital-twin
npm --prefix apps/operator-console ci
npm --prefix apps/operator-console run build
docker compose --env-file deploy/compose/.env.example -f deploy/compose/docker-compose.yml config
```

## Code Style

- Python uses Ruff for formatting and linting.
- Python dependencies are managed through uv and committed in `uv.lock`.
- Frontend dependencies are managed through npm and committed in `apps/operator-console/package-lock.json`.
- Docker Compose paths should remain relative to `deploy/compose/docker-compose.yml`.

## Pull Request Expectations

A useful pull request includes:

- A short summary of what changed.
- The validation commands that were run.
- Screenshots when UI, Grafana dashboards, or architecture visuals change.
- Notes about any operational impact, such as new ports, env vars, volumes, topics, tables, or startup assumptions.

## Release Changes

Changes intended for a release should update:

- `CHANGELOG.md`
- `docs/known-limitations.md`, when a limitation is added, removed, or materially changed
- `docs/release-hygiene.md`, when the release process changes
- `README.md`, when entry points or user-facing commands change
