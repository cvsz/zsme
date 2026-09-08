from decimal import Decimal
from uuid import UUID

import pytest

from app.db.models import AuditEvent, BankTransaction, BusinessPartner


def _login(client) -> dict[str, str]:
    response = client.post(
        "/v1/auth/login",
        json={
            "tenant_slug": "demo",
            "email": "admin@example.com",
            "password": "correct horse battery staple",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _partner(db_session, seeded_user) -> BusinessPartner:
    partner = BusinessPartner(
        tenant_id=seeded_user.tenant_id,
        organization_id=seeded_user.organization_id,
        partner_code="CUS-BANK-1",
        partner_type="customer",
        display_name="Bank reconciliation customer",
    )
    db_session.add(partner)
    db_session.commit()
    return partner


def test_bank_account_import_is_idempotent_and_scoped(
    client, db_session, seeded_user, ledger_ready
) -> None:
    headers = _login(client)
    account = client.post(
        "/v1/banking/accounts",
        headers={**headers, "Idempotency-Key": "bank-account-1"},
        json={
            "account_code": "BANK-001",
            "name": "Operating bank",
            "bank_name": "Demo Bank",
            "currency_code": "THB",
            "ledger_account_code": "1001",
        },
    )
    assert account.status_code == 201
    import_body = {
        "batch_reference": "STATEMENT-2026-09",
        "source_name": "bank-september.csv",
        "transactions": [
            {
                "external_id": "TX-001",
                "transaction_date": "2026-09-08",
                "description": "Customer transfer",
                "reference": "INV-001",
                "amount": "1070.00",
            }
        ],
    }
    first = client.post(
        f"/v1/banking/accounts/{account.json()['id']}/imports",
        headers={**headers, "Idempotency-Key": "bank-import-1"},
        json=import_body,
    )
    replay = client.post(
        f"/v1/banking/accounts/{account.json()['id']}/imports",
        headers={**headers, "Idempotency-Key": "bank-import-1"},
        json=import_body,
    )

    assert first.status_code == 201
    assert first.json()["transaction_count"] == 1
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert db_session.query(BankTransaction).count() == 1


def test_bank_import_rejects_duplicate_external_transaction(
    client, seeded_user, ledger_ready
) -> None:
    headers = _login(client)
    account = client.post(
        "/v1/banking/accounts",
        headers={**headers, "Idempotency-Key": "bank-account-2"},
        json={
            "account_code": "BANK-002",
            "name": "Savings bank",
            "bank_name": "Demo Bank",
            "currency_code": "THB",
            "ledger_account_code": "1001",
        },
    )
    body = {
        "batch_reference": "STATEMENT-DUP",
        "source_name": "duplicate.csv",
        "transactions": [
            {
                "external_id": "TX-DUP",
                "transaction_date": "2026-09-08",
                "description": "Duplicate",
                "amount": "10.00",
            },
            {
                "external_id": "TX-DUP",
                "transaction_date": "2026-09-08",
                "description": "Duplicate again",
                "amount": "10.00",
            },
        ],
    }
    response = client.post(
        f"/v1/banking/accounts/{account.json()['id']}/imports",
        headers={**headers, "Idempotency-Key": "bank-import-dup"},
        json=body,
    )

    assert account.status_code == 201
    assert response.status_code == 409
    assert "external_id" in response.json()["detail"]


def test_bank_transaction_reconcile_matches_posted_receipt(
    client, db_session, seeded_user, ledger_ready
) -> None:
    partner = _partner(db_session, seeded_user)
    headers = _login(client)
    invoice = client.post(
        "/v1/ar/invoices",
        headers={**headers, "Idempotency-Key": "bank-invoice-create"},
        json={
            "document_number": "INV-BANK-1",
            "partner_id": str(partner.id),
            "issue_date": "2026-09-08",
            "due_date": "2026-09-08",
            "currency_code": "THB",
            "control_account_code": "1100",
            "tax_account_code": "2101",
            "lines": [
                {
                    "description": "Bank test service",
                    "quantity": "1.000",
                    "unit_price": "1000.00",
                    "tax_rate": "7.00",
                    "account_code": "4000",
                }
            ],
        },
    )
    posted_invoice = client.post(
        f"/v1/ar/invoices/{invoice.json()['id']}/post",
        headers={**headers, "Idempotency-Key": "bank-invoice-post"},
    )
    receipt = client.post(
        "/v1/ar/receipts",
        headers={**headers, "Idempotency-Key": "bank-receipt-create"},
        json={
            "payment_number": "REC-BANK-1",
            "partner_id": str(partner.id),
            "payment_date": "2026-09-08",
            "currency_code": "THB",
            "amount": "1070.00",
            "cash_account_code": "1001",
            "allocations": [{"document_id": invoice.json()["id"], "amount": "1070.00"}],
        },
    )
    posted_receipt = client.post(
        f"/v1/ar/receipts/{receipt.json()['id']}/post",
        headers={**headers, "Idempotency-Key": "bank-receipt-post"},
    )
    account = client.post(
        "/v1/banking/accounts",
        headers={**headers, "Idempotency-Key": "bank-account-3"},
        json={
            "account_code": "BANK-003",
            "name": "Reconciliation bank",
            "bank_name": "Demo Bank",
            "currency_code": "THB",
            "ledger_account_code": "1001",
        },
    )
    imported = client.post(
        f"/v1/banking/accounts/{account.json()['id']}/imports",
        headers={**headers, "Idempotency-Key": "bank-import-reconcile"},
        json={
            "batch_reference": "STATEMENT-MATCH",
            "source_name": "match.csv",
            "transactions": [
                {
                    "external_id": "TX-MATCH",
                    "transaction_date": "2026-09-08",
                    "description": "Matched receipt",
                    "amount": "1070.00",
                }
            ],
        },
    )
    transaction_id = imported.json()["transactions"][0]["id"]
    reconciled = client.post(
        f"/v1/banking/transactions/{transaction_id}/reconcile",
        headers={**headers, "Idempotency-Key": "bank-reconcile-1"},
        json={"payment_id": posted_receipt.json()["id"]},
    )

    assert posted_invoice.status_code == 200
    assert posted_receipt.status_code == 200
    assert reconciled.status_code == 200
    assert reconciled.json()["status"] == "reconciled"
    assert reconciled.json()["matched_payment_id"] == posted_receipt.json()["id"]

    replay = client.post(
        f"/v1/banking/transactions/{transaction_id}/reconcile",
        headers={**headers, "Idempotency-Key": "bank-reconcile-1"},
        json={"payment_id": posted_receipt.json()["id"]},
    )

    assert replay.status_code == 200
    assert replay.json()["id"] == reconciled.json()["id"]
    assert db_session.query(AuditEvent).filter_by(action="bank.reconcile").count() == 1


def test_imported_bank_source_fields_are_immutable(
    client, db_session, seeded_user, ledger_ready
) -> None:
    headers = _login(client)
    account = client.post(
        "/v1/banking/accounts",
        headers={**headers, "Idempotency-Key": "bank-account-immutable"},
        json={
            "account_code": "BANK-IMMUTABLE",
            "name": "Immutable bank",
            "bank_name": "Demo Bank",
            "currency_code": "THB",
            "ledger_account_code": "1001",
        },
    )
    imported = client.post(
        f"/v1/banking/accounts/{account.json()['id']}/imports",
        headers={**headers, "Idempotency-Key": "bank-import-immutable"},
        json={
            "batch_reference": "STATEMENT-IMMUTABLE",
            "source_name": "immutable.csv",
            "transactions": [
                {
                    "external_id": "TX-IMMUTABLE",
                    "transaction_date": "2026-09-08",
                    "description": "Source record",
                    "amount": "100.00",
                }
            ],
        },
    )
    transaction = db_session.get(
        BankTransaction, UUID(imported.json()["transactions"][0]["id"])
    )
    assert transaction is not None

    transaction.amount = Decimal("101.00")
    with pytest.raises(ValueError, match="source fields are immutable"):
        db_session.flush()
    db_session.rollback()
