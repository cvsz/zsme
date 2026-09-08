from app.db.models import AuditEvent


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


def test_tax_rate_is_versioned_effective_dated_and_idempotent(
    client, db_session, seeded_user
) -> None:
    headers = _login(client)
    body = {
        "tax_type": "vat",
        "code": "VAT-STD",
        "name": "Standard VAT",
        "rate": "7.00",
        "effective_from": "2026-01-01",
        "effective_to": "2026-12-31",
    }
    created = client.post(
        "/v1/tax/rates",
        headers={**headers, "Idempotency-Key": "tax-rate-create-1"},
        json=body,
    )
    replay = client.post(
        "/v1/tax/rates",
        headers={**headers, "Idempotency-Key": "tax-rate-create-1"},
        json=body,
    )
    effective = client.get(
        "/v1/tax/rates/effective?tax_type=vat&code=VAT-STD&on_date=2026-09-08",
        headers=headers,
    )

    assert created.status_code == 201
    assert created.json()["version"] == 1
    assert replay.status_code == 200
    assert replay.json()["id"] == created.json()["id"]
    assert effective.status_code == 200
    assert effective.json()["code"] == "VAT-STD"
    assert effective.json()["rate"] == "7.00"
    assert db_session.query(AuditEvent).filter_by(action="tax_rate.create").count() == 1


def test_tax_rate_overlap_and_invalid_effective_date_are_rejected(client, seeded_user) -> None:
    headers = _login(client)
    first = client.post(
        "/v1/tax/rates",
        headers={**headers, "Idempotency-Key": "tax-rate-overlap-1"},
        json={
            "tax_type": "withholding",
            "code": "WHT-SVC",
            "name": "Service withholding",
            "rate": "3.00",
            "effective_from": "2026-01-01",
            "effective_to": "2026-12-31",
        },
    )
    overlap = client.post(
        "/v1/tax/rates",
        headers={**headers, "Idempotency-Key": "tax-rate-overlap-2"},
        json={
            "tax_type": "withholding",
            "code": "WHT-SVC",
            "name": "Service withholding replacement",
            "rate": "5.00",
            "effective_from": "2026-06-01",
            "effective_to": None,
        },
    )
    invalid = client.post(
        "/v1/tax/rates",
        headers={**headers, "Idempotency-Key": "tax-rate-invalid-1"},
        json={
            "tax_type": "vat",
            "code": "VAT-BAD",
            "name": "Invalid",
            "rate": "7.00",
            "effective_from": "2027-01-01",
            "effective_to": "2026-12-31",
        },
    )

    assert first.status_code == 201
    assert overlap.status_code == 409
    assert "overlap" in overlap.json()["detail"]
    assert invalid.status_code == 422
