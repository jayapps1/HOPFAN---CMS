"""Authorized, atomic household relationships; master member data stays separate."""
from contextlib import contextmanager
from datetime import date, datetime, timezone
import logging
import uuid

from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import aliased
from src.config.database import SessionLocal
from src.models import Household, HouseholdMember, HouseholdAuditLog, Member, User
from src.security.household_permissions import RELATIONSHIPS, MINOR_AGE
from src.services.authorization_service import AuthorizationService, AuthorizationDenied
from src.services.administration_base import search_pattern, page_bounds


class HouseholdServiceError(Exception):
    pass


class HouseholdAuthorizationError(HouseholdServiceError, AuthorizationDenied):
    pass


class HouseholdMoveRequired(HouseholdServiceError):
    def __init__(self, current):
        self.current = current
        super().__init__(f"This member currently belongs to {current['household_name']}. Confirm a move to continue.")


class HouseholdHeadConflict(HouseholdServiceError):
    def __init__(self, current):
        self.current = current
        super().__init__(f"{current['full_name']} is the current household head. Confirm the head transition to continue.")


def identifier(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HouseholdServiceError('Invalid household or member identifier.') from exc


def age_on(dob, today=None):
    today = today or date.today()
    if not dob or dob > today:
        return None
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


class HouseholdService:
    MUTATION_LOCK = 847212

    def __init__(self, user_id=None, session_factory=SessionLocal):
        self.user_id, self.session_factory = user_id, session_factory

    @contextmanager
    def _db(self, permission=None, write=False):
        with self.session_factory() as db:
            try:
                if write:
                    db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': self.MUTATION_LOCK})
                access = AuthorizationService.load(db, self.user_id)
                if not access.has_any({'HOUSEHOLD_VIEW', 'HOUSEHOLD_VIEW_ALL'}):
                    raise HouseholdAuthorizationError('Household access is not assigned.')
                if permission:
                    self._require(access, permission)
                if write:
                    self._require(access, 'HOUSEHOLD_VIEW_ALL')
                yield db, access
            except HouseholdAuthorizationError:
                raise
            except AuthorizationDenied as exc:
                raise HouseholdAuthorizationError(str(exc)) from exc
            except IntegrityError as exc:
                db.rollback()
                raise HouseholdServiceError('A current household, head or household code already exists. Refresh and retry.') from exc
            except SQLAlchemyError as exc:
                db.rollback()
                logging.getLogger(__name__).error('Household operation failed: %s', type(exc).__name__)
                raise HouseholdServiceError('The household operation could not be completed. Refresh and retry.') from exc

    @staticmethod
    def _require(access, permission):
        if not access.has(permission):
            raise HouseholdAuthorizationError('You do not have permission for this household operation.')

    @staticmethod
    def _visible(db, access, stmt):
        if access.has('HOUSEHOLD_VIEW_ALL'):
            return stmt
        linked = db.scalar(select(User.member_id).where(User.id == access.user_id))
        membership = select(HouseholdMember.id).where(HouseholdMember.household_id == Household.id,
            HouseholdMember.member_id == linked, HouseholdMember.is_active.is_(True)).correlate(Household).exists() if linked else False
        return stmt.where(membership)

    @staticmethod
    def _date(value, *, required=False):
        if value in (None, ''):
            if required:
                raise HouseholdServiceError('Choose an effective date.')
            return None
        if isinstance(value, datetime):
            value = value.date()
        if not isinstance(value, date):
            for pattern in ('%Y-%m-%d', '%d/%m/%Y'):
                try:
                    value = datetime.strptime(str(value).strip(), pattern).date()
                    break
                except ValueError:
                    continue
            else:
                raise HouseholdServiceError('Enter a valid date in DD/MM/YYYY format.')
        if value > date.today():
            raise HouseholdServiceError('Household dates cannot be in the future.')
        return value

    @staticmethod
    def _values(data):
        name = str(data.get('household_name') or '').strip()
        if not name or len(name) > 200:
            raise HouseholdServiceError('Enter a household name of 1–200 characters.')
        status = str(data.get('status', 'ACTIVE')).upper()
        if status not in ('ACTIVE', 'INACTIVE'):
            raise HouseholdServiceError('Choose Active or Inactive; use Archive household to archive relationships.')
        result = dict(household_name=name, status=status)
        for field, limit in (('primary_address', 5000), ('primary_phone', 30), ('notes', 10000)):
            value = str(data.get(field) or '').strip()
            if len(value) > limit:
                raise HouseholdServiceError(f'{field.replace("_", " ").title()} is too long (maximum {limit} characters).')
            result[field] = value or None
        return result

    @staticmethod
    def _notes(value):
        value = str(value or '').strip()
        if len(value) > 10000:
            raise HouseholdServiceError('Keep relationship notes within 10,000 characters.')
        return value or None

    @staticmethod
    def _relationship(value, head=False):
        if not isinstance(head, bool):
            raise HouseholdServiceError('Choose Yes or No for household head.')
        value = str(value or '').upper()
        if value not in RELATIONSHIPS:
            raise HouseholdServiceError('Choose a family relationship.')
        return 'HEAD' if head else value

    @staticmethod
    def _version(row, expected):
        if expected is not None and row.updated_at != expected:
            raise HouseholdServiceError('This record changed. Refresh before saving.')

    @staticmethod
    def _touch(row, actor):
        row.updated_at, row.updated_by_user_id = datetime.now(timezone.utc), actor

    @staticmethod
    def _snapshot(row):
        if isinstance(row, Household):
            return dict(household_name=row.household_name, household_code=row.household_code, status=row.status)
        return dict(member_id=str(row.member_id), relationship=row.relationship, is_household_head=row.is_household_head,
            is_active=row.is_active, joined_at=row.joined_at.isoformat() if row.joined_at else None,
            left_at=row.left_at.isoformat() if row.left_at else None)

    @staticmethod
    def _audit(db, access, household_id, action, link=None, old=None, new=None):
        db.add(HouseholdAuditLog(household_id=household_id, action=action, actor_user_id=access.user_id,
            member_id=link.member_id if link else None, membership_id=link.id if link else None,
            old_values=old, new_values=new))

    def _household(self, db, access, household_id, *, active=False):
        row = db.scalar(self._visible(db, access, select(Household)).where(Household.id == identifier(household_id)))
        if row is None:
            raise HouseholdAuthorizationError('Household not found or outside your family access.')
        if active and row.status != 'ACTIVE':
            raise HouseholdServiceError('New family memberships require an active household.')
        return row

    @staticmethod
    def _directory():
        head, head_link = aliased(Member), aliased(HouseholdMember)
        counts = select(HouseholdMember.household_id, func.count().label('members')).where(
            HouseholdMember.is_active.is_(True)).group_by(HouseholdMember.household_id).subquery()
        history = select(HouseholdMember.id).where(HouseholdMember.household_id == Household.id).correlate(Household).exists()
        return select(Household, head, func.coalesce(counts.c.members, 0), history).outerjoin(
            counts, counts.c.household_id == Household.id).outerjoin(head_link,
            (head_link.household_id == Household.id) & head_link.is_active.is_(True) & head_link.is_household_head.is_(True))\
            .outerjoin(head, head.id == head_link.member_id)

    @staticmethod
    def _dto(row, head=None, count=0, history=False):
        return dict(id=str(row.id), household_name=row.household_name, household_code=row.household_code or '',
            primary_address=row.primary_address or '', primary_phone=row.primary_phone or '', notes=row.notes or '',
            status=row.status, created_at=row.created_at, updated_at=row.updated_at, archived_at=row.archived_at,
            head_name=head.full_name if head else '', head_member_id=str(head.id) if head else None,
            member_count=count, has_history=bool(history))

    @staticmethod
    def _member_dto(link, member):
        return dict(id=str(link.id), household_id=str(link.household_id), member_id=str(member.id),
            full_name=member.full_name, member_no=member.member_no, phone=member.phone or '', email=member.email or '',
            photo_path=member.photo_path or '', date_of_birth=member.date_of_birth, age=age_on(member.date_of_birth),
            member_status=member.status.value, relationship=link.relationship, relationship_label=RELATIONSHIPS[link.relationship],
            is_household_head=link.is_household_head, joined_at=link.joined_at, left_at=link.left_at,
            is_active=link.is_active, notes=link.notes or '', updated_at=link.updated_at)

    def capabilities(self):
        with self._db() as (db, access):
            global_access = access.has('HOUSEHOLD_VIEW_ALL')
            return dict(view=True, view_all=global_access,
                **{name: global_access and access.has(code) for name, code in (
                    ('create', 'HOUSEHOLD_CREATE'), ('edit', 'HOUSEHOLD_EDIT'), ('archive', 'HOUSEHOLD_ARCHIVE'),
                    ('delete', 'HOUSEHOLD_DELETE_UNUSED'), ('remove_member', 'HOUSEHOLD_REMOVE_MEMBER'))},
                add_member=global_access and access.has('HOUSEHOLD_ADD_MEMBER') and access.has('MEMBERS_VIEW_ALL'),
                member_search=global_access and access.has('MEMBERS_VIEW_ALL'),
                create_member=global_access and access.has('MEMBERS_VIEW_ALL') and access.has('MEMBERS_CREATE'))

    def list_households(self, search='', status='ACTIVE', limit=25, offset=0):
        with self._db() as (db, access):
            stmt = self._visible(db, access, self._directory())
            status = status.upper()
            if status != 'ALL':
                if status not in ('ACTIVE', 'INACTIVE', 'ARCHIVED'):
                    raise HouseholdServiceError('Choose a valid household status.')
                stmt = stmt.where(Household.status == status)
            if search.strip():
                pattern = search_pattern(search)
                matches = select(HouseholdMember.id).join(Member, Member.id == HouseholdMember.member_id).where(
                    HouseholdMember.household_id == Household.id, HouseholdMember.is_active.is_(True),
                    or_(func.concat_ws(' ', Member.first_name, Member.middle_name, Member.last_name).ilike(pattern),
                        Member.member_no.ilike(pattern), Member.phone.ilike(pattern), Member.email.ilike(pattern))).exists()
                stmt = stmt.where(or_(Household.household_name.ilike(pattern), Household.household_code.ilike(pattern),
                    Household.primary_phone.ilike(pattern), matches))
            total = db.scalar(select(func.count()).select_from(stmt.subquery()))
            limit, offset = page_bounds(limit, offset)
            rows = db.execute(stmt.order_by(func.lower(Household.household_name), Household.id).limit(limit).offset(offset)).all()
            return dict(total=total, rows=[self._dto(*row) for row in rows])

    def get_household_stats(self):
        with self._db() as (db, access):
            visible = self._visible(db, access, select(Household.id)).subquery()
            total, active = db.execute(select(func.count(), func.count().filter(Household.status == 'ACTIVE'))
                .where(Household.id.in_(select(visible.c.id)))).one()
            members = db.scalar(select(func.count()).select_from(HouseholdMember).where(
                HouseholdMember.is_active.is_(True), HouseholdMember.household_id.in_(select(visible.c.id))))
            without = db.scalar(select(func.count()).select_from(Member).where(~select(HouseholdMember.id).where(
                HouseholdMember.member_id == Member.id, HouseholdMember.is_active.is_(True)).exists())) if access.has('HOUSEHOLD_VIEW_ALL') else None
            return dict(total=total, active=active, members=members, without=without)

    def _summary(self, db, household_id):
        today = date.today()
        try:
            cutoff = today.replace(year=today.year-MINOR_AGE)
        except ValueError:
            cutoff = date(today.year-MINOR_AGE, 2, 28)
        total, adults, children, dependants, active = db.execute(select(func.count(),
            func.count().filter(Member.date_of_birth <= cutoff),
            func.count().filter((Member.date_of_birth > cutoff) & (Member.date_of_birth <= today)),
            func.count().filter(HouseholdMember.relationship == 'DEPENDANT'),
            func.count().filter(Member.status == 'ACTIVE')).select_from(HouseholdMember).join(Member)
            .where(HouseholdMember.household_id == household_id, HouseholdMember.is_active.is_(True))).one()
        return dict(total=total, adults=adults, children=children, dependants=dependants,
            active=active, inactive=total-active, unknown_age=total-adults-children)

    def get_household(self, household_id):
        with self._db() as (db, access):
            household = self._household(db, access, household_id)
            result = self._dto(*db.execute(self._directory().where(Household.id == household.id)).one())
            result['stats'] = self._summary(db, household.id)
            head = db.scalar(select(HouseholdMember).where(HouseholdMember.household_id == household.id,
                HouseholdMember.is_active.is_(True), HouseholdMember.is_household_head.is_(True)))
            result['head_membership_id'] = str(head.id) if head else None
            result['head_updated_at'] = head.updated_at if head else None
            return result

    def get_household_members(self, household_id, *, history=False, limit=25, offset=0):
        with self._db() as (db, access):
            household = self._household(db, access, household_id)
            if history:
                self._require(access, 'HOUSEHOLD_VIEW_ALL')
            stmt = select(HouseholdMember, Member).join(Member).where(HouseholdMember.household_id == household.id,
                HouseholdMember.is_active.is_(not history))
            total = db.scalar(select(func.count()).select_from(stmt.subquery()))
            limit, offset = page_bounds(limit, offset)
            rows = db.execute(stmt.order_by(HouseholdMember.is_household_head.desc(), Member.last_name,
                Member.first_name, HouseholdMember.id).limit(limit).offset(offset)).all()
            items=[self._member_dto(*row) for row in rows]
            if access.has_any({'SUNDAY_SCHOOL_STUDENT_VIEW','SUNDAY_SCHOOL_TEACHER_VIEW'}):
                from src.services.sunday_school_service import SundaySchoolService
                summaries=SundaySchoolService.member_summaries(db,access,[member.id for _link,member in rows])
                for item in items:
                    school=summaries.get(identifier(item['member_id']))
                    if school and school.get('student'):item['sunday_school']=school
            return dict(total=total, rows=items)

    def candidate_members(self, *, search='', unassigned_only=False, limit=20, offset=0):
        with self._db('HOUSEHOLD_VIEW_ALL') as (db, access):
            self._require(access, 'MEMBERS_VIEW_ALL')
            stmt = select(Member, HouseholdMember, Household).outerjoin(HouseholdMember,
                (HouseholdMember.member_id == Member.id) & HouseholdMember.is_active.is_(True))\
                .outerjoin(Household, Household.id == HouseholdMember.household_id)
            if unassigned_only:
                stmt = stmt.where(HouseholdMember.id.is_(None))
            if search.strip():
                pattern = search_pattern(search)
                stmt = stmt.where(or_(func.concat_ws(' ', Member.first_name, Member.middle_name, Member.last_name).ilike(pattern),
                    Member.member_no.ilike(pattern), Member.phone.ilike(pattern), Member.email.ilike(pattern)))
            total = db.scalar(select(func.count()).select_from(stmt.subquery()))
            limit, offset = page_bounds(limit, offset)
            rows = db.execute(stmt.order_by(Member.last_name, Member.first_name, Member.id).limit(limit).offset(offset)).all()
            return dict(total=total, rows=[dict(id=str(member.id), full_name=member.full_name, member_no=member.member_no,
                phone=member.phone or '', email=member.email or '', photo_path=member.photo_path or '',
                member_status=member.status.value, household_name=household.household_name if household else '',
                current_membership_id=str(link.id) if link else None) for member, link, household in rows])

    @classmethod
    def member_household(cls, db, access, member_id):
        if not access.has_any({'HOUSEHOLD_VIEW', 'HOUSEHOLD_VIEW_ALL'}):
            return False, None
        stmt = cls._visible(db, access, cls._directory()).join(HouseholdMember,
            HouseholdMember.household_id == Household.id).where(HouseholdMember.member_id == member_id,
            HouseholdMember.is_active.is_(True))
        row = db.execute(stmt).first()
        if not row:
            own_member = db.scalar(select(User.member_id).where(User.id == access.user_id)) if not access.has('HOUSEHOLD_VIEW_ALL') else None
            return access.has('HOUSEHOLD_VIEW_ALL') or own_member == member_id, None
        result = cls._dto(*row)
        link = db.scalar(select(HouseholdMember).where(HouseholdMember.member_id == member_id, HouseholdMember.is_active.is_(True)))
        result.update(relationship=link.relationship, relationship_label=RELATIONSHIPS[link.relationship])
        return True, result

    def get_member_household(self, member_id):
        with self._db() as (db, access):
            permitted, result = self.member_household(db, access, identifier(member_id))
            if not permitted:
                raise HouseholdAuthorizationError('This member is outside your family access.')
            return result

    def _next_code(self, db):
        prefix = f'HH-{date.today().year}-'
        # Retained creation audits reserve codes even after an unused household
        # is deleted, so references in its audit history remain unambiguous.
        reserved = HouseholdAuditLog.new_values['household_code'].astext
        codes = db.scalars(select(Household.household_code).where(Household.household_code.like(prefix+'%')).union_all(
            select(reserved).where(HouseholdAuditLog.action == 'HOUSEHOLD_CREATED', reserved.like(prefix+'%'))))
        highest = max((int(code[len(prefix):]) for code in codes if code[len(prefix):].isdigit()), default=0)
        return prefix + f'{highest+1:04d}'

    def create_household(self, data, head_member_id=None, *, move_from_membership_id=None, expected_source_updated_at=None):
        values = self._values(data)
        with self._db('HOUSEHOLD_CREATE', write=True) as (db, access):
            row = Household(**values, household_code=self._next_code(db), created_by_user_id=access.user_id, updated_by_user_id=access.user_id)
            db.add(row); db.flush()
            self._audit(db, access, row.id, 'HOUSEHOLD_CREATED', new=self._snapshot(row))
            if head_member_id:
                if row.status != 'ACTIVE':
                    raise HouseholdServiceError('Choose Active before adding a household head.')
                self._require(access, 'HOUSEHOLD_ADD_MEMBER')
                self._add(db, access, row, head_member_id, 'HEAD', date.today(), None,
                    move_from_membership_id, expected_source_updated_at, None, None, 'RELATIVE')
            db.flush()
            result = self._dto(*db.execute(self._directory().where(Household.id == row.id)).one())
            db.commit()
            return result

    def update_household(self, household_id, data, expected_updated_at=None):
        values = self._values(data)
        with self._db('HOUSEHOLD_EDIT', write=True) as (db, access):
            row = self._household(db, access, household_id)
            self._version(row, expected_updated_at)
            if row.status == 'ARCHIVED':
                raise HouseholdServiceError('Restore this household before editing it.')
            old = self._snapshot(row)
            changed = [field for field, value in values.items() if getattr(row, field) != value]
            for field, value in values.items():
                setattr(row, field, value)
            self._touch(row, access.user_id)
            self._audit(db, access, row.id, 'HOUSEHOLD_EDITED', old=old, new=dict(self._snapshot(row), changed_fields=changed))
            db.flush()
            result = self._dto(*db.execute(self._directory().where(Household.id == row.id)).one())
            db.commit()
            return result

    def _close(self, db, access, link, effective, reason='', action='HOUSEHOLD_MEMBER_REMOVED'):
        if not link.is_active:
            raise HouseholdServiceError('This household membership is already historical.')
        if link.joined_at and effective < link.joined_at:
            raise HouseholdServiceError('The effective date cannot be before the joined date.')
        old = self._snapshot(link)
        link.is_active, link.left_at, link.updated_at = False, effective, datetime.now(timezone.utc)
        reason = self._notes(reason)
        if reason:
            link.notes = ((link.notes or '')+'\n'+reason).strip()
            self._notes(link.notes)
        self._audit(db, access, link.household_id, action, link, old, self._snapshot(link))
        if link.is_household_head:
            self._audit(db, access, link.household_id, 'HOUSEHOLD_HEAD_CHANGED', link,
                old={'head_member_id': str(link.member_id)}, new={'head_member_id': None})
        source = db.get(Household, link.household_id)
        self._touch(source, access.user_id)
        db.flush()

    def _add(self, db, access, household, member_id, relationship, joined, notes, source_id, source_version,
            replace_head_id, head_version, previous_relationship):
        self._require(access, 'MEMBERS_VIEW_ALL')
        member = db.scalar(select(Member).where(Member.id == identifier(member_id)).with_for_update())
        if not member:
            raise HouseholdServiceError('Choose an existing HOPFAN member.')
        current = db.scalar(select(HouseholdMember).where(HouseholdMember.member_id == member.id,
            HouseholdMember.is_active.is_(True)).with_for_update())
        if current:
            if current.household_id == household.id:
                raise HouseholdServiceError('This member already belongs to this household.')
            previous = db.get(Household, current.household_id)
            if not source_id or current.id != identifier(source_id):
                raise HouseholdMoveRequired(dict(id=str(current.id), household_id=str(previous.id),
                    household_name=previous.household_name, updated_at=current.updated_at))
            self._require(access, 'HOUSEHOLD_REMOVE_MEMBER')
            self._version(current, source_version)
            if joined is None:
                raise HouseholdServiceError('Choose an effective date for the move.')
            self._close(db, access, current, joined, action='HOUSEHOLD_MEMBER_MOVED')
        elif source_id:
            raise HouseholdServiceError('The original membership changed. Refresh before moving this member.')
        last_exit = db.scalar(select(func.max(HouseholdMember.left_at)).where(HouseholdMember.member_id == member.id))
        if joined and last_exit and joined < last_exit:
            raise HouseholdServiceError('The joined date cannot be before the last household exit.')
        old_head = db.scalar(select(HouseholdMember).where(HouseholdMember.household_id == household.id,
            HouseholdMember.is_active.is_(True), HouseholdMember.is_household_head.is_(True)).with_for_update())
        if relationship == 'HEAD' and old_head:
            person = db.get(Member, old_head.member_id)
            if not replace_head_id or old_head.id != identifier(replace_head_id):
                raise HouseholdHeadConflict(dict(id=str(old_head.id), full_name=person.full_name, updated_at=old_head.updated_at))
            self._require(access, 'HOUSEHOLD_EDIT')
            self._version(old_head, head_version)
            previous_relationship = self._relationship(previous_relationship)
            if previous_relationship == 'HEAD':
                raise HouseholdServiceError('Choose the previous head\'s new relationship.')
            old_head.relationship, old_head.is_household_head = previous_relationship, False
            old_head.updated_at = datetime.now(timezone.utc)
            db.flush()
        link = HouseholdMember(household_id=household.id, member_id=member.id, relationship=relationship,
            is_household_head=relationship == 'HEAD', joined_at=joined, notes=notes)
        db.add(link); db.flush()
        self._touch(household, access.user_id)
        self._audit(db, access, household.id, 'HOUSEHOLD_MEMBER_MOVED' if current else 'HOUSEHOLD_MEMBER_ADDED', link,
            new=dict(self._snapshot(link), source_household_id=str(current.household_id) if current else None))
        if relationship == 'HEAD':
            self._audit(db, access, household.id, 'HOUSEHOLD_HEAD_CHANGED', link,
                old={'head_member_id': str(old_head.member_id) if old_head else None},
                new={'head_member_id': str(member.id), 'previous_relationship': previous_relationship if old_head else None})
        return self._member_dto(link, member)

    def add_member(self, household_id, member_id, relationship, *, is_household_head=False, joined_at=None, notes='',
            move_from_membership_id=None, expected_source_updated_at=None, replace_head_id=None,
            expected_head_updated_at=None, previous_head_relationship='RELATIVE'):
        relationship = self._relationship(relationship, is_household_head)
        joined, notes = self._date(joined_at), self._notes(notes)
        with self._db('HOUSEHOLD_ADD_MEMBER', write=True) as (db, access):
            household = self._household(db, access, household_id, active=True)
            result = self._add(db, access, household, member_id, relationship, joined, notes,
                move_from_membership_id, expected_source_updated_at, replace_head_id, expected_head_updated_at, previous_head_relationship)
            db.commit()
            return result

    def move_member(self, source_membership_id, target_household_id, member_id, relationship, *, effective_date,
            expected_updated_at=None, **kwargs):
        return self.add_member(target_household_id, member_id, relationship, joined_at=effective_date,
            move_from_membership_id=source_membership_id, expected_source_updated_at=expected_updated_at, **kwargs)

    def _link(self, db, access, membership_id):
        link = db.scalar(select(HouseholdMember).where(HouseholdMember.id == identifier(membership_id)).with_for_update())
        if not link:
            raise HouseholdServiceError('Household membership not found.')
        self._household(db, access, link.household_id)
        return link

    def remove_member(self, membership_id, effective_date, reason='', expected_updated_at=None):
        effective = self._date(effective_date, required=True)
        with self._db('HOUSEHOLD_REMOVE_MEMBER', write=True) as (db, access):
            link = self._link(db, access, membership_id)
            self._version(link, expected_updated_at)
            self._close(db, access, link, effective, reason)
            db.commit()

    def update_relationship(self, membership_id, relationship, notes='', expected_updated_at=None):
        relationship, notes = self._relationship(relationship), self._notes(notes)
        with self._db('HOUSEHOLD_EDIT', write=True) as (db, access):
            link = self._link(db, access, membership_id)
            self._version(link, expected_updated_at)
            if not link.is_active:
                raise HouseholdServiceError('Historical memberships retain their recorded relationship.')
            if (relationship == 'HEAD') != link.is_household_head:
                raise HouseholdServiceError('Use Change household head for a controlled head transition.')
            old = self._snapshot(link)
            link.relationship, link.notes, link.updated_at = relationship, notes, datetime.now(timezone.utc)
            self._touch(db.get(Household, link.household_id), access.user_id)
            self._audit(db, access, link.household_id, 'HOUSEHOLD_MEMBER_EDITED', link, old, self._snapshot(link))
            db.commit()

    def change_household_head(self, household_id, membership_id, *, current_head_id=None,
            expected_updated_at=None, expected_head_updated_at=None, previous_relationship='RELATIVE'):
        previous_relationship = self._relationship(previous_relationship)
        if previous_relationship == 'HEAD':
            raise HouseholdServiceError('Choose the previous head\'s new relationship.')
        with self._db('HOUSEHOLD_EDIT', write=True) as (db, access):
            household = self._household(db, access, household_id, active=True)
            link = self._link(db, access, membership_id)
            self._version(link, expected_updated_at)
            if link.household_id != household.id or not link.is_active:
                raise HouseholdServiceError('Choose a current member of this household.')
            old_head = db.scalar(select(HouseholdMember).where(HouseholdMember.household_id == household.id,
                HouseholdMember.is_active.is_(True), HouseholdMember.is_household_head.is_(True)))
            if old_head and old_head.id == link.id:
                raise HouseholdServiceError('This member is already the household head.')
            if old_head:
                if not current_head_id or old_head.id != identifier(current_head_id):
                    raise HouseholdHeadConflict(dict(id=str(old_head.id), full_name=db.get(Member, old_head.member_id).full_name, updated_at=old_head.updated_at))
                self._version(old_head, expected_head_updated_at)
                old_head.relationship, old_head.is_household_head = previous_relationship, False
                old_head.updated_at = datetime.now(timezone.utc)
                db.flush()
            elif current_head_id:
                raise HouseholdServiceError('The household head changed. Refresh before continuing.')
            link.relationship, link.is_household_head, link.updated_at = 'HEAD', True, datetime.now(timezone.utc)
            self._touch(household, access.user_id)
            self._audit(db, access, household.id, 'HOUSEHOLD_HEAD_CHANGED', link,
                old={'head_member_id': str(old_head.member_id) if old_head else None},
                new={'head_member_id': str(link.member_id), 'previous_relationship': previous_relationship if old_head else None})
            db.commit()

    def archive_household(self, household_id, effective_date=None, expected_updated_at=None):
        effective = self._date(effective_date or date.today(), required=True)
        with self._db('HOUSEHOLD_ARCHIVE', write=True) as (db, access):
            row = self._household(db, access, household_id)
            self._version(row, expected_updated_at)
            if row.status == 'ARCHIVED':
                raise HouseholdServiceError('This household is already archived.')
            old = self._snapshot(row)
            links = db.scalars(select(HouseholdMember).where(HouseholdMember.household_id == row.id, HouseholdMember.is_active.is_(True))).all()
            for link in links:
                self._close(db, access, link, effective)
            row.status, row.archived_at = 'ARCHIVED', datetime.now(timezone.utc)
            self._touch(row, access.user_id)
            self._audit(db, access, row.id, 'HOUSEHOLD_ARCHIVED', old=old, new=dict(self._snapshot(row), ended_memberships=len(links)))
            db.commit()

    def restore_household(self, household_id, expected_updated_at=None):
        with self._db('HOUSEHOLD_ARCHIVE', write=True) as (db, access):
            row = self._household(db, access, household_id)
            self._version(row, expected_updated_at)
            if row.status != 'ARCHIVED':
                raise HouseholdServiceError('Choose an archived household to restore.')
            old = self._snapshot(row)
            row.status, row.archived_at = 'ACTIVE', None
            self._touch(row, access.user_id)
            self._audit(db, access, row.id, 'HOUSEHOLD_RESTORED', old=old, new=self._snapshot(row))
            db.commit()

    def delete_unused_household(self, household_id, *, confirmed=False, expected_updated_at=None):
        with self._db('HOUSEHOLD_DELETE_UNUSED', write=True) as (db, access):
            row = self._household(db, access, household_id)
            self._version(row, expected_updated_at)
            if confirmed is not True:
                raise HouseholdServiceError('Explicit confirmation is required for permanent deletion.')
            if db.scalar(select(HouseholdMember.id).where(HouseholdMember.household_id == row.id).limit(1)):
                raise HouseholdServiceError('This household has membership history. Archive it instead.')
            self._audit(db, access, row.id, 'HOUSEHOLD_DELETED_UNUSED', old=self._snapshot(row))
            db.delete(row); db.commit()

    def audit_events(self, household_id, limit=25, offset=0):
        with self._db('HOUSEHOLD_VIEW_ALL') as (db, access):
            household = self._household(db, access, household_id)
            stmt = select(HouseholdAuditLog, User.username).outerjoin(User,
                User.id == HouseholdAuditLog.actor_user_id).where(HouseholdAuditLog.household_id == household.id)
            total = db.scalar(select(func.count()).select_from(stmt.subquery()))
            limit, offset = page_bounds(limit, offset)
            rows = db.execute(stmt.order_by(HouseholdAuditLog.occurred_at.desc(), HouseholdAuditLog.id).limit(limit).offset(offset)).all()
            return dict(total=total, rows=[dict(id=str(log.id), action=log.action, actor=actor or 'System',
                member_id=str(log.member_id) if log.member_id else None, old_values=log.old_values,
                new_values=log.new_values, occurred_at=log.occurred_at) for log, actor in rows])
