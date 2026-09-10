from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import SessionToken


def test_login_rejects_wrong_tenant_or_password(client: TestClient, seeded_user) -> None:
    response = client.post(
        "/v1/auth/login",
        json={
            "tenant_slug": "other",
            "email": seeded_user.email,
            "password": "bad",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid credentials"


def test_login_returns_opaque_token(client: TestClient, seeded_user) -> None:
    response = client.post(
        "/v1/auth/login",
        json={
            "tenant_slug": seeded_user.tenant.slug,
            "email": seeded_user.email,
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert len(response.json()["access_token"]) >= 32


def test_me_never_crosses_tenant_boundary(
    client: TestClient, seeded_user, other_tenant_user
) -> None:
    login = client.post(
        "/v1/auth/login",
        json={
            "tenant_slug": seeded_user.tenant.slug,
            "email": seeded_user.email,
            "password": "correct horse battery staple",
        },
    )
    token = login.json()["access_token"]

    response = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["tenant_id"] == str(seeded_user.tenant_id)
    assert str(other_tenant_user.tenant_id) not in response.text


def test_logout_revokes_session(client: TestClient, seeded_user) -> None:
    login = client.post(
        "/v1/auth/login",
        json={
            "tenant_slug": seeded_user.tenant.slug,
            "email": seeded_user.email,
            "password": "correct horse battery staple",
        },
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    logout = client.post("/v1/auth/logout", headers=headers)
    me = client.get("/v1/auth/me", headers=headers)

    assert logout.status_code == 204
    assert me.status_code == 401


def test_login_does_not_persist_raw_token(client: TestClient, db_session, seeded_user) -> None:
    login = client.post(
        "/v1/auth/login",
        json={
            "tenant_slug": seeded_user.tenant.slug,
            "email": seeded_user.email,
            "password": "correct horse battery staple",
        },
    )
    raw_token = login.json()["access_token"]
    stored = db_session.scalar(select(SessionToken).where(SessionToken.user_id == seeded_user.id))

    assert stored is not None
    assert stored.token_hash != raw_token


def test_login_rate_limit_blocks_repeated_failures(client: TestClient, seeded_user) -> None:
    payload = {
        "tenant_slug": seeded_user.tenant.slug,
        "email": seeded_user.email,
        "password": "wrong password",
    }

    responses = [client.post("/v1/auth/login", json=payload) for _ in range(5)]

    assert [response.status_code for response in responses[:4]] == [401, 401, 401, 401]
    assert responses[4].status_code == 429
    assert responses[4].headers["Retry-After"]
