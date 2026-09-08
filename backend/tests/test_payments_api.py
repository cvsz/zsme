from decimal import Decimal
from uuid import UUID

from app.db.models import AuditEvent, BusinessPartner, JournalEntryRecord


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


def _partner(db_session, seeded_user, partner_type: str, code: str) -> BusinessPartner:
    partner = BusinessPartner(
        tenant_id=seeded_user.tenant_id,
        organization_id=seeded_user.organization_id,
        partner_code=code,
        partner_type=partner_type,
        display_name=f"{partner_type} for payment tests",
    )
    db_session.add(partner)
    db_session.commit()
    return partner


def _invoice(client, headers: dict[str, str], partner_id: UUID, number: str) -> dict[str, object]:
    created = client.post(
        "/v1/ar/invoices",
        headers={**headers, "Idempotency-Key": f"{number}-create"},
        json={
            "document_number": number,
            "partner_id": str(partner_id),
            "issue_date": "2026-09-08",
            "due_date": "2026-10-08",
            "currency_code": "THB",
            "control_account_code": "1100",
            "tax_account_code": "2101",
            "lines": [
                {
                    "description": "Payment test service",
                    "quantity": "1.000",
                    "unit_price": "1000.00",
                    "tax_rate": "7.00",
                    "account_code": "4000",
                }
            ],
        },
    )
    assert created.status_code == 201
    posted = client.post(
        f"/v1/ar/invoices/{created.json()['id']}/post",
        headers={**headers, "Idempotency-Key": f"{number}-post"},
    )
    assert posted.status_code == 200
    return posted.json()


def _receipt_body(
    partner_id: UUID, document_id: str, amount: str, number: str
) -> dict[str, object]:
    return {
        "payment_number": number,
        "partner_id": str(partner_id),
        "payment_date": "2026-09-08",
        "currency_code": "THB",
        "amount": amount,
        "cash_account_code": "1001",
        "allocations": [{"document_id": document_id, "amount": amount}],
    }


def test_receipt_is_idempotent_posts_and_audits(
    client, db_session, seeded_user, ledger_ready
) -> None:
    partner = _partner(db_session, seeded_user, "customer", "CUS-REC-1")
    headers = _login(client)
    invoice = _invoice(client, headers, partner.id, "INV-REC-1")
    body = _receipt_body(partner.id, invoice["id"], "1070.00", "REC-0001")

    created = client.post(
        "/v1/ar/receipts",
        headers={**headers, "Idempotency-Key": "receipt-create-1"},
        json=body,
    )
    replay = client.post(
        "/v1/ar/receipts",
        headers={**headers, "Idempotency-Key": "receipt-create-1"},
        json=body,
    )
    posted = client.post(
        f"/v1/ar/receipts/{created.json()['id']}/post",
        headers={**headers, "Idempotency-Key": "receipt-post-1"},
    )

    assert created.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["id"] == created.json()["id"]
    assert posted.status_code == 200
    assert posted.json()["status"] == "posted"
    entry = db_session.get(JournalEntryRecord, UUID(posted.json()["ledger_entry_id"]))
    assert entry is not None
    assert {line.account_code for line in entry.lines} == {"1001", "1100"}
    assert sum((line.debit for line in entry.lines), Decimal("0")) == Decimal("1070.00")
    assert sum((line.credit for line in entry.lines), Decimal("0")) == Decimal("1070.00")
    assert db_session.query(AuditEvent).filter_by(action="payment.post").count() == 1


