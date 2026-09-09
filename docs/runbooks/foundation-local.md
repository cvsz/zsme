# ZSME foundation local runbook

This runbook starts the foundation slice locally and records evidence without pretending that local Docker is staging or production.

## Prerequisites

- Docker Engine with the Compose plugin
- Python 3.12 or newer for API-only checks
- Node 22 or newer and npm for frontend checks
- `curl`, `openssl`, and an available host port 18081

## Configure a local boundary

Create the ignored Compose configuration and replace both placeholder values with local-only material:

```bash
cp backend/.env.compose.example backend/.env.compose
${EDITOR:-vi} backend/.env.compose
```

Do not commit `backend/.env.compose`. The API reads `SECRET_KEY` and database credentials from the environment; they are not supplied by the browser.

## Start, migrate, and smoke test

```bash
docker compose --env-file backend/.env.compose config --quiet
docker compose --env-file backend/.env.compose up --build -d db
docker compose --env-file backend/.env.compose run --rm api alembic upgrade head
docker compose --env-file backend/.env.compose up --build -d api
docker compose --env-file backend/.env.compose ps
curl --fail-with-body http://127.0.0.1:18081/health
curl --fail-with-body http://127.0.0.1:18081/ready
```

`/health` is liveness. `/ready` is dependency readiness and returns a failure response when the database cannot be reached. A successful local response is local evidence only.

## Run repository quality gates

```bash
backend/.venv/bin/ruff check backend
backend/.venv/bin/pytest -q backend/tests
(cd frontend && npm ci && npm run lint && npm run typecheck && npm test -- --project=chromium && npm run build)
```

If Docker, Chromium, PostgreSQL, or external package access is unavailable, record the exact skipped command and reason. Do not convert a skipped gate into a passing claim.

## Inspect and stop

```bash
docker compose --env-file backend/.env.compose logs --tail=100 api db
docker compose --env-file backend/.env.compose down
```

`down` preserves the named database volume. Do not use `down --volumes` without a confirmed backup and an explicit local-data deletion decision.

## Rollback boundary

For a local code rollback, rebuild from a known commit and rerun the migration smoke test. For a schema rollback, take a backup first and use the reviewed Alembic downgrade command from the backup/restore runbook. Never assume a downgrade is safe for production data merely because it succeeds on an empty local database.

## Evidence levels

This runbook can prove local configuration, local migration replay, local endpoint behavior, and local test results. It cannot prove staging traffic, production secrets, external identity-provider behavior, database restore readiness, observability coverage, signed image publication, or a production rollback rehearsal. Those require separate staging/production evidence.
