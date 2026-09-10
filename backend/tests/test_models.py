from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import JournalEntryRecord, JournalLineRecord, Organization, Tenant


@pytest.fixture
def db_engine():
    return create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})


@pytest.fixture
def db_session(db_engine):
    Base.metadata.create_all(db_engine)
    with Session(db_engine) as session:
        yield session


def test_platform_records_require_tenant_scope(db_session: Session) -> None:
    tenant = Tenant(slug="demo", name="Demo Tenant")
    organization = Organization(tenant=tenant, legal_name="Demo Co", slug="demo-co")
    db_session.add_all([tenant, organization])
    db_session.commit()

    assert organization.tenant_id == tenant.id


def test_journal_line_has_one_sided_amount_constraint(db_session: Session) -> None:
    tenant = Tenant(slug="ledger-demo", name="Ledger Demo")
    organization = Organization(tenant=tenant, legal_name="Ledger Co", slug="ledger-co")
    db_session.add_all([tenant, organization])
    db_session.flush()
    entry = JournalEntryRecord(
        tenant_id=tenant.id,
        organization_id=organization.id,
        reference="JV-0001",
        journal_date=date(2026, 9, 8),
    )
    line = JournalLineRecord(
        tenant_id=tenant.id,
        organization_id=organization.id,
        entry=entry,
        line_no=1,
        account_code="1100",
        debit=Decimal("10.00"),
        credit=Decimal("10.00"),
    )
    db_session.add_all([entry, line])

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_metadata_contains_required_tables(db_engine) -> None:
    Base.metadata.create_all(db_engine)
    names = set(inspect(db_engine).get_table_names())

    assert {"tenants", "journal_entries", "audit_events", "login_throttles"} <= names
