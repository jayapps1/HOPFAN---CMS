"""Foundation contracts and security checks; no production database writes."""
import logging
import subprocess
import sys
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from src.api.main import create_app
from src.api.schemas.common import HealthResponse
from src.config.online_settings import OnlineSettings

SECRET = "SYNTHETIC_PRIVATE_PASSWORD_TOKEN_987654"
DB_ERROR = f"postgresql://private_user:{SECRET}@private_database/internal SQL"


@pytest.fixture
def api():
    return create_app(OnlineSettings())


@pytest.fixture
def client(api):
    with TestClient(api, base_url="http://localhost") as test_client:
        yield test_client


@pytest.fixture
def database(monkeypatch):
    from src.config import database as shared_database

    db = Mock()
    db.execute.side_effect = [Mock(scalar_one=Mock(return_value=True)), Mock(scalar_one=Mock(return_value=1))]
    factory = Mock(return_value=db)
    monkeypatch.setattr(shared_database, "SessionLocal", factory)
    return db, factory


@pytest.mark.parametrize("path, expected", [
    ("health", {"status": "ok", "service": "hopfan-api"}),
    ("version", {"application": "HOPFAN", "api_version": "v1", "platform": "online"}),
])
def test_public_contracts_do_not_open_database(client, database, path, expected):
    response = client.get(f"/api/v1/{path}")
    assert response.status_code == 200
    assert response.json() == expected
    database[1].assert_not_called()


def test_readiness_uses_shared_factory_and_closes_session(client, database):
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "available"}
    db, factory = database
    factory.assert_called_once_with()
    assert db.execute.call_count == 2
    db.close.assert_called_once_with()


@pytest.mark.parametrize("failure", ["construct", "role_check", "readiness_query", "close"])
def test_database_failures_are_safe_and_close_opened_sessions(client, database, caplog, failure):
    db, factory = database
    if failure == "construct":
        factory.side_effect = RuntimeError(DB_ERROR)
    elif failure == "role_check":
        db.execute.side_effect = RuntimeError(DB_ERROR)
    elif failure == "readiness_query":
        db.execute.side_effect = [Mock(scalar_one=Mock(return_value=True)), RuntimeError(DB_ERROR)]
    else:
        db.close.side_effect = RuntimeError(DB_ERROR)
    response = client.get("/api/v1/ready")
    assert response.status_code == (500 if failure == "close" else 503)
    assert response.json()["error"]["code"] == (
        "INTERNAL_SERVER_ERROR" if failure == "close" else "DATABASE_UNAVAILABLE"
    )
    assert SECRET not in response.text + caplog.text
    assert "private_database" not in response.text + caplog.text
    assert "Traceback" not in response.text + caplog.text
    if failure != "construct":
        db.close.assert_called_once_with()
    else:
        db.close.assert_not_called()


@pytest.mark.parametrize("role_allowed", [False, None])
def test_superuser_or_unknown_role_is_rejected(client, database, role_allowed):
    db, _ = database
    db.execute.side_effect = [Mock(scalar_one=Mock(return_value=role_allowed))]
    response = client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_ACCESS_UNSAFE"
    assert db.execute.call_count == 1
    db.close.assert_called_once_with()


def test_unknown_route_and_disallowed_method_have_safe_errors(client):
    assert client.get("/api/v1/unknown").json() == {
        "error": {"code": "RESOURCE_NOT_FOUND", "message": "The requested resource was not found."}
    }
    assert client.get("/api/v1/unknown").status_code == 404
    response = client.post("/api/v1/health")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert "GET" in response.headers["allow"]


def test_validation_does_not_echo_sensitive_inputs(api, client, caplog):
    class TestInput(BaseModel):
        password: int

    @api.post("/test-validation")
    def validate(body: TestInput):
        return {"accepted": True}

    response = client.post("/test-validation", json={"password": SECRET})
    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "VALIDATION_ERROR", "message": "The request contains invalid data."}
    }
    assert SECRET not in response.text + caplog.text


@pytest.mark.parametrize("kind", ["unexpected", "http_detail", "response_schema"])
def test_internal_details_are_hidden_and_errors_keep_headers(api, client, caplog, kind):
    if kind == "unexpected":
        @api.get("/test-failure")
        def fail():
            raise RuntimeError(DB_ERROR)
        expected_status = 500
    elif kind == "http_detail":
        @api.get("/test-failure")
        def fail():
            raise HTTPException(400, detail=DB_ERROR)
        expected_status = 400
    else:
        @api.get("/test-failure", response_model=HealthResponse)
        def fail():
            return {"status": "ok", "service": "hopfan-api", "password_hash": SECRET}
        expected_status = 500
    response = client.get("/test-failure", headers={"Origin": "http://localhost:3001"})
    assert response.status_code == expected_status
    assert set(response.json()) == {"error"}
    assert SECRET not in response.text + caplog.text
    assert response.headers["access-control-allow-origin"] == "http://localhost:3001"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert UUID(response.headers["x-request-id"])


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://localhost:3001"])
def test_configured_cors_origin_and_preflight(client, origin):
    response = client.get("/api/v1/health", headers={"Origin": origin})
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"
    preflight = client.options("/api/v1/health", headers={
        "Origin": origin, "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "X-Request-ID",
    })
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == origin
    assert set(preflight.headers["access-control-allow-methods"].split(", ")) == {"GET", "POST", "PATCH"}


