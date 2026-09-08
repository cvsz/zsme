from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import IdentifiedTimestampMixin, OrganizationScopeMixin


class ChartAccount(IdentifiedTimestampMixin, OrganizationScopeMixin, Base):
    __tablename__ = "chart_accounts"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_chart_accounts_org_code"),
    )

    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    account_type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


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


class JournalEntryRecord(IdentifiedTimestampMixin, OrganizationScopeMixin, Base):
    __tablename__ = "journal_entries"
    __table_args__ = (
        UniqueConstraint("organization_id", "reference", name="uq_journal_entries_org_reference"),
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_journal_entries_org_idempotency"
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


__all__ = ["ChartAccount", "FiscalPeriod", "JournalEntryRecord", "JournalLineRecord"]
