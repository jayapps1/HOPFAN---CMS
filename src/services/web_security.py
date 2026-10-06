"""Framework-independent session credentials, CSRF binding and safe errors."""
import hashlib
import hmac
import re
import secrets


class WebSecurityError(Exception):
    def __init__(self, status: int, code: str, message: str, *, clear_cookie: bool = False, retry_after: int | None = None):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.clear_cookie, self.retry_after = clear_cookie, retry_after


def authentication_required(*, clear_cookie: bool = True) -> WebSecurityError:
    return WebSecurityError(401, "AUTHENTICATION_REQUIRED", "Sign in to access this resource.", clear_cookie=clear_cookie)


def csrf_denied() -> WebSecurityError:
    return WebSecurityError(403, "CSRF_INVALID", "Refresh the sign-in page and try again.")


def new_session_secret() -> str:
    return secrets.token_urlsafe(32)


def session_hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("ascii")).hexdigest()


def valid_session_secret(secret: str | None) -> bool:
    return isinstance(secret, str) and re.fullmatch(r"[A-Za-z0-9_-]{43}", secret) is not None


def csrf_token(secret: str) -> str:
    # Domain-separated one-way derivation: a CSRF token does not reveal the
    # HttpOnly session secret, and remains stable across legitimate browser tabs.
    return hmac.new(secret.encode("ascii"), b"HOPFAN browser CSRF v1", hashlib.sha256).hexdigest()


def valid_csrf(secret: str, supplied: str | None) -> bool:
    return isinstance(supplied, str) and re.fullmatch(r"[0-9a-f]{64}", supplied) is not None and hmac.compare_digest(csrf_token(secret), supplied)