@pytest.mark.parametrize("origin", ["https://unconfigured.example", "http://localhost:3002", "null"])
def test_unconfigured_origin_has_no_broad_access(client, origin):
    response = client.get("/api/v1/health", headers={"Origin": origin})
    assert "access-control-allow-origin" not in response.headers
    preflight = client.options("/api/v1/health", headers={
        "Origin": origin, "Access-Control-Request-Method": "GET",
    })
    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in preflight.headers


@pytest.mark.parametrize("method", ["get", "options"])
def test_host_checks_cover_preflights_and_ignore_forwarded_host(client, method):
    response = getattr(client, method)("/api/v1/health", headers={
        "Host": "unconfigured.example", "X-Forwarded-Host": "localhost",
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET",
    })
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_HOST"
    assert "access-control-allow-origin" not in response.headers
    assert response.headers["x-request-id"]


def test_safe_logging_request_ids_and_security_headers(client, caplog):
    with caplog.at_level(logging.INFO, logger="hopfan.api"):
        first = client.get(f"/api/v1/health?password={SECRET}", headers={
            "Authorization": f"Bearer {SECRET}", "X-Request-ID": SECRET,
        })
        second = client.get(f"/api/v1/{SECRET}")
    assert SECRET not in caplog.text
    assert "method=GET path=/api/v1/health status=200" in caplog.text
    assert "path=/<unmatched> status=404" in caplog.text
    assert "duration_ms=" in caplog.text
    assert first.headers["x-request-id"] != second.headers["x-request-id"]
    for response in [first, second]:
        assert UUID(response.headers["x-request-id"])
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["x-frame-options"] == "DENY"


def test_only_implemented_routes_and_explicit_public_schemas_are_published(client):
    schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {'/api/v1/public/donations/options', '/api/v1/public/donations', '/api/v1/public/donations/{reference}', '/api/v1/public/donations/{reference}/verify', '/api/v1/payments/paystack/webhook', '/api/v1/finance/donations', '/api/v1/ministries/{ministry_id}', '/api/v1/auth/totp-login', '/api/v1/attendance/options', '/api/v1/sunday-school/reports/attendance.csv', '/api/v1/website/media/{media_id}/approve', '/api/v1/public/pages', '/api/v1/sunday-school/attendance/sessions', '/api/v1/public/announcements', '/api/v1/sunday-school/attendance/sessions/{session_id}/{action}', '/api/v1/ready', '/api/v1/website/settings/publish', '/api/v1/visitor-inquiries/{inquiry_id}/convert', '/api/v1/visitor-inquiries', '/api/v1/website/content/{entry_id}/{action}', '/api/v1/public/prayer-requests', '/api/v1/events', '/api/v1/public/sermons', '/api/v1/sunday-school/students/{member_id}', '/api/v1/announcements/{entity_id}/{action}', '/api/v1/sunday-school/attendance/sessions/{session_id}/mark', '/api/v1/website/media/{media_id}/archive', '/api/v1/website/settings', '/api/v1/attendance/sessions/{session_id}/summary', '/api/v1/events/{entity_id}/{action}', '/api/v1/version', '/api/v1/events/{entity_id}', '/api/v1/public/pages/{slug}', '/api/v1/announcements', '/api/v1/members/{member_id}', '/api/v1/website/media', '/api/v1/sunday-school/lessons/{lesson_id}', '/api/v1/public/sermons/{slug}', '/api/v1/public/testimonies/{slug}', '/api/v1/sunday-school/reports/attendance', '/api/v1/sunday-school/options', '/api/v1/sunday-school/attendance/sessions/{session_id}', '/api/v1/website/overview', '/api/v1/auth/logout', '/api/v1/public/site', '/api/v1/members', '/api/v1/attendance/sessions', '/api/v1/website/media/{media_id}/preview', '/api/v1/auth/csrf', '/api/v1/attendance/sessions/{session_id}', '/api/v1/sunday-school/classes', '/api/v1/public/gallery', '/api/v1/public/visitor-inquiries', '/api/v1/public/contact', '/api/v1/sunday-school/teachers', '/api/v1/attendance/sessions/{session_id}/photo/{member_id}', '/api/v1/public/events', '/api/v1/public/testimonies', '/api/v1/public/media/{media_id}', '/api/v1/media/member-photo/{member_id}', '/api/v1/public/ministries', '/api/v1/sunday-school/attendance/records/{record_id}/correct', '/api/v1/ministries/{ministry_id}/leadership', '/api/v1/sunday-school/attendance/sessions/{session_id}/roster', '/api/v1/sunday-school/reports/summary', '/api/v1/announcements/options', '/api/v1/sunday-school/classes/{class_id}', '/api/v1/public/leadership', '/api/v1/auth/password-login', '/api/v1/attendance/sessions/{session_id}/mark', '/api/v1/public/leadership/{slug}', '/api/v1/visitor-inquiries/{inquiry_id}/matches', '/api/v1/website/options', '/api/v1/attendance/sessions/{session_id}/{action}', '/api/v1/sunday-school/students', '/api/v1/public/events/{slug}', '/api/v1/events/options', '/api/v1/announcements/{entity_id}', '/api/v1/public/ministries/{slug}', '/api/v1/sunday-school/lessons', '/api/v1/me', '/api/v1/attendance/records/{record_id}/correct', '/api/v1/visitor-inquiries/{inquiry_id}', '/api/v1/sunday-school/attendance/sessions/{session_id}/photo/{member_id}', '/api/v1/visitor-inquiries/assignees', '/api/v1/health', '/api/v1/attendance/sessions/{session_id}/roster', '/api/v1/website/content', '/api/v1/website/content/{entry_id}', '/api/v1/dashboard', '/api/v1/ministries', '/api/v1/sunday-school/dashboard', '/api/v1/ministries/{ministry_id}/members', '/api/v1/members/options', '/api/v1/public/gallery/{slug}'}
    for name in ["password_hash", "totp_secret", "DB_PASSWORD", "APP_ENCRYPTION_KEY", "DATABASE_URL"]:
        assert name not in str(schema)
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200


