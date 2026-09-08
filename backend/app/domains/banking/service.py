from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.auth import Principal
from app.db.models import (
    AuditEvent,
    BankAccount,
    BankImportBatch,
    BankTransaction,
    ChartAccount,
    IdempotencyRecord,
    PaymentRecord,
)
from app.domains.banking.schemas import BankAccountCreate, BankImportCreate, BankTransactionStatus

MONEY = Decimal("0.01")


class BankingDomainError(Exception):
    """A safe, expected banking-domain failure."""


@dataclass(frozen=True)
class BankAccountMutationResult:
    account: BankAccount
    replayed: bool = False


@dataclass(frozen=True)
class BankImportMutationResult:
    batch: BankImportBatch
    replayed: bool = False


@dataclass(frozen=True)
class BankTransactionMutationResult:
    transaction: BankTransaction
    replayed: bool = False


def _hash(payload: object) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(serialized.encode("utf-8")).hexdigest()


def _key(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 200:
        raise BankingDomainError("a valid idempotency key is required")
    return normalized


def _org(principal: Principal) -> UUID:
    if principal.organization_id is None:
        raise BankingDomainError("an organization is required for banking operations")
    return principal.organization_id


def _record(db: Session, principal: Principal, key: str) -> IdempotencyRecord | None:
    return db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == principal.tenant_id,
            IdempotencyRecord.organization_id == principal.organization_id,
            IdempotencyRecord.key == key,
        )
    )


def _account_query(principal: Principal):
    return select(BankAccount).where(
        BankAccount.tenant_id == principal.tenant_id,
        BankAccount.organization_id == principal.organization_id,
    )


def _get_account(db: Session, principal: Principal, account_id: UUID) -> BankAccount:
    _org(principal)
    account = db.scalar(_account_query(principal).where(BankAccount.id == account_id))
    if account is None:
        raise BankingDomainError("bank account not found")
    return account


def _batch_query(principal: Principal):
    return (
        select(BankImportBatch)
        .options(selectinload(BankImportBatch.transactions))
        .where(
            BankImportBatch.tenant_id == principal.tenant_id,
            BankImportBatch.organization_id == principal.organization_id,
        )
    )


def _get_batch(db: Session, principal: Principal, batch_id: UUID) -> BankImportBatch:
    _org(principal)
    batch = db.scalar(_batch_query(principal).where(BankImportBatch.id == batch_id))
    if batch is None:
        raise BankingDomainError("bank import batch not found")
    return batch


def _get_transaction(db: Session, principal: Principal, transaction_id: UUID) -> BankTransaction:
    _org(principal)
    transaction = db.scalar(
        select(BankTransaction)
        .options(selectinload(BankTransaction.bank_account))
        .where(
            BankTransaction.id == transaction_id,
            BankTransaction.tenant_id == principal.tenant_id,
            BankTransaction.organization_id == principal.organization_id,
        )
    )
    if transaction is None:
        raise BankingDomainError("bank transaction not found")
    return transaction


def _audit(
    db: Session,
    principal: Principal,
    entity_type: str,
    entity_id: UUID,
    action: str,
    payload: dict[str, object],
) -> AuditEvent:
    audit = AuditEvent(
        tenant_id=principal.tenant_id,
        organization_id=principal.organization_id,
        actor_user_id=principal.user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        correlation_id=str(uuid4()),
        payload=payload,
    )
    db.add(audit)
    db.flush()
    return audit


def _store(
    db: Session,
    principal: Principal,
    key: str,
    operation: str,
    request_hash: str,
    resource_id: UUID,
    response_status: int,
    resource_key: str,
) -> None:
    db.add(
        IdempotencyRecord(
            tenant_id=principal.tenant_id,
            organization_id=principal.organization_id,
            key=key,
            operation=operation,
            request_hash=request_hash,
            response_status=response_status,
            response_body={resource_key: str(resource_id)},
            resource_id=resource_id,
        )
    )
    db.flush()


def list_accounts(
    db: Session, principal: Principal, include_inactive: bool = False
) -> list[BankAccount]:
    statement = _account_query(principal)
    if not include_inactive:
        statement = statement.where(BankAccount.is_active.is_(True))
    return list(db.scalars(statement.order_by(BankAccount.account_code)).all())


def get_account(db: Session, principal: Principal, account_id: UUID) -> BankAccount:
    return _get_account(db, principal, account_id)


