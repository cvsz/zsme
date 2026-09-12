from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    event,
    text,
)
from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import IdentifiedTimestampMixin, OrganizationScopeMixin


class ChartAccount(IdentifiedTimestampMixin, OrganizationScopeMixin, Base):
    __tablename__ = "chart_accounts"
    __table_args__ = (
        CheckConstraint(
            "account_type IN ('asset', 'liability', 'equity', 'revenue', 'expense')",
            name="ck_chart_accounts_type",
        ),
        UniqueConstraint("organization_id", "code", name="uq_chart_accounts_org_code"),
    )

    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    account_type: Mapped[str] = mapped_column(String(30), nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chart_accounts.id", ondelete="RESTRICT"), nullable=True
    )
    is_control: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    is_cash_equivalent: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    version: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)

    parent: Mapped[ChartAccount | None] = relationship(
        "ChartAccount", remote_side="ChartAccount.id", back_populates="children"
    )
    children: Mapped[list[ChartAccount]] = relationship(
        "ChartAccount", back_populates="parent", cascade="save-update"
    )


class FiscalPeriod(IdentifiedTimestampMixin, OrganizationScopeMixin, Base):
    __tablename__ = "fiscal_periods"
    __table_args__ = (
        CheckConstraint("start_date <= end_date", name="ck_fiscal_period_dates"),
        CheckConstraint("status IN ('open', 'locked')", name="ck_fiscal_period_status"),
        UniqueConstraint(
            "organization_id", "start_date", "end_date", name="uq_fiscal_period_org_dates"
        ),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)


class JournalEntryRecord(IdentifiedTimestampMixin, OrganizationScopeMixin, Base):
    __tablename__ = "journal_entries"
    __table_args__ = (
        UniqueConstraint("organization_id", "reference", name="uq_journal_entries_org_reference"),
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_journal_entries_org_idempotency"
        ),
        Index(
            "uq_journal_entries_org_source",
            "organization_id",
            "source_type",
            "source_id",
            unique=True,
            postgresql_where=text("source_id IS NOT NULL"),
            sqlite_where=text("source_id IS NOT NULL"),
        ),
    )

    fiscal_period_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("fiscal_periods.id", ondelete="RESTRICT"), nullable=True
    )
    reference: Mapped[str] = mapped_column(String(100), nullable=False)
    journal_date: Mapped[date] = mapped_column(Date, nullable=False)
    memo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="posted", nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reversal_of_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=True
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lines: Mapped[list[JournalLineRecord]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", order_by="JournalLineRecord.line_no"
    )


class JournalLineRecord(IdentifiedTimestampMixin, OrganizationScopeMixin, Base):
    __tablename__ = "journal_lines"
    __table_args__ = (
        CheckConstraint("debit >= 0 AND credit >= 0", name="ck_journal_lines_non_negative"),
        CheckConstraint(
            "(debit > 0 AND credit = 0) OR (debit = 0 AND credit > 0)",
            name="ck_journal_lines_one_sided",
        ),
        UniqueConstraint("entry_id", "line_no", name="uq_journal_lines_entry_line_no"),
    )

    entry_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=False
    )
    account_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chart_accounts.id", ondelete="RESTRICT"), nullable=True
    )
    line_no: Mapped[int] = mapped_column(nullable=False)
    account_code: Mapped[str] = mapped_column(String(32), nullable=False)
    debit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00"), server_default="0", nullable=False
    )
    credit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00"), server_default="0", nullable=False
    )
    memo: Mapped[str | None] = mapped_column(String(500), nullable=True)

    entry: Mapped[JournalEntryRecord] = relationship(back_populates="lines")


@event.listens_for(JournalEntryRecord, "before_update")
@event.listens_for(JournalEntryRecord, "before_delete")
def prevent_posted_entry_mutation(_mapper, _connection, target: JournalEntryRecord) -> None:
    history = sqlalchemy_inspect(target).attrs.status.history
    previous_status = history.deleted[0] if history.deleted else (
        history.unchanged[0] if history.unchanged else None
    )
    if previous_status == "posted":
        raise ValueError("posted journal entries are immutable")


@event.listens_for(JournalLineRecord, "before_update")
@event.listens_for(JournalLineRecord, "before_delete")
def prevent_posted_line_mutation(_mapper, _connection, target: JournalLineRecord) -> None:
    raise ValueError("posted journal entries are immutable")


__all__ = ["ChartAccount", "FiscalPeriod", "JournalEntryRecord", "JournalLineRecord"]