def test_partial_receipts_preserve_residual_and_reject_over_allocation(
    client, db_session, seeded_user, ledger_ready
) -> None:
    partner = _partner(db_session, seeded_user, "customer", "CUS-REC-2")
    headers = _login(client)
    invoice = _invoice(client, headers, partner.id, "INV-REC-2")

    first = client.post(
        "/v1/ar/receipts",
        headers={**headers, "Idempotency-Key": "receipt-partial-create-1"},
        json=_receipt_body(partner.id, invoice["id"], "500.00", "REC-0002"),
    )
    first_post = client.post(
        f"/v1/ar/receipts/{first.json()['id']}/post",
        headers={**headers, "Idempotency-Key": "receipt-partial-post-1"},
    )
    second = client.post(
        "/v1/ar/receipts",
        headers={**headers, "Idempotency-Key": "receipt-partial-create-2"},
        json=_receipt_body(partner.id, invoice["id"], "570.00", "REC-0003"),
    )
    second_post = client.post(
        f"/v1/ar/receipts/{second.json()['id']}/post",
        headers={**headers, "Idempotency-Key": "receipt-partial-post-2"},
    )
    over = client.post(
        "/v1/ar/receipts",
        headers={**headers, "Idempotency-Key": "receipt-partial-over"},
        json=_receipt_body(partner.id, invoice["id"], "1.00", "REC-0004"),
    )

    assert first_post.status_code == 200
    assert second_post.status_code == 200
    assert second_post.json()["status"] == "posted"
    assert over.status_code == 409
    assert "outstanding" in over.json()["detail"]


def test_vendor_disbursement_posts_payable_to_cash(
    client, db_session, seeded_user, ledger_ready
) -> None:
    partner = _partner(db_session, seeded_user, "vendor", "VEN-PAY-1")
    headers = _login(client)
    bill = client.post(
        "/v1/ap/bills",
        headers={**headers, "Idempotency-Key": "bill-payment-create"},
        json={
            "document_number": "BILL-PAY-1",
            "partner_id": str(partner.id),
            "issue_date": "2026-09-08",
            "due_date": "2026-10-08",
            "currency_code": "THB",
            "control_account_code": "2100",
            "tax_account_code": "1400",
            "lines": [
                {
                    "description": "Supplier service",
                    "quantity": "1.000",
                    "unit_price": "1000.00",
                    "tax_rate": "7.00",
                    "account_code": "5000",
                }
            ],
        },
    )
    assert bill.status_code == 201
    bill_post = client.post(
        f"/v1/ap/bills/{bill.json()['id']}/post",
        headers={**headers, "Idempotency-Key": "bill-payment-post"},
    )
    assert bill_post.status_code == 200

    disbursement = client.post(
        "/v1/ap/disbursements",
        headers={**headers, "Idempotency-Key": "disbursement-create-1"},
        json={
            "payment_number": "PAY-0001",
            "partner_id": str(partner.id),
            "payment_date": "2026-09-08",
            "currency_code": "THB",
            "amount": "1070.00",
            "cash_account_code": "1001",
            "allocations": [{"document_id": bill.json()["id"], "amount": "1070.00"}],
        },
    )
    posted = client.post(
        f"/v1/ap/disbursements/{disbursement.json()['id']}/post",
        headers={**headers, "Idempotency-Key": "disbursement-post-1"},
    )

    assert disbursement.status_code == 201
    assert posted.status_code == 200
    entry = db_session.get(JournalEntryRecord, UUID(posted.json()["ledger_entry_id"]))
    assert entry is not None
    assert {line.account_code for line in entry.lines} == {"1001", "2100"}
    assert sum((line.debit for line in entry.lines), Decimal("0")) == Decimal("1070.00")
    assert sum((line.credit for line in entry.lines), Decimal("0")) == Decimal("1070.00")


def test_payment_requires_unapplied_account_for_unallocated_amount(
    client, db_session, seeded_user, ledger_ready
) -> None:
    partner = _partner(db_session, seeded_user, "customer", "CUS-REC-3")
    headers = _login(client)
    response = client.post(
        "/v1/ar/receipts",
        headers={**headers, "Idempotency-Key": "receipt-unapplied-1"},
        json={
            "payment_number": "REC-0005",
            "partner_id": str(partner.id),
            "payment_date": "2026-09-08",
            "currency_code": "THB",
            "amount": "100.00",
            "cash_account_code": "1001",
            "allocations": [],
        },
    )

    assert response.status_code == 409
    assert "unapplied" in response.json()["detail"]
