"""Shared administration transactions, delegation limits and secret-free audit."""
from contextlib import contextmanager
import json
import logging
import uuid
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import selectinload
from src.config.database import SessionLocal
from src.models import User, UserStatus, Role, SecurityAuditLog
from src.services.authorization_service import AuthorizationService, AuthorizationDenied


class AdministrationError(Exception):
    pass


def identifier(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise AdministrationError('Invalid record identifier.') from exc


def page_bounds(limit, offset):
    return min(100, max(1, int(limit))), max(0, int(offset))


def search_pattern(value):
    return '%'+value.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'


def audit(db, actor, action, *, user_id=None, role_id=None, old=None, new=None):
    db.add(SecurityAuditLog(actor_user_id=actor, target_user_id=user_id, target_role_id=role_id,
        action=action, old_values=json.dumps(old, sort_keys=True) if old is not None else None,
        new_values=json.dumps(new or {}, sort_keys=True)))


class AdministrationService:
    MUTATION_LOCK = 847209
    # A recovery administrator must be able to restore account and role access.
    RECOVERY_PERMISSIONS = {'USER_VIEW','USER_EDIT','ROLE_ASSIGN','ROLE_EDIT'}

    def __init__(self, user_id=None, session_factory=SessionLocal):
        self.user_id, self.session_factory = user_id, session_factory

    @contextmanager
    def _db(self, permission, *, write=False):
        with self.session_factory() as db:
            try:
                if write:
                    db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key':self.MUTATION_LOCK})
                access = AuthorizationService.load(db, self.user_id)
                access.require_permission(permission)
                yield db, access
            except IntegrityError as exc:
                db.rollback()
                raise AdministrationError('This username, email, member link or role name/code is already used. Refresh and retry.') from exc
            except SQLAlchemyError as exc:
                db.rollback()
                logging.getLogger(__name__).error('Administration operation failed: %s', type(exc).__name__)
                raise AdministrationError('The operation could not be completed. Refresh and retry.') from exc

    @staticmethod
    def _user(db, user_id, lock=False):
        stmt = select(User).where(User.id == identifier(user_id)).options(
            selectinload(User.roles).selectinload(Role.permissions), selectinload(User.member))
        user = db.scalar(stmt.with_for_update() if lock else stmt)
        if not user:
            raise AdministrationError('User account not found.')
        return user

    @staticmethod
    def _permissions(roles):
        return frozenset(p.code for r in roles if r.is_active for p in r.permissions if p.is_active)

    @classmethod
    def _protect_recovery(cls, db):
        db.flush()
        users = db.scalars(select(User).where(User.status.in_([UserStatus.ACTIVE, UserStatus.LOCKED]))
            .options(selectinload(User.roles).selectinload(Role.permissions)).execution_options(populate_existing=True)).all()
        # A timed lock can recover automatically; a permanent lock cannot.
        for user in users:
            recoverable = user.status == UserStatus.ACTIVE or user.locked_until is not None
            if recoverable and cls.RECOVERY_PERMISSIONS.issubset(cls._permissions(user.roles)):
                return
        raise AdministrationError('Keep at least one active administrator able to manage users and roles.')

    @staticmethod
    def _can_delegate(access, role):
        return role.is_active and all(not p.is_active or access.has(p.code) for p in role.permissions)

    def capabilities(self):
        with self.session_factory() as db:
            access = AuthorizationService.load(db, self.user_id)
            return {'permissions':sorted(access.permissions), **{code.lower():access.has(code) for code in access.permissions}}

    def audit_events(self, *, user_id=None, role_id=None, limit=25, offset=0):
        with self._db('SECURITY_AUDIT_VIEW') as (db, access):
            from sqlalchemy import func
            from sqlalchemy.orm import aliased
            actor, target = aliased(User), aliased(User)
            stmt = select(SecurityAuditLog, actor.username, target.username, Role.name).outerjoin(
                actor, actor.id == SecurityAuditLog.actor_user_id).outerjoin(
                target, target.id == SecurityAuditLog.target_user_id).outerjoin(Role, Role.id == SecurityAuditLog.target_role_id)
            if user_id:
                stmt = stmt.where(SecurityAuditLog.target_user_id == identifier(user_id))
            if role_id:
                stmt = stmt.where(SecurityAuditLog.target_role_id == identifier(role_id))
            total = db.scalar(select(func.count()).select_from(stmt.subquery()))
            limit, offset = page_bounds(limit, offset)
            rows = db.execute(stmt.order_by(SecurityAuditLog.created_at.desc(), SecurityAuditLog.id.desc()).limit(limit).offset(offset))
            return dict(total=total, rows=[dict(id=str(event.id), action=event.action, actor=a or 'Sign-in / system',
                target=u or r or 'Unknown account', created_at=event.created_at,
                old_values=json.loads(event.old_values) if event.old_values else None,
                new_values=json.loads(event.new_values)) for event,a,u,r in rows])
