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
    from app.db.models.ledger import JournalEntryRecord
    from app.db.models.partners import BusinessPartner


class FinancialDocument(IdentifiedTimestampMixin, OrganizationScopeMixin, Base):
    """A tenant-scoped commercial document whose posted state is ledger-backed."""

    __tablename__ = "financial_documents"
    __table_args__ = (
        CheckConstraint(
            "document_type IN ('sales_invoice', 'vendor_bill')",
            name="ck_financial_documents_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'posted', 'void')",
            name="ck_financial_documents_status",
        ),
        CheckConstraint("issue_date <= due_date", name="ck_financial_documents_dates"),
        CheckConstraint(
            "subtotal >= 0 AND tax_total >= 0 AND total >= 0",
            name="ck_financial_documents_totals_non_negative",
        ),
        UniqueConstraint(
            "organization_id",
            "document_type",
            "document_number",
            name="uq_financial_documents_org_type_number",
        ),
    )

    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    document_number: Mapped[str] = mapped_column(String(100), nullable=False)
    partner_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("business_partners.id", ondelete="RESTRICT"), nullable=False
    )
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    control_account_code: Mapped[str] = mapped_column(String(32), nullable=False)
    tax_account_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    memo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00"), server_default="0", nullable=False
    )
    tax_total: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00"), server_default="0", nullable=False
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00"), server_default="0", nullable=False
    )
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
    lines: Mapped[list[FinancialDocumentLine]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="FinancialDocumentLine.line_no",
    )


class FinancialDocumentLine(IdentifiedTimestampMixin, OrganizationScopeMixin, Base):
    __tablename__ = "financial_document_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_financial_document_lines_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_financial_document_lines_unit_price"),
        CheckConstraint(
            "tax_rate >= 0 AND tax_rate <= 100", name="ck_financial_document_lines_tax_rate"
        ),
        CheckConstraint(
            "net_amount >= 0 AND tax_amount >= 0 AND total_amount >= 0",
            name="ck_financial_document_lines_amounts_non_negative",
        ),
        UniqueConstraint(
            "document_id", "line_no", name="uq_financial_document_lines_document_line_no"
        ),
    )

    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("financial_documents.id", ondelete="CASCADE"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    account_code: Mapped[str] = mapped_column(String(32), nullable=False)

    document: Mapped[FinancialDocument] = relationship(back_populates="lines")


def _status_was_posted(target: FinancialDocument) -> bool:
    history = sqlalchemy_inspect(target).attrs.status.history
    previous_status = history.deleted[0] if history.deleted else (
        history.unchanged[0] if history.unchanged else None
    )
    return previous_status == "posted"


@event.listens_for(FinancialDocument, "before_update")
def prevent_posted_document_mutation(_mapper, _connection, target: FinancialDocument) -> None:
    if _status_was_posted(target):
        raise ValueError("posted financial documents are immutable")


@event.listens_for(FinancialDocument, "before_delete")
def prevent_posted_document_delete(_mapper, _connection, target: FinancialDocument) -> None:
    if _status_was_posted(target):
        raise ValueError("posted financial documents are immutable")


@event.listens_for(FinancialDocumentLine, "before_update")
@event.listens_for(FinancialDocumentLine, "before_delete")
def prevent_posted_document_line_mutation(
    _mapper, _connection, target: FinancialDocumentLine
) -> None:
    if target.document is not None and target.document.status == "posted":
        raise ValueError("posted financial documents are immutable")


__all__ = ["FinancialDocument", "FinancialDocumentLine"]
