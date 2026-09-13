import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.dev_routes import router as dev_router


@pytest.fixture
def test_db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(test_db_session):
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_missing_page_returns_branded_404_html(client):
    response = client.get("/this-page-does-not-exist-12345")
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    assert "404 - Page Not Found" in response.text
    assert "Return to Front Page" in response.text
    assert "Browse Archive" in response.text

    # Verify no stack traces or internal technical keywords leaked
    assert "Traceback" not in response.text
    assert "File \"" not in response.text
    assert "AttributeError" not in response.text


def test_missing_api_route_returns_json_404(client):
    response = client.get("/api/non-existent-endpoint-xyz")
    assert response.status_code == 404
    assert "application/json" in response.headers["content-type"]
    data = response.json()
    assert "detail" in data
    assert data["status_code"] == 404


def test_forced_500_exception_returns_branded_500_html(client):
    response = client.get("/_test/force-error")
    assert response.status_code == 500
    assert "text/html" in response.headers["content-type"]
    assert "500 - Internal Server Error" in response.text
    assert "Return to Front Page" in response.text

    # Critical requirement: Never leak internal exception, tracebacks or secret details to users
    assert "Traceback" not in response.text
    assert "File \"" not in response.text
    assert "Simulated internal database exception" not in response.text


def test_forced_api_500_exception_returns_structured_json(client):
    response = client.get("/_test/force-error", headers={"accept": "application/json"})
    assert response.status_code == 500
    assert "application/json" in response.headers["content-type"]
    data = response.json()
    assert data["detail"] == "Internal Server Error"
    assert data["status_code"] == 500


def test_dev_error_routes_disabled_by_default(client):
    """Verify that development error test routes return 404 when ENABLE_ERROR_TEST_ROUTES=false."""
    error_codes = [400, 403, 429, 500, 502, 503]
    for code in error_codes:
        response = client.get(f"/dev/error/{code}")
        assert response.status_code == 404
        assert "404 - Page Not Found" in response.text


def test_dev_error_routes_enabled_html_and_json(test_db_session):
    """Verify development error test routes when ENABLE_ERROR_TEST_ROUTES=true."""
    # Temporarily attach dev_router if not already attached
    test_app = app
    if not any(r.path == "/dev/error/400" for r in test_app.routes):
        test_app.include_router(dev_router)

    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    test_app.dependency_overrides[get_db] = override_get_db

    with TestClient(test_app, raise_server_exceptions=False) as dev_client:
        # 1. Test HTML responses for all error test routes
        html_expectations = [
            (400, "400 - Bad Request"),
            (403, "403 - Forbidden"),
            (429, "429 - Rate Limit Exceeded"),
            (500, "500 - Internal Server Error"),
            (502, "502 - Bad Gateway"),
            (503, "503 - Service Unavailable"),
        ]

        for code, expected_title in html_expectations:
            resp = dev_client.get(f"/dev/error/{code}")
            assert resp.status_code == code, f"Expected {code} for /dev/error/{code}"
            assert "text/html" in resp.headers["content-type"]
            assert expected_title in resp.text
            assert "Return to Front Page" in resp.text

            # Retry button check for 502 & 503
            if code in (502, 503):
                assert "Retry Request" in resp.text

            # Security assertions: Never leak stack trace, secrets or paths
            assert "Traceback" not in resp.text
            assert "File \"" not in resp.text
            assert "DATABASE_URL" not in resp.text
            assert "CHANGE_ME" not in resp.text

        # 2. Test API JSON responses for all error test routes
        for code, _ in html_expectations:
            resp_api = dev_client.get(f"/dev/error/{code}", headers={"accept": "application/json"})
            assert resp_api.status_code == code
            assert "application/json" in resp_api.headers["content-type"]
            json_data = resp_api.json()
            assert "detail" in json_data
            assert json_data["status_code"] == code

    test_app.dependency_overrides.clear()
