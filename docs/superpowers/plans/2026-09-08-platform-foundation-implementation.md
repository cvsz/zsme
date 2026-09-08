# ZSME Platform Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current in-memory FastAPI ledger bootstrap into the first enterprise-capable vertical slice with persistent tenancy, authentication, authorization, auditability, idempotent ledger posting, and a professional application shell that can host every approved ZSME module.

**Architecture:** Keep a modular monolith with explicit domain boundaries. Use synchronous FastAPI services over SQLAlchemy/PostgreSQL, Alembic migrations, durable sessions, append-only audit events, and transactional ledger posting. Add a Next.js/TypeScript shell only after the backend contracts and design tokens are testable.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, psycopg 3, Alembic, PostgreSQL 17, Redis-ready worker boundary, Next.js App Router, TypeScript, Tailwind CSS, Lucide icons, Playwright.

## Global Constraints

- Preserve the existing `/health`, `/v1/accounting/validate-entry`, and `/v1/accounting/example-entry` contracts.
- Every persisted business record carries tenant and organization scope.
- Posted journal entries are immutable; corrections use reversal or adjustment entries.
- Financial mutations are atomic and require durable idempotency keys.
- Money uses fixed-precision decimal values and explicit currency/rounding policy.
- Secrets are loaded from configuration/secret-manager interfaces and never logged or committed.
- UI follows the ZSME Enterprise theme in `design-system/zsme-enterprise/MASTER.md`.
- UI is mobile-first, WCAG AA-oriented, keyboard accessible, and verified at 375, 414, 768, 1024, and 1440px.
- Use test-first development: each production behavior starts with a failing focused test.
- Work only in `/home/cvsz/zsme`; do not deploy, push, publish releases, import external data, or mutate external systems.

---

### Task 1: Add typed configuration and database session boundaries

**Files:**
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Create: `backend/tests/test_config.py`
- Create: `backend/tests/test_db_session.py`
- Modify: `backend/pyproject.toml`

**Interfaces:**
- `get_settings() -> Settings` returns cached validated settings.
- `Settings.database_url: str`, `Settings.environment: str`, `Settings.secret_key: str`, `Settings.access_token_ttl_minutes: int`.
- `get_engine(database_url: str | None = None) -> Engine` creates a SQLAlchemy engine without connecting during import.
- `get_session() -> Iterator[Session]` yields and closes a request session.

- [x] **Step 1: Write the failing tests**

```python
def test_settings_reads_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("SECRET_KEY", "a-secret-key-with-at-least-32-characters")
    settings = Settings()
    assert settings.database_url.startswith("sqlite")


def test_engine_is_lazy_and_uses_requested_url():
    engine = get_engine("sqlite+pysqlite:///:memory:")
    assert str(engine.url) == "sqlite+pysqlite:///:memory:"


def test_production_settings_reject_short_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("SECRET_KEY", "short")
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings()
```

- [x] **Step 2: Run the focused tests and verify the expected missing-module failure**

Run: `cd backend && pytest -q tests/test_config.py tests/test_db_session.py`

Expected: FAIL because `app.core.config` and `app.db.session` do not exist yet.

- [x] **Step 3: Add dependencies and minimal implementation**

Add `pydantic-settings`, `sqlalchemy`, `psycopg[binary]`, and `alembic` to runtime dependencies. Implement `Settings` with explicit environment aliases, a 32-character production secret requirement, and safe non-production defaults. Implement `DeclarativeBase`, `create_engine`, and a generator that rolls back on exceptions and always closes sessions.

- [x] **Step 4: Run focused and existing tests**

Run: `cd backend && pytest -q tests/test_config.py tests/test_db_session.py tests/test_ledger.py`

Expected: PASS with 8 tests and 0 failures.

