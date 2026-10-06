"""UI-independent authorization, validators and operational contact queries."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
import logging
import uuid
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import aliased
from src.config.database import SessionLocal
from src.models import (Member, Household, HouseholdMember, SundaySchoolClass as SchoolClass,
    SundaySchoolStudent as Student, SundaySchoolEnrollment as Enrollment,
    SundaySchoolGuardian as Guardian, SundaySchoolUserClassScope as ClassScope, SundaySchoolAuditLog as Audit)
from src.services.authorization_service import AuthorizationService, AuthorizationDenied
from src.services.administration_base import search_pattern, page_bounds
from src.services.household_service import age_on
from src.services.operation_errors import OperationConflict, OperationNotFound


class SundaySchoolError(Exception): pass
class SundaySchoolConflict(SundaySchoolError, OperationConflict): pass
class SundaySchoolNotFound(SundaySchoolError, OperationNotFound): pass
class SundaySchoolDenied(SundaySchoolError, AuthorizationDenied): pass


class EnrollmentMoveRequired(SundaySchoolError):
    def __init__(self, current):
        self.current = current
        super().__init__(f"This student is currently enrolled in {current['class_name']}. Use a controlled class move.")


class AgeRangeWarning(SundaySchoolError):
    def __init__(self, student_name, class_name, age):
        self.age = age
        super().__init__(f'{student_name}, age {age}, is outside the recommended age range for {class_name}. Confirm an age-range override to enroll.')


def identifier(value):
    try: return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc: raise SundaySchoolError('Invalid Sunday School record identifier.') from exc


def today(): return datetime.now(timezone.utc).date()


def school_date(value, *, optional=False, future=False):
    if value in (None, ''):
        if optional: return None
        raise SundaySchoolError('Choose a date.')
    if isinstance(value, datetime): value = value.date()
    if not isinstance(value, date):
        for pattern in ('%Y-%m-%d', '%d/%m/%Y'):
            try: value = datetime.strptime(str(value).strip(), pattern).date(); break
            except ValueError: continue
        else: raise SundaySchoolError('Enter a valid date in DD/MM/YYYY format.')
    if not future and value > today(): raise SundaySchoolError('This operation cannot take effect in the future.')
    return value


def text_value(value, limit=10000):
    value = str(value or '').strip()
    if len(value) > limit: raise SundaySchoolError(f'Text exceeds the {limit}-character limit.')
    return value or None


def version(row, expected):
    if expected is not None and row.updated_at != expected: raise SundaySchoolConflict('This record changed. Refresh before saving.')


@dataclass(frozen=True)
class SchoolAccess:
    user_id: uuid.UUID
    permissions: frozenset
    class_ids: frozenset

    @property
    def global_access(self): return 'SUNDAY_SCHOOL_VIEW_ALL' in self.permissions
    def has(self, code): return code in self.permissions
    def require(self, code):
        if not self.has(code): raise SundaySchoolDenied('You do not have permission for this Sunday School operation.')
    def contains(self, class_id): return self.global_access or identifier(class_id) in self.class_ids
    def restrict(self, stmt, column): return stmt if self.global_access else stmt.where(column.in_(self.class_ids))


class SundaySchoolBase:
    MUTATION_LOCK = 847213
    def __init__(self, user_id=None, session_factory=SessionLocal): self.user_id, self.session_factory = user_id, session_factory

    @staticmethod
    def access(db, user_id, auth=None):
        auth = auth or AuthorizationService.load(db, user_id)
        if not auth.has_any({'SUNDAY_SCHOOL_VIEW','SUNDAY_SCHOOL_VIEW_ALL'}): raise SundaySchoolDenied('Sunday School access is not assigned.')
        ids = frozenset(db.scalars(select(ClassScope.class_id).where(ClassScope.user_id==auth.user_id, ClassScope.is_active.is_(True))))
        return SchoolAccess(auth.user_id, auth.permissions, ids)

    @contextmanager
    def _db(self, permission=None, write=False):
        with self.session_factory() as db:
            try:
                if write: db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key':self.MUTATION_LOCK})
                access = self.access(db, self.user_id)
                if permission: access.require(permission)
                yield db, access
            except SundaySchoolDenied: raise
            except AuthorizationDenied as exc: raise SundaySchoolDenied(str(exc)) from exc
            except IntegrityError as exc:
                db.rollback()
                raise SundaySchoolError('A duplicate/current record or related dependency exists. Refresh and retry.') from exc
            except SQLAlchemyError as exc:
                db.rollback(); logging.getLogger(__name__).error('Sunday School operation failed: %s', type(exc).__name__)
                raise SundaySchoolError('The Sunday School operation could not be completed. Refresh and retry.') from exc

    @staticmethod
    def _class(db, access, class_id, *, active=False):
        if not access.contains(class_id): raise SundaySchoolDenied('This class is outside your assigned class access.')
        row = db.get(SchoolClass, identifier(class_id))
        if not row: raise SundaySchoolNotFound('Class not found.')
        if active and row.status!='ACTIVE': raise SundaySchoolError('Choose an active Sunday School class.')
        return row

    @staticmethod
    def member_clause(access):
        if access.global_access: return True
        return select(Enrollment.id).where(Enrollment.member_id==Student.member_id,
            Enrollment.is_current.is_(True), Enrollment.class_id.in_(access.class_ids)).correlate(Student).exists()

    @classmethod
    def _student(cls, db, access, member_id):
        row = db.scalar(select(Student).where(Student.member_id==identifier(member_id), cls.member_clause(access)))
        if not row: raise SundaySchoolDenied('Student not found or outside your permitted classes.')
        return row

    @staticmethod
    def audit(db, access, action, *, class_id=None, member_id=None, session_id=None, record_id=None, old=None, new=None, reason=None):
        db.add(Audit(actor_user_id=access.user_id, action=action, class_id=class_id,
            member_id=member_id, session_id=session_id, record_id=record_id, old_values=old, new_values=new, reason=reason))

    @staticmethod
    def member_dto(member):
        return dict(id=str(member.id), member_id=str(member.id), full_name=member.full_name,
            member_no=member.member_no, photo_path=member.photo_path or '', date_of_birth=member.date_of_birth,
            age=age_on(member.date_of_birth, today()), member_status=member.status.value)

    @classmethod
    def household_map(cls, db, ids):
        result = {}
        if ids:
            for mid, hid, name in db.execute(select(HouseholdMember.member_id, Household.id, Household.household_name)
                .join(Household).where(HouseholdMember.member_id.in_(ids), HouseholdMember.is_active.is_(True))):
                result[mid] = dict(id=str(hid), household_name=name)
        return result

    @classmethod
    def guardian_map(cls, db, access, ids):
        result = {mid:[] for mid in ids}
        if not ids or not access.has('SUNDAY_SCHOOL_GUARDIAN_VIEW'): return result
        guardian = aliased(Member)
        stmt = select(Student.member_id, Guardian, guardian).join(Guardian, Guardian.student_id==Student.id)\
            .join(guardian, guardian.id==Guardian.guardian_member_id).where(Student.member_id.in_(ids),
                Guardian.is_active.is_(True), cls.member_clause(access))
        for mid, link, member in db.execute(stmt.order_by(Guardian.is_primary.desc(), guardian.last_name, Guardian.id)):
            result[mid].append(dict(id=str(link.id), guardian_member_id=str(member.id), full_name=member.full_name,
                phone=member.phone or member.alternate_phone or '', relationship=link.relationship,
                is_primary=link.is_primary, can_receive_sms=link.can_receive_sms, member_status=member.status.value))
        return result

    @classmethod
    def contact_fields(cls, member_id, households, guardians):
        contacts = guardians.get(member_id, [])
        primary = next((contact for contact in contacts if contact['is_primary']), None)
        return dict(household=households.get(member_id), guardians=contacts,
            guardian_name=primary['full_name'] if primary else '', guardian_phone=primary['phone'] if primary else '')
