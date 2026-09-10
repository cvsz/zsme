import asyncio
import json

import pytest

from app.core.config import Settings
from app.main import app


def test_cors_origins_support_comma_separated_and_json_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, https://app.example.com")
    settings = Settings()
    assert settings.cors_origin_list == ["http://localhost:3000", "https://app.example.com"]

    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:3000"]')
    assert Settings().cors_origin_list == ["http://localhost:3000"]


def test_http_responses_include_security_headers(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_no_body_request_does_not_fail_in_security_middleware(client) -> None:
    response = client.get("/health", headers={"X-Correlation-ID": "get-health-001"})

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "get-health-001"
    assert response.headers["X-Request-ID"] == "get-health-001"


def test_chunked_request_body_limit_is_enforced() -> None:
    async def request() -> tuple[int, bytes]:
        sent: list[dict[str, object]] = []
        delivered = False

        async def receive() -> dict[str, object]:
            nonlocal delivered
            if delivered:
                return {"type": "http.disconnect"}
            delivered = True
            return {
                "type": "http.request",
                "body": b"x" * (1_048_576 + 1),
                "more_body": False,
            }

        async def send(message: dict[str, object]) -> None:
            sent.append(message)

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/v1/accounting/validate-entry",
            "raw_path": b"/v1/accounting/validate-entry",
            "query_string": b"",
            "headers": [(b"content-type", b"application/json")],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
        await app(scope, receive, send)
        response = next(item for item in sent if item["type"] == "http.response.start")
        body = b"".join(
            item.get("body", b"") for item in sent if item["type"] == "http.response.body"
        )
        assert response["status"] == 413
        assert json.loads(body)["code"] == "request_too_large"
        return int(response["status"]), body

    status_code, _body = asyncio.run(request())
    assert status_code == 413