- [x] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/app/core backend/app/db backend/tests/test_config.py backend/tests/test_db_session.py
git commit -S -m "feat: add typed configuration and database boundary"
```

### Task 2: Create tenant, organization, identity, role, session, audit, and idempotency models

**Files:**
- Create: `backend/app/db/models/__init__.py`
- Create: `backend/app/db/models/platform.py`
- Create: `backend/app/db/models/ledger.py`
- Create: `backend/app/db/models/mixins.py`
- Create: `backend/app/db/schema.py`
- Create: `backend/tests/test_models.py`
- Create: `backend/alembic.ini`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/script.py.mako`
- Create: `backend/migrations/versions/f27b9d5a4dc3_create_platform_and_ledger_schema.py`

**Interfaces:**
- `Tenant`, `Organization`, `User`, `Role`, `UserRole`, `SessionToken`, `AuditEvent`, `IdempotencyRecord`.
- `ChartAccount`, `FiscalPeriod`, `JournalEntryRecord`, `JournalLineRecord`.
- `BaseModel.id`, `BaseModel.created_at`, `BaseModel.updated_at`.
- `TenantScope.tenant_id`, `TenantScope.organization_id`.
- `Base.metadata` contains every model for Alembic autogeneration.

- [x] **Step 1: Write failing persistence tests**

```python
def test_platform_records_require_tenant_scope(db_session):
    tenant = Tenant(slug="demo", name="Demo Tenant")
    organization = Organization(tenant=tenant, legal_name="Demo Co")
    db_session.add_all([tenant, organization])
    db_session.commit()
    assert organization.tenant_id == tenant.id


def test_journal_line_has_one_sided_amount_constraint(db_session):
    line = JournalLineRecord(account_code="1100", debit=Decimal("10.00"), credit=Decimal("10.00"))
    db_session.add(line)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_metadata_contains_required_tables(db_engine):
    Base.metadata.create_all(db_engine)
    names = set(inspect(db_engine).get_table_names())
    assert {"tenants", "journal_entries", "audit_events"} <= names
```

- [x] **Step 2: Run tests and verify they fail for absent models/schema**

Run: `cd backend && pytest -q tests/test_models.py`

Expected: FAIL because model modules, metadata, and migration do not exist.

- [x] **Step 3: Implement models and first migration**

Use UUID primary keys, UTC timestamps, tenant/org foreign keys, unique tenant slug, unique organization slug within tenant, normalized user email within tenant, durable session token hashes, append-only audit rows, unique `(tenant_id, key)` idempotency records, unique account code within organization, fiscal-period lock state, and journal source/idempotency lineage. Add database checks for non-negative debit/credit and one-sided journal lines.

- [x] **Step 4: Run migration and persistence tests**

Run: `cd backend && alembic upgrade head && pytest -q tests/test_models.py`

Expected: PASS with 3 tests and 0 failures against a clean SQLite test database and the configured migration target.

- [x] **Step 5: Commit**

```bash
git add backend/app/db/models backend/app/db/schema.py backend/alembic.ini backend/migrations backend/tests/test_models.py
git commit -S -m "feat: add tenant identity and ledger persistence schema"
```

### Task 3: Implement password/session authentication and scoped authorization

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/app/core/auth.py`
- Create: `backend/app/api/dependencies.py`
- Create: `backend/app/api/auth.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_security.py`
- Create: `backend/tests/test_auth_api.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- `hash_password(password: str) -> str`.
- `verify_password(password: str, password_hash: str) -> bool`.
- `create_session(db: Session, user: User) -> str`.
- `get_current_principal(request: Request, db: Session) -> Principal`.
- `require_permission(permission: str) -> Callable`.
- `POST /v1/auth/login` accepts `{tenant_slug, email, password}` and returns `{access_token, token_type, expires_in}`.
- `POST /v1/auth/logout` revokes the current session.
- `GET /v1/auth/me` returns the tenant, organization, user, roles, and permissions without password or token hashes.

- [x] **Step 1: Write failing tests**

