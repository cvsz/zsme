from datetime import date

from fastapi.testclient import TestClient

from app.db.models import FiscalPeriod, JournalEntryRecord


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


def test_journal_list_returns_organization_scoped_lines_and_totals(
    client: TestClient, seeded_user, ledger_ready
) -> None:
    headers = {
        "Authorization": f"Bearer {_login(client, seeded_user)}",
        "Idempotency-Key": "api-list-001",
    }
    posted = client.post("/v1/accounting/journal-entries", headers=headers, json=_journal_body())
    assert posted.status_code == 201

    response = client.get(
        "/v1/accounting/journal-entries?reference=AR-202609&from_date=2026-09-01&to_date=2026-09-30",
        headers={"Authorization": headers["Authorization"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["next_offset"] is None
    assert body["items"][0]["reference"] == "AR-202609-0002"
    assert body["items"][0]["organization_id"] == str(seeded_user.organization_id)
    assert body["items"][0]["total_debit"] == "1070.00"
    assert body["items"][0]["total_credit"] == "1070.00"
    assert len(body["items"][0]["lines"]) == 3


def test_journal_list_rejects_an_invalid_date_range(
    client: TestClient, seeded_user, ledger_ready
) -> None:
    response = client.get(
        "/v1/accounting/journal-entries?from_date=2026-10-01&to_date=2026-09-01",
        headers={"Authorization": f"Bearer {_login(client, seeded_user)}"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "from_date must be on or before to_date"


def test_reversal_moves_to_next_open_period_and_uses_bounded_reference(
    client: TestClient, db_session, seeded_user, ledger_ready
) -> None:
    headers = {
        "Authorization": f"Bearer {_login(client, seeded_user)}",
        "Idempotency-Key": "api-reversal-source",
    }
    body = _journal_body()
    body["reference"] = "R" * 100
    posted = client.post("/v1/accounting/journal-entries", headers=headers, json=body)
    assert posted.status_code == 201

    ledger_ready.status = "locked"
    next_period = FiscalPeriod(
        tenant_id=seeded_user.tenant_id,
        organization_id=seeded_user.organization_id,
        name="2027",
        start_date=date(2027, 1, 1),
        end_date=date(2027, 12, 31),
        status="open",
    )
    db_session.add(next_period)
    db_session.commit()

    reversed_response = client.post(
        f"/v1/accounting/journal-entries/{posted.json()['entry_id']}/reverse",
        headers={
            "Authorization": headers["Authorization"],
            "Idempotency-Key": "api-reversal-target",
        },
    )

    assert reversed_response.status_code == 201
    reversal = db_session.get(JournalEntryRecord, reversed_response.json()["entry_id"])
    assert reversal is not None
    assert reversal.journal_date == date(2027, 1, 1)
    assert len(reversal.reference) <= 100
    assert reversal.reference.startswith("REV/")
