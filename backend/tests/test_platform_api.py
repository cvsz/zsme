from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db.session import get_session
from app.main import app


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


def test_ready_reports_healthy_database(client: TestClient) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_ready_reports_dependency_failure(client: TestClient) -> None:
    class BrokenSession:
        def execute(self, *_args, **_kwargs):
            raise OperationalError("SELECT 1", {}, RuntimeError("database down"))

    def broken_session() -> Iterator[BrokenSession]:
        yield BrokenSession()

    app.dependency_overrides[get_session] = broken_session
    try:
        response = client.get("/ready")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "service_unavailable"
    assert response.json()["detail"] == "database unavailable"


def test_authentication_failure_uses_problem_shape(client: TestClient) -> None:
    response = client.get("/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "authentication_required"
    assert response.json()["correlation_id"]


def test_organization_list_is_tenant_scoped(
    client: TestClient, seeded_user, other_tenant_user
) -> None:
    response = client.get(
        "/v1/organizations",
        headers={"Authorization": f"Bearer {_login(client, seeded_user)}"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == str(seeded_user.organization_id)
    assert response.json()[0]["id"] != str(other_tenant_user.organization_id)


def test_validation_error_has_stable_problem_shape(
    client: TestClient, seeded_user
) -> None:
    headers = {
        "Authorization": f"Bearer {_login(client, seeded_user)}",
        "Idempotency-Key": "bad-request-001",
    }
    response = client.post("/v1/accounting/journal-entries", headers=headers, json={})

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "validation_error"
    assert response.json()["correlation_id"]
