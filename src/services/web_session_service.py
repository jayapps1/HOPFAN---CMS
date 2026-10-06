"""Persisted browser sessions; authentication and RBAC remain existing services."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.config.online_settings import OnlineSettings
from src.models import User, SecurityAuditLog, WebSession
from src.services.web_security import (
    WebSecurityError, authentication_required, csrf_denied, new_session_secret,
    session_hash, valid_csrf, valid_session_secret,
)

if TYPE_CHECKING:
    from src.services.authorization_service import AuthorizationContext


@dataclass(frozen=True)
class WebPrincipal:
    user: User
    session_id: UUID
    authorization: AuthorizationContext


class WebSessionService:
    def __init__(self, settings: OnlineSettings):
        self.settings = settings

    @staticmethod
    def audit(db: Session, action: str, *, user_id: UUID | None = None, actor_id: UUID | None = None,
              session_id: UUID | None = None, reason: str | None = None) -> None:
        values = {}
        if session_id is not None:
            values["session_id"] = str(session_id)  # Public UUID, never cookie/hash.
        if reason is not None:
            values["reason"] = reason
        db.add(SecurityAuditLog(actor_user_id=actor_id, target_user_id=user_id,
                                action=action, new_values=json.dumps(values, sort_keys=True)))

    @staticmethod
    def _find(db: Session, secret: str | None, *, lock: bool = False) -> WebSession | None:
        if not valid_session_secret(secret):
            return None
        query = select(WebSession).where(WebSession.session_hash == session_hash(secret))
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return db.scalar(query)

    def _expired(self, row: WebSession, now: datetime) -> str | None:
        if now >= row.expires_at:
            return "ABSOLUTE_EXPIRED"
        if row.user_id is not None and now - row.last_activity_at >= timedelta(minutes=self.settings.web_session_idle_minutes):
            return "IDLE_EXPIRED"
        return None

    def _revoke(self, db: Session, row: WebSession, reason: str, now: datetime, *, actor_id: UUID | None = None) -> None:
        if row.revoked_at is not None:
            return
        row.revoked_at, row.revocation_reason = now, reason
        if row.user_id is not None:
            self.audit(db, "WEB_SESSION_EXPIRED" if reason.endswith("EXPIRED") else "WEB_SESSION_REVOKED",
                       user_id=row.user_id, actor_id=actor_id, session_id=row.id, reason=reason)

    def require_csrf(self, db: Session, secret: str | None, supplied: str | None) -> None:
        row = self._find(db, secret)
        now = datetime.now(timezone.utc)
        if row is None or row.revoked_at is not None or self._expired(row, now) or not valid_csrf(secret, supplied):
            raise csrf_denied()

    def resolve(self, db: Session, secret: str | None, *, touch: bool = True) -> WebPrincipal:
        from src.services.authorization_service import AuthorizationService, AuthorizationDenied

        row = self._find(db, secret)
        if row is None:
            raise authentication_required()
        if row.user_id is None:
            raise authentication_required(clear_cookie=row.revoked_at is not None or bool(self._expired(row, datetime.now(timezone.utc))))
        # All authenticated session operations lock user first, then session.
        # This serializes account changes and avoids logout/activity races.
        user = db.scalar(select(User).where(User.id == row.user_id).with_for_update().execution_options(populate_existing=True))
        row = self._find(db, secret, lock=True)
        now = datetime.now(timezone.utc)
        if row is None or row.revoked_at is not None:
            raise authentication_required()
        expired = self._expired(row, now)
        if expired:
            self._revoke(db, row, expired, now); db.commit()
            raise authentication_required()
        try:
            access = AuthorizationService.load(db, row.user_id)
        except AuthorizationDenied:
            self._revoke(db, row, "ACCOUNT_CHANGED", now); db.commit()
            raise authentication_required()
        if user is None or access.auth_revision != row.auth_revision:
            self._revoke(db, row, "ACCOUNT_CHANGED", now); db.commit()
            raise authentication_required()
        if touch:
            row.last_activity_at = now
        return WebPrincipal(user, row.id, access)

    def bootstrap(self, db: Session, secret: str | None) -> tuple[str, bool, bool]:
        """Return cookie secret, authenticated flag, and whether cookie changed."""
        row = self._find(db, secret)
        if row is not None and row.user_id is not None:
            try:
                self.resolve(db, secret, touch=False)
                db.commit()
                return secret, True, False
            except WebSecurityError:
                pass
        elif row is not None:
            row = self._find(db, secret, lock=True)
            now = datetime.now(timezone.utc)
            if row.revoked_at is None and not self._expired(row, now):
                db.commit()
                return secret, False, False
            self._revoke(db, row, "ABSOLUTE_EXPIRED", now)
        now = datetime.now(timezone.utc)
        new_secret = new_session_secret()
        db.add(WebSession(session_hash=session_hash(new_secret), login_method="anonymous",
                          created_at=now, last_activity_at=now,
                          expires_at=now + timedelta(minutes=self.settings.web_csrf_session_minutes)))
        db.commit()
        return new_secret, False, True

    def create_authenticated(self, db: Session, user_id: UUID, previous_secret: str, supplied_csrf: str, method: str) -> str:
        from src.services.authorization_service import AuthorizationService, AuthorizationDenied

        previous = self._find(db, previous_secret)
        user_ids = {user_id}
        if previous is not None and previous.user_id is not None:
            user_ids.add(previous.user_id)
        users = {user.id: user for user in db.scalars(select(User).where(User.id.in_(user_ids))
                 .order_by(User.id).with_for_update().execution_options(populate_existing=True))}
        previous = self._find(db, previous_secret, lock=True)
        now = datetime.now(timezone.utc)
        if previous is None or previous.revoked_at is not None or self._expired(previous, now) or not valid_csrf(previous_secret, supplied_csrf):
            raise csrf_denied()
        user = users.get(user_id)
        if user is not None and user.require_password_change:
            raise WebSecurityError(403, "PASSWORD_CHANGE_REQUIRED", "Change your temporary password in the desktop application before signing in online.")
        try:
            access = AuthorizationService.load(db, user_id)
        except AuthorizationDenied:
            raise authentication_required() from None
        self._revoke(db, previous, "ROTATED", now, actor_id=user_id)
        secret = new_session_secret()
        session = WebSession(user_id=user_id, session_hash=session_hash(secret), auth_revision=access.auth_revision,
                             login_method=method, created_at=now, last_activity_at=now,
                             expires_at=now + timedelta(hours=self.settings.web_session_max_hours))
        db.add(session); db.flush()
        self.audit(db, "WEB_TOTP_LOGIN_SUCCESS" if method == "totp" else "WEB_LOGIN_SUCCESS",
                   user_id=user_id, actor_id=user_id, session_id=session.id)
        db.commit()
        return secret

    def logout(self, db: Session, principal: WebPrincipal) -> None:
        row = db.get(WebSession, principal.session_id)
        row.revoked_at, row.revocation_reason = datetime.now(timezone.utc), "LOGOUT"
        self.audit(db, "WEB_LOGOUT", user_id=principal.user.id, actor_id=principal.user.id, session_id=row.id)
        db.commit()

    def revoke_all(self, db: Session, target_user_id: UUID, actor: AuthorizationContext) -> int:
        """Future administration hook: self-revocation or USER_DEACTIVATE grant."""
        from src.services.authorization_service import AuthorizationService
        actor = AuthorizationService.load(db, actor.user_id)
        if actor.user_id != target_user_id:
            actor.require_permission("USER_DEACTIVATE")
        db.scalar(select(User).where(User.id == target_user_id).with_for_update())
        rows = list(db.scalars(select(WebSession).where(WebSession.user_id == target_user_id,
                              WebSession.revoked_at.is_(None)).order_by(WebSession.id).with_for_update()))
        now = datetime.now(timezone.utc)
        for row in rows:
            self._revoke(db, row, "MANUAL", now, actor_id=actor.user_id)
        db.commit()
        return len(rows)

    @staticmethod
    def purge_anonymous(db: Session) -> int:
        """Trusted scheduler hook; preserve authenticated session/audit history."""
        result = db.execute(delete(WebSession).where(WebSession.user_id.is_(None),
                            WebSession.expires_at < datetime.now(timezone.utc) - timedelta(days=1)))
        db.commit()
        return result.rowcount