```python
def test_password_hash_is_not_plaintext():
    password_hash = hash_password("correct horse battery staple")
    assert password_hash != "correct horse battery staple"
    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong", password_hash)


def test_login_rejects_wrong_tenant_or_password(client, seeded_user):
    response = client.post("/v1/auth/login", json={"tenant_slug": "other", "email": seeded_user.email, "password": "bad"})
    assert response.status_code == 401


def test_me_never_crosses_tenant_boundary(client, seeded_user, other_tenant_user):
    token = login_as(seeded_user)
    response = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.json()["tenant_id"] == str(seeded_user.tenant_id)
    assert str(other_tenant_user.tenant_id) not in response.text
```

- [x] **Step 2: Run the tests and verify the expected missing-auth failure**

Run: `cd backend && pytest -q tests/test_security.py tests/test_auth_api.py`

Expected: FAIL because authentication helpers and routes do not exist.

- [x] **Step 3: Implement the minimal secure session flow**

Use Argon2 password hashing, cryptographically random opaque bearer tokens stored only as SHA-256 hashes, expiration and revocation timestamps, constant-time verification, generic login failure messages, and tenant-derived principal context. Apply permission dependencies to protected routes and use a default `ADMIN` role only in test fixtures/bootstrap code, never as an implicit production bypass.

- [x] **Step 4: Run focused and full backend tests**

Run: `cd backend && pytest -q tests/test_security.py tests/test_auth_api.py tests/test_ledger.py`

Expected: PASS with all focused tests and the existing ledger tests.

- [x] **Step 5: Commit**

```bash
git add backend/app/core/security.py backend/app/core/auth.py backend/app/api backend/app/main.py backend/tests/test_security.py backend/tests/test_auth_api.py
git commit -S -m "feat: add tenant-scoped session authentication"
```

### Task 4: Implement auditable idempotent ledger posting and period locks

**Files:**
- Create: `backend/app/domains/ledger/__init__.py`
- Create: `backend/app/domains/ledger/service.py`
- Create: `backend/app/domains/ledger/schemas.py`
- Create: `backend/app/domains/ledger/api.py`
- Create: `backend/tests/test_ledger_persistence.py`
- Create: `backend/tests/test_ledger_api.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- `DomainError(Exception)` in `service.py` is the stable domain exception raised for locked periods, missing accounts, duplicate source lineage, and invalid reversal requests.
- `post_journal_entry(db: Session, command: JournalPostCommand, principal: Principal, idempotency_key: str) -> JournalPostResult`.
- `reverse_journal_entry(db: Session, entry_id: UUID, principal: Principal, idempotency_key: str) -> JournalPostResult`.
- `JournalPostCommand(reference: str, memo: str | None, journal_date: date, lines: list[JournalLineInput], source_type: str, source_id: UUID | None)`.
- `JournalPostResult(entry_id: UUID, status: Literal["posted", "already_posted"], total: Decimal, audit_event_id: UUID)`.
- `POST /v1/accounting/journal-entries` requires `Idempotency-Key` and returns 201 for a new posting or 200 for a replay.
- `POST /v1/accounting/journal-entries/{entry_id}/reverse` creates a linked reversal and never edits the original.

- [x] **Step 1: Write failing behavior tests**

```python
def test_posting_is_atomic_and_audited(db_session, principal, balanced_command):
    result = post_journal_entry(db_session, balanced_command, principal, "post-001")
    assert result.status == "posted"
    assert journal_entry_is_immutable(db_session, result.entry_id)
    assert audit_exists(db_session, result.audit_event_id, action="journal.post")


def test_replaying_idempotency_key_does_not_duplicate_financial_effect(db_session, principal, balanced_command):
    first = post_journal_entry(db_session, balanced_command, principal, "post-002")
    second = post_journal_entry(db_session, balanced_command, principal, "post-002")
    assert second.status == "already_posted"
    assert second.entry_id == first.entry_id
    assert count_entries_for_key(db_session, "post-002") == 1


