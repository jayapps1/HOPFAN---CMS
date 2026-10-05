"""Permission codes are persisted grants; church titles never imply access."""
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


# Compatibility imports for existing attendance service callers.
from src.services.authorization_service import (
    AuthorizationContext as AttendanceAccess,
    AuthorizationDenied as AttendancePermissionError,
    AuthorizationService,
)


def load_access(db, user_id):
    return AuthorizationService.load(db, user_id)
