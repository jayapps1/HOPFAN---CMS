from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user, get_db, require_login_csrf
from src.api.schemas.auth import CsrfResponse, LoginResponse, LogoutResponse, PasswordLoginRequest, TotpLoginRequest
from src.api.security.csrf import require_trusted_origin
from src.api.security.session import clear_session_cookie, read_session_cookie, set_session_cookie
from src.api.v1 import API_PREFIX
from src.services.web_auth_service import WebAuthService
from src.services.web_rate_limit_service import WebRateLimitService
from src.services.web_session_service import WebPrincipal, WebSessionService
from src.services.web_security import csrf_token

router = APIRouter(prefix=API_PREFIX + "/auth", tags=["Authentication"], dependencies=[Depends(require_trusted_origin)])
Database = Annotated[Session, Depends(get_db, scope="function")]
LoginCookie = Annotated[str, Depends(require_login_csrf)]


def _peer(request: Request) -> str:
    # Only Uvicorn may interpret forwarded IPs, with explicit proxy trust.
    return request.client.host if request.client else "unknown"


@router.get("/csrf", response_model=CsrfResponse)
def csrf(request: Request, response: Response, db: Database) -> CsrfResponse:
    settings = request.app.state.settings
    WebRateLimitService.bootstrap(db, settings, _peer(request))
    secret, authenticated, changed = WebSessionService(settings).bootstrap(db, read_session_cookie(request))
    if changed:
        set_session_cookie(response, secret, settings)
    return CsrfResponse(csrf_token=csrf_token(secret), authenticated=authenticated)


@router.post("/password-login", response_model=LoginResponse)
def password_login(body: PasswordLoginRequest, request: Request, response: Response, db: Database, cookie: LoginCookie) -> LoginResponse:
    settings = request.app.state.settings
    WebRateLimitService.login(db, settings, _peer(request), body.email)
    secret = WebAuthService(settings).login(db, body.email, body.password.get_secret_value(), cookie,
                                          request.headers["X-CSRF-Token"], method="password")
    set_session_cookie(response, secret, settings)
    return LoginResponse(csrf_token=csrf_token(secret))


@router.post("/totp-login", response_model=LoginResponse)
def totp_login(body: TotpLoginRequest, request: Request, response: Response, db: Database, cookie: LoginCookie) -> LoginResponse:
    settings = request.app.state.settings
    WebRateLimitService.login(db, settings, _peer(request), body.email)
    secret = WebAuthService(settings).login(db, body.email, body.code.get_secret_value(), cookie,
                                          request.headers["X-CSRF-Token"], method="totp")
    set_session_cookie(response, secret, settings)
    return LoginResponse(csrf_token=csrf_token(secret))


@router.post("/logout", response_model=LogoutResponse)
def logout(request: Request, response: Response, db: Database,
           principal: Annotated[WebPrincipal, Depends(get_current_user)]) -> LogoutResponse:
    WebSessionService(request.app.state.settings).logout(db, principal)
    clear_session_cookie(response, request.app.state.settings)
    return LogoutResponse()
