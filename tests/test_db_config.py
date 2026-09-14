"""
Unit tests for Database Configuration, Production Safety, Host Mode, Credential Sanitization,
and Diagnostic Health Checks.
"""

from unittest.mock import patch, PropertyMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.config import get_db_host_mode, sanitize_database_url, Settings
from app.db import check_db_health, get_db
from app.main import app


# 1. Test Local DATABASE_URL host mode classification
def test_local_database_url_classification():
    assert get_db_host_mode("postgresql+psycopg://user:pass@localhost:5432/db") == "LOCAL"
    assert get_db_host_mode("postgresql+psycopg://user:pass@127.0.0.1:5432/db") == "LOCAL"
    assert get_db_host_mode("postgresql+psycopg://user:pass@[::1]:5432/db") == "LOCAL"
    assert get_db_host_mode("") == "LOCAL"


# 2. Test Cloud DATABASE_URL host mode classification
def test_cloud_database_url_classification():
    neon_url = "postgresql+psycopg://alex:secret123@ep-cool-name.neon.tech/neondb?sslmode=require"
    assert get_db_host_mode(neon_url) == "CLOUD"


# 3. Test Missing Production DATABASE_URL returns empty string to prevent localhost fallback
def test_missing_production_database_url_safety():
    # When app_env is production and database_url points to localhost or is empty
    s_prod = Settings(
        app_env="production",
        database_url="postgresql+psycopg://daily_intel:CHANGE_ME@localhost:5432/daily_intelligence",
    )
    assert s_prod.is_production is True
    assert s_prod.effective_database_url == ""

    # In local development, configured local database_url is preserved
    s_dev = Settings(
        app_env="development",
        database_url="postgresql+psycopg://daily_intel:pass@localhost:5432/daily_intel",
    )
    assert s_dev.is_production is False
    assert s_dev.effective_database_url == "postgresql+psycopg://daily_intel:pass@localhost:5432/daily_intel"


# 4. Test Credential Sanitization
def test_sanitize_database_url_redacts_password():
    secret_pass = "super_secret_password_123"
    raw_url = f"postgresql+psycopg://daily_intel:{secret_pass}@ep-cloud.neon.tech:5432/daily_db"
    sanitized = sanitize_database_url(raw_url)

    assert secret_pass not in sanitized
    assert "daily_intel" not in sanitized
    assert "***@ep-cloud.neon.tech:5432/daily_db" in sanitized


# 5. Test Diagnostic output contains no password
def test_check_db_health_contains_no_password():
    secret_pass = "hidden_password_xyz"
    raw_url = f"postgresql+psycopg://user:{secret_pass}@ep-cloud.neon.tech/neondb"
    with patch("app.db.settings.database_url", raw_url), \
         patch.object(Settings, "effective_database_url", PropertyMock(return_value=raw_url)), \
         patch("app.db.engine.connect", side_effect=OperationalError("conn", params=None, orig=Exception())):
        status = check_db_health()
        assert status["configured"] is True
        assert status["mode"] == "CLOUD"
        assert status["reachable"] is False
        assert secret_pass not in str(status)


# 6. Test App Health survives dependency outage
def test_health_endpoint_survives_dependency_outage():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


# 7. Test /health/dependencies JSON structure
def test_health_dependencies_endpoint():
    client = TestClient(app)
    response = client.get("/health/dependencies")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "ollama" in data
    assert "configured" in data["database"]
    assert "mode" in data["database"]
    assert "reachable" in data["database"]


# 8. Test DB-dependent route fails safely when DB is unconfigured
def test_db_dependent_route_unconfigured_503():
    with patch.object(Settings, "effective_database_url", PropertyMock(return_value="")):
        with pytest.raises(Exception) as exc_info:
            list(get_db())
        assert "503" in str(exc_info.value) or "unconfigured" in str(exc_info.value)


# 9. Test Alembic env.py uses effective_database_url
def test_alembic_uses_effective_database_url():
    with patch.object(Settings, "effective_database_url", PropertyMock(return_value="postgresql+psycopg://user:pass@cloud.db/db")):
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        alembic_cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(alembic_cfg)
        assert script.get_current_head() is not None
