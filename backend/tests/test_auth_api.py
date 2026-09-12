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
    assert len(response.json()["csrf_token"]) >= 32


def test_login_establishes_cookie_session_and_cookie_mutations_require_csrf(
    client: TestClient, seeded_user
) -> None:
    login = client.post(
        "/v1/auth/login",
        json={
            "tenant_slug": seeded_user.tenant.slug,
            "email": seeded_user.email,
            "password": "correct horse battery staple",
        },
    )

    assert login.status_code == 200
    set_cookie = login.headers["set-cookie"]
    assert "zsme_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "zsme_csrf=" in set_cookie
    assert client.cookies.get("zsme_csrf")

    me = client.get("/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user_id"] == str(seeded_user.id)

    blocked_logout = client.post("/v1/auth/logout")
    assert blocked_logout.status_code == 403
    assert blocked_logout.json()["detail"] == "CSRF validation failed"

    logout = client.post(
        "/v1/auth/logout",
        headers={"X-CSRF-Token": client.cookies.get("zsme_csrf")},
    )
    assert logout.status_code == 204


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


def test_csrf_bootstrap_rotates_the_session_bound_token(client: TestClient, seeded_user) -> None:
    login = client.post(
        "/v1/auth/login",
        json={
            "tenant_slug": seeded_user.tenant.slug,
            "email": seeded_user.email,
            "password": "correct horse battery staple",
        },
    )
    initial_token = login.json()["csrf_token"]

    refreshed = client.get("/v1/auth/csrf")

    assert refreshed.status_code == 200
    assert refreshed.json()["csrf_token"] != initial_token
    assert client.cookies.get("zsme_csrf") == refreshed.json()["csrf_token"]


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


def test_browser_login_never_returns_raw_session_token(client: TestClient, seeded_user) -> None:
    response = client.post(
        "/v1/auth/browser-login",
        json={
            "tenant_slug": seeded_user.tenant.slug,
            "email": seeded_user.email,
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == 200
    assert "access_token" not in response.json()
    assert response.json()["csrf_token"]
    assert client.cookies.get("zsme_session")
    assert client.cookies.get("zsme_csrf")
