import pytest

from app.core.config import Settings


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
