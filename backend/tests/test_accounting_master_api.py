from app.db.models import AuditEvent, ChartAccount


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


def test_chart_account_create_replay_and_scoped_list(
    client, db_session, seeded_user, other_tenant_user, ledger_ready
) -> None:
    headers = _login(client)
    body = {
        "code": "1200",
        "name": "Short-term investments",
        "account_type": "asset",
        "is_control": False,
    }
    first = client.post(
        "/v1/accounting/accounts",
        headers={**headers, "Idempotency-Key": "account-create-1"},
        json=body,
    )
    replay = client.post(
        "/v1/accounting/accounts",
        headers={**headers, "Idempotency-Key": "account-create-1"},
        json=body,
    )

    other = ChartAccount(
        tenant_id=other_tenant_user.tenant_id,
        organization_id=other_tenant_user.organization_id,
        code="1200",
        name="Other account",
        account_type="asset",
    )
    db_session.add(other)
    db_session.commit()
    listed = client.get("/v1/accounting/accounts", headers=headers)

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert listed.status_code == 200
    assert [item["code"] for item in listed.json()] == [
        "1100",
        "1200",
        "1400",
        "2100",
        "2101",
        "4000",
        "5000",
    ]


def test_fiscal_period_can_be_created_and_locked_once(
    client, db_session, seeded_user, ledger_ready
) -> None:
    headers = _login(client)
    created = client.post(
        "/v1/accounting/periods",
        headers={**headers, "Idempotency-Key": "period-create-1"},
        json={
            "name": "2027",
            "start_date": "2027-01-01",
            "end_date": "2027-12-31",
        },
    )
    period_id = created.json()["id"]
    locked = client.post(
        f"/v1/accounting/periods/{period_id}/lock",
        headers={**headers, "Idempotency-Key": "period-lock-1"},
    )
    replay = client.post(
        f"/v1/accounting/periods/{period_id}/lock",
        headers={**headers, "Idempotency-Key": "period-lock-1"},
    )

    assert created.status_code == 201
    assert locked.status_code == 200
    assert locked.json()["status"] == "locked"
    assert locked.json()["version"] == 2
    assert replay.status_code == 200
    assert replay.json()["id"] == period_id
    assert db_session.query(AuditEvent).filter_by(action="period.lock").count() == 1


def test_control_account_cannot_receive_a_posting(
    client, db_session, seeded_user, ledger_ready
) -> None:
    headers = _login(client)
    account = client.post(
        "/v1/accounting/accounts",
        headers={**headers, "Idempotency-Key": "account-control-1"},
        json={
            "code": "1000",
            "name": "Cash and cash equivalents",
            "account_type": "asset",
            "is_control": True,
        },
    )
    assert account.status_code == 201

    posting = client.post(
        "/v1/accounting/journal-entries",
        headers={**headers, "Idempotency-Key": "control-post-1"},
        json={
            "reference": "CONTROL-001",
            "journal_date": "2026-09-08",
            "source_type": "manual",
            "lines": [
                {"account_code": "1000", "debit": "10.00"},
                {"account_code": "4000", "credit": "10.00"},
            ],
        },
    )

    assert posting.status_code == 409
    assert "control account" in posting.json()["detail"]