@pytest.fixture
def isolated_online_environment(monkeypatch):
    import src.config.online_settings as settings_module
    monkeypatch.setattr(settings_module, "load_environment", lambda: None)
    for name in ["APP_ENV", "API_HOST", "API_PORT", "API_DEBUG", "API_DOCS_ENABLED",
                 "API_ALLOWED_HOSTS", "WEB_PUBLIC_ORIGIN", "WEB_PORTAL_ORIGIN"]:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_deployed_defaults_disable_docs_debug_and_cors(isolated_online_environment, environment):
    isolated_online_environment.setenv("APP_ENV", environment)
    isolated_online_environment.setenv("API_ALLOWED_HOSTS", "api.example.org")
    settings = OnlineSettings.from_environment()
    assert not settings.api_docs_enabled
    assert not settings.api_debug
    assert settings.cors_origins == ()
    app = create_app(settings)
    assert app.debug is False
    with TestClient(app, base_url="https://api.example.org") as client:
        assert client.get("/api/v1/health").status_code == 200
        for path in ["/docs", "/redoc", "/openapi.json"]:
            assert client.get(path).status_code == 404


@pytest.mark.parametrize("name, value", [
    ("WEB_PORTAL_ORIGIN", "*"), ("WEB_PORTAL_ORIGIN", "http://localhost:3001"),
    ("API_DEBUG", "true"), ("API_ALLOWED_HOSTS", "*"), ("API_ALLOWED_HOSTS", ""),
    ("API_DEBUG", SECRET), ("API_PORT", SECRET), ("API_PORT", "70000"),
])
def test_unsafe_production_configuration_is_rejected(isolated_online_environment, name, value):
    isolated_online_environment.setenv("APP_ENV", "production")
    isolated_online_environment.setenv("API_ALLOWED_HOSTS", "api.example.org")
    isolated_online_environment.setenv(name, value)
    with pytest.raises(ValueError) as failure:
        OnlineSettings.from_environment()
    assert SECRET not in str(failure.value)


def test_production_docs_can_be_explicitly_enabled(isolated_online_environment):
    isolated_online_environment.setenv("APP_ENV", "production")
    isolated_online_environment.setenv("API_ALLOWED_HOSTS", "api.example.org")
    isolated_online_environment.setenv("API_DOCS_ENABLED", "true")
    isolated_online_environment.setenv("WEB_PORTAL_ORIGIN", "https://portal.example.org")
    settings = OnlineSettings.from_environment()
    assert settings.api_docs_enabled
    assert settings.cors_origins == ("https://portal.example.org",)


@pytest.mark.parametrize("target, forbidden", [
    ("src.api.main", ("tkinter", "customtkinter", "hopfan", "src.ui")),
    ("hopfan", ("fastapi", "uvicorn", "pydantic")),
])
def test_api_and_desktop_imports_are_independent(target, forbidden):
    code = (
        "import importlib.abc, sys\n"
        "class Guard(importlib.abc.MetaPathFinder):\n"
        " def find_spec(self, fullname, path=None, target=None):\n"
        f"  if any(fullname == n or fullname.startswith(n + '.') for n in {forbidden!r}):\n"
        "   raise ImportError('Forbidden cross-application import')\n"
        "sys.meta_path.insert(0, Guard())\n"
        f"__import__({target!r})\n"
        "print('Independent import OK')\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    # Never echo subprocess stderr, which could contain environment-dependent paths.
    assert result.returncode == 0, "Independent application import failed."
    assert result.stdout.strip() == "Independent import OK"
