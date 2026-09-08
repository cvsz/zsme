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


def test_trial_balance_is_derived_from_posted_ledger(client, seeded_user, ledger_ready) -> None:
    headers = {**_login(client), "Idempotency-Key": "report-post-1"}
    posting = client.post(
        "/v1/accounting/journal-entries",
        headers=headers,
        json={
            "reference": "REPORT-001",
            "journal_date": "2026-09-08",
            "source_type": "manual",
            "lines": [
                {"account_code": "1100", "debit": "1070.00"},
                {"account_code": "4000", "credit": "1000.00"},
                {"account_code": "2101", "credit": "70.00"},
            ],
        },
    )
    assert posting.status_code == 201

    response = client.get(
        "/v1/reports/trial-balance?from_date=2026-09-01&to_date=2026-09-30",
        headers={"Authorization": headers["Authorization"]},
    )

    assert response.status_code == 200
    assert response.json()["total_debit"] == "1070.00"
    assert response.json()["total_credit"] == "1070.00"
    rows = {row["account_code"]: row for row in response.json()["rows"]}
    assert rows["1100"]["debit"] == "1070.00"
    assert rows["4000"]["credit"] == "1000.00"
    assert rows["2101"]["credit"] == "70.00"


def test_trial_balance_excludes_unposted_and_out_of_range_entries(
    client, seeded_user, ledger_ready
) -> None:
    response = client.get(
        "/v1/reports/trial-balance?from_date=2027-01-01&to_date=2027-01-31",
        headers=_login(client),
    )

    assert response.status_code == 200
    assert response.json()["rows"] == []
    assert response.json()["total_debit"] == "0.00"
    assert response.json()["total_credit"] == "0.00"
