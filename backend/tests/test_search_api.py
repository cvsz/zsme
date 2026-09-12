from app.db.models import BusinessPartner


def _token(client) -> str:
    response = client.post(
        "/v1/auth/login",
        json={
            "tenant_slug": "demo",
            "email": "admin@example.com",
            "password": "correct horse battery staple",
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_workspace_search_stays_inside_tenant(
    client, db_session, seeded_user, other_tenant_user
) -> None:
    first = BusinessPartner(
        tenant_id=seeded_user.tenant_id,
        organization_id=seeded_user.organization_id,
        partner_code="CUS-SEARCH-1",
        partner_type="customer",
        display_name="Searchable Customer",
    )
    second = BusinessPartner(
        tenant_id=other_tenant_user.tenant_id,
        organization_id=other_tenant_user.organization_id,
        partner_code="CUS-SEARCH-2",
        partner_type="customer",
        display_name="Searchable Customer Other",
    )
    db_session.add_all([first, second])
    db_session.commit()

    response = client.get(
        "/v1/search?q=Searchable",
        headers={"Authorization": f"Bearer {_token(client)}"},
    )

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(first.id) in ids
    assert str(second.id) not in ids
