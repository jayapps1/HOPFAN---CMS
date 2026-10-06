from collections.abc import Generator
from typing import Annotated, Callable

from fastapi import Depends, Request

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.services.api_readiness_service import (
    DatabaseAccessUnsafe, DatabaseUnavailable, check_api_database_access,
)
from src.api.security.csrf import require_trusted_origin
from src.api.security.session import read_session_cookie
from src.services.web_session_service import WebPrincipal, WebSessionService
from src.services.web_security import WebSecurityError, authentication_required


def get_db() -> Generator[Session, None, None]:
    """One existing SessionLocal session per request; always close it.

    Load database configuration lazily so process liveness stays available even
    when database configuration or connectivity is unavailable.
    """
    db: Session | None = None
    try:
        try:
            from src.config.database import SessionLocal

            db = SessionLocal()
            check_api_database_access(db)
        except DatabaseAccessUnsafe:
            raise
        except Exception:
            raise DatabaseUnavailable() from None
        yield db
    finally:
        if db is not None:
            db.close()


def require_login_csrf(
    request: Request,
    origin: Annotated[None, Depends(require_trusted_origin)],
    db: Annotated[Session, Depends(get_db, scope="function")],
) -> str:
    cookie = read_session_cookie(request)
    WebSessionService(request.app.state.settings).require_csrf(db, cookie, request.headers.get("X-CSRF-Token"))
    return cookie


def get_current_user(
    request: Request,
    origin: Annotated[None, Depends(require_trusted_origin)],
    db: Annotated[Session, Depends(get_db, scope="function")],
) -> WebPrincipal:
    cookie = read_session_cookie(request)
    if cookie is None:
        raise authentication_required()
    sessions = WebSessionService(request.app.state.settings)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        sessions.require_csrf(db, cookie, request.headers.get("X-CSRF-Token"))
    principal = sessions.resolve(db, cookie)
    db.commit()
    return principal


def require_permission(permission: str) -> Callable:
    def dependency(principal: Annotated[WebPrincipal, Depends(get_current_user)]) -> WebPrincipal:
        from src.services.authorization_service import AuthorizationDenied
        try:
            principal.authorization.require_permission(permission)
        except AuthorizationDenied:
            raise WebSecurityError(403, "ACCESS_DENIED", "Access to this resource is denied.") from None
        return principal
    return dependency


def require_any_permission(*permissions: str) -> Callable:
    def dependency(principal: Annotated[WebPrincipal, Depends(get_current_user)]) -> WebPrincipal:
        if not principal.authorization.has_any(permissions):
            raise WebSecurityError(403, "ACCESS_DENIED", "Access to this resource is denied.")
        return principal
    return dependency


def require_ministry_permission(permission: str, parameter: str = "ministry_id") -> Callable:
    def dependency(request: Request, principal: Annotated[WebPrincipal, Depends(get_current_user)]) -> WebPrincipal:
        from src.services.authorization_service import AuthorizationDenied
        try:
            principal.authorization.require_ministry_permission(request.path_params.get(parameter), permission)
        except AuthorizationDenied:
            raise WebSecurityError(403, "ACCESS_DENIED", "Access to this resource is denied.") from None
        return principal
    return dependency


def get_workspace(
    db: Annotated[Session, Depends(get_db, scope="function")],
    principal: Annotated[WebPrincipal, Depends(get_current_user)],
):
    # Keep domain imports lazy: health/startup do not require DB configuration.
    from src.services.online_workspace_service import OnlineWorkspaceService
    from src.services.authorization_service import AuthorizationDenied
    from src.security.attendance_permissions import AttendancePermissionError
    from src.services.member_service import MemberServiceError
    from src.services.ministry_service import MinistryServiceError
    from src.services.sunday_school_base import SundaySchoolError
    from src.services.attendance_service import AttendanceServiceError
    try:
        yield OnlineWorkspaceService(db, principal)
    except (AuthorizationDenied, AttendancePermissionError):
        raise WebSecurityError(403, "ACCESS_DENIED", "Access to this resource is denied.") from None
    except (MemberServiceError, MinistryServiceError, SundaySchoolError, AttendanceServiceError) as exc:
        if isinstance(exc.__cause__, SQLAlchemyError):
            raise WebSecurityError(503, "DATABASE_UNAVAILABLE", "HOPFAN is temporarily unavailable.") from None
        raise WebSecurityError(404, "RESOURCE_NOT_FOUND", "The requested resource was not found.") from None


def get_operations(
    db: Annotated[Session, Depends(get_db, scope="function")],
    principal: Annotated[WebPrincipal, Depends(get_current_user)],
):
    from sqlalchemy.exc import IntegrityError
    from src.services.online_operations_service import OnlineOperationsService
    from src.services.authorization_service import AuthorizationDenied
    from src.services.operation_errors import OperationConflict, OperationNotFound
    from src.services.attendance_service import AttendanceServiceError
    from src.services.sunday_school_base import SundaySchoolError
    try:
        yield OnlineOperationsService(db,principal)
    except AuthorizationDenied:
        raise WebSecurityError(403,"ACCESS_DENIED","Access to this resource is denied.") from None
    except OperationConflict:
        raise WebSecurityError(409,"OPERATION_CONFLICT","This record changed or already exists. Refresh and try again.") from None
    except OperationNotFound:
        raise WebSecurityError(404,"RESOURCE_NOT_FOUND","The requested resource was not found.") from None
    except (AttendanceServiceError,SundaySchoolError) as exc:
        if isinstance(exc.__cause__,IntegrityError):
            raise WebSecurityError(409,"OPERATION_CONFLICT","This record changed or already exists. Refresh and try again.") from None
        if isinstance(exc.__cause__,SQLAlchemyError):
            raise WebSecurityError(503,"DATABASE_UNAVAILABLE","HOPFAN is temporarily unavailable.") from None
        raise WebSecurityError(400,"BUSINESS_RULE_VIOLATION","This operation is unavailable in the current state. Check the fields and refresh.") from None
