import re

from fastapi import Request, Response

from src.config.online_settings import OnlineSettings
from src.services.web_security import authentication_required


def read_session_cookie(request: Request) -> str | None:
    name = request.app.state.settings.web_session_cookie_name
    # Reject duplicate names rather than guessing which browser cookie is valid.
    matches = sum(len(re.findall(r"(?:^|;\s*)" + re.escape(name) + r"\s*=", header))
                  for header in request.headers.getlist("cookie"))
    if matches > 1:
        raise authentication_required()
    return request.cookies.get(name)


def set_session_cookie(response: Response, secret: str, settings: OnlineSettings) -> None:
    response.set_cookie(str(settings.web_session_cookie_name), secret, path="/", domain=None,
                        secure=bool(settings.web_cookie_secure), httponly=True,
                        samesite=settings.web_cookie_samesite)


def clear_session_cookie(response: Response, settings: OnlineSettings) -> None:
    response.delete_cookie(str(settings.web_session_cookie_name), path="/", domain=None,
                           secure=bool(settings.web_cookie_secure), httponly=True,
                           samesite=settings.web_cookie_samesite)
