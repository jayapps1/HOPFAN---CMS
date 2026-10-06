"""Browser security metadata referencing the existing User identity."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base


class WebSession(Base):
    __tablename__ = "web_sessions"
    __table_args__ = (
        CheckConstraint("session_hash ~ '^[0-9a-f]{64}$'", name="ck_web_session_hash"),
        CheckConstraint("(user_id IS NULL AND auth_revision IS NULL AND login_method='anonymous') OR "
                        "(user_id IS NOT NULL AND auth_revision IS NOT NULL AND auth_revision >= 0 AND login_method IN ('password','totp'))",
                        name="ck_web_session_identity"),
        CheckConstraint("expires_at > created_at AND last_activity_at >= created_at", name="ck_web_session_dates"),
        CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="ck_web_session_revoked_date"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # A short-lived anonymous pre-session protects login itself against CSRF.
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    session_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    auth_revision: Mapped[int | None] = mapped_column(Integer)
    login_method: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(32))


class WebRateLimit(Base):
    __tablename__ = "web_rate_limits"
    __table_args__ = (
        CheckConstraint("bucket_hash ~ '^[0-9a-f]{64}$'", name="ck_web_rate_hash"),
        CheckConstraint("request_count > 0", name="ck_web_rate_count"),
        CheckConstraint("expires_at > window_started_at", name="ck_web_rate_dates"),
    )
    bucket_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False)
