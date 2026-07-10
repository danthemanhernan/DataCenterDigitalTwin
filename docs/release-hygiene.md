# Release Hygiene

Release hygiene is the practice of making a repository understandable at specific points in time. It answers a practical question: if someone finds this project later, can they tell what was released, what changed, what license applies, how to contribute, and what is not production-ready?

For this repo, Phase 1 release hygiene means:

- Use version tags for stable checkpoints.
- Keep a changelog.
- Keep the license explicit.
- Document contribution expectations.
- Document known limitations.

## Crash Course

### Git Tag

A Git tag is a named pointer to a commit. For example, `v0.1.0` says "this exact commit is the 0.1.0 release baseline."

Tags matter because branches move. `main` changes every time new work lands, but a release tag stays attached to the same commit.

Common commands:

```bash
git tag
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```

Use annotated tags for releases because they carry a message and timestamp.

### GitHub Release

A GitHub Release is a GitHub page attached to a tag. It gives humans a readable release summary, downloadable source archives, and optional attached files.

The relationship is:

```text
commit -> git tag -> GitHub Release page
```

A GitHub Release is useful for:

- Presenting release notes.
- Showing what changed since the previous release.
- Attaching build artifacts.
- Giving reviewers a clean portfolio checkpoint.

It does not deploy the app by itself.

### Changelog

`CHANGELOG.md` is the long-lived release history in the repo. GitHub Release notes are the release announcement on GitHub.

The simple rule is:

- `CHANGELOG.md`: permanent project history.
- GitHub Release notes: public summary for one version.

For this repo, copy the relevant changelog section into the GitHub Release notes.

### GitHub Container Registry

GitHub Container Registry, usually called GHCR, stores Docker images at `ghcr.io`.

Right now, Compose builds local images:

```text
mini-dc-app:latest
mini-dc-frontend:latest
```

Those images only exist on the machine that built them. GHCR would let the project publish immutable remote images such as:

```text
ghcr.io/danthemanhernan/datacenterdigitaltwin/api:v0.1.0
ghcr.io/danthemanhernan/datacenterdigitaltwin/operator-console:v0.1.0
```

That changes the deployment model:

- Local build: "build this checkout on my machine."
- Registry image: "pull this exact published artifact."

GHCR is useful when you want Compose, Kubernetes, or another environment to run the same image that CI built.

### Version Tags Versus Image Tags

Git tags and Docker image tags often share the same version string, but they point to different things:

- Git tag `v0.1.0`: source code snapshot.
- Docker image tag `v0.1.0`: built container artifact.

For reliable releases, the Docker image should be built from the same commit as the Git tag.

## Current Release Policy

The current project version is `0.1.0` in `apps/api/pyproject.toml`.

Phase 1 uses `v0.1.0` as the initial release tag because it marks the first clean repository baseline with:

- CI validation.
- Local Compose stack.
- Backend tests.
- Frontend build validation.
- Architecture and operations documentation.
- Known limitations documented.

## How To Cut A Release

From a clean `main` branch:

```bash
git status --short --branch
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
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```

Then create the GitHub Release:

1. Open the GitHub repository.
2. Go to **Releases**.
3. Choose **Draft a new release**.
4. Select tag `v0.1.0`.
5. Use `v0.1.0` as the title.
6. Copy the `v0.1.0` notes from `CHANGELOG.md`.
7. Publish the release.

## GHCR Publishing Model

GHCR publishing is not enabled yet. When it is added, the release workflow should:

1. Trigger from tags like `v0.1.0`.
2. Build `apps/api/Dockerfile`.
3. Build `apps/operator-console/Dockerfile`.
4. Push both images to GHCR with the release tag.
5. Optionally also push a moving `latest` tag from `main`.

The workflow will need these GitHub Actions permissions:

```yaml
permissions:
  contents: read
  packages: write
```

Manual GHCR login for local testing uses a GitHub token with package permissions:

```bash
echo "$GITHUB_TOKEN" | docker login ghcr.io -u danthemanhernan --password-stdin
docker build -t ghcr.io/danthemanhernan/datacenterdigitaltwin/api:v0.1.0 apps/api
docker build -t ghcr.io/danthemanhernan/datacenterdigitaltwin/operator-console:v0.1.0 apps/operator-console
docker push ghcr.io/danthemanhernan/datacenterdigitaltwin/api:v0.1.0
docker push ghcr.io/danthemanhernan/datacenterdigitaltwin/operator-console:v0.1.0
```

For this repo, automating GHCR should wait until the deployment target needs pullable images. Local Compose development is still faster when images are built from the checkout.

## License Review

The repository uses the MIT License in `LICENSE`.

Practical meaning:

- Others may use, copy, modify, publish, distribute, sublicense, or sell copies of the project.
- The copyright notice and license text must stay with substantial copies of the software.
- The software is provided without warranty.

This license is appropriate for a portfolio and learning project because it is permissive and easy for reviewers to understand.
