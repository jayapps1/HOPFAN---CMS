"""Permission codes are persisted grants; church titles never imply access."""
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.models import Ministry, Role, User, UserMinistryScope, UserStatus

PERMISSIONS = {
    "ATTENDANCE_VIEW_OWN_MINISTRY": "View assigned ministry attendance",
    "ATTENDANCE_CREATE_OWN_MINISTRY": "Create assigned ministry attendance",
    "ATTENDANCE_RECORD_OWN_MINISTRY": "Record assigned ministry attendance",
    "ATTENDANCE_CORRECT_OWN_MINISTRY": "Correct assigned ministry attendance",
    "ATTENDANCE_VIEW_ALL": "View all attendance",
    "ATTENDANCE_CREATE_GLOBAL": "Create global and ministry attendance",
    "ATTENDANCE_RECORD_ALL": "Record all attendance",
    "ATTENDANCE_CORRECT_ALL": "Correct all attendance",
    "ATTENDANCE_CORRECT_CLOSED": "Correct closed attendance sessions",
    "ATTENDANCE_CLOSE_SESSION": "Close assigned attendance sessions",
    "ATTENDANCE_REOPEN_SESSION": "Reopen assigned closed sessions",
    "ATTENDANCE_LOCK_SESSION": "Lock assigned closed sessions",
    "ATTENDANCE_UNLOCK_SESSION": "Centrally reopen locked sessions",
    "ATTENDANCE_VIEW_AUDIT": "View permitted attendance history",
    "ATTENDANCE_EXPORT": "Export permitted attendance reports",
    "ATTENDANCE_SCOPE_MANAGE": "Manage and audit ministry attendance grants",
}
LEADER_PERMISSIONS = {
    "ATTENDANCE_VIEW_OWN_MINISTRY", "ATTENDANCE_CREATE_OWN_MINISTRY",
    "ATTENDANCE_RECORD_OWN_MINISTRY", "ATTENDANCE_CORRECT_OWN_MINISTRY",
    "ATTENDANCE_CLOSE_SESSION", "ATTENDANCE_VIEW_AUDIT", "ATTENDANCE_EXPORT",
}
OBSERVER_PERMISSIONS = {"ATTENDANCE_VIEW_ALL", "ATTENDANCE_VIEW_AUDIT", "ATTENDANCE_EXPORT"}


class AttendancePermissionError(Exception):
    pass


@dataclass(frozen=True)
class AttendanceAccess:
    user_id: UUID
    permissions: frozenset[str]
    scopes: dict[str, frozenset[UUID]]

    def has(self, code: str) -> bool:
        return code in self.permissions

    def ministries(self, action: str) -> frozenset[UUID]:
        own = f"ATTENDANCE_{action.upper()}_OWN_MINISTRY"
        if action in {"close", "reports"}:
            own = "ATTENDANCE_CLOSE_SESSION" if action == "close" else "ATTENDANCE_EXPORT"
        return self.scopes.get(action, frozenset()) if self.has(own) else frozenset()


def load_access(db, user_id) -> AttendanceAccess:
    if user_id is None:
        raise AttendancePermissionError("Sign in to access attendance.")
    try:
        user_uuid = UUID(str(user_id))
    except (ValueError, TypeError) as exc:
        raise AttendancePermissionError("Invalid attendance user.") from exc
    user = db.scalar(select(User).where(User.id == user_uuid).options(
        selectinload(User.roles).selectinload(Role.permissions),
    ))
    if user is None or user.status != UserStatus.ACTIVE:
        raise AttendancePermissionError("This account cannot access attendance.")
    permissions = frozenset(p.code for role in user.roles if role.is_active
                            for p in role.permissions if p.is_active)
    grants = db.scalars(select(UserMinistryScope).join(Ministry).where(
        UserMinistryScope.user_id == user.id, UserMinistryScope.is_active.is_(True),
        Ministry.is_active.is_(True),
    )).all()
    scopes = {action: frozenset(g.ministry_id for g in grants if getattr(g, field))
              for action, field in {
                  "view": "can_view_attendance", "create": "can_create_attendance",
                  "record": "can_record_attendance", "correct": "can_correct_attendance",
                  "close": "can_close_attendance", "reports": "can_view_reports",
              }.items()}
    return AttendanceAccess(user.id, permissions, scopes)
