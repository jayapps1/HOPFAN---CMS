"""HTTP-independent orchestration around the existing desktop AuthService."""
from contextlib import contextmanager

from sqlalchemy.orm import Session

from src.config.online_settings import OnlineSettings
from src.services.web_session_service import WebSessionService
from src.services.web_security import WebSecurityError


class WebAuthService:
    def __init__(self, settings: OnlineSettings):
        self.sessions = WebSessionService(settings)

    def login(self, db: Session, email: str, credential: str, cookie: str, csrf: str, *, method: str) -> str:
        # Lazy import keeps liveness independent of missing DB/auth configuration.
        from src.services.auth_service import AuthService, AuthenticationError

        @contextmanager
        def borrowed_session():
            # AuthService owns its existing commits; the request dependency owns
            # final close. No second engine, session factory, or identity store.
            yield db

        action = "WEB_TOTP_LOGIN_FAILED" if method == "totp" else "WEB_LOGIN_FAILED"
        service = AuthService(session_factory=borrowed_session)
        try:
            user = (service.authenticate_totp_only(email, credential) if method == "totp"
                    else service.authenticate_password(email, credential))
            return self.sessions.create_authenticated(db, user.id, cookie, csrf, method)
        except AuthenticationError:
            self.sessions.audit(db, action, reason="INVALID_CREDENTIALS")
            db.commit()
            raise WebSecurityError(401, "INVALID_CREDENTIALS",
                "Invalid authenticator code." if method == "totp" else "Invalid email or password.") from None
        except WebSecurityError as error:
            self.sessions.audit(db, action, reason=error.code)
            db.commit()
            raise
