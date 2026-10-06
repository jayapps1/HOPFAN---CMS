"""Atomic PostgreSQL rate buckets shared across API processes and workers."""
from datetime import datetime, timedelta, timezone
import hashlib

from sqlalchemy import case, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.config.online_settings import OnlineSettings
from src.models.user_session import WebRateLimit
from src.services.web_security import WebSecurityError


class WebRateLimitService:
    @staticmethod
    def consume(db: Session, buckets: list[tuple[str, str, int, int]]) -> None:
        now = datetime.now(timezone.utc)
        retry_after = 0
        for kind, subject, limit, seconds in buckets:
            key = hashlib.sha256((kind + "\0" + subject).encode("utf-8")).hexdigest()
            expires = now + timedelta(seconds=seconds)
            fresh = WebRateLimit.expires_at <= now
            statement = insert(WebRateLimit).values(
                bucket_hash=key, window_started_at=now, expires_at=expires, request_count=1,
            ).on_conflict_do_update(
                index_elements=[WebRateLimit.bucket_hash],
                set_={
                    "window_started_at": case((fresh, now), else_=WebRateLimit.window_started_at),
                    "expires_at": case((fresh, expires), else_=WebRateLimit.expires_at),
                    "request_count": case((fresh, 1), else_=WebRateLimit.request_count + 1),
                },
            ).returning(WebRateLimit.request_count, WebRateLimit.expires_at)
            count, bucket_expiry = db.execute(statement).one()
            if count > limit:
                retry_after = max(retry_after, max(1, int((bucket_expiry - now).total_seconds()) + 1))
        # Count unsuccessful attempts too; this does not commit credentials or
        # session changes because callers run the limiter before authentication.
        db.commit()
        if retry_after:
            raise WebSecurityError(429, "RATE_LIMITED", "Too many attempts. Try again later.", retry_after=retry_after)

    @classmethod
    def login(cls, db: Session, settings: OnlineSettings, peer: str, login: str) -> None:
        cls.consume(db, [
            ("login-ip", peer, settings.web_login_rate_ip_limit, settings.web_login_rate_window_seconds),
            ("login-account", login.strip().casefold(), settings.web_login_rate_account_limit, settings.web_login_rate_window_seconds),
        ])

    @classmethod
    def bootstrap(cls, db: Session, settings: OnlineSettings, peer: str) -> None:
        cls.consume(db, [("csrf-ip", peer, settings.web_csrf_rate_ip_limit, settings.web_csrf_rate_window_seconds)])

    @staticmethod
    def purge_expired(db: Session) -> int:
        """Maintenance hook for a trusted scheduler; no public cleanup endpoint."""
        result = db.execute(delete(WebRateLimit).where(WebRateLimit.expires_at < datetime.now(timezone.utc)))
        db.commit()
        return result.rowcount
