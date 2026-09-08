from uuid import UUID

from app.db.models import AuditEvent, BusinessPartner


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


def _create(client, headers: dict[str, str], key: str = "partner-create-1"):
    return client.post(
        "/v1/partners",
        headers={**headers, "Idempotency-Key": key},
        json={
            "partner_code": "CUS-0001",
            "partner_type": "customer",
            "display_name": "Bangkok Example Co.",
            "legal_name": "Bangkok Example Company Limited",
            "tax_id": "0105559999999",
            "tax_branch": "00000",
            "email": "finance@example.test",
            "payment_terms_days": 30,
            "credit_limit": "50000.00",
        },
    )


def test_partner_create_is_idempotent_and_audited(client, db_session, seeded_user) -> None:
    headers = _login(client)
    first = _create(client, headers)
    replay = _create(client, headers)

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert replay.json()["version"] == 1

    audit = db_session.query(AuditEvent).filter_by(action="partner.create").one()
    assert audit.tenant_id == seeded_user.tenant_id
    assert audit.entity_id == UUID(first.json()["id"])


def test_partner_idempotency_key_cannot_change_request(client, seeded_user) -> None:
    headers = _login(client)
    first = _create(client, headers, key="partner-reuse-1")
    assert first.status_code == 201

    changed = client.post(
        "/v1/partners",
        headers={**headers, "Idempotency-Key": "partner-reuse-1"},
        json={
            "partner_code": "CUS-0002",
            "partner_type": "vendor",
            "display_name": "Changed request",
        },
    )

    assert changed.status_code == 409
    assert "different request" in changed.text


def test_partner_list_is_scoped_and_update_uses_optimistic_version(
    client, db_session, seeded_user, other_tenant_user
) -> None:
    headers = _login(client)
    created = _create(client, headers, key="partner-update-1")
    assert created.status_code == 201

    other_partner = BusinessPartner(
        tenant_id=other_tenant_user.tenant_id,
        organization_id=other_tenant_user.organization_id,
        partner_code="CUS-OTHER",
        partner_type="customer",
        display_name="Other tenant customer",
    )
    db_session.add(other_partner)
    db_session.commit()

    listed = client.get("/v1/partners", headers=headers)
    assert listed.status_code == 200
    assert [item["partner_code"] for item in listed.json()] == ["CUS-0001"]

    partner_id = created.json()["id"]
    updated = client.patch(
        f"/v1/partners/{partner_id}",
        headers={**headers, "Idempotency-Key": "partner-update-2"},
        json={"display_name": "Updated customer", "expected_version": 1},
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Updated customer"
    assert updated.json()["version"] == 2

    stale = client.patch(
        f"/v1/partners/{partner_id}",
        headers={**headers, "Idempotency-Key": "partner-update-3"},
        json={"display_name": "Stale update", "expected_version": 1},
    )
    assert stale.status_code == 409
    assert "version" in stale.text


def test_partner_archive_is_soft_and_audited(client, db_session, seeded_user) -> None:
    headers = _login(client)
    created = _create(client, headers, key="partner-archive-1")
    partner_id = created.json()["id"]

    archived = client.post(
        f"/v1/partners/{partner_id}/archive",
        headers={**headers, "Idempotency-Key": "partner-archive-2"},
        json={"expected_version": 1},
    )

    assert archived.status_code == 200
    assert archived.json()["is_active"] is False
    assert db_session.query(BusinessPartner).filter_by(id=UUID(partner_id)).one().is_active is False
    assert db_session.query(AuditEvent).filter_by(action="partner.archive").count() == 1