def test_locked_period_rejects_posting(db_session, principal, balanced_command, locked_period):
    with pytest.raises(DomainError, match="period is locked"):
        post_journal_entry(db_session, balanced_command, principal, "post-003")


def test_reversal_balances_and_preserves_original(db_session, principal, balanced_command):
    original = post_journal_entry(db_session, balanced_command, principal, "post-004")
    reversal = reverse_journal_entry(db_session, original.entry_id, principal, "reverse-004")
    assert reversal.entry_id != original.entry_id
    assert reversal.status == "posted"
    assert original_still_exists_and_is_unchanged(db_session, original.entry_id)
```

- [x] **Step 2: Run tests and verify they fail for absent service**

Run: `cd backend && pytest -q tests/test_ledger_persistence.py tests/test_ledger_api.py`

Expected: FAIL because persistent posting service and routes do not exist.

- [x] **Step 3: Implement transactional posting**

Validate the existing Pydantic ledger invariants, resolve accounts and period under the principal organization, lock the idempotency row during replay, insert the immutable entry and lines, create the audit event, and commit once. Reject posted-entry update/delete routes. Use an explicit domain error mapper that returns stable problem responses and a correlation ID.

- [x] **Step 4: Run focused, API, and regression tests**

Run: `cd backend && pytest -q tests/test_ledger_persistence.py tests/test_ledger_api.py tests/test_ledger.py`

Expected: PASS with all posting, reversal, lock, replay, audit, API, and legacy validation tests.

- [x] **Step 5: Commit**

```bash
git add backend/app/domains/ledger backend/app/main.py backend/tests/test_ledger_persistence.py backend/tests/test_ledger_api.py
git commit -S -m "feat: add auditable idempotent ledger posting"
```

### Task 5: Add platform APIs and operational error/health contracts

**Files:**
- Create: `backend/app/api/errors.py`
- Create: `backend/app/api/organizations.py`
- Create: `backend/app/api/health.py`
- Create: `backend/app/observability/logging.py`
- Create: `backend/tests/test_platform_api.py`
- Modify: `backend/app/main.py`
- Modify: `backend/.env.example`

**Interfaces:**
- `GET /health` remains the liveness response.
- `GET /ready` checks database availability and returns 503 when unavailable.
- `GET /v1/organizations` returns only organizations in the current principal scope.
- `POST /v1/organizations` creates an organization only for an authorized principal.
- Errors use `application/problem+json` with `code`, `detail`, `correlation_id`, and optional `fields`.

- [x] **Step 1: Write failing tests**

```python
def test_ready_reports_dependency_failure(client, unavailable_db):
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/json")


def test_organization_list_is_scoped(client, tenant_a_token, tenant_b_organization):
    response = client.get("/v1/organizations", headers=bearer(tenant_a_token))
    assert response.status_code == 200
    assert all(item["id"] != str(tenant_b_organization.id) for item in response.json())


def test_domain_error_has_stable_problem_shape(client, authenticated_headers):
    response = client.post("/v1/accounting/journal-entries", headers=authenticated_headers | {"Idempotency-Key": "bad-1"}, json={})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.json()["correlation_id"]
