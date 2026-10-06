from fastapi import Request

from src.services.web_security import WebSecurityError


def require_trusted_origin(request: Request) -> None:
    origins = request.headers.getlist("origin")
    unsafe = request.method not in {"GET", "HEAD", "OPTIONS"}
    if not origins and not unsafe:
        return
    settings = request.app.state.settings
    same_origin = f"{request.url.scheme}://{request.url.netloc}"
    if (len(origins) != 1 or origins[0] not in {*settings.cors_origins, same_origin}
            or settings.app_env != "development" and not origins[0].startswith("https://")):
        raise WebSecurityError(403, "ORIGIN_NOT_ALLOWED", "The request origin is not allowed.")
