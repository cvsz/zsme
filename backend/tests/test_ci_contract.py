from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_compose_uses_service_dns_and_health_dependencies() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    api = compose["services"]["api"]
    frontend = compose["services"]["frontend"]

    assert "@db:" in api["environment"]["DATABASE_URL"]
    assert api["depends_on"]["db"]["condition"] == "service_healthy"
    assert api["healthcheck"]["test"][0:2] == ["CMD", "python"]
    assert "/ready" in " ".join(api["healthcheck"]["test"])
    assert compose["services"]["db"]["healthcheck"]["test"][0] == "CMD-SHELL"
    assert frontend["depends_on"]["api"]["condition"] == "service_healthy"
    assert frontend["healthcheck"]["test"][0:2] == ["CMD", "node"]


def test_compose_does_not_publish_database_by_default() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    db = compose["services"]["db"]

    assert "ports" not in db
    assert "POSTGRES_PASSWORD" not in db["environment"]
    assert db["env_file"] == ["./backend/.env.compose"]


def test_ci_contains_required_quality_gates() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()

    for required in (
        "ruff check",
        "pytest -q",
        "alembic upgrade head",
        "npm ci",
        "npm audit",
        "npm run lint",
        "npm run build",
        "docker build",
    ):
        assert required in workflow


def test_container_declares_non_root_healthchecked_runtime() -> None:
    dockerfile = (ROOT / "backend/Dockerfile").read_text()
    frontend_dockerfile = (ROOT / "frontend/Dockerfile").read_text()

    assert "USER zsme" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "alembic upgrade head" not in dockerfile
    assert "USER node" in frontend_dockerfile
    assert "HEALTHCHECK" in frontend_dockerfile
    assert "server.js" in frontend_dockerfile


def test_operational_runbooks_exist_and_mark_external_evidence() -> None:
    foundation = (ROOT / "docs/runbooks/foundation-local.md").read_text()
    backup = (ROOT / "docs/runbooks/backup-restore.md").read_text()

    for content in (foundation, backup):
        assert "staging" in content.lower()
        assert "production" in content.lower()
        assert "rollback" in content.lower()
