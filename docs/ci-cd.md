# CI/CD Foundation

The project uses GitHub Actions as a first CI foundation. The workflow is defined in `.github/workflows/ci.yml` and runs on pull requests, pushes to `main`, and manual dispatches.

## What CI Proves

CI is not deployment yet. At this phase, it is a merge gate that answers five practical questions:

1. Is the Python dependency lockfile still valid?
2. Can the backend test suite run from a clean checkout?
3. Does Python formatting and linting pass?
4. Can the backend package and frontend app build?
5. Can the local Docker Compose configuration render from checked-in files?

Those checks are intentionally boring. Boring CI is useful CI: it catches regressions before they merge without depending on local machine state.

## Workflow Triggers

```yaml
on:
  pull_request:
  workflow_dispatch:
  push:
    branches:
      - main
```

- `pull_request`: validates proposed changes before merge.
- `push` to `main`: validates the branch after merge.
- `workflow_dispatch`: allows a manual run from the GitHub Actions tab.

## Jobs

### Python

The Python job runs from the repo root because uv owns the workspace there.

It checks:

- `.python-version` through `actions/setup-python`.
- uv installation and dependency cache through `astral-sh/setup-uv`.
- `uv lock --check`, which fails if `pyproject.toml` and `uv.lock` drift apart.
- `uv sync --locked`, which installs exactly from the committed lockfile.
- `pytest apps/api/tests`, which runs backend tests.
- `ruff format --check`, which fails on formatting drift.
- `ruff check`, which fails on lint issues.
- `python -m compileall apps/api/app`, which catches syntax/import compilation problems.
- `uv build --package dc-digital-twin`, which verifies the backend package can be built.

### Frontend

The frontend job runs in `apps/operator-console`.

It checks:

- Node setup with npm cache keyed from `apps/operator-console/package-lock.json`.
- `npm ci`, which installs exactly from the lockfile.
- `npm run build`, which verifies the Vite production build.

### Deployment Config

The deployment config job renders Docker Compose with the checked-in environment template:

```bash
docker compose --env-file deploy/compose/.env.example -f deploy/compose/docker-compose.yml config
```

This catches broken YAML, missing variables, invalid service references, and bad relative paths without starting the full stack.

## Caching

CI uses dependency caching to reduce repeated install time:

- `astral-sh/setup-uv` caches uv downloads and package resolution artifacts.
- `actions/setup-node` caches npm dependencies using `apps/operator-console/package-lock.json`.

The cache is an optimization, not a source of truth. The source of truth is still `uv.lock` for Python and `package-lock.json` for the frontend.

## How To Read Failures

- `uv lock --check` failed: update dependency metadata and run `uv lock`.
- `uv sync --locked` failed: the lockfile is inconsistent or a package cannot install on the CI runner.
- `pytest` failed: a backend behavior changed or a test fixture needs updating.
- `ruff format --check` failed: run Ruff format locally and commit the result.
- `ruff check` failed: fix or intentionally configure the lint rule.
- `uv build` failed: package metadata or included package files are invalid.
- `npm ci` failed: `package.json` and `package-lock.json` drifted.
- `npm run build` failed: the React production build is broken.
- `docker compose config` failed: Compose YAML, env defaults, or relative paths are invalid.

## Local Parity

Before opening a PR, run the same gates locally:

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

## What This Is Not Yet

This workflow does not publish Docker images, deploy infrastructure, run migrations against a live database, or exercise the full Compose stack. Those are later release and deployment concerns. Phase 1 is focused on reliable validation before merge.
