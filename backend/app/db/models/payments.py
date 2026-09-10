from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
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
    event,
)
from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import IdentifiedTimestampMixin, OrganizationScopeMixin

if TYPE_CHECKING:
    from app.db.models.documents import FinancialDocument
    from app.db.models.ledger import JournalEntryRecord
    from app.db.models.partners import BusinessPartner


class PaymentRecord(IdentifiedTimestampMixin, OrganizationScopeMixin, Base):
    __tablename__ = "payment_records"
    __table_args__ = (
        CheckConstraint(
            "payment_type IN ('receipt', 'disbursement')",
            name="ck_payment_records_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'posted', 'void')",
            name="ck_payment_records_status",
        ),
        CheckConstraint("amount > 0", name="ck_payment_records_amount"),
        UniqueConstraint(
            "organization_id",
            "payment_type",
            "payment_number",
            name="uq_payment_records_org_type_number",
        ),
    )

    payment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_number: Mapped[str] = mapped_column(String(100), nullable=False)
    partner_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("business_partners.id", ondelete="RESTRICT"), nullable=False
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    cash_account_code: Mapped[str] = mapped_column(String(32), nullable=False)
    unapplied_account_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    memo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", nullable=False
    )
    ledger_entry_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=True
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)

    partner: Mapped[BusinessPartner] = relationship("BusinessPartner")
    ledger_entry: Mapped[JournalEntryRecord | None] = relationship("JournalEntryRecord")
    allocations: Mapped[list[PaymentAllocation]] = relationship(
        back_populates="payment",
        cascade="all, delete-orphan",
        order_by="PaymentAllocation.created_at",
    )


class PaymentAllocation(IdentifiedTimestampMixin, OrganizationScopeMixin, Base):
    __tablename__ = "payment_allocations"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payment_allocations_amount"),
        UniqueConstraint(
            "payment_id", "document_id", name="uq_payment_allocations_payment_document"
        ),
    )

    payment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("payment_records.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("financial_documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    payment: Mapped[PaymentRecord] = relationship(back_populates="allocations")
    document: Mapped[FinancialDocument] = relationship("FinancialDocument")


def _status_was_posted(target: PaymentRecord) -> bool:
    history = sqlalchemy_inspect(target).attrs.status.history
    previous_status = history.deleted[0] if history.deleted else (
        history.unchanged[0] if history.unchanged else None
    )
    return previous_status == "posted"


@event.listens_for(PaymentRecord, "before_update")
def prevent_posted_payment_mutation(_mapper, _connection, target: PaymentRecord) -> None:
    if _status_was_posted(target):
        raise ValueError("posted payments are immutable")


@event.listens_for(PaymentRecord, "before_delete")
def prevent_posted_payment_delete(_mapper, _connection, target: PaymentRecord) -> None:
    if _status_was_posted(target):
        raise ValueError("posted payments are immutable")


@event.listens_for(PaymentAllocation, "before_update")
@event.listens_for(PaymentAllocation, "before_delete")
def prevent_posted_payment_allocation_mutation(
    _mapper, _connection, target: PaymentAllocation
) -> None:
    if target.payment is not None and target.payment.status == "posted":
        raise ValueError("posted payments are immutable")


__all__ = ["PaymentAllocation", "PaymentRecord"]
