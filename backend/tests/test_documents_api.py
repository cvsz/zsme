from decimal import Decimal
from uuid import UUID

from app.db.models import AuditEvent, BusinessPartner, FinancialDocument, JournalEntryRecord


def _login(client, tenant_slug: str = "demo", email: str = "admin@example.com") -> dict[str, str]:
    response = client.post(
        "/v1/auth/login",
        json={
            "tenant_slug": tenant_slug,
            "email": email,
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
        display_name=f"{partner_type} for document tests",
    )
    db_session.add(partner)
    db_session.commit()
    return partner


def _invoice_body(partner_id: UUID, number: str = "INV-0001") -> dict[str, object]:
    return {
        "document_number": number,
        "partner_id": str(partner_id),
        "issue_date": "2026-09-08",
        "due_date": "2026-10-08",
        "currency_code": "THB",
        "control_account_code": "1100",
        "tax_account_code": "2101",
        "lines": [
            {
                "description": "Implementation service",
                "quantity": "1.000",
                "unit_price": "1000.00",
                "tax_rate": "7.00",
                "account_code": "4000",
            }
        ],
    }


def _bill_body(partner_id: UUID) -> dict[str, object]:
    return {
        "document_number": "BILL-0001",
        "partner_id": str(partner_id),
        "issue_date": "2026-09-08",
        "due_date": "2026-10-08",
        "currency_code": "THB",
        "control_account_code": "2100",
        "tax_account_code": "1400",
        "lines": [
            {
                "description": "Office supplies",
                "quantity": "2.000",
                "unit_price": "500.00",
                "tax_rate": "7.00",
                "account_code": "5000",
            }
        ],
    }


def test_sales_invoice_create_replay_and_post_is_audited(
    client, db_session, seeded_user, ledger_ready
) -> None:
    partner = _partner(db_session, seeded_user, "customer", "CUS-INV-1")
    headers = _login(client)
    body = _invoice_body(partner.id)

    created = client.post(
        "/v1/ar/invoices",
        headers={**headers, "Idempotency-Key": "invoice-create-1"},
        json=body,
    )
    replay = client.post(
        "/v1/ar/invoices",
        headers={**headers, "Idempotency-Key": "invoice-create-1"},
        json=body,
    )

    assert created.status_code == 201
    assert created.json()["status"] == "draft"
    assert created.json()["subtotal"] == "1000.00"
    assert created.json()["tax_total"] == "70.00"
    assert created.json()["total"] == "1070.00"
    assert replay.status_code == 200
    assert replay.json()["id"] == created.json()["id"]

    posted = client.post(
        f"/v1/ar/invoices/{created.json()['id']}/post",
        headers={**headers, "Idempotency-Key": "invoice-post-1"},
    )

    assert posted.status_code == 200
    assert posted.json()["status"] == "posted"
    assert posted.json()["ledger_entry_id"]
    entry = db_session.get(JournalEntryRecord, UUID(posted.json()["ledger_entry_id"]))
    assert entry is not None
    assert sum((line.debit for line in entry.lines), Decimal("0")) == Decimal("1070.00")
    assert sum((line.credit for line in entry.lines), Decimal("0")) == Decimal("1070.00")
    assert db_session.query(AuditEvent).filter_by(action="document.post").count() == 1


def test_vendor_bill_posts_expense_input_vat_and_payable(
    client, db_session, seeded_user, ledger_ready
) -> None:
    partner = _partner(db_session, seeded_user, "vendor", "VEN-BILL-1")
    headers = _login(client)
    created = client.post(
        "/v1/ap/bills",
        headers={**headers, "Idempotency-Key": "bill-create-1"},
        json=_bill_body(partner.id),
    )
    assert created.status_code == 201

    posted = client.post(
        f"/v1/ap/bills/{created.json()['id']}/post",
        headers={**headers, "Idempotency-Key": "bill-post-1"},
    )

    assert posted.status_code == 200
    assert posted.json()["status"] == "posted"
    entry = db_session.get(JournalEntryRecord, UUID(posted.json()["ledger_entry_id"]))
    assert entry is not None
    assert {line.account_code for line in entry.lines} == {"5000", "1400", "2100"}
    assert sum((line.debit for line in entry.lines), Decimal("0")) == Decimal("1070.00")
    assert sum((line.credit for line in entry.lines), Decimal("0")) == Decimal("1070.00")


def test_document_requires_compatible_partner_and_idempotency_key(
    client, db_session, seeded_user, ledger_ready
) -> None:
    vendor = _partner(db_session, seeded_user, "vendor", "VEN-INV-1")
    headers = _login(client)
    missing_key = client.post(
        "/v1/ar/invoices", headers=headers, json=_invoice_body(vendor.id, "INV-0002")
    )
    incompatible = client.post(
        "/v1/ar/invoices",
        headers={**headers, "Idempotency-Key": "invoice-invalid-1"},
        json=_invoice_body(vendor.id, "INV-0002"),
    )

    assert missing_key.status_code == 422
    assert missing_key.json()["code"] == "validation_error"
    assert incompatible.status_code == 409
    assert incompatible.json()["code"] == "conflict"
    assert "customer" in incompatible.json()["detail"]


def test_posted_document_is_immutable(client, db_session, seeded_user, ledger_ready) -> None:
    partner = _partner(db_session, seeded_user, "customer", "CUS-IMM-1")
    headers = _login(client)
    created = client.post(
        "/v1/ar/invoices",
        headers={**headers, "Idempotency-Key": "invoice-immutable-create"},
        json=_invoice_body(partner.id, "INV-IMM-1"),
    )
    posted = client.post(
        f"/v1/ar/invoices/{created.json()['id']}/post",
        headers={**headers, "Idempotency-Key": "invoice-immutable-post"},
    )
    assert posted.status_code == 200

    document = db_session.get(FinancialDocument, UUID(posted.json()["id"]))
    assert document is not None
    document.memo = "attempted mutation"
    try:
        db_session.flush()
    except ValueError as error:
        db_session.rollback()
        assert "immutable" in str(error)
    else:
        raise AssertionError("posted document was mutable")


def test_document_rejects_foreign_currency_and_ineffective_vat_rate(
    client, db_session, seeded_user, ledger_ready
) -> None:
    partner = _partner(db_session, seeded_user, "customer", "CUS-CURRENCY-1")
    headers = _login(client)

    foreign = _invoice_body(partner.id, "INV-USD-1")
    foreign["currency_code"] = "USD"
    foreign_response = client.post(
        "/v1/ar/invoices",
        headers={**headers, "Idempotency-Key": "invoice-usd-reject"},
        json=foreign,
    )

    invalid_vat = _invoice_body(partner.id, "INV-VAT-INVALID")
    invalid_vat["lines"][0]["tax_rate"] = "8.00"
    vat_response = client.post(
        "/v1/ar/invoices",
        headers={**headers, "Idempotency-Key": "invoice-vat-reject"},
        json=invalid_vat,
    )

    assert foreign_response.status_code == 409
    assert "foreign-currency" in foreign_response.json()["detail"]
    assert vat_response.status_code == 409
    assert "VAT rate" in vat_response.json()["detail"]
