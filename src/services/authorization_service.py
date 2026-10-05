"""Fresh RBAC and ministry scope intersection shared by every service.

Legacy attendance flags are restrictions only, never capability grants. New
scopes depend entirely on role permissions. Church appointments are not read.
"""
from dataclasses import dataclass
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from src.config.database import SessionLocal
from src.models import User, UserStatus, Role, Ministry, UserMinistryScope


class AuthorizationDenied(Exception):
    pass


GLOBAL_EQUIVALENTS = {
    'MEMBERS_VIEW_OWN_MINISTRY': 'MEMBERS_VIEW_ALL',
    'MINISTRIES_VIEW_OWN': 'MINISTRIES_VIEW_ALL',
    'MINISTRY_LEADERSHIP_VIEW': 'MINISTRY_LEADERSHIP_VIEW_ALL',
    'SMS_VIEW_OWN': 'SMS_VIEW_ALL',
    **{f'ATTENDANCE_{action}_OWN_MINISTRY': global_code for action, global_code in (
        ('VIEW','ATTENDANCE_VIEW_ALL'), ('CREATE','ATTENDANCE_CREATE_GLOBAL'),
        ('RECORD','ATTENDANCE_RECORD_ALL'), ('CORRECT','ATTENDANCE_CORRECT_ALL'))},
}
ATTENDANCE_FIELDS = {'view':'can_view_attendance', 'create':'can_create_attendance',
    'record':'can_record_attendance', 'correct':'can_correct_attendance',
    'close':'can_close_attendance', 'reports':'can_view_reports'}
OWN_CODES = {**{f'ATTENDANCE_{a.upper()}_OWN_MINISTRY':a for a in ('view','create','record','correct')},
    'ATTENDANCE_CLOSE_SESSION':'close', 'ATTENDANCE_EXPORT':'reports'}


@dataclass(frozen=True)
class AuthorizationContext:
    user_id: UUID
    permissions: frozenset[str]
    scopes: dict[str, frozenset[UUID]]
    scope_ids: frozenset[UUID]
    historical_scope_ids: frozenset[UUID]
    auth_revision: int

    def has(self, code):
        return code in self.permissions

    def has_any(self, codes):
        return bool(self.permissions.intersection(codes))

    def require_permission(self, code):
        if not self.has(code):
            raise AuthorizationDenied('You do not have permission for this operation.')

    def ministries(self, action):
        own = f'ATTENDANCE_{action.upper()}_OWN_MINISTRY'
        if action in {'close','reports'}:
            own = 'ATTENDANCE_CLOSE_SESSION' if action == 'close' else 'ATTENDANCE_EXPORT'
        return self.scopes.get(action, frozenset()) if self.has(own) else frozenset()

    def ministry_ids(self, permission, *, include_inactive=False):
        if not self.has(permission):
            return frozenset()
        if permission in OWN_CODES:
            return self.scopes[OWN_CODES[permission]]
        return self.historical_scope_ids if include_inactive else self.scope_ids

    def can_access_ministry(self, ministry_id, permission, *, include_inactive=False):
        try:
            mid = UUID(str(ministry_id))
        except (ValueError, TypeError):
            return False
        if permission == 'MINISTRY_POSITION_VIEW':
            return self.has(permission) and (self.has('MINISTRIES_VIEW_ALL') or mid in self.ministry_ids(permission, include_inactive=include_inactive))
        if permission in {'ATTENDANCE_CLOSE_SESSION','ATTENDANCE_EXPORT'}:
            return self.has(permission) and (self.has('ATTENDANCE_VIEW_ALL') or mid in self.ministry_ids(permission))
        if permission in {'ATTENDANCE_REOPEN_SESSION','ATTENDANCE_LOCK_SESSION'}:
            return self.has(permission) and (self.has('ATTENDANCE_VIEW_ALL') or mid in self.ministries('correct'))
        if permission == 'ATTENDANCE_CORRECT_CLOSED':
            return self.has(permission) and (self.has('ATTENDANCE_CORRECT_ALL') or mid in self.ministries('correct'))
        if permission == 'ATTENDANCE_VIEW_AUDIT':
            return self.has(permission) and (self.has('ATTENDANCE_VIEW_ALL') or mid in self.ministries('view'))
        if permission == 'ATTENDANCE_UNLOCK_SESSION':
            return self.has(permission) and self.has('ATTENDANCE_REOPEN_SESSION') and self.has('ATTENDANCE_VIEW_ALL')
        global_code = GLOBAL_EQUIVALENTS.get(permission)
        if global_code and self.has(global_code):
            return True
        scoped = permission in GLOBAL_EQUIVALENTS or permission in OWN_CODES or permission == 'MINISTRY_POSITION_VIEW'
        return self.has(permission) and (not scoped or mid in self.ministry_ids(permission, include_inactive=include_inactive))

    def require_ministry_permission(self, ministry_id, permission, **kwargs):
        if not self.can_access_ministry(ministry_id, permission, **kwargs):
            raise AuthorizationDenied('This ministry is outside your permitted access.')