```

- [x] **Step 2: Run focused tests and verify absent route/error behavior**

Run: `cd backend && pytest -q tests/test_platform_api.py`

Expected: FAIL because readiness, organization routes, and stable error mapping do not exist.

- [x] **Step 3: Implement contracts**

Register exception handlers, request correlation middleware, JSON redacted logging, liveness/readiness routes, and scoped organization CRUD. Ensure readiness never leaks the database URL or credentials.

- [x] **Step 4: Run full backend checks**

Run: `cd backend && ruff check . && pytest -q`

Expected: PASS with zero lint errors and zero test failures.

- [x] **Step 5: Commit**

```bash
git add backend/app/api backend/app/observability backend/app/main.py backend/.env.example backend/tests/test_platform_api.py
git commit -S -m "feat: add scoped platform APIs and readiness checks"
```

### Task 6: Build the professional Next.js application shell and theme contract

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.ts`
- Create: `frontend/app/layout.tsx`
- Create: `frontend/app/page.tsx`
- Create: `frontend/app/(auth)/login/page.tsx`
- Create: `frontend/app/(app)/dashboard/page.tsx`
- Create: `frontend/app/(app)/accounting/page.tsx`
- Create: `frontend/app/(app)/sales/page.tsx`
- Create: `frontend/app/(app)/settings/page.tsx`
- Create: `frontend/components/design-system/tokens.css`
- Create: `frontend/components/design-system/app-shell.tsx`
- Create: `frontend/components/design-system/status-badge.tsx`
- Create: `frontend/components/design-system/data-card.tsx`
- Create: `frontend/components/design-system/nav.tsx`
- Create: `frontend/tests/shell.spec.ts`
- Create: `frontend/tests/accessibility.spec.ts`

**Interfaces:**
- `AppShell({ children, navigation, principal })` renders responsive navigation and context controls.
- `StatusBadge({ status, label })` always renders text plus accessible status semantics.
- `tokens.css` exposes semantic light/dark tokens from `MASTER.md`.
- Authenticated pages use explicit `not_configured` or `empty` states until APIs supply data; they never display fabricated financial success.

- [x] **Step 1: Write failing browser tests**

```typescript
test('dashboard exposes keyboard navigable shell and tenant context', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page.getByRole('navigation')).toBeVisible();
  await expect(page.getByRole('button', { name: /search/i })).toBeVisible();
  await expect(page.getByText(/not configured|empty/i)).toBeVisible();
});

test('shell has no horizontal overflow at mobile width', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/dashboard');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
```

- [x] **Step 2: Run browser tests and verify the missing-frontend failure**

Run: `cd frontend && npm test -- --project=chromium`

Expected: FAIL because the frontend package and routes do not exist.

- [x] **Step 3: Implement shell and design tokens**

Use self-hostable font loading with Lexend and Source Sans 3 plus Noto Sans Thai fallback, blue/amber semantic tokens, dark default authenticated theme, light and print alternate, Lucide SVG icons, visible focus styles, minimum 44px controls, mobile drawer navigation, desktop collapsible sidebar, route loading/error boundaries, and reduced-motion support.

- [x] **Step 4: Run browser, accessibility, and build checks**

Run: `cd frontend && npm test -- --project=chromium && npm run build`

Expected: PASS with no accessibility violations in the shell suite, no mobile horizontal overflow, and a successful production build.

- [x] **Step 5: Commit**

```bash
git add frontend
git commit -S -m "feat: add enterprise responsive application shell"
```

### Task 7: Harden CI, Compose, and release evidence for the foundation slice

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `docker-compose.yml`
- Modify: `backend/Dockerfile`
- Modify: `backend/.env.example`
- Create: `infra/compose/README.md`
- Create: `docs/runbooks/foundation-local.md`
- Create: `docs/runbooks/backup-restore.md`
- Create: `backend/tests/test_ci_contract.py`

**Interfaces:**
- CI runs backend lint/type/test/security checks, migration smoke, frontend lint/test/build, container build, and artifact checks.
- Compose has explicit API liveness/readiness, database health, non-secret example configuration, and no pinned container IPs.
- Runbooks describe exact local startup, migration, smoke, backup, restore, and rollback commands.

- [x] **Step 1: Write failing configuration checks**

```python
def test_compose_uses_service_dns_and_health_dependencies():
    compose = yaml.safe_load(Path('../docker-compose.yml').read_text())
    assert 'db' in compose['services']['api']['environment']['DATABASE_URL']
    assert compose['services']['api']['depends_on']['db']['condition'] == 'service_healthy'


def test_ci_contains_required_quality_jobs():
    workflow = Path('../.github/workflows/ci.yml').read_text()
    for required in ('pytest', 'ruff', 'docker build', 'alembic'):
        assert required in workflow
```

