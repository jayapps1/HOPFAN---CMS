"""Real existing credentials/RBAC and browser sessions in private PostgreSQL."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4
import hashlib
import json
import re

from argon2 import PasswordHasher
from fastapi import Depends
from fastapi.testclient import TestClient
import pyotp
import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from src.api.dependencies import get_db, require_permission, require_any_permission, require_ministry_permission
from src.api.main import create_app
from src.config.database import engine
from src.config.online_settings import OnlineSettings
from src.database.base import Base
from src.models import (Member, MemberStatus, Ministry, Permission, Role, User, UserStatus,
                        UserMinistryScope, SecurityAuditLog, WebSession, WebRateLimit,
                        MinistryPosition, MinistryLeadershipAssignment,
                        SundaySchoolClass, SundaySchoolUserClassScope)
from src.security.application_permissions import PERMISSIONS as APP
from src.security.attendance_permissions import PERMISSIONS as ATT
from src.security.administration_permissions import PERMISSIONS as ADMIN
from src.security.sunday_school_permissions import TEACHER_PERMISSIONS
from src.services.api_readiness_service import check_api_database_access
from src.services.totp_service import TotpService
from src.services.web_security import csrf_token, session_hash
from src.services.web_session_service import WebSessionService
from src.services.web_rate_limit_service import WebRateLimitService
from src.services.web_security import WebSecurityError
from src.services.authorization_service import AuthorizationService, AuthorizationDenied

PASSWORD = "Synthetic-Online!Password-123"
ORIGIN = "http://localhost:3001"


@pytest.fixture(scope="module")
def security_database():
    schema = "hcms_web_auth_test_" + uuid4().hex
    test_engine = engine.execution_options(schema_translate_map={None: schema})
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    try:
        Base.metadata.create_all(test_engine)
        yield sessionmaker(bind=test_engine, expire_on_commit=False)
    finally:
        assert re.fullmatch(r"hcms_web_auth_test_[a-f0-9]{32}", schema)
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))


@pytest.fixture(scope="module")
def credential_hash():
    return PasswordHasher().hash(PASSWORD)


@pytest.fixture
def environment(security_database, credential_hash):
    factory = security_database
    with factory() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        permissions = {code: Permission(code=code, name=name, module="Test", is_active=True)
                       for code, name in (APP | ATT | ADMIN).items()}
        db.add_all(permissions.values())
        roles = {
            "admin": Role(code="TEST_CHURCH_ADMIN", name="Church Administrator", is_active=True, permissions=list(permissions.values())),
            "officer": Role(code="TEST_MINISTRY_OFFICER", name="Ministry Officer", is_active=True,
                            permissions=[permissions[code] for code in {"MEMBERS_VIEW_OWN_MINISTRY", "MINISTRIES_VIEW_OWN", "ATTENDANCE_VIEW_OWN_MINISTRY", "ATTENDANCE_RECORD_OWN_MINISTRY"}]),
            "teacher": Role(code="TEST_SCHOOL_TEACHER", name="Sunday School Teacher", is_active=True,
                            permissions=[permissions[code] for code in TEACHER_PERMISSIONS]),
        }
        db.add_all(roles.values())
        ministries = {name: Ministry(code=name.upper(), name=name, is_active=True) for name in ["Youth", "Women", "Men", "Choir"]}
        db.add_all(ministries.values())
        member = Member(member_no="WEB-SYNTHETIC-0001", first_name="Ama", last_name="Synthetic", status=MemberStatus.ACTIVE)
        db.add(member); db.flush()
        users = {}
        for name, role in [("admin", "admin"), ("youth", "officer"), ("women", "officer"), ("secretary", "officer"), ("treasurer", "officer"), ("teacher", "teacher"), ("position_only", None)]:
            user = User(username=name, email=name+"@example.invalid", password_hash=credential_hash,
                        status=UserStatus.ACTIVE, roles=[roles[role]] if role else [],
                        member_id=member.id if name == "youth" else None)
            users[name] = user; db.add(user)
        db.flush()
        for name, scopes in [("youth", ["Youth"]), ("women", ["Women"]), ("secretary", ["Youth"]), ("treasurer", ["Youth", "Choir"])]:
            for scope in scopes:
                db.add(UserMinistryScope(user_id=users[name].id, ministry_id=ministries[scope].id,
                                        legacy_attendance_limits=False, is_active=True))
        school = SundaySchoolClass(name="Synthetic Primary", code="WEB_PRIMARY", status="ACTIVE")
        db.add(school); db.flush()
        db.add(SundaySchoolUserClassScope(user_id=users["teacher"].id, class_id=school.id))
        position = MinistryPosition(ministry_id=ministries["Youth"].id, code="WEB_LEADER", name="Youth Leader", is_active=True, is_leadership=True)
        db.add(position); db.flush()
        db.add(MinistryLeadershipAssignment(ministry_id=ministries["Youth"].id, position_id=position.id, member_id=member.id,
                                            position_name=position.name, position_code=position.code,
                                            start_date=datetime.now(timezone.utc).date(), is_current=True))
        db.commit()
    settings = OnlineSettings()
    app = create_app(settings)

    def database():
        with factory() as db:
            check_api_database_access(db)
            yield db
    app.dependency_overrides[get_db] = database

    @app.get("/test-permission", dependencies=[Depends(require_permission("MEMBERS_VIEW_ALL"))])
    def permission_probe():
        return {"allowed": True}

    @app.get("/test-any-permission", dependencies=[Depends(require_any_permission("MEMBERS_VIEW_ALL", "ATTENDANCE_VIEW_OWN_MINISTRY"))])
    def any_permission_probe():
        return {"allowed": True}

    @app.get("/test-ministry/{ministry_id}", dependencies=[Depends(require_ministry_permission("ATTENDANCE_VIEW_OWN_MINISTRY"))])
    def ministry_probe(ministry_id: UUID):
        return {"allowed": True}

    yield SimpleNamespace(factory=factory, app=app, users=users, ministries=ministries, member=member, school=school, settings=settings)


@pytest.fixture
def client(environment):
    with TestClient(environment.app, base_url="http://localhost") as client:
        yield client


def bootstrap(client):
    response = client.get("/api/v1/auth/csrf", headers={"Origin": ORIGIN})
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def login(client, username="admin", *, method="password", credential=PASSWORD):
    token = bootstrap(client)
    return client.post(f"/api/v1/auth/{method}-login",
        json={"email": username+"@example.invalid", "password" if method == "password" else "code": credential},
        headers={"Origin": ORIGIN, "X-CSRF-Token": token})


def session_for(environment, client):
    cookie = client.cookies.get(environment.settings.web_session_cookie_name)
    with environment.factory() as db:
        return db.scalar(select(WebSession).where(WebSession.session_hash == session_hash(cookie)))


def test_password_login_rotates_cookie_and_stores_only_hash(environment, client):
    original_csrf = bootstrap(client)
    original_cookie = client.cookies.get(environment.settings.web_session_cookie_name)
    response = login(client)
    assert response.status_code == 200
    assert response.json()["status"] == "authenticated"
    cookie = client.cookies.get(environment.settings.web_session_cookie_name)
    assert cookie != original_cookie
    assert response.json()["csrf_token"] != original_csrf
    record = session_for(environment, client)
    assert record.user_id == environment.users["admin"].id
    assert record.session_hash == hashlib.sha256(cookie.encode()).hexdigest()
    assert cookie not in record.session_hash
    with environment.factory() as db:
        previous = db.scalar(select(WebSession).where(WebSession.session_hash == session_hash(original_cookie)))
        assert previous.revoked_at is not None
        user = db.get(User, record.user_id)
        assert user.last_login_at is not None and user.failed_login_attempts == 0
        assert "WEB_LOGIN_SUCCESS" in set(db.scalars(select(SecurityAuditLog.action)))
        event = db.scalar(select(SecurityAuditLog).where(SecurityAuditLog.action == "WEB_LOGIN_SUCCESS"))
        assert event.actor_user_id == event.target_user_id == user.id
    assert client.get("/api/v1/me").status_code == 200
    assert original_cookie not in response.text and cookie not in response.text


def test_cookie_flags_are_http_only_host_only_and_no_remember_me(client):
    response = login(client)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie
    assert "domain=" not in cookie and "max-age=" not in cookie and "expires=" not in cookie


@pytest.mark.parametrize("status", [UserStatus.INACTIVE, UserStatus.SUSPENDED, UserStatus.LOCKED])
def test_inactive_suspended_and_permanently_locked_accounts_are_denied(environment, client, status):
    with environment.factory() as db:
        db.get(User, environment.users["admin"].id).status = status; db.commit()
    response = login(client)
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password."
    with environment.factory() as db:
        assert not db.scalars(select(WebSession).where(WebSession.user_id.is_not(None))).all()


def test_lockout_is_counted_and_success_resets_existing_policy(environment, client):
    for _ in range(5):
        assert login(client, credential="Wrong-Synthetic!Password").status_code == 401
    with environment.factory() as db:
        user = db.get(User, environment.users["admin"].id)
        assert user.failed_login_attempts == 5 and user.status == UserStatus.LOCKED
        assert user.locked_until > datetime.now(timezone.utc)
        user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1); db.commit()
    assert login(client).status_code == 200
    with environment.factory() as db:
        user = db.get(User, environment.users["admin"].id)
        assert user.status == UserStatus.ACTIVE and user.failed_login_attempts == 0 and user.locked_until is None


def test_unknown_email_and_wrong_password_use_identical_safe_errors(client):
    unknown = login(client, "unknown-person")
    wrong = login(client, credential="Wrong-Synthetic!Password")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


def test_temporary_password_cannot_bypass_required_desktop_change(environment, client):
    with environment.factory() as db:
        db.get(User, environment.users["admin"].id).require_password_change = True; db.commit()
    response = login(client)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"
    assert client.get("/api/v1/me").status_code == 401


def test_totp_is_an_alternative_login_and_secret_is_not_exposed(environment, client, caplog):
    secret = pyotp.random_base32()
    encrypted = TotpService().encrypt_secret(secret)
    with environment.factory() as db:
        user = db.get(User, environment.users["youth"].id)
        user.totp_enabled = True; user.totp_secret = encrypted; db.commit()
    code = pyotp.TOTP(secret).now()
    response = login(client, "youth", method="totp", credential=code)
    assert response.status_code == 200
    me = client.get("/api/v1/me")
    assert me.status_code == 200
    for value in [secret, encrypted, code]:
        assert value not in me.text + response.text + caplog.text
    with environment.factory() as db:
        assert "WEB_TOTP_LOGIN_SUCCESS" in set(db.scalars(select(SecurityAuditLog.action)))


@pytest.mark.parametrize("code", ["12345", "1234567", "abcdef", "", "\u0661\u0662\u0663\u0664\u0665\u0666"])
def test_malformed_totp_is_safe_validation_error(client, code):
    response = login(client, method="totp", credential=code)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "input" not in response.json()["error"]


def test_disabled_and_invalid_totp_are_denied_and_audited(environment, client):
    assert login(client, method="totp", credential="123456").status_code == 401
    secret = pyotp.random_base32()
    with environment.factory() as db:
        user = db.get(User, environment.users["admin"].id)
        user.totp_enabled = True; user.totp_secret = TotpService().encrypt_secret(secret); db.commit()
    invalid = next(f"{number:06d}" for number in range(10) if not TotpService().verify_plain(secret, f"{number:06d}"))
    assert login(client, method="totp", credential=invalid).status_code == 401
    with environment.factory() as db:
        assert db.get(User, environment.users["admin"].id).failed_login_attempts == 1
        assert list(db.scalars(select(SecurityAuditLog.action))).count("WEB_TOTP_LOGIN_FAILED") == 2


def test_logout_revokes_server_session_and_clears_cookie(environment, client):
    response = login(client)
    old_cookie = client.cookies.get(environment.settings.web_session_cookie_name)
    result = client.post("/api/v1/auth/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": response.json()["csrf_token"]})
    assert result.status_code == 200 and result.json() == {"status": "signed_out"}
    assert "max-age=0" in result.headers["set-cookie"].lower()
    assert client.get("/api/v1/me").status_code == 401
    client.cookies.set(environment.settings.web_session_cookie_name, old_cookie)
    assert client.get("/api/v1/me").status_code == 401
    with environment.factory() as db:
        assert "WEB_LOGOUT" in set(db.scalars(select(SecurityAuditLog.action)))


@pytest.mark.parametrize("reason", ["idle", "absolute", "revoked", "inactive", "suspended", "revision", "password_change"])
def test_invalidated_sessions_cannot_provide_access(environment, client, reason):
    assert login(client).status_code == 200
    record = session_for(environment, client)
    with environment.factory() as db:
        row = db.get(WebSession, record.id); user = db.get(User, row.user_id)
        if reason == "idle":
            row.created_at -= timedelta(hours=1); row.last_activity_at -= timedelta(minutes=31)
        elif reason == "absolute":
            row.created_at -= timedelta(hours=13); row.last_activity_at -= timedelta(hours=13); row.expires_at = datetime.now(timezone.utc)-timedelta(seconds=1)
        elif reason == "revoked": row.revoked_at = datetime.now(timezone.utc)
        elif reason == "revision": user.auth_revision += 1
        elif reason == "password_change": user.require_password_change = True
        else: user.status = UserStatus.INACTIVE if reason == "inactive" else UserStatus.SUSPENDED
        db.commit()
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert "max-age=0" in response.headers["set-cookie"].lower()
    with environment.factory() as db:
        row = db.get(WebSession, record.id)
        assert row.revoked_at is not None
        if reason != "revoked":
            expected = "WEB_SESSION_EXPIRED" if reason in {"idle", "absolute"} else "WEB_SESSION_REVOKED"
            assert expected in set(db.scalars(select(SecurityAuditLog.action)))
            event = db.scalar(select(SecurityAuditLog).where(SecurityAuditLog.action == expected))
            assert event.actor_user_id is None and event.target_user_id == user.id


@pytest.mark.parametrize("name,expected_scopes", [
    ("admin", set()), ("youth", {"Youth"}), ("women", {"Women"}),
    ("secretary", {"Youth"}), ("treasurer", {"Youth", "Choir"}), ("teacher", set()),
])
def test_me_uses_actual_roles_permissions_and_exact_scopes(environment, client, name, expected_scopes):
    assert login(client, name).status_code == 200
    response = client.get("/api/v1/me")
    assert response.status_code == 200
    profile = response.json()
    assert profile["id"] == str(environment.users[name].id)
    assert {row["name"] for row in profile["ministry_scopes"]} == expected_scopes
    assert "Men" not in {row["name"] for row in profile["ministry_scopes"]}
    with environment.factory() as db:
        access = AuthorizationService.load(db, environment.users[name].id)
        assert set(profile["permissions"]) == set(access.permissions)
    if name == "youth":
        assert profile["member"]["member_no"] == environment.member.member_no
        assert profile["member"]["photo_url"] is None
    else:
        assert profile["member"] is None
    if name == "teacher":
        assert {row["id"] for row in profile["sunday_school_scopes"]} == {str(environment.school.id)}
    for field in ["password_hash", "totp_secret", "failed_login_attempts", "auth_revision", "photo_path", "DB_PASSWORD"]:
        assert field not in response.text


def test_global_and_scoped_permission_dependencies_enforce_existing_rules(environment, client):
    assert login(client, "youth").status_code == 200
    assert client.get("/test-permission").status_code == 403
    assert client.get("/test-any-permission").status_code == 200
    assert client.get("/test-ministry/"+str(environment.ministries["Youth"].id)).status_code == 200
    assert client.get("/test-ministry/"+str(environment.ministries["Women"].id)).status_code == 403
    with TestClient(environment.app, base_url="http://localhost") as admin_client:
        assert login(admin_client).status_code == 200
        assert admin_client.get("/test-permission").status_code == 200
        assert admin_client.get("/test-ministry/"+str(environment.ministries["Women"].id)).status_code == 200


def test_multiple_devices_and_scoped_revocation_helper(environment, client):
    assert login(client, "youth").status_code == 200
    with TestClient(environment.app, base_url="http://localhost") as second:
        assert login(second, "youth").status_code == 200
        assert second.cookies.get(environment.settings.web_session_cookie_name) != client.cookies.get(environment.settings.web_session_cookie_name)
        with environment.factory() as db:
            actor = AuthorizationService.load(db, environment.users["youth"].id)
            with pytest.raises(AuthorizationDenied):
                WebSessionService(environment.settings).revoke_all(db, environment.users["admin"].id, actor)
            assert WebSessionService(environment.settings).revoke_all(db, actor.user_id, actor) == 2
        assert client.get("/api/v1/me").status_code == 401
        assert second.get("/api/v1/me").status_code == 401


def test_position_title_never_grants_permissions(environment, client):
    # No software role/scope is inferred from any church office or linked member.
    with environment.factory() as db:
        youth = db.get(User, environment.users["youth"].id)
        youth.member_id = None
        db.get(User, environment.users["position_only"].id).member_id = environment.member.id
        db.commit()
    assert login(client, "position_only").status_code == 200
    profile = client.get("/api/v1/me").json()
    assert profile["roles"] == [] and profile["permissions"] == [] and profile["ministry_scopes"] == []
    assert client.get("/test-permission").status_code == 403


@pytest.mark.parametrize("fault", ["missing", "wrong", "foreign", "forged_cookie"])
def test_login_csrf_cannot_be_bypassed(environment, client, fault):
    token = bootstrap(client)
    headers = {"Origin": ORIGIN, "X-CSRF-Token": token}
    if fault == "missing": headers.pop("X-CSRF-Token")
    elif fault == "wrong": headers["X-CSRF-Token"] = "0"*64
    elif fault == "foreign":
        with TestClient(environment.app, base_url="http://localhost") as other:
            headers["X-CSRF-Token"] = bootstrap(other)
    else:
        client.cookies.clear(); client.cookies.set(environment.settings.web_session_cookie_name, "A"*43)
        headers["X-CSRF-Token"] = csrf_token("A"*43)
    response = client.post("/api/v1/auth/password-login", json={"email":"admin@example.invalid", "password":PASSWORD}, headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_INVALID"
    with environment.factory() as db:
        assert db.get(User, environment.users["admin"].id).last_login_at is None


@pytest.mark.parametrize("origin", [None, "null", "http://unconfigured.example", "http://localhost:3002"])
def test_login_rejects_missing_or_untrusted_origins(environment, client, origin):
    token = bootstrap(client)
    headers = {"X-CSRF-Token": token}
    if origin is not None: headers["Origin"] = origin
    response = client.post("/api/v1/auth/password-login", json={"email":"admin@example.invalid", "password":PASSWORD}, headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"


def test_logout_rejects_missing_csrf_and_preserves_authenticated_session(client):
    assert login(client).status_code == 200
    response = client.post("/api/v1/auth/logout", headers={"Origin":ORIGIN})
    assert response.status_code == 403
    assert client.get("/api/v1/me").status_code == 200


def test_rotated_pre_session_and_csrf_cannot_be_replayed(environment, client):
    original_csrf = bootstrap(client)
    original_cookie = client.cookies.get(environment.settings.web_session_cookie_name)
    assert login(client).status_code == 200
    with TestClient(environment.app, base_url="http://localhost") as attacker:
        attacker.cookies.set(environment.settings.web_session_cookie_name, original_cookie)
        response = attacker.post("/api/v1/auth/password-login", json={"email":"admin@example.invalid", "password":PASSWORD},
                                 headers={"Origin":ORIGIN,"X-CSRF-Token":original_csrf})
        assert response.status_code == 403
        assert attacker.get("/api/v1/me").status_code == 401


def test_activity_updates_and_csrf_fetch_does_not_extend_idle_timeout(environment, client):
    assert login(client).status_code == 200
    record = session_for(environment, client)
    old_activity = datetime.now(timezone.utc)-timedelta(minutes=10)
    with environment.factory() as db:
        row = db.get(WebSession, record.id)
        row.created_at = old_activity-timedelta(minutes=1); row.last_activity_at = old_activity; db.commit()
    first = bootstrap(client); second = bootstrap(client)
    assert first == second
    assert session_for(environment, client).last_activity_at == old_activity
    assert client.get("/api/v1/me").status_code == 200
    assert session_for(environment, client).last_activity_at > old_activity


def test_fresh_permissions_and_scope_updates_are_used_on_each_request(environment, client):
    assert login(client, "youth").status_code == 200
    with environment.factory() as db:
        permission = db.scalar(select(Permission).where(Permission.code == "ATTENDANCE_VIEW_OWN_MINISTRY"))
        permission.is_active = False
        scope = db.scalar(select(UserMinistryScope).where(UserMinistryScope.user_id == environment.users["youth"].id))
        scope.is_active = False; db.commit()
    profile = client.get("/api/v1/me").json()
    assert "ATTENDANCE_VIEW_OWN_MINISTRY" not in profile["permissions"]
    assert profile["ministry_scopes"] == []
    assert client.get("/test-ministry/"+str(environment.ministries["Youth"].id)).status_code == 403


def test_duplicate_cookie_names_and_bearer_transport_are_rejected(environment, client):
    assert login(client).status_code == 200
    cookie = client.cookies.get(environment.settings.web_session_cookie_name)
    name = environment.settings.web_session_cookie_name
    response = client.get("/api/v1/me", headers={"Cookie":f"{name}={cookie}; {name} ={cookie}"})
    assert response.status_code == 401
    with TestClient(environment.app, base_url="http://localhost") as other:
        assert other.get("/api/v1/me", headers={"Authorization":"Bearer "+cookie}).status_code == 401


def test_cookie_secure_prefix_and_https_production_configuration(environment):
    settings = replace(environment.settings, app_env="production", api_allowed_hosts=("api.example.org",),
                       api_docs_enabled=False, web_public_origin="", web_portal_origin="https://portal.example.org",
                       web_cookie_secure=True, web_session_cookie_name=None)
    app = create_app(settings); app.dependency_overrides.update(environment.app.dependency_overrides)
    with TestClient(app, base_url="https://api.example.org") as client:
        response = client.get("/api/v1/auth/csrf", headers={"Origin":"https://portal.example.org"})
        assert response.status_code == 200
        cookie = response.headers["set-cookie"].lower()
        assert cookie.startswith("__host-hopfan_session=")
        assert "secure" in cookie and "httponly" in cookie and "domain=" not in cookie
        assert client.post("/api/v1/auth/password-login", json={"email":"admin@example.invalid","password":PASSWORD},
                           headers={"Origin":"https://portal.example.org","X-CSRF-Token":response.json()["csrf_token"]}).status_code == 200
        assert client.get("/api/v1/me").status_code == 200


@pytest.mark.parametrize("unsafe", ["insecure", "unprefixed", "samesite_none", "zero_timeout", "zero_rate"])
def test_unsafe_cookie_session_and_rate_settings_are_rejected(unsafe):
    values = dict(app_env="production", web_public_origin="", web_portal_origin="", api_allowed_hosts=("api.example.org",))
    if unsafe == "insecure": values["web_cookie_secure"] = False
    elif unsafe == "unprefixed": values["web_session_cookie_name"] = "unprefixed_session"
    elif unsafe == "samesite_none": values["web_cookie_samesite"] = "none"
    elif unsafe == "zero_timeout": values["web_session_idle_minutes"] = 0
    else: values["web_login_rate_ip_limit"] = 0
    with pytest.raises(ValueError): OnlineSettings(**values)


def test_cors_allows_credentialed_post_only_from_configured_origin(client):
    response = client.options("/api/v1/auth/password-login", headers={
        "Origin":ORIGIN,"Access-Control-Request-Method":"POST","Access-Control-Request-Headers":"Content-Type,X-CSRF-Token",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["access-control-allow-origin"] == ORIGIN
    rejected = client.options("/api/v1/auth/password-login", headers={"Origin":"http://unconfigured.example","Access-Control-Request-Method":"POST"})
    assert rejected.status_code == 400 and "access-control-allow-origin" not in rejected.headers


def test_account_rate_limit_is_shared_between_api_instances(environment, client):
    settings = replace(environment.settings, web_login_rate_account_limit=1)
    environment.app.state.settings = settings
    assert login(client).status_code == 200
    other_app = create_app(settings); other_app.dependency_overrides.update(environment.app.dependency_overrides)
    with TestClient(other_app, base_url="http://localhost", client=("another-peer",50000)) as other:
        response = login(other)
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "RATE_LIMITED"
        assert int(response.headers["retry-after"]) > 0


def test_ip_limit_ignores_untrusted_forwarded_headers_and_does_not_weaken_lockout(environment, client):
    environment.app.state.settings = replace(environment.settings, web_login_rate_ip_limit=1)
    assert login(client, credential="Wrong-Synthetic!Password").status_code == 401
    client.headers["X-Forwarded-For"] = "203.0.113.99"
    response = login(client, "youth")
    assert response.status_code == 429
    with environment.factory() as db:
        assert db.get(User, environment.users["admin"].id).failed_login_attempts == 1


def test_csrf_bootstrap_is_rate_limited(environment, client):
    environment.app.state.settings = replace(environment.settings, web_csrf_rate_ip_limit=1)
    assert client.get("/api/v1/auth/csrf").status_code == 200
    assert client.get("/api/v1/auth/csrf").status_code == 429


def test_session_secret_password_totp_and_headers_are_never_logged(environment, client, caplog):
    response = login(client)
    secret = client.cookies.get(environment.settings.web_session_cookie_name)
    token = response.json()["csrf_token"]
    assert client.get("/api/v1/me?password="+PASSWORD, headers={"X-Request-ID":secret}).status_code == 200
    for value in [PASSWORD, secret, token]:
        assert value not in caplog.text
    with environment.factory() as db:
        events = [event.new_values for event in db.scalars(select(SecurityAuditLog))]
        for value in [PASSWORD, secret, token]:
            assert all(value not in event for event in events)


def test_rate_limit_counts_are_atomic_under_concurrent_workers(environment):
    from concurrent.futures import ThreadPoolExecutor
    settings = replace(environment.settings, web_login_rate_ip_limit=3, web_login_rate_account_limit=3)
    def attempt(_index):
        with environment.factory() as db:
            try:
                WebRateLimitService.login(db, settings, "synthetic-concurrent-peer", "concurrent@example.invalid")
                return 200
            except WebSecurityError as error:
                return error.status
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(attempt, range(6)))
    assert results.count(200) == 3 and results.count(429) == 3


def test_rate_window_expiry_restores_quota(environment, client):
    environment.app.state.settings = replace(environment.settings, web_login_rate_account_limit=1)
    assert login(client).status_code == 200
    assert login(client).status_code == 429
    with environment.factory() as db:
        for bucket in db.scalars(select(WebRateLimit)):
            bucket.window_started_at = datetime.now(timezone.utc)-timedelta(minutes=20)
            bucket.expires_at = datetime.now(timezone.utc)-timedelta(seconds=1)
        db.commit()
    assert login(client).status_code == 200
