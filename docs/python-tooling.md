# Python Tooling

This repo uses a root uv workspace with one Python package under `apps/api/`.

## Workspace Layout

- Root `pyproject.toml` owns the uv workspace.
- `apps/api/pyproject.toml` owns the backend package metadata, runtime dependencies, development dependencies, Ruff configuration, and build settings.
- `.python-version` pins local tooling to Python 3.11, matching the backend Docker image family.
- `uv.lock` is committed and should be updated whenever Python dependency metadata changes.

## Local Commands

Run Python tooling from the repo root:

```bash
uv lock --check
uv sync --locked
uv run --package dc-digital-twin pytest apps/api/tests
uv run --package dc-digital-twin ruff format --check apps/api/app apps/api/tests
uv run --package dc-digital-twin ruff check apps/api/app apps/api/tests
uv run --package dc-digital-twin python -m compileall apps/api/app
```

To format or lint while working:

```bash
uv run --package dc-digital-twin ruff format apps/api/app apps/api/tests
uv run --package dc-digital-twin ruff check --fix apps/api/app apps/api/tests
```

## Dependency Policy

- Add runtime Python dependencies to `dependencies` in `apps/api/pyproject.toml`.
- Add test, lint, format, and developer-only tools to `dependency-groups.dev`.
- Keep tool versions intentionally constrained where runtime behavior matters; use `uv lock` to refresh transitive versions.
- Do not add Python dependency metadata to the root `pyproject.toml` unless the root becomes a real package.
- Rebuild the Python image after dependency or package-code changes that need to run in Compose:

```bash
docker compose -f deploy/compose/docker-compose.yml --env-file deploy/compose/.env up -d --build api ingest alerting simulator maintenance-model
```

## Ruff Policy

Ruff is the source of truth for Python formatting, import sorting, and linting. The current rules are configured in `apps/api/pyproject.toml`.

The active checks cover:

- `E`: pycodestyle errors
- `F`: pyflakes
- `I`: import sorting
- `UP`: modern Python upgrades
- `B`: bugbear likely-bug checks
- `SIM`: simplification checks

Formatting uses Ruff defaults with double quotes, spaces, automatic line endings, Python 3.11 syntax, and a 120-character line length.

## Type-Checking Plan

Phase 1 does not enforce static type checking yet. The codebase currently has useful annotations, but it also depends on dynamic data returned by ClickHouse, MQTT payloads, and JSON config files. Enforcing a type checker before those boundaries are modeled would create noise instead of useful signal.

The planned path is:

1. Keep `python -m compileall apps/api/app` in CI as the current syntax/import sanity check.
2. Add typed payload models or `TypedDict` boundaries for telemetry rows, alert rows, scenario state, and config JSON.
3. Add a type checker as a dev dependency once the boundary types exist.
4. Start with a non-blocking CI command or a narrow path, then make it blocking after the first pass is clean.

Good first targets for boundary types:

- `apps/api/app/logic.py`: simulator points, normalized telemetry rows, scenario control state.
- `apps/api/app/ingest.py`: MQTT payload and ClickHouse insert row.
- `apps/api/app/alerting.py`: alert candidates, actions, and lifecycle state.
- `apps/api/app/maintenance_model.py`: telemetry samples and risk-score rows.
