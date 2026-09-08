# ZSME local Compose boundary

This Compose file is a local integration harness for the ZSME API and PostgreSQL. It is not a production orchestrator or a substitute for a reviewed deployment platform.

## Operating rules

- Copy `backend/.env.compose.example` to the ignored `backend/.env.compose` and replace its placeholders before starting services.
- The API reaches PostgreSQL through the Compose service name `db`; do not add container IPs or commit credentials.
- PostgreSQL has no host port published by default. Use the API's published port for smoke checks and keep database access inside the Compose network.
- Run migrations explicitly with the API image before treating `/ready` as an application-ready signal.
- Keep the named volume for local persistence. Use the backup/restore runbook before deleting a volume or changing schema.

## Boundary and production handoff

Compose validation is local evidence only. Staging and production additionally require a managed secret source, TLS termination, a private database network, backups with restore evidence, image provenance, alerting, and an approved rollback rehearsal. None of those external controls are implied by `docker compose config` or a green local test suite.
