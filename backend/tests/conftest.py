from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.db.models import (
    ChartAccount,
    FiscalPeriod,
    Organization,
    Role,
    Tenant,
    User,
    UserRole,
)
from app.db.session import get_session


@pytest.fixture
def db_engine() -> Iterator[Engine]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    with Session(db_engine) as session:
        yield session
        session.rollback()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    from app.main import app

    def override_get_session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def seeded_user(db_session: Session) -> User:
    tenant = Tenant(slug="demo", name="Demo Tenant")
    organization = Organization(tenant=tenant, legal_name="Demo Co", slug="demo-co")
    user = User(
        tenant=tenant,
        organization=organization,
        email="admin@example.com",
        display_name="Demo Admin",
        password_hash=hash_password("correct horse battery staple"),
    )
    role = Role(
        tenant=tenant,
        name="ADMIN",
        permissions=[
            "auth:read",
            "organization:read",
            "organization:write",
            "partner:read",
            "partner:write",
        ],
        is_system=True,
    )
    db_session.add_all([tenant, organization, user, role])
    db_session.flush()
    db_session.add(UserRole(tenant_id=tenant.id, user_id=user.id, role_id=role.id))
    db_session.commit()
    return user


@pytest.fixture
def other_tenant_user(db_session: Session) -> User:
    tenant = Tenant(slug="other", name="Other Tenant")
    organization = Organization(tenant=tenant, legal_name="Other Co", slug="other-co")
    user = User(
        tenant=tenant,
        organization=organization,
        email="other@example.com",
        display_name="Other Admin",
        password_hash=hash_password("correct horse battery staple"),
    )
    db_session.add_all([tenant, organization, user])
    db_session.commit()
    return user


@pytest.fixture
def ledger_ready(db_session: Session, seeded_user: User) -> FiscalPeriod:
    accounts = [
        ChartAccount(
            tenant_id=seeded_user.tenant_id,
            organization_id=seeded_user.organization_id,
            code="1100",
            name="Accounts receivable",
            account_type="asset",
        ),
        ChartAccount(
            tenant_id=seeded_user.tenant_id,
            organization_id=seeded_user.organization_id,
            code="4000",
            name="Revenue",
            account_type="revenue",
        ),
        ChartAccount(
            tenant_id=seeded_user.tenant_id,
            organization_id=seeded_user.organization_id,
            code="2101",
            name="Output VAT",
            account_type="liability",
        ),
    ]
    period = FiscalPeriod(
        tenant_id=seeded_user.tenant_id,
        organization_id=seeded_user.organization_id,
        name="2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status="open",
    )
    db_session.add_all([*accounts, period])
    db_session.commit()
    return period
