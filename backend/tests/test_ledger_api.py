from fastapi.testclient import TestClient


def _login(client: TestClient, seeded_user) -> str:
    response = client.post(
        "/v1/auth/login",
        json={
            "tenant_slug": seeded_user.tenant.slug,
            "email": seeded_user.email,
            "password": "correct horse battery staple",
        },
    )
    return response.json()["access_token"]


def _journal_body() -> dict[str, object]:
    return {
        "reference": "AR-202609-0002",
        "memo": "API invoice",
        "journal_date": "2026-09-08",
        "source_type": "invoice",
        "lines": [
            {"account_code": "1100", "debit": "1070.00"},
            {"account_code": "4000", "credit": "1000.00"},
            {"account_code": "2101", "credit": "70.00"},
        ],
    }


def test_posting_requires_idempotency_key(
    client: TestClient, seeded_user, ledger_ready
) -> None:
    response = client.post(
        "/v1/accounting/journal-entries",
        headers={"Authorization": f"Bearer {_login(client, seeded_user)}"},
        json=_journal_body(),
    )

    assert response.status_code == 422


def test_posting_replay_returns_same_resource_without_duplication(
    client: TestClient, seeded_user, ledger_ready
) -> None:
    headers = {
        "Authorization": f"Bearer {_login(client, seeded_user)}",
        "Idempotency-Key": "api-post-001",
    }

    first = client.post("/v1/accounting/journal-entries", headers=headers, json=_journal_body())
    second = client.post("/v1/accounting/journal-entries", headers=headers, json=_journal_body())

    assert first.status_code == 201
    assert first.json()["status"] == "posted"
    assert second.status_code == 200
    assert second.json()["status"] == "already_posted"
    assert second.json()["entry_id"] == first.json()["entry_id"]