- [x] **Step 2: Run the checks and verify missing hardening**

Run: `python3 -m pytest -q backend/tests/test_ci_contract.py`

Expected: FAIL because the contract tests and hardened CI workflow do not exist.

- [x] **Step 3: Implement non-secret CI/Compose/runbook hardening**

Add migration smoke, type/security tooling with explicit versions, frontend checks, container health probes, non-root runtime, pinned service DNS, and runbooks that distinguish local evidence from staging/production evidence. Add `PyYAML>=6.0,<7` to development dependencies for the Compose contract test.

- [x] **Step 4: Run the complete foundation gate**

Run: `cd backend && ruff check . && pytest -q`; `docker compose config`; `docker build -t zsme-api:foundation ./backend`; `cd frontend && npm run build`.

Expected: all commands exit 0, or a documented environment-only skip identifies the missing external tool without claiming the gate passed.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml docker-compose.yml backend/Dockerfile backend/.env.example infra/compose docs/runbooks
git commit -S -m "ci: harden foundation build and operational checks"
```

## Acceptance Criteria

- The legacy API endpoints continue to work.
- A clean database can be migrated without manual SQL.
- Tenant and organization scope is enforced in models, services, and API tests.
- Passwords and bearer tokens are never stored or returned in plaintext.
- Protected routes require a valid non-revoked session and permission.
- Ledger posting is transactional, balanced, immutable, audited, period-aware, and idempotent.
- Reversal creates a new linked entry and leaves the original unchanged.
- Liveness and readiness have distinct, safe responses.
- The application shell renders the approved professional theme in light/dark modes, supports Thai text, keyboard access, mobile layouts, and explicit empty/unconfigured states.
- Backend and frontend quality gates are reproducible locally and represented in CI.
- No external deployment or production claim is made without the corresponding evidence level.

## Risk Matrix

| Risk | Impact | Mitigation | Stop condition |
|---|---|---|---|
| Database migration changes financial schema unsafely | Data loss or incorrect reports | Clean migration, representative fixture, rollback/restore rehearsal | Any migration cannot be replayed or verified |
| Tenant filter omitted in a repository/query | Cross-company data disclosure | Principal context, repository boundaries, cross-tenant denial tests | Any cross-tenant test fails |
| Idempotency race duplicates posting | Incorrect ledger | Unique key, transaction lock, concurrent test | Duplicate financial effect observed |
| Thai date/tax rules are stale | Regulatory error | Effective-dated rules and official validation record | Current rule source is unavailable |
| UI density harms accessibility/mobile use | Operator error | WCAG checks, keyboard tests, breakpoint snapshots | Contrast, focus, overflow, or truncation regression |
| External provider credentials/contracts are absent | False integration state | Adapter states and explicit `not_configured` | Code would need a fake success path |

## Verification Matrix

| Acceptance area | Narrow check | Broad check | Evidence level |
|---|---|---|---|
| Ledger invariants | Domain and persistence tests | API and concurrency tests | Local/CI |
| Tenant security | Cross-tenant API tests | Security suite and review | Local/CI |
| Migrations | Alembic clean upgrade | Restore/rehearsal against staging data | Local/staging |
| UI/UX | Playwright and accessibility tests | Visual regression at five breakpoints | Local/CI |
| Runtime | Liveness/readiness smoke | Observability and failure drills | Local/staging |
| Release | Container build and SBOM | Signed artifact and rollback rehearsal | CI/staging |

## Stop Condition

Stop the current slice and report the exact failure if a financial invariant, tenant boundary, authorization check, migration, test, or accessibility gate fails. Continue independent non-dependent tasks only when the failed boundary is isolated and no unsafe workaround is required.
