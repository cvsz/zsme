# ZSME PostgreSQL backup and restore runbook

Backups contain tenant and financial data. Restrict access, use an approved destination, and never commit a backup file to the repository.

## Pre-flight controls

- Confirm the target environment, maintenance window, operator authorization, and retention policy.
- Confirm the backup destination is encrypted and access-controlled.
- Record the database version, application image, migration revision, and UTC timestamp.
- Treat local backup/restore output as a rehearsal; staging and production restore evidence must be recorded separately.

## Create a logical backup

With `backend/.env.compose` configured for the intended local or approved environment:

```bash
BACKUP_FILE="./backups/zsme-$(date -u +%Y%m%dT%H%M%SZ).dump"
mkdir -p "$(dirname "$BACKUP_FILE")"
docker compose --env-file backend/.env.compose exec -T db sh -lc 'pg_dump --format=custom --no-owner --file=- "$POSTGRES_DB"' > "$BACKUP_FILE"
sha256sum "$BACKUP_FILE"
```

For staging or production, use the managed database backup mechanism when available and retain the provider's completion ID alongside the application release evidence.

## Restore into a controlled target

Restoring with `--clean` removes objects in the target database. Stop writers, confirm the target, and obtain the required approval before running it.

```bash
docker compose --env-file backend/.env.compose stop api
docker compose --env-file backend/.env.compose exec -T db sh -lc 'pg_restore --clean --if-exists --no-owner --dbname="$POSTGRES_DB"' < "$BACKUP_FILE"
docker compose --env-file backend/.env.compose run --rm api alembic upgrade head
docker compose --env-file backend/.env.compose up -d api
curl --fail-with-body http://127.0.0.1:18081/ready
```

Validate row counts, tenant boundaries, journal balances, audit events, and application smoke flows against an independent checklist. Do not use a restored database for customer traffic until validation is signed off.

## Rollback and failure handling

If restore validation fails, keep the target isolated, preserve logs and checksums, and escalate. Roll back the application image to the last known compatible artifact only after confirming migration compatibility. A destructive database downgrade is not an automatic recovery action; restore the last verified backup or follow the approved migration rollback procedure.

## Evidence record

Record the backup checksum, source/target identifiers without credentials, database and image versions, migration revision, validation results, operator, approver, and UTC timestamps. A successful local command is not production backup or restore proof until the corresponding staging/production rehearsal exists.