class AuthorizationService:
    def __init__(self, user_id=None, session_factory=SessionLocal):
        self.user_id, self.session_factory = user_id, session_factory

    @staticmethod
    def load(db, user_id, *, allow_password_change=False):
        try:
            user_uuid = UUID(str(getattr(user_id, 'id', user_id)))
        except (ValueError, TypeError, AttributeError) as exc:
            raise AuthorizationDenied('Sign in with an active HOPFAN account.') from exc
        user = db.scalar(select(User).where(User.id == user_uuid).options(
            selectinload(User.roles).selectinload(Role.permissions)))
        if not user or user.status != UserStatus.ACTIVE:
            raise AuthorizationDenied('This account cannot access HOPFAN.')
        if user.require_password_change and not allow_password_change:
            raise AuthorizationDenied('Change your temporary password before accessing HOPFAN.')
        permissions = frozenset(p.code for role in user.roles if role.is_active for p in role.permissions if p.is_active)
        grants = db.execute(select(UserMinistryScope, Ministry.is_active).join(Ministry).where(
            UserMinistryScope.user_id == user.id, UserMinistryScope.is_active.is_(True))).all()
        active = [(g, active) for g, active in grants if active]
        def permitted(g, action):
            return not g.legacy_attendance_limits or getattr(g, ATTENDANCE_FIELDS[action])
        scopes = {action:frozenset(g.ministry_id for g, _ in active if permitted(g, action)) for action in ATTENDANCE_FIELDS}
        # The previous member/ministry/leadership read paths used attendance view
        # restrictions. Preserve that intersection for legacy grants only.
        historical = frozenset(g.ministry_id for g, _ in grants if permitted(g, 'view'))
        return AuthorizationContext(user.id, permissions, scopes, scopes['view'], historical, user.auth_revision)

    def context(self, user=None):
        with self.session_factory() as db:
            return self.load(db, user if user is not None else self.user_id)

    def has_permission(self, user, permission_code=None):
        if permission_code is None:
            user, permission_code = self.user_id, user
        return self.context(user).has(permission_code)

    def has_any_permission(self, user, codes=None):
        if codes is None:
            user, codes = self.user_id, user
        return self.context(user).has_any(codes)

    def get_effective_permissions(self, user=None):
        return self.context(user).permissions

    def get_ministry_scopes(self, user=None):
        return self.context(user).scope_ids

    def has_ministry_scope(self, user, ministry_id):
        try:
            mid=UUID(str(ministry_id))
        except (ValueError,TypeError):
            return False
        return mid in self.context(user).scope_ids

    def can_access_ministry(self, user, ministry_id, permission_code):
        return self.context(user).can_access_ministry(ministry_id, permission_code)

    def require_permission(self, user, permission_code):
        self.context(user).require_permission(permission_code)

    def require_ministry_permission(self, user, ministry_id, permission_code):
        self.context(user).require_ministry_permission(ministry_id, permission_code)
