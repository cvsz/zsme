from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
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
    from app.db.models.payments import PaymentRecord


class BankAccount(IdentifiedTimestampMixin, OrganizationScopeMixin, Base):
    """A tenant-scoped bank account mapped to one active asset ledger account."""

    __tablename__ = "bank_accounts"
    __table_args__ = (
        UniqueConstraint("organization_id", "account_code", name="uq_bank_accounts_org_code"),
    )

    account_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(200), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    ledger_account_code: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    version: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)

    import_batches: Mapped[list[BankImportBatch]] = relationship(
        back_populates="bank_account",
        cascade="save-update",
        order_by="BankImportBatch.created_at",
    )
    transactions: Mapped[list[BankTransaction]] = relationship(
        back_populates="bank_account",
        cascade="save-update",
        order_by="BankTransaction.transaction_date.desc()",
    )


class BankImportBatch(IdentifiedTimestampMixin, OrganizationScopeMixin, Base):
    """An immutable import boundary for a bank statement or provider feed."""

    __tablename__ = "bank_import_batches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('staged', 'committed', 'failed')",
            name="ck_bank_import_batches_status",
        ),
        CheckConstraint("transaction_count >= 0", name="ck_bank_import_batches_count"),
        UniqueConstraint(
            "organization_id",
            "bank_account_id",
            "batch_reference",
            name="uq_bank_import_batches_org_account_reference",
        ),
    )

    bank_account_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("bank_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    batch_reference: Mapped[str] = mapped_column(String(150), nullable=False)
    source_name: Mapped[str] = mapped_column(String(250), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="staged", server_default="staged", nullable=False
    )
    transaction_count: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    version: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)

    bank_account: Mapped[BankAccount] = relationship(back_populates="import_batches")
    transactions: Mapped[list[BankTransaction]] = relationship(
        back_populates="import_batch",
        cascade="all, delete-orphan",
        order_by="BankTransaction.transaction_date, BankTransaction.external_id",
    )


class BankTransaction(IdentifiedTimestampMixin, OrganizationScopeMixin, Base):
    """An imported bank movement; source fields are immutable after ingestion."""

    __tablename__ = "bank_transactions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('unmatched', 'reconciled')",
            name="ck_bank_transactions_status",
        ),
        CheckConstraint("amount <> 0", name="ck_bank_transactions_amount_nonzero"),
        UniqueConstraint(
            "bank_account_id",
            "external_id",
            name="uq_bank_transactions_account_external_id",
        ),
    )

    bank_account_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("bank_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    import_batch_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bank_import_batches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    external_id: Mapped[str] = mapped_column(String(150), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="unmatched", server_default="unmatched", nullable=False
    )
    matched_payment_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("payment_records.id", ondelete="RESTRICT"), nullable=True
    )
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)

    bank_account: Mapped[BankAccount] = relationship(back_populates="transactions")
    import_batch: Mapped[BankImportBatch] = relationship(back_populates="transactions")
    matched_payment: Mapped[PaymentRecord | None] = relationship("PaymentRecord")


_SOURCE_FIELDS = (
    "bank_account_id",
    "import_batch_id",
    "external_id",
    "transaction_date",
    "value_date",
    "description",
    "reference",
    "amount",
)


@event.listens_for(BankTransaction, "before_update")
def prevent_bank_transaction_source_mutation(_mapper, _connection, target: BankTransaction) -> None:
    state = sqlalchemy_inspect(target)
    if any(state.attrs[field].history.has_changes() for field in _SOURCE_FIELDS):
        raise ValueError("imported bank transaction source fields are immutable")
    status_history = state.attrs.status.history
    previous_status = status_history.deleted[0] if status_history.deleted else (
        status_history.unchanged[0] if status_history.unchanged else None
    )
    if previous_status == "reconciled":
        if target.status != "reconciled" or any(
            state.attrs[field].history.has_changes()
            for field in ("matched_payment_id", "reconciled_at")
        ):
            raise ValueError("reconciled bank transactions are immutable")
    if target.status == "unmatched" and (
        target.matched_payment_id is not None or target.reconciled_at is not None
    ):
        raise ValueError("an unmatched bank transaction cannot have a reconciliation match")
    if target.status == "reconciled" and (
        target.matched_payment_id is None or target.reconciled_at is None
    ):
        raise ValueError("a reconciled bank transaction requires a payment match and timestamp")


@event.listens_for(BankTransaction, "before_delete")
def prevent_bank_transaction_delete(_mapper, _connection, _target: BankTransaction) -> None:
    raise ValueError("imported bank transactions are immutable")


@event.listens_for(BankImportBatch, "before_delete")
def prevent_bank_import_delete(_mapper, _connection, _target: BankImportBatch) -> None:
    raise ValueError("bank import batches are immutable")


@event.listens_for(BankImportBatch, "before_update")
def prevent_committed_bank_import_mutation(_mapper, _connection, target: BankImportBatch) -> None:
    history = sqlalchemy_inspect(target).attrs.status.history
    previous_status = history.deleted[0] if history.deleted else (
        history.unchanged[0] if history.unchanged else None
    )
    if previous_status == "committed":
        raise ValueError("committed bank import batches are immutable")


__all__ = ["BankAccount", "BankImportBatch", "BankTransaction"]