def create_account(
    db: Session,
    payload: BankAccountCreate,
    principal: Principal,
    idempotency_key: str,
) -> BankAccountMutationResult:
    organization_id = _org(principal)
    key = _key(idempotency_key)
    request_hash = _hash(
        {"operation": "bank_account.create", "payload": payload.model_dump(mode="json")}
    )
    existing = _record(db, principal, key)
    if existing is not None:
        if existing.operation != "bank_account.create" or existing.request_hash != request_hash:
            raise BankingDomainError("idempotency key was reused with a different request")
        if existing.resource_id is None:
            raise BankingDomainError("idempotency record has no bank account resource")
        return BankAccountMutationResult(
            _get_account(db, principal, existing.resource_id), replayed=True
        )

    ledger_code = payload.ledger_account_code.strip().upper()
    ledger_account = db.scalar(
        select(ChartAccount).where(
            ChartAccount.tenant_id == principal.tenant_id,
            ChartAccount.organization_id == organization_id,
            ChartAccount.code == ledger_code,
        )
    )
    if ledger_account is None:
        raise BankingDomainError("bank ledger account not found")
    if not ledger_account.is_active or ledger_account.account_type != "asset":
        raise BankingDomainError("bank ledger account must be an active asset account")
    if ledger_account.is_control:
        raise BankingDomainError("bank ledger account cannot be a control account")

    account_code = payload.account_code.strip().upper()
    if db.scalar(
        select(BankAccount.id).where(
            BankAccount.organization_id == organization_id,
            BankAccount.account_code == account_code,
        )
    ):
        raise BankingDomainError("bank account code already exists in this organization")

    account = BankAccount(
        tenant_id=principal.tenant_id,
        organization_id=organization_id,
        account_code=account_code,
        name=payload.name.strip(),
        bank_name=payload.bank_name.strip(),
        currency_code=payload.currency_code.upper(),
        ledger_account_code=ledger_code,
        is_active=True,
    )
    db.add(account)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise BankingDomainError("bank account code already exists in this organization") from error
    _audit(
        db,
        principal,
        "bank_account",
        account.id,
        "bank_account.create",
        {"account_code": account.account_code, "ledger_account_code": account.ledger_account_code},
    )
    _store(
        db,
        principal,
        key,
        "bank_account.create",
        request_hash,
        account.id,
        201,
        "bank_account_id",
    )
    return BankAccountMutationResult(account)


def import_transactions(
    db: Session,
    account_id: UUID,
    payload: BankImportCreate,
    principal: Principal,
    idempotency_key: str,
) -> BankImportMutationResult:
    organization_id = _org(principal)
    account = _get_account(db, principal, account_id)
    if not account.is_active:
        raise BankingDomainError("bank account is archived")
    key = _key(idempotency_key)
    request_hash = _hash(
        {
            "operation": "bank.import",
            "account_id": str(account_id),
            "payload": payload.model_dump(mode="json"),
        }
    )
    existing = _record(db, principal, key)
    if existing is not None:
        if existing.operation != "bank.import" or existing.request_hash != request_hash:
            raise BankingDomainError("idempotency key was reused with a different request")
        if existing.resource_id is None:
            raise BankingDomainError("idempotency record has no bank import resource")
        return BankImportMutationResult(
            _get_batch(db, principal, existing.resource_id), replayed=True
        )

    normalized_ids = [item.external_id.strip() for item in payload.transactions]
    if len(set(normalized_ids)) != len(normalized_ids):
        raise BankingDomainError("external_id must be unique within an import batch")
    existing_transaction = db.scalar(
        select(BankTransaction.id).where(
            BankTransaction.tenant_id == principal.tenant_id,
            BankTransaction.organization_id == organization_id,
            BankTransaction.bank_account_id == account.id,
            BankTransaction.external_id.in_(normalized_ids),
        )
    )
    if existing_transaction is not None:
        raise BankingDomainError("external_id already exists for this bank account")

    batch = BankImportBatch(
        tenant_id=principal.tenant_id,
        organization_id=organization_id,
        bank_account_id=account.id,
        batch_reference=payload.batch_reference.strip(),
        source_name=payload.source_name.strip(),
        status="committed",
        transaction_count=len(payload.transactions),
        transactions=[
            BankTransaction(
                tenant_id=principal.tenant_id,
                organization_id=organization_id,
                bank_account_id=account.id,
                external_id=external_id,
                transaction_date=item.transaction_date,
                value_date=item.value_date,
                description=item.description.strip(),
                reference=item.reference,
                amount=item.amount,
                status="unmatched",
            )
            for item, external_id in zip(payload.transactions, normalized_ids, strict=True)
        ],
    )
    db.add(batch)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise BankingDomainError("bank import batch or external_id already exists") from error
    _audit(
        db,
        principal,
        "bank_import_batch",
        batch.id,
        "bank.import",
        {
            "bank_account_id": str(account.id),
            "batch_reference": batch.batch_reference,
            "transaction_count": batch.transaction_count,
        },
    )
    _store(
        db,
        principal,
        key,
        "bank.import",
        request_hash,
        batch.id,
        201,
        "bank_import_id",
    )
    return BankImportMutationResult(batch)


