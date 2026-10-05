"""Transactional church appointments. Office titles never authorize software access."""
from datetime import date, datetime, timezone
import re
from sqlalchemy import func, or_, select
from src.models import (Member, MemberMinistry, MemberStatus, Ministry, MinistryPosition,
                        MinistryLeadershipAssignment as Assignment, MinistryLeadershipAuditLog as Audit, User)
from src.services.ministry_service import MinistryService, MinistryServiceError, MinistryAuthorizationError, ministry_uuid


class LeadershipServiceError(MinistryServiceError):
    pass


class LeadershipAuthorizationError(LeadershipServiceError, MinistryAuthorizationError):
    pass


class MembershipRequiredError(LeadershipServiceError):
    pass


class PositionConflictError(LeadershipServiceError):
    def __init__(self, position, holders):
        self.position, self.holders = position, holders
        names = ', '.join(row['full_name'] for row in holders)
        super().__init__(f"{position['name']} is currently assigned to {names}. End an assignment or use controlled replacement.")


class MinistryLeadershipService(MinistryService):
    @staticmethod
    def _check_version(row, expected_updated_at):
        if expected_updated_at is not None and row.updated_at != expected_updated_at:
            raise LeadershipServiceError('This record was changed by another user. Refresh before saving.')

    @staticmethod
    def _grant(access, permission, write=False):
        allowed = access.has(permission)
        if permission == 'MINISTRY_LEADERSHIP_VIEW':
            allowed = allowed or access.has('MINISTRY_LEADERSHIP_VIEW_ALL')
        if not allowed or (write and not access.has('MINISTRIES_VIEW_ALL')):
            raise LeadershipAuthorizationError('You do not have permission for this leadership operation.')

    def _ministry(self, db, access, ministry_id, permission='MINISTRY_LEADERSHIP_VIEW', write=False, active=False):
        self._grant(access, permission, write)
        row = self._get(db, access, ministry_id)
        if permission == 'MINISTRY_LEADERSHIP_VIEW' and not access.has('MINISTRY_LEADERSHIP_VIEW_ALL'):
            # VIEW grants are scoped even if the account can read global ministry configuration.
            from src.models import UserMinistryScope
            assigned = db.scalar(select(UserMinistryScope.id).where(UserMinistryScope.user_id == access.user_id,
                UserMinistryScope.ministry_id == row.id, UserMinistryScope.is_active.is_(True),
                UserMinistryScope.can_view_attendance.is_(True)))
            if not assigned:
                raise LeadershipAuthorizationError('Leadership is outside your assigned ministries.')
        if active:
            row = db.scalar(select(Ministry).where(Ministry.id == row.id).with_for_update(read=True).execution_options(populate_existing=True))
            if not row.is_active:
                raise LeadershipServiceError('New appointments require an active ministry.')
        return row

    def capabilities(self, ministry_id):
        with self._db() as (db, access):
            ministry = self._get(db, access, ministry_id)
            global_access = access.has('MINISTRIES_VIEW_ALL')
            from src.models import UserMinistryScope
            scoped = access.has('MINISTRY_LEADERSHIP_VIEW') and bool(db.scalar(select(UserMinistryScope.id).where(
                UserMinistryScope.user_id == access.user_id, UserMinistryScope.ministry_id == ministry.id,
                UserMinistryScope.is_active.is_(True), UserMinistryScope.can_view_attendance.is_(True))))
            result = dict(view=scoped or access.has('MINISTRY_LEADERSHIP_VIEW_ALL'),
                positions_view=access.has('MINISTRY_POSITION_VIEW'),
                **{name: global_access and access.has(permission) for name, permission in {
                    'position_create':'MINISTRY_POSITION_CREATE', 'position_edit':'MINISTRY_POSITION_EDIT',
                    'position_archive':'MINISTRY_POSITION_ARCHIVE', 'position_delete':'MINISTRY_POSITION_DELETE_UNUSED',
                    'assign':'MINISTRY_LEADERSHIP_ASSIGN', 'edit':'MINISTRY_LEADERSHIP_EDIT', 'end':'MINISTRY_LEADERSHIP_END',
                    'add_membership':'MEMBERS_EDIT'}.items()},
                member_search=access.has('MEMBERS_VIEW_ALL') or access.has('MEMBERS_VIEW_OWN_MINISTRY'))
            result['add_membership'] = result['add_membership'] and access.has('MEMBERS_VIEW_ALL')
            return result

    @staticmethod
    def _position_dto(row, holders=0, used=False):
        return dict(id=str(row.id), ministry_id=str(row.ministry_id), name=row.name, code=row.code,
            description=row.description or '', sort_order=row.sort_order, is_leadership=row.is_leadership,
            is_active=row.is_active, max_current_holders=row.max_current_holders, current_holders=holders,
            in_use=bool(used), updated_at=row.updated_at, created_at=row.created_at)

    @staticmethod
    def _position_values(data):
        name, code = str(data.get('name') or '').strip(), str(data.get('code') or '').strip().upper()
        if not name or len(name) > 150:
            raise LeadershipServiceError('Enter a position name of 1–150 characters.')
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,59}', code):
            raise LeadershipServiceError('Enter a code starting with a letter, using letters, digits and underscores (up to 60 characters).')
        try:
            order = int(str(data.get('sort_order', 0)))
            raw = data.get('max_current_holders', 1)
            maximum = None if raw in (None, '', 'Unlimited') else int(str(raw))
            if order < 0 or order > 2147483647 or (maximum is not None and not 1 <= maximum <= 2147483647):
                raise ValueError
        except (ValueError, TypeError) as exc:
            raise LeadershipServiceError('Display order must be a non-negative integer; holder limit must be positive or Unlimited.') from exc
        for field in ('is_active', 'is_leadership'):
            if not isinstance(data.get(field, True), bool):
                raise LeadershipServiceError('Choose an explicit position status and type.')
        description = str(data.get('description') or '').strip()
        if len(description) > 10000:
            raise LeadershipServiceError('Keep the description within 10,000 characters.')
        return dict(name=name, code=code, description=description or None, sort_order=order,
                    max_current_holders=maximum, is_leadership=data.get('is_leadership', True), is_active=data.get('is_active', True))

    @staticmethod
    def _position_unique(db, ministry_id, values, excluding=None):
        stmt = select(MinistryPosition.id).where(MinistryPosition.ministry_id == ministry_id,
            or_(func.upper(MinistryPosition.code) == values['code'], func.lower(MinistryPosition.name) == values['name'].lower()))
        if excluding:
            stmt = stmt.where(MinistryPosition.id != excluding)
        if db.scalar(stmt):
            raise LeadershipServiceError('This name or code is already used by a position in this ministry, including inactive positions.')

    @staticmethod
    def _positions(db, ministry_id, active_only=False):
        counts = select(Assignment.position_id, func.count().label('holders')).where(Assignment.is_current.is_(True)).group_by(Assignment.position_id).subquery()
        used = select(Assignment.id).where(Assignment.position_id == MinistryPosition.id).exists()
        stmt = select(MinistryPosition, func.coalesce(counts.c.holders, 0), used).outerjoin(counts, counts.c.position_id == MinistryPosition.id).where(MinistryPosition.ministry_id == ministry_id)
        if active_only:
            stmt = stmt.where(MinistryPosition.is_active.is_(True))
        return [MinistryLeadershipService._position_dto(*row) for row in db.execute(stmt.order_by(MinistryPosition.sort_order, func.lower(MinistryPosition.name), MinistryPosition.id))]

    def list_positions(self, ministry_id, active_only=False):
        with self._db() as (db, access):
            ministry = self._ministry(db, access, ministry_id, 'MINISTRY_POSITION_VIEW')
            return self._positions(db, ministry.id, active_only)

    @staticmethod
    def _position(db, position_id, lock=False):
        stmt = select(MinistryPosition).where(MinistryPosition.id == ministry_uuid(position_id))
        row = db.scalar(stmt.with_for_update().execution_options(populate_existing=True) if lock else stmt)
        if not row:
            raise LeadershipServiceError('Position is unavailable.')
        return row

    def get_position(self, position_id):
        with self._db() as (db, access):
            row = self._position(db, position_id)
            self._ministry(db, access, row.ministry_id, 'MINISTRY_POSITION_VIEW')
            return next(item for item in self._positions(db, row.ministry_id) if item['id'] == str(row.id))

    @staticmethod
    def _position_snapshot(row):
        return dict(name=row.name, code=row.code, description=row.description, sort_order=row.sort_order,
                    max_current_holders=row.max_current_holders, is_leadership=row.is_leadership, is_active=row.is_active)

    @staticmethod
    def _assignment_snapshot(row):
        return dict(member_id=str(row.member_id), position_id=str(row.position_id), position_name=row.position_name,
            position_code=row.position_code, start_date=row.start_date.isoformat(), end_date=row.end_date.isoformat() if row.end_date else None,
            is_current=row.is_current, notes=row.notes)

    @staticmethod
    def _record(db, access, ministry_id, action, position_id=None, assignment=None, old=None, new=None):
        db.add(Audit(ministry_id=ministry_id, actor_user_id=access.user_id, action=action, position_id=position_id,
            assignment_id=assignment.id if assignment else None, member_id=assignment.member_id if assignment else None,
            old_values=old, new_values=new))

    def create_position(self, ministry_id, data):
        with self._db() as (db, access):
            ministry = self._ministry(db, access, ministry_id, 'MINISTRY_POSITION_CREATE', write=True)
            values = self._position_values(data)
            self._position_unique(db, ministry.id, values)
            row = MinistryPosition(ministry_id=ministry.id, **values, created_by_user_id=access.user_id, updated_by_user_id=access.user_id)
            db.add(row)
            db.flush()
            self._record(db, access, ministry.id, 'POSITION_CREATED', row.id, new=self._position_snapshot(row))
            db.commit()
            return self._position_dto(row)

    def update_position(self, position_id, data, expected_updated_at=None):
        with self._db() as (db, access):
            row = self._position(db, position_id)
            self._ministry(db, access, row.ministry_id, 'MINISTRY_POSITION_EDIT', write=True)
            row = self._position(db, position_id, lock=True)
            self._check_version(row, expected_updated_at)
            values = self._position_values(data)
            used = db.scalar(select(Assignment.id).where(Assignment.position_id == row.id).limit(1))
            holders = db.scalar(select(func.count()).select_from(Assignment).where(Assignment.position_id == row.id, Assignment.is_current.is_(True)))
            if values['code'] != row.code and used:
                raise LeadershipServiceError('Position code is locked because assignment history exists.')
            if values['max_current_holders'] is not None and holders > values['max_current_holders']:
                raise LeadershipServiceError('End surplus assignments before reducing the holder limit.')
            if values['is_active'] != row.is_active:
                self._grant(access, 'MINISTRY_POSITION_ARCHIVE' if not values['is_active'] else 'MINISTRY_POSITION_EDIT', True)
                if not values['is_active'] and holders:
                    raise LeadershipServiceError('End current assignments before deactivating this position.')
            self._position_unique(db, row.ministry_id, values, row.id)
            old = self._position_snapshot(row)
            for field, value in values.items():
                setattr(row, field, value)
            row.updated_at, row.updated_by_user_id = datetime.now(timezone.utc), access.user_id
            action = 'POSITION_DEACTIVATED' if old['is_active'] and not row.is_active else 'POSITION_EDITED'
            self._record(db, access, row.ministry_id, action, row.id, old=old, new=self._position_snapshot(row))
            db.commit()
            return self._position_dto(row, holders, bool(used))

    def deactivate_position(self, position_id, expected_updated_at=None):
        # Permit ARCHIVE independently of ordinary position editing.
        with self._db() as (db, access):
            row = self._position(db, position_id)
            self._ministry(db, access, row.ministry_id, 'MINISTRY_POSITION_ARCHIVE', write=True)
            row = self._position(db, position_id, lock=True)
            self._check_version(row, expected_updated_at)
            if db.scalar(select(Assignment.id).where(Assignment.position_id == row.id, Assignment.is_current.is_(True)).limit(1)):
                raise LeadershipServiceError('End current assignments before deactivating this position.')
            if not row.is_active:
                raise LeadershipServiceError('This position is already inactive.')
            old = self._position_snapshot(row)
            row.is_active = False
            row.updated_at, row.updated_by_user_id = datetime.now(timezone.utc), access.user_id
            self._record(db, access, row.ministry_id, 'POSITION_DEACTIVATED', row.id, old=old, new=self._position_snapshot(row))
            db.commit()
            return self._position_dto(row)

    def delete_unused_position(self, position_id, *, confirmed=False, expected_updated_at=None):
        with self._db() as (db, access):
            row = self._position(db, position_id)
            self._ministry(db, access, row.ministry_id, 'MINISTRY_POSITION_DELETE_UNUSED', write=True)
            row = self._position(db, position_id, lock=True)
            self._check_version(row, expected_updated_at)
            if confirmed is not True:
                raise LeadershipServiceError('Explicit confirmation is required for permanent deletion.')
            if db.scalar(select(Assignment.id).where(Assignment.position_id == row.id).limit(1)):
                raise LeadershipServiceError('This position has assignment history. Deactivate it instead.')
            self._record(db, access, row.ministry_id, 'POSITION_DELETED_UNUSED', row.id, old=self._position_snapshot(row))
            db.delete(row)
            db.commit()

    @staticmethod
    def _date(value, required=True):
        if not value and not required:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        for pattern in ('%Y-%m-%d', '%d/%m/%Y'):
            try:
                return datetime.strptime(str(value).strip(), pattern).date()
            except ValueError:
                pass
        raise LeadershipServiceError('Enter a valid date as DD/MM/YYYY.')

    @classmethod
    def _dates(cls, start, end=None):
        start, end = cls._date(start), cls._date(end, False)
        if start > date.today() or (end and (end < start or end > date.today())):
            raise LeadershipServiceError('Appointments must start on or before today. End dates must be between the start date and today.')
        return start, end

    @staticmethod
    def _notes(value):
        notes = str(value or '').strip()
        if len(notes) > 10000:
            raise LeadershipServiceError('Keep appointment notes within 10,000 characters.')
        return notes or None

    @staticmethod
    def _current(db, position_id):
        return db.execute(select(Assignment, Member).join(Member, Member.id == Assignment.member_id)
            .where(Assignment.position_id == position_id, Assignment.is_current.is_(True)).order_by(Assignment.start_date, Assignment.id)).all()

    @staticmethod
    def _assignment_dto(row, member, position, ministry):
        return dict(id=str(row.id), ministry_id=str(row.ministry_id), ministry_name=ministry.name,
            member_id=str(row.member_id), full_name=member.full_name, member_no=member.member_no,
            phone=member.phone or '', photo_path=member.photo_path or '', position_id=str(row.position_id),
            position_name=position.name if row.is_current else row.position_name, position_code=row.position_code,
            is_leadership=position.is_leadership, position_active=position.is_active, is_current=row.is_current,
            start_date=row.start_date, end_date=row.end_date, notes=row.notes or '', updated_at=row.updated_at, created_at=row.created_at)

    @staticmethod
    def _assignment_query():
        return select(Assignment, Member, MinistryPosition, Ministry).join(Member, Member.id == Assignment.member_id)\
            .join(MinistryPosition, MinistryPosition.id == Assignment.position_id).join(Ministry, Ministry.id == Assignment.ministry_id)

    def _assignment(self, db, access, assignment_id, permission, write=False, lock=False):
        row = db.scalar(select(Assignment).where(Assignment.id == ministry_uuid(assignment_id)))
        if not row:
            raise LeadershipServiceError('Assignment is unavailable.')
        self._ministry(db, access, row.ministry_id, permission, write)
        if lock:
            self._position(db, row.position_id, lock=True)
            row = db.scalar(select(Assignment).where(Assignment.id == row.id).with_for_update().execution_options(populate_existing=True))
        return row

    def get_assignment(self, assignment_id):
        with self._db() as (db, access):
            row = self._assignment(db, access, assignment_id, 'MINISTRY_LEADERSHIP_VIEW')
            return self._assignment_dto(*db.execute(self._assignment_query().where(Assignment.id == row.id)).one())

    def candidate_members(self, ministry_id, search='', offset=0, limit=20):
        with self._db() as (db, access):
            ministry = self._ministry(db, access, ministry_id, 'MINISTRY_LEADERSHIP_ASSIGN', write=True, active=True)
            from src.services.member_service import MemberService
            stmt = MemberService._visible(access, select(Member)).where(Member.status == MemberStatus.ACTIVE)
            if search.strip():
                pattern = '%'+search.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
                full_name = func.concat_ws(' ', Member.first_name, Member.middle_name, Member.last_name)
                stmt = stmt.where(or_(*(column.ilike(pattern, escape='\\') for column in (full_name, Member.member_no, Member.phone))))
            total = db.scalar(select(func.count()).select_from(stmt.subquery()))
            membership = select(MemberMinistry.id).where(MemberMinistry.member_id == Member.id, MemberMinistry.ministry_id == ministry.id, MemberMinistry.is_active.is_(True)).exists()
            rows = db.execute(stmt.add_columns(membership).order_by(Member.last_name, Member.first_name, Member.id).offset(max(0, offset)).limit(min(50, max(1, limit))))
            return dict(total=total, rows=[dict(id=str(member.id), full_name=member.full_name, member_no=member.member_no,
                phone=member.phone or '', photo_path=member.photo_path or '', in_ministry=joined) for member, joined in rows])

    def _member(self, db, access, ministry, member_id, add_membership=False):
        from src.services.member_service import MemberService
        member = db.scalar(MemberService._visible(access, select(Member)).where(Member.id == ministry_uuid(member_id)).with_for_update())
        if not member or member.status != MemberStatus.ACTIVE:
            raise LeadershipServiceError('Select an active member you are permitted to view.')
        membership = db.scalar(select(MemberMinistry).where(MemberMinistry.member_id == member.id, MemberMinistry.ministry_id == ministry.id))
        if membership is None or not membership.is_active:
            if not add_membership:
                raise MembershipRequiredError(f'{member.full_name} is not currently a member of {ministry.name}.')
            self._grant(access, 'MEMBERS_EDIT', True)
            self._grant(access, 'MEMBERS_VIEW_ALL')
            old = dict(is_active=membership.is_active, left_at=membership.left_at.isoformat() if membership.left_at else None) if membership else None
            if membership:
                membership.is_active, membership.left_at = True, None
            else:
                primary = not db.scalar(select(MemberMinistry.id).where(MemberMinistry.member_id == member.id, MemberMinistry.is_active.is_(True)).limit(1))
                membership = MemberMinistry(member_id=member.id, ministry_id=ministry.id, is_active=True, is_primary=primary, joined_at=date.today())
                db.add(membership)
            self._record(db, access, ministry.id, 'MEMBERSHIP_JOINED_FOR_ASSIGNMENT', old=old,
                new=dict(member_id=str(member.id), is_active=True))
        return member

    def assign_member(self, ministry_id, member_id, position_id, start_date, end_date=None, notes='', *,
                      add_membership=False, replace_assignment_id=None, expected_replaced_updated_at=None):
        with self._db() as (db, access):
            ministry = self._ministry(db, access, ministry_id, 'MINISTRY_LEADERSHIP_ASSIGN', write=True, active=True)
            start, end = self._dates(start_date, end_date)
            notes = self._notes(notes)
            member = self._member(db, access, ministry, member_id, add_membership)
            position = self._position(db, position_id, lock=True)
            if position.ministry_id != ministry.id or not position.is_active:
                raise LeadershipServiceError('Select an active position belonging to this ministry.')
            holders = self._current(db, position.id)
            if any(holder.member_id == member.id for holder, _ in holders) and end is None:
                raise LeadershipServiceError('This member already holds this position. Edit or end the existing assignment.')
            replaced = None
            if replace_assignment_id:
                self._grant(access, 'MINISTRY_LEADERSHIP_END', True)
                if end is not None or position.max_current_holders != 1 or len(holders) != 1:
                    raise LeadershipServiceError('Controlled replacement requires one current holder in a single-holder position.')
                replaced = holders[0][0]
                if replaced.id != ministry_uuid(replace_assignment_id):
                    raise LeadershipServiceError('The current holder changed. Refresh before replacing.')
                self._check_version(replaced, expected_replaced_updated_at)
                if start < replaced.start_date:
                    raise LeadershipServiceError('Replacement date cannot precede the current appointment start.')
                self._finish(db, access, replaced, start, 'Replaced by '+member.full_name)
                db.flush()
            elif end is None and position.max_current_holders is not None and len(holders) >= position.max_current_holders:
                people = [dict(id=str(holder.id), full_name=person.full_name, updated_at=holder.updated_at) for holder, person in holders]
                raise PositionConflictError(self._position_dto(position), people)
            # Prevent overlapping repeat appointments for the same member/position. Boundary dates may meet.
            overlap = select(Assignment.id).where(Assignment.position_id == position.id, Assignment.member_id == member.id,
                or_(Assignment.end_date.is_(None), Assignment.end_date > start))
            if end is not None:
                overlap = overlap.where(Assignment.start_date < end)
            if db.scalar(overlap.limit(1)):
                raise LeadershipServiceError('The dates overlap another appointment for this member and position.')
            row = Assignment(ministry_id=ministry.id, member_id=member.id, position_id=position.id,
                position_name=position.name, position_code=position.code, start_date=start, end_date=end,
                is_current=end is None, notes=notes, created_by_user_id=access.user_id, updated_by_user_id=access.user_id)
            db.add(row)
            db.flush()
            self._record(db, access, ministry.id, 'LEADER_REPLACED' if replaced else 'MEMBER_ASSIGNED', position.id, row,
                old=self._assignment_snapshot(replaced) if replaced else None, new=self._assignment_snapshot(row))
            db.commit()
            return self._assignment_dto(row, member, position, ministry)

    def update_assignment(self, assignment_id, data, expected_updated_at=None):
        with self._db() as (db, access):
            row = self._assignment(db, access, assignment_id, 'MINISTRY_LEADERSHIP_EDIT', write=True, lock=True)
            self._check_version(row, expected_updated_at)
            # Identity is immutable: changing the office/person requires ending and appointing.
            for key in ('member_id', 'position_id', 'ministry_id'):
                if key in data and ministry_uuid(data[key]) != getattr(row, key):
                    raise LeadershipServiceError('Member, position and ministry cannot change on an existing appointment. End it and create a new appointment.')
            start, end = self._dates(data.get('start_date', row.start_date), data.get('end_date', row.end_date))
            if (end is None) != row.is_current:
                raise LeadershipServiceError('Use End Assignment for current appointments. Historical appointments cannot be reopened.')
            overlap = select(Assignment.id).where(Assignment.position_id == row.position_id,
                Assignment.member_id == row.member_id, Assignment.id != row.id,
                or_(Assignment.end_date.is_(None), Assignment.end_date > start))
            if end is not None:
                overlap = overlap.where(Assignment.start_date < end)
            if db.scalar(overlap.limit(1)):
                raise LeadershipServiceError('The dates overlap another appointment for this member and position.')
            old = self._assignment_snapshot(row)
            row.start_date, row.end_date, row.notes = start, end, self._notes(data.get('notes', row.notes))
            row.updated_at, row.updated_by_user_id = datetime.now(timezone.utc), access.user_id
            self._record(db, access, row.ministry_id, 'ASSIGNMENT_EDITED', row.position_id, row, old=old, new=self._assignment_snapshot(row))
            db.commit()
            return self._assignment_dto(*db.execute(self._assignment_query().where(Assignment.id == row.id)).one())

    def _finish(self, db, access, row, end, notes):
        if not row.is_current:
            raise LeadershipServiceError('This appointment has already ended.')
        _, end = self._dates(row.start_date, end)
        if end is None:
            raise LeadershipServiceError('Choose an end date.')
        old = self._assignment_snapshot(row)
        row.is_current, row.end_date = False, end
        if notes:
            row.notes = self._notes((row.notes+'\n' if row.notes else '')+notes)
        row.updated_at, row.updated_by_user_id = datetime.now(timezone.utc), access.user_id
        self._record(db, access, row.ministry_id, 'ASSIGNMENT_ENDED', row.position_id, row, old=old, new=self._assignment_snapshot(row))

    def end_assignment(self, assignment_id, end_date, notes='', expected_updated_at=None):
        with self._db() as (db, access):
            row = self._assignment(db, access, assignment_id, 'MINISTRY_LEADERSHIP_END', write=True, lock=True)
            self._check_version(row, expected_updated_at)
            self._finish(db, access, row, end_date, self._notes(notes))
            db.commit()
            return self._assignment_dto(*db.execute(self._assignment_query().where(Assignment.id == row.id)).one())

    def list_leadership(self, ministry_id, status='CURRENT', search='', limit=20, offset=0):
        with self._db() as (db, access):
            ministry = self._ministry(db, access, ministry_id)
            if status not in ('CURRENT', 'HISTORY', 'VACANT'):
                raise LeadershipServiceError('Choose Current, Historical or Vacant.')
            if status == 'VACANT':
                positions = [row for row in self._positions(db, ministry.id, True) if row['is_leadership'] and
                    row['current_holders'] < (row['max_current_holders'] or 1) and
                    (not search.strip() or search.casefold().strip() in (row['name']+' '+row['code']).casefold())]
                return dict(total=len(positions), rows=positions[max(0, offset):max(0, offset)+min(100, max(1, limit))])
            stmt = self._assignment_query().where(Assignment.ministry_id == ministry.id, Assignment.is_current.is_(status == 'CURRENT'))
            if search.strip():
                pattern = '%'+search.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
                full_name = func.concat_ws(' ', Member.first_name, Member.middle_name, Member.last_name)
                stmt = stmt.where(or_(*(column.ilike(pattern, escape='\\') for column in (full_name, Member.member_no, MinistryPosition.name, Assignment.position_name))))
            total = db.scalar(select(func.count()).select_from(stmt.subquery()))
            rows = db.execute(stmt.order_by(MinistryPosition.sort_order, Assignment.start_date.desc(), Assignment.id)
                .offset(max(0, offset)).limit(min(100, max(1, limit))))
            return dict(total=total, rows=[self._assignment_dto(*row) for row in rows])

    def list_current_leadership(self, ministry_id, **filters):
        return self.list_leadership(ministry_id, 'CURRENT', **filters)

    def list_leadership_history(self, ministry_id, **filters):
        return self.list_leadership(ministry_id, 'HISTORY', **filters)

    def leadership_stats(self, ministry_id):
        with self._db() as (db, access):
            ministry = self._ministry(db, access, ministry_id)
            positions = self._positions(db, ministry.id, True)
            current, people = db.execute(select(func.count(), func.count(func.distinct(Assignment.member_id)))
                .where(Assignment.ministry_id == ministry.id, Assignment.is_current.is_(True))).one()
            vacant = sum(row['is_leadership'] and row['current_holders'] < (row['max_current_holders'] or 1) for row in positions)
            return dict(positions=len(positions), current=current, members=people, vacant=vacant)

    @classmethod
    def member_leadership(cls, db, access, member_id):
        """Used after member visibility validation; restrict cross-ministry disclosure."""
        cls._grant(access, 'MINISTRY_LEADERSHIP_VIEW')
        stmt = cls._assignment_query().where(Assignment.member_id == ministry_uuid(member_id))
        if not (access.has('MINISTRY_LEADERSHIP_VIEW_ALL') and access.has('MINISTRIES_VIEW_ALL')):
            from src.models import UserMinistryScope
            scope = select(UserMinistryScope.ministry_id).where(UserMinistryScope.user_id == access.user_id,
                UserMinistryScope.is_active.is_(True), UserMinistryScope.can_view_attendance.is_(True))
            stmt = stmt.where(Assignment.ministry_id.in_(scope))
        return [cls._assignment_dto(*row) for row in db.execute(stmt.order_by(Assignment.is_current.desc(), Ministry.name, Assignment.start_date.desc(), Assignment.id))]

    def get_member_leadership(self, member_id):
        with self._db() as (db, access):
            from src.services.member_service import MemberService
            member = db.scalar(MemberService._visible(access, select(Member)).where(Member.id == ministry_uuid(member_id)))
            if not member:
                raise LeadershipAuthorizationError('Member is outside your permitted directory.')
            return self.member_leadership(db, access, member.id)

    def leadership_audit(self, ministry_id, assignment_id=None, limit=50):
        with self._db() as (db, access):
            ministry = self._ministry(db, access, ministry_id)
            stmt = select(Audit, User.username).outerjoin(User, User.id == Audit.actor_user_id).where(Audit.ministry_id == ministry.id)
            if assignment_id:
                stmt = stmt.where(Audit.assignment_id == ministry_uuid(assignment_id))
            rows = db.execute(stmt.order_by(Audit.occurred_at.desc(), Audit.id.desc()).limit(min(100, max(1, limit))))
            return [dict(action=row.action, actor=name or 'Unavailable account', occurred_at=row.occurred_at,
                         old_values=row.old_values, new_values=row.new_values) for row, name in rows]
