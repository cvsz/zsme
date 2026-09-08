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


def test_audit_events_are_scoped_filterable_and_paginated(
    client, db_session, seeded_user
) -> None:
    db_session.add(
        AuditEvent(
            tenant_id=seeded_user.tenant_id,
            organization_id=seeded_user.organization_id,
            actor_user_id=seeded_user.id,
            action="partner.create",
            entity_type="business_partner",
            entity_id=seeded_user.id,
            correlation_id="corr-partner",
            payload={"partner_code": "CUS-001"},
        )
    )
    db_session.add(
        AuditEvent(
            tenant_id=seeded_user.tenant_id,
            organization_id=seeded_user.organization_id,
            actor_user_id=seeded_user.id,
            action="journal.post",
            entity_type="journal_entry",
            entity_id=seeded_user.id,
            correlation_id="corr-journal",
            payload={"reference": "JRN-001"},
        )
    )
    db_session.commit()

    response = client.get(
        "/v1/audit/events?action=partner.create&limit=1&offset=0",
        headers=_login(client),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["action"] == "partner.create"
    assert body["next_offset"] is None


def test_audit_events_do_not_expose_sensitive_payload_keys(client, db_session, seeded_user) -> None:
    db_session.add(
        AuditEvent(
            tenant_id=seeded_user.tenant_id,
            organization_id=seeded_user.organization_id,
            actor_user_id=seeded_user.id,
            action="integration.create",
            entity_type="integration",
            entity_id=seeded_user.id,
            correlation_id="corr-secret",
            payload={
                "provider": "demo",
                "access_token": "must-not-leak",
                "nested": {"password": "also-hidden"},
            },
        )
    )
    db_session.commit()

    response = client.get(
        "/v1/audit/events?action=integration.create", headers=_login(client)
    )

    assert response.status_code == 200
    payload = response.json()["items"][0]["payload"]
    assert payload == {
        "provider": "demo",
        "access_token": "[REDACTED]",
        "nested": {"password": "[REDACTED]"},
    }