def list_transactions(
    db: Session,
    principal: Principal,
    account_id: UUID | None = None,
    transaction_status: BankTransactionStatus | None = None,
) -> list[BankTransaction]:
    if account_id is not None:
        _get_account(db, principal, account_id)
    statement = select(BankTransaction).where(
        BankTransaction.tenant_id == principal.tenant_id,
        BankTransaction.organization_id == principal.organization_id,
    )
    if account_id is not None:
        statement = statement.where(BankTransaction.bank_account_id == account_id)
    if transaction_status is not None:
        statement = statement.where(BankTransaction.status == transaction_status)
    return list(
        db.scalars(
            statement.order_by(BankTransaction.transaction_date.desc(), BankTransaction.external_id)
        ).all()
    )


def get_transaction(db: Session, principal: Principal, transaction_id: UUID) -> BankTransaction:
    return _get_transaction(db, principal, transaction_id)


def reconcile_transaction(
    db: Session,
    transaction_id: UUID,
    payment_id: UUID,
    principal: Principal,
    idempotency_key: str,
) -> BankTransactionMutationResult:
    organization_id = _org(principal)
    key = _key(idempotency_key)
    request_hash = _hash(
        {
            "operation": "bank.reconcile",
            "transaction_id": str(transaction_id),
            "payment_id": str(payment_id),
        }
    )
    existing = _record(db, principal, key)
    if existing is not None:
        if existing.operation != "bank.reconcile" or existing.request_hash != request_hash:
            raise BankingDomainError("idempotency key was reused with a different request")
        if existing.resource_id is None:
            raise BankingDomainError("idempotency record has no bank transaction resource")
        return BankTransactionMutationResult(
            _get_transaction(db, principal, existing.resource_id), replayed=True
        )

    transaction = _get_transaction(db, principal, transaction_id)
    if transaction.status != "unmatched":
        raise BankingDomainError("bank transaction is already reconciled")
    payment = db.scalar(
        select(PaymentRecord).where(
            PaymentRecord.id == payment_id,
            PaymentRecord.tenant_id == principal.tenant_id,
            PaymentRecord.organization_id == organization_id,
        )
    )
    if payment is None or payment.status != "posted":
        raise BankingDomainError("only a posted payment in this organization can be reconciled")

    expected_type = "receipt" if transaction.amount > 0 else "disbursement"
    if payment.payment_type != expected_type:
        raise BankingDomainError("bank transaction direction does not match payment type")
    if payment.currency_code != transaction.bank_account.currency_code:
        raise BankingDomainError("bank transaction and payment currencies must match")
    if payment.cash_account_code != transaction.bank_account.ledger_account_code:
        raise BankingDomainError("payment cash account does not match the bank ledger account")
    if payment.amount.quantize(MONEY) != abs(transaction.amount).quantize(MONEY):
        raise BankingDomainError("bank transaction amount does not match payment amount")

    transaction.status = "reconciled"
    transaction.matched_payment_id = payment.id
    transaction.reconciled_at = datetime.now(UTC)
    transaction.version += 1
    db.flush()
    _audit(
        db,
        principal,
        "bank_transaction",
        transaction.id,
        "bank.reconcile",
        {
            "payment_id": str(payment.id),
            "amount": str(transaction.amount),
            "transaction_date": transaction.transaction_date.isoformat(),
        },
    )
    _store(
        db,
        principal,
        key,
        "bank.reconcile",
        request_hash,
        transaction.id,
        200,
        "bank_transaction_id",
    )
    return BankTransactionMutationResult(transaction)


__all__ = [
    "BankAccountMutationResult",
    "BankImportMutationResult",
    "BankTransactionMutationResult",
    "BankingDomainError",
    "create_account",
    "get_account",
    "get_transaction",
    "import_transactions",
    "list_accounts",
    "list_transactions",
    "reconcile_transaction",
]
