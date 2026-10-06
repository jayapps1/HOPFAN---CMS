"""Online settings share HOPFAN's .env loader; no database configuration here."""
import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from src.config.environment import load_environment


def _boolean(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    if value.lower() in {"true", "1"}:
        return True
    if value.lower() in {"false", "0"}:
        return False
    raise ValueError(f"{name} must be true or false.")


def _integer(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        raise ValueError(f"{name} must be an integer.") from None


def _validate_origin(value: str, *, require_https: bool) -> None:
    if not value:
        return
    try:
        url = urlsplit(value)
        valid = (
            value.isascii() and not any(char.isspace() for char in value)
            and "*" not in value and url.scheme in {"http", "https"}
            and url.hostname and url.port != 0
            and not url.username and not url.password
            and not url.path and not url.query and not url.fragment
            and (not require_https or url.scheme == "https")
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Web origins must be exact HTTP(S) origins; staging/production require HTTPS.")


@dataclass(frozen=True)
class OnlineSettings:
    app_env: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_debug: bool = False
    api_docs_enabled: bool = True
    web_public_origin: str = "http://localhost:3000"
    web_portal_origin: str = "http://localhost:3001"
    api_allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost")
    web_session_idle_minutes: int = 30
    web_session_max_hours: int = 12
    web_csrf_session_minutes: int = 10
    web_cookie_secure: bool | None = None
    web_cookie_samesite: str = "lax"
    web_session_cookie_name: str | None = None
    web_login_rate_window_seconds: int = 900
    web_login_rate_ip_limit: int = 30
    web_login_rate_account_limit: int = 10
    web_csrf_rate_window_seconds: int = 60
    web_csrf_rate_ip_limit: int = 60

    def __post_init__(self) -> None:
        if self.app_env not in {"development", "staging", "production"}:
            raise ValueError("APP_ENV must be development, staging, or production.")
        if not 1 <= self.api_port <= 65535:
            raise ValueError("API_PORT must be between 1 and 65535.")
        if not re.fullmatch(r"[A-Za-z0-9.:-]+", self.api_host):
            raise ValueError("API_HOST must be a hostname or bind address.")
        if not self.api_allowed_hosts or any(
            not re.fullmatch(r"[A-Za-z0-9.-]+", host) for host in self.api_allowed_hosts
        ):
            raise ValueError("API_ALLOWED_HOSTS must contain exact hostnames without ports or wildcards.")
        if self.app_env != "development" and self.api_debug:
            raise ValueError("API_DEBUG must be false in staging and production.")
        for origin in self.cors_origins:
            _validate_origin(origin, require_https=self.app_env != "development")
        if self.web_cookie_secure is None:
            object.__setattr__(self, "web_cookie_secure", self.app_env != "development")
        if self.web_session_cookie_name is None:
            object.__setattr__(self, "web_session_cookie_name", (
                "__Host-hopfan_session" if self.web_cookie_secure else "hopfan_session"
            ))
        if self.app_env != "development" and not self.web_cookie_secure:
            raise ValueError("WEB_COOKIE_SECURE must be true in staging and production.")
        if self.web_cookie_samesite not in {"lax", "strict"}:
            raise ValueError("WEB_COOKIE_SAMESITE must be lax or strict.")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.web_session_cookie_name):
            raise ValueError("WEB_SESSION_COOKIE_NAME must be a valid cookie name.")
        if self.web_session_cookie_name.startswith("__Host-") and not self.web_cookie_secure:
            raise ValueError("A __Host- session cookie requires Secure=true.")
        if self.app_env != "development" and not self.web_session_cookie_name.startswith("__Host-"):
            raise ValueError("Staging and production require a __Host- session cookie name.")
        limits = {
            "WEB_SESSION_IDLE_MINUTES": (self.web_session_idle_minutes, 1, 1440),
            "WEB_SESSION_MAX_HOURS": (self.web_session_max_hours, 1, 168),
            "WEB_CSRF_SESSION_MINUTES": (self.web_csrf_session_minutes, 1, 60),
            "WEB_LOGIN_RATE_WINDOW_SECONDS": (self.web_login_rate_window_seconds, 1, 86400),
            "WEB_LOGIN_RATE_IP_LIMIT": (self.web_login_rate_ip_limit, 1, 10000),
            "WEB_LOGIN_RATE_ACCOUNT_LIMIT": (self.web_login_rate_account_limit, 1, 1000),
            "WEB_CSRF_RATE_WINDOW_SECONDS": (self.web_csrf_rate_window_seconds, 1, 3600),
            "WEB_CSRF_RATE_IP_LIMIT": (self.web_csrf_rate_ip_limit, 1, 10000),
        }
        for name, (value, minimum, maximum) in limits.items():
            if not minimum <= value <= maximum:
                raise ValueError(f"{name} is outside its supported positive range.")

    @property
    def cors_origins(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(origin for origin in (
            self.web_public_origin, self.web_portal_origin
        ) if origin))

    @classmethod
    def from_environment(cls) -> "OnlineSettings":
        load_environment()
        environment = os.getenv("APP_ENV", "development").lower()
        development = environment == "development"
        try:
            port = int(os.getenv("API_PORT", "8000"))
        except ValueError:
            raise ValueError("API_PORT must be an integer.") from None
        hosts = os.getenv("API_ALLOWED_HOSTS", "127.0.0.1,localhost" if development else "")
        return cls(
            app_env=environment,
            api_host=os.getenv("API_HOST", "127.0.0.1"),
            api_port=port,
            api_debug=_boolean("API_DEBUG", False),
            api_docs_enabled=_boolean("API_DOCS_ENABLED", development),
            web_public_origin=os.getenv("WEB_PUBLIC_ORIGIN", "http://localhost:3000" if development else ""),
            web_portal_origin=os.getenv("WEB_PORTAL_ORIGIN", "http://localhost:3001" if development else ""),
            api_allowed_hosts=tuple(host.strip().lower() for host in hosts.split(",") if host.strip()),
            web_session_idle_minutes=_integer("WEB_SESSION_IDLE_MINUTES", 30),
            web_session_max_hours=_integer("WEB_SESSION_MAX_HOURS", 12),
            web_csrf_session_minutes=_integer("WEB_CSRF_SESSION_MINUTES", 10),
            web_cookie_secure=_boolean("WEB_COOKIE_SECURE", not development),
            web_cookie_samesite=os.getenv("WEB_COOKIE_SAMESITE", "lax").lower(),
            web_session_cookie_name=os.getenv("WEB_SESSION_COOKIE_NAME") or None,
            web_login_rate_window_seconds=_integer("WEB_LOGIN_RATE_WINDOW_SECONDS", 900),
            web_login_rate_ip_limit=_integer("WEB_LOGIN_RATE_IP_LIMIT", 30),
            web_login_rate_account_limit=_integer("WEB_LOGIN_RATE_ACCOUNT_LIMIT", 10),
            web_csrf_rate_window_seconds=_integer("WEB_CSRF_RATE_WINDOW_SECONDS", 60),
            web_csrf_rate_ip_limit=_integer("WEB_CSRF_RATE_IP_LIMIT", 60),
        )
