from fastapi.testclient import TestClient

from app.db.models import BankAccount


def _login(client: TestClient, seeded_user) -> str:
    response = client.post(
        "/v1/auth/login",
        json={
            "tenant_slug": seeded_user.tenant.slug,
            "email": seeded_user.email,
            "password": "correct horse battery staple",
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_dashboard_summary_is_organization_scoped_and_ledger_derived(
    client: TestClient, db_session, seeded_user, ledger_ready
) -> None:
    db_session.add(
        BankAccount(
            tenant_id=seeded_user.tenant_id,
            organization_id=seeded_user.organization_id,
            account_code="BANK-001",
            name="Operating account",
            bank_name="Demo Bank",
            currency_code="THB",
            ledger_account_code="1001",
        )
    )
    db_session.commit()
    headers = {
        "Authorization": f"Bearer {_login(client, seeded_user)}",
        "Idempotency-Key": "dashboard-post-001",
    }
    posting = client.post(
        "/v1/accounting/journal-entries",
        headers=headers,
        json={
            "reference": "DASH-001",
            "journal_date": "2026-09-08",
            "source_type": "manual",
            "lines": [
                {"account_code": "1001", "debit": "1070.00"},
                {"account_code": "4000", "credit": "1070.00"},
            ],
        },
    )
    assert posting.status_code == 201

    response = client.get(
        "/v1/dashboard/summary?as_of=2026-09-08",
        headers={"Authorization": headers["Authorization"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["organization_id"] == str(seeded_user.organization_id)
    assert body["currency_code"] == "THB"
    assert body["cash_position"] == "1070.00"
    assert body["receivables"] == "0.00"
    assert body["payables"] == "0.00"
    assert body["unmatched_bank_transactions"] == 0
    assert body["recent_activity"][0]["action"] == "journal.post"


def test_dashboard_summary_rejects_invalid_as_of_value(client: TestClient, seeded_user) -> None:
    response = client.get(
        "/v1/dashboard/summary?as_of=not-a-date",
        headers={"Authorization": f"Bearer {_login(client, seeded_user)}"},
    )

    assert response.status_code == 422
