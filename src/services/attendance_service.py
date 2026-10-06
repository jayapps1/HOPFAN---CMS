"""Transactional attendance operations. Every entry point reloads database grants."""
from contextlib import contextmanager
from datetime import date, datetime, time, timezone
import json
import logging
import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import aliased, selectinload

from src.config.database import SessionLocal
from src.models import (
    AttendanceAuditLog, AttendanceRecord, AttendanceRosterMember, AttendanceRosterType,
    AttendanceScopeType, AttendanceSession, AttendanceSessionState, AttendanceSessionType,
    AttendanceStatus, AuthorizationAuditLog, Member, MemberMinistry, MemberStatus,
    Ministry, Role, User, UserMinistryScope, MinistryPosition, MinistryLeadershipAssignment,
)
from src.security.attendance_permissions import AttendancePermissionError, load_access
from src.services.operation_errors import OperationConflict

logger = logging.getLogger(__name__)


class AttendanceServiceError(Exception):
    pass


class AttendanceConflict(AttendanceServiceError, OperationConflict):
    pass


class AttendanceAuthorizationError(AttendanceServiceError, AttendancePermissionError):
    pass


def as_uuid(value) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise AttendanceServiceError("Invalid record identifier.") from exc


def value_of(value):
    return value.value if hasattr(value, "value") else value


class AttendanceService:
    def __init__(self, user_id=None, session_factory=SessionLocal):
        self.user_id = user_id
        self.session_factory = session_factory

    @contextmanager
    def _db(self):
        with self.session_factory() as db:
            try:
                yield db, load_access(db, self.user_id)
            except AttendanceAuthorizationError:
                raise
            except AttendancePermissionError as exc:
                db.rollback()
                raise AttendanceAuthorizationError(str(exc)) from exc
            except SQLAlchemyError as exc:
                db.rollback()
                logger.error("Attendance database operation failed: %s", type(exc).__name__)
                raise AttendanceServiceError("Attendance could not be saved or loaded. Please refresh and retry.") from exc

    @staticmethod
    def _deny():
        raise AttendanceAuthorizationError("You do not have permission for this attendance scope.")

    @staticmethod
    def _memberships(ministry_ids):
        return select(MemberMinistry.id).join(Ministry).where(
            MemberMinistry.member_id == Member.id,
            MemberMinistry.ministry_id.in_(ministry_ids),
            MemberMinistry.is_active.is_(True), Ministry.is_active.is_(True),
        ).exists()

    def capabilities(self):
        with self._db() as (_, access):
            return {"permissions": sorted(access.permissions),
                    "church_wide": access.has("ATTENDANCE_VIEW_ALL"),
                    "scope_ids": sorted(str(mid) for mid in access.scope_ids),
                    "can_view": access.has("ATTENDANCE_VIEW_ALL") or bool(access.ministries("view")),
                    "can_create": access.has("ATTENDANCE_CREATE_GLOBAL") or bool(access.ministries("create")),
                    "can_report": access.has("ATTENDANCE_EXPORT") and (
                        access.has("ATTENDANCE_VIEW_ALL") or bool(access.ministries("reports"))),
                    "can_manage_access": access.has("ATTENDANCE_SCOPE_MANAGE")}

    def _visible_sessions(self, access):
        if access.has("ATTENDANCE_VIEW_ALL"):
            return select(AttendanceSession)
        scopes = access.ministries("view")
        if not scopes:
            self._deny()
        shared_selected = select(AttendanceRosterMember.member_id).join(
            Member, Member.id == AttendanceRosterMember.member_id,
        ).where(AttendanceRosterMember.session_id == AttendanceSession.id,
                self._memberships(scopes)).exists()
        return select(AttendanceSession).where(or_(
            AttendanceSession.ministry_id.in_(scopes),
            and_(AttendanceSession.scope_type == AttendanceScopeType.GLOBAL,
                 or_(AttendanceSession.roster_type == AttendanceRosterType.WHOLE_CHURCH, shared_selected)),
        ))

    def _get(self, db, access, session_id, lock=False):
        stmt = self._visible_sessions(access).where(AttendanceSession.id == as_uuid(session_id))
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        session = db.scalar(stmt)
        if session is None:
            raise AttendanceAuthorizationError("Attendance session is unavailable or outside your scope.")
        return session

    def _require_action(self, access, session, action):
        if access.has(f"ATTENDANCE_{action.upper()}_ALL"):
            return
        scopes = access.ministries(action)
        if not scopes or (session.ministry_id and session.ministry_id not in scopes):
            self._deny()

    def _member_query(self, access, session, action="view", ministry_id=None, report=False):
        stmt = select(Member.id).join(AttendanceRosterMember,
            AttendanceRosterMember.member_id == Member.id).where(
                AttendanceRosterMember.session_id == session.id)
        self._require_action(access, session, action)
        if not access.has(f"ATTENDANCE_{action.upper()}_ALL"):
            stmt = stmt.where(self._memberships(access.ministries(action)))
        if ministry_id:
            ministry_uuid = as_uuid(ministry_id)
            if not access.has("ATTENDANCE_VIEW_ALL") and ministry_uuid not in access.ministries("view"):
                self._deny()
            if session.ministry_id and ministry_uuid != session.ministry_id:
                self._deny()
            stmt = stmt.where(self._memberships([ministry_uuid]))
        if report and not access.has("ATTENDANCE_VIEW_ALL"):
            stmt = stmt.where(self._memberships(access.ministries("reports")))
        return stmt

    @staticmethod
    def _session_dict(session, ministry_name=None, created_by=None):
        return {"id": str(session.id), "title": session.name, "name": session.name,
                "description": session.description or "", "session_type": value_of(session.session_type),
                "scope_type": value_of(session.scope_type), "roster_type": value_of(session.roster_type),
                "session_date": session.session_date, "start_time": session.start_time,
                "end_time": session.end_time, "state": value_of(session.state),
                "ministry_id": str(session.ministry_id) if session.ministry_id else None,
                "ministry_name": ministry_name or "Whole church", "created_by": created_by or "Unknown",
                "updated_at": session.updated_at,
                "created_at": session.created_at, "created_by_user_id": str(session.created_by_user_id) if session.created_by_user_id else None}

    def list_ministries(self, action="view"):
        with self._db() as (db, access):
            stmt = select(Ministry)
            if action == 'create':
                stmt = stmt.where(Ministry.is_active.is_(True))
            central = access.has("ATTENDANCE_CREATE_GLOBAL") if action == "create" else access.has("ATTENDANCE_VIEW_ALL")
            if not central:
                stmt = stmt.where(Ministry.id.in_(access.ministries(action)))
            return [{"id": str(m.id), "name": m.name} for m in db.scalars(stmt.order_by(Ministry.name)).all()]

    def list_sessions(self, state=None, ministry_id=None, limit=25, offset=0,
                      search="", session_type=None, date_from=None, date_to=None,
                      created_by_user_id=None, section=None):
        with self._db() as (db, access):
            stmt = self._visible_sessions(access)
            if search.strip():
                pattern = "%" + search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
                stmt = stmt.where(AttendanceSession.name.ilike(pattern, escape="\\"))
            if session_type and session_type != "ALL":
                stmt = stmt.where(AttendanceSession.session_type == self._enum(AttendanceSessionType, session_type))
            if date_from:
                stmt = stmt.where(AttendanceSession.session_date >= date_from)
            if date_to:
                stmt = stmt.where(AttendanceSession.session_date <= date_to)
            if date_from and date_to and date_from > date_to:
                raise AttendanceServiceError("The end date must be on or after the start date.")
            if created_by_user_id:
                stmt = stmt.where(AttendanceSession.created_by_user_id == as_uuid(created_by_user_id))
            if section == "UPCOMING":
                stmt = stmt.where(AttendanceSession.session_date > date.today())
            elif section == "MEETINGS":
                stmt = stmt.where(AttendanceSession.scope_type == AttendanceScopeType.MINISTRY)
            elif section == "RECENT":
                stmt = stmt.where(AttendanceSession.scope_type == AttendanceScopeType.MINISTRY,
                                  AttendanceSession.session_date <= date.today())
            elif section == "SUNDAY":
                stmt = stmt.where(AttendanceSession.session_type == AttendanceSessionType.SUNDAY_SERVICE)
            if state and state != "ALL":
                stmt = stmt.where(AttendanceSession.state == self._enum(AttendanceSessionState, state))
            if ministry_id:
                mid = as_uuid(ministry_id)
                if not access.has("ATTENDANCE_VIEW_ALL") and mid not in access.ministries("view"):
                    self._deny()
                stmt = stmt.where(or_(AttendanceSession.ministry_id == mid,
                                      AttendanceSession.scope_type == AttendanceScopeType.GLOBAL))
            total = db.scalar(select(func.count()).select_from(stmt.subquery()))
            stmt = stmt.add_columns(Ministry.name, User.username).outerjoin(
                Ministry, Ministry.id == AttendanceSession.ministry_id).outerjoin(
                User, User.id == AttendanceSession.created_by_user_id)
            rows = db.execute(stmt.order_by(AttendanceSession.session_date.desc(), AttendanceSession.created_at.desc())
                              .limit(min(max(limit, 1), 100)).offset(max(offset, 0))).all()
            stats = self._summaries(db, access, [row[0].id for row in rows], ministry_id)
            return {"total": total, "rows": [dict(self._session_dict(s, ministry, creator),
                    stats=stats.get(s.id, self._empty_stats())) for s, ministry, creator in rows]}

    def get_session(self, session_id):
        with self._db() as (db, access):
            session = self._get(db, access, session_id)
            ministry = db.get(Ministry, session.ministry_id) if session.ministry_id else None
            creator = db.get(User, session.created_by_user_id) if session.created_by_user_id else None
            result = self._session_dict(session, ministry.name if ministry else None, creator.username if creator else None)
            result["actions"] = self._session_actions(access, session)
            return result

    @staticmethod
    def _enum(enum_class, value):
        if enum_class is AttendanceRosterType and value == "EXECUTIVES":
            value = "MINISTRY_LEADERSHIP"
        try:
            return enum_class(value)
        except (TypeError, ValueError) as exc:
            raise AttendanceServiceError(f"Invalid {enum_class.__name__}.") from exc

    @staticmethod
    def _time(value):
        if not value:
            return None
        if isinstance(value, time):
            return value.replace(tzinfo=None)
        try:
            return datetime.strptime(str(value).strip(), "%H:%M").time()
        except ValueError as exc:
            raise AttendanceServiceError("Enter times as HH:MM, for example 09:30.") from exc

    def _candidate_query(self, ministry_id=None, executives=False):
        stmt = select(Member).where(Member.status == MemberStatus.ACTIVE)
        if ministry_id:
            membership = select(MemberMinistry.id).where(
                MemberMinistry.member_id == Member.id, MemberMinistry.ministry_id == ministry_id,
                MemberMinistry.is_active.is_(True))
            if executives:
                structured = select(MinistryLeadershipAssignment.id).join(MinistryPosition,
                    MinistryPosition.id == MinistryLeadershipAssignment.position_id).where(
                    MinistryLeadershipAssignment.member_id == Member.id,
                    MinistryLeadershipAssignment.ministry_id == ministry_id,
                    MinistryLeadershipAssignment.is_current.is_(True), MinistryPosition.is_leadership.is_(True)).correlate(Member).exists()
                modernized = select(MinistryLeadershipAssignment.id).where(
                    MinistryLeadershipAssignment.member_id == Member.id,
                    MinistryLeadershipAssignment.ministry_id == ministry_id).correlate(Member).exists()
                membership = membership.where(or_(structured, and_(~modernized, func.trim(MemberMinistry.position_title) != "")))
            stmt = stmt.where(membership.exists())
        return stmt

    def candidate_members(self, ministry_id=None, search="", offset=0, limit=50):
        with self._db() as (db, access):
            self._check_create(db, access, as_uuid(ministry_id) if ministry_id else None)
            stmt = self._search(self._candidate_query(as_uuid(ministry_id) if ministry_id else None), search)
            total = db.scalar(select(func.count()).select_from(stmt.subquery()))
            members = db.scalars(stmt.order_by(Member.last_name, Member.first_name)
                                 .offset(max(0, offset)).limit(min(limit, 100))).all()
            return {"total": total, "rows": [{"id": str(m.id), "full_name": m.full_name,
                      "member_no": m.member_no} for m in members]}

    def _check_create(self, db, access, ministry_id):
        if ministry_id:
            ministry = db.scalar(select(Ministry).where(Ministry.id==ministry_id).with_for_update(read=True))
            if ministry is None or not ministry.is_active:
                raise AttendanceServiceError("Select an active ministry.")
        if not access.has("ATTENDANCE_CREATE_GLOBAL"):
            if ministry_id is None or ministry_id not in access.ministries("create"):
                self._deny()
        if not access.has("ATTENDANCE_VIEW_ALL") and ministry_id not in access.ministries("view"):
            self._deny()

    def create_session(self, *, title, session_type, scope_type, session_date,
                       ministry_id=None, roster_type=None, selected_member_ids=None,
                       description="", start_time=None, end_time=None, state="OPEN"):
        title = str(title).strip()
        if not title or len(title) > 150:
            raise AttendanceServiceError("Enter an attendance title of 1–150 characters.")
        if not isinstance(session_date, date) or isinstance(session_date, datetime):
            raise AttendanceServiceError("Select a valid attendance date.")
        kind = self._enum(AttendanceSessionType, session_type)
        scope = self._enum(AttendanceScopeType, scope_type)
        roster = self._enum(AttendanceRosterType, roster_type or (
            "WHOLE_CHURCH" if scope == AttendanceScopeType.GLOBAL else
            "MINISTRY_LEADERSHIP" if kind == AttendanceSessionType.LEADERSHIP_MEETING else "ALL_MINISTRY_MEMBERS"))
        state = self._enum(AttendanceSessionState, state)
        if state not in {AttendanceSessionState.DRAFT, AttendanceSessionState.OPEN}:
            raise AttendanceServiceError("New sessions must be Draft or Open.")
        mid = as_uuid(ministry_id) if ministry_id else None
        if (scope == AttendanceScopeType.MINISTRY) != bool(mid):
            raise AttendanceServiceError("Ministry scope requires a ministry; global scope cannot have one.")
        allowed = {AttendanceRosterType.WHOLE_CHURCH, AttendanceRosterType.SELECTED_MEMBERS} if mid is None else {
            AttendanceRosterType.ALL_MINISTRY_MEMBERS, AttendanceRosterType.SELECTED_MEMBERS, AttendanceRosterType.EXECUTIVES}
        if roster not in allowed:
            raise AttendanceServiceError("Choose a roster appropriate to the session scope.")
        if kind == AttendanceSessionType.SUNDAY_SERVICE and (mid or roster != AttendanceRosterType.WHOLE_CHURCH):
            raise AttendanceServiceError("Sunday services must share one whole-church roster.")
        start, end = self._time(start_time), self._time(end_time)
        if start and end and end < start:
            raise AttendanceServiceError("End time must be at or after start time.")
        with self._db() as (db, access):
            self._check_create(db, access, mid)
            candidates = self._candidate_query(mid, roster == AttendanceRosterType.EXECUTIVES)
            eligible = set(db.scalars(candidates.with_only_columns(Member.id)).all())
            if roster == AttendanceRosterType.SELECTED_MEMBERS:
                selected = {as_uuid(member) for member in (selected_member_ids or [])}
                if not selected or not selected <= eligible:
                    raise AttendanceServiceError("Select eligible members within the chosen attendance scope.")
                eligible = selected
            now = datetime.now(timezone.utc)
            session = AttendanceSession(name=title, description=description.strip() or None,
                session_type=kind, scope_type=scope, roster_type=roster, session_date=session_date,
                ministry_id=mid, start_time=start, end_time=end, state=state,
                created_by_user_id=access.user_id,
                opened_at=now if state == AttendanceSessionState.OPEN else None)
            db.add(session)
            db.flush()
            db.add_all(AttendanceRosterMember(session_id=session.id, member_id=member) for member in eligible)
            self._audit(db, access, session, "SESSION_CREATED", new=state.value)
            db.commit()
            return self._session_dict(session)

    @staticmethod
    def _search(stmt, search):
        if search.strip():
            pattern = "%" + search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            full_name = func.concat_ws(" ", Member.first_name, Member.middle_name, Member.last_name)
            stmt = stmt.where(or_(*(column.ilike(pattern, escape="\\") for column in (
                full_name, Member.first_name, Member.last_name, Member.member_no, Member.phone))))
        return stmt

    @staticmethod
    def _empty_stats():
        return dict(eligible=0, PRESENT=0, LATE=0, EXCUSED=0, ABSENT=0, unmarked=0, rate=0.0)

    def _summaries(self, db, access, session_ids, ministry_id=None):
        if not session_ids:
            return {}
        stmt = select(AttendanceRosterMember.session_id, func.count(Member.id), *(
            func.count(AttendanceRecord.id).filter(AttendanceRecord.status == status)
            for status in AttendanceStatus)).select_from(AttendanceRosterMember).join(
                Member, Member.id == AttendanceRosterMember.member_id).outerjoin(AttendanceRecord, and_(
                    AttendanceRecord.session_id == AttendanceRosterMember.session_id,
                    AttendanceRecord.member_id == Member.id)).where(
                        AttendanceRosterMember.session_id.in_(session_ids))
        if not access.has("ATTENDANCE_VIEW_ALL"):
            stmt = stmt.where(self._memberships(access.ministries("view")))
        if ministry_id:
            stmt = stmt.where(self._memberships([as_uuid(ministry_id)]))
        result = {}
        for sid, eligible, present, late, excused, absent in db.execute(stmt.group_by(AttendanceRosterMember.session_id)):
            result[sid] = dict(eligible=eligible, PRESENT=present, LATE=late, EXCUSED=excused,
                ABSENT=absent, unmarked=eligible-present-late-excused-absent,
                rate=round((present+late)*100/eligible, 1) if eligible else 0.0)
        return result

    def session_counts(self, session_id, ministry_id=None):
        with self._db() as (db, access):
            session = self._get(db, access, session_id)
            self._member_query(access, session, ministry_id=ministry_id)
            return self._summaries(db, access, [session.id], ministry_id).get(session.id, self._empty_stats())

    def roster(self, session_id, search="", ministry_id=None, status=None, limit=40, offset=0, report=False, *, member_id=None):
        with self._db() as (db, access):
            session = self._get(db, access, session_id)
            if report and not access.has("ATTENDANCE_EXPORT"):
                self._deny()
            allowed = self._member_query(access, session, ministry_id=ministry_id, report=report)
            marker, updater = aliased(User), aliased(User)
            stmt = select(Member, AttendanceRecord, marker.username, updater.username).outerjoin(
                AttendanceRecord, and_(AttendanceRecord.member_id == Member.id,
                                       AttendanceRecord.session_id == session.id)).outerjoin(
                marker, marker.id == AttendanceRecord.marked_by_user_id).outerjoin(
                updater, updater.id == AttendanceRecord.updated_by_user_id).where(Member.id.in_(allowed))
            stmt = self._search(stmt, search)
            if member_id is not None:
                stmt = stmt.where(Member.id == as_uuid(member_id))
            if status == "UNMARKED":
                stmt = stmt.where(AttendanceRecord.id.is_(None))
            elif status and status != "ALL":
                stmt = stmt.where(AttendanceRecord.status == self._enum(AttendanceStatus, status))
            total = db.scalar(select(func.count()).select_from(stmt.subquery()))
            rows = db.execute(stmt.order_by(Member.last_name, Member.first_name, Member.id)
                              .limit(min(max(limit, 1), 200)).offset(max(offset, 0))).all()
            memberships = {}
            if rows:
                for member_id, name in db.execute(select(MemberMinistry.member_id, Ministry.name).join(Ministry).where(
                        MemberMinistry.member_id.in_([r[0].id for r in rows]),
                        MemberMinistry.is_active.is_(True), Ministry.is_active.is_(True)).order_by(Ministry.name)):
                    memberships.setdefault(member_id, []).append(name)
            result = []
            for member, record, marked_by, updated_by in rows:
                result.append(dict(id=str(member.id), member_no=member.member_no, full_name=member.full_name,
                    record_id=str(record.id) if record else None,
                    phone=member.phone or "", photo_path=member.photo_path or "",
                    ministries=memberships.get(member.id, []), attendance_status=value_of(record.status) if record else None,
                    marked_by=marked_by or ("Legacy / unavailable" if record else ""), marked_at=record.marked_at if record else None,
                    updated_by=updated_by, updated_at=record.updated_at if record else None,
                    notes=record.notes if record else None))
            # Two bounded set queries compute row grants without an N+1 lookup.
            for action in ("record", "correct"):
                central = access.has(f"ATTENDANCE_{action.upper()}_ALL")
                own = access.ministries(action)
                authorized = central or (own and (session.ministry_id is None or session.ministry_id in own))
                permitted = set(db.scalars(self._member_query(access, session, action).where(
                    Member.id.in_([r[0].id for r in rows]))).all()) if authorized and rows else set()
                state_ok = session.state == AttendanceSessionState.OPEN or (
                    action == "correct" and session.state == AttendanceSessionState.CLOSED
                    and access.has("ATTENDANCE_CORRECT_CLOSED"))
                for row in result:
                    row[f"can_{action}"] = state_ok and as_uuid(row["id"]) in permitted
            return {"rows": result, "total": total,
                    "stats": self._summaries(db, access, [session.id], ministry_id).get(session.id, self._empty_stats())}

    def _audit(self, db, access, session, action, record=None, old=None, new=None, reason=None):
        db.add(AttendanceAuditLog(session_id=session.id, attendance_record_id=record.id if record else None,
            member_id=record.member_id if record else None, old_status=old, new_status=new,
            reason=reason, changed_by_user_id=access.user_id, action_type=action))

    def mark(self, session_id, member_id, status, *, reason=None, expected_status=None, notes=None,
             expected_updated_at=None, ministry_id=None):
        status = self._enum(AttendanceStatus, status)
        member_uuid = as_uuid(member_id)
        with self._db() as (db, access):
            # Serializes marking/correction/closure, including concurrent first inserts.
            session = self._get(db, access, session_id, lock=True)
            record = db.scalar(select(AttendanceRecord).where(
                AttendanceRecord.session_id == session.id, AttendanceRecord.member_id == member_uuid)
                .execution_options(populate_existing=True))
            action = "correct" if record else "record"
            self._require_action(access, session, action)
            if not db.scalar(self._member_query(access, session, action, ministry_id=ministry_id).where(Member.id == member_uuid)):
                self._deny()
            if session.state in {AttendanceSessionState.DRAFT, AttendanceSessionState.LOCKED}:
                raise AttendanceServiceError("Open the session before changing attendance.")
            if session.state == AttendanceSessionState.CLOSED and (
                    not record or not access.has("ATTENDANCE_CORRECT_CLOSED")):
                raise AttendanceAuthorizationError("Closed sessions require explicit correction permission.")
            now = datetime.now(timezone.utc)
            if record:
                if expected_updated_at is not None and record.updated_at != expected_updated_at:
                    raise AttendanceConflict("This attendance record changed. Refresh before correcting.")
                if expected_status != record.status.value:
                    raise AttendanceConflict("Attendance has already been marked or changed. Refresh before correcting it.")
                if record.status == status:
                    return
                if not reason or not reason.strip():
                    raise AttendanceServiceError("A reason is required for every attendance correction.")
                old = record.status.value
                record.status = status
                record.updated_by_user_id = access.user_id
                record.updated_at = now
                self._audit(db, access, session, "CORRECTED", record, old, status.value, reason.strip())
            else:
                if expected_status is not None:
                    raise AttendanceConflict("This record has changed. Refresh the roster.")
                record = AttendanceRecord(session_id=session.id, member_id=member_uuid,
                    status=status, marked_by_user_id=access.user_id, marked_at=now,
                    updated_at=now, notes=notes)
                db.add(record)
                db.flush()
                self._audit(db, access, session, "CREATED", record, new=status.value)
            db.commit()

    def correct_record(self, record_id, status, reason, expected_status, expected_updated_at, ministry_id=None):
        with self._db() as (db, access):
            record = db.get(AttendanceRecord, as_uuid(record_id))
            if record is None:
                self._deny()
            session = self._get(db, access, record.session_id)
            if not db.scalar(self._member_query(access, session, "correct", ministry_id=ministry_id)
                             .where(Member.id == record.member_id)):
                self._deny()
            session_id, member_id = record.session_id, record.member_id
        self.mark(session_id, member_id, status, reason=reason, expected_status=expected_status,
                  expected_updated_at=expected_updated_at, ministry_id=ministry_id)
        return session_id, member_id

    def _session_actions(self, access, session):
        central = access.has("ATTENDANCE_VIEW_ALL")
        own_close = session.ministry_id in access.ministries("close") if session.ministry_id else False
        own_correct = session.ministry_id in access.ministries("correct") if session.ministry_id else False
        creator = access.has("ATTENDANCE_CREATE_GLOBAL") or session.ministry_id in access.ministries("create")
        return dict(open=session.state == AttendanceSessionState.DRAFT and creator,
            close=session.state == AttendanceSessionState.OPEN and access.has("ATTENDANCE_CLOSE_SESSION") and (central or own_close),
            reopen=session.state == AttendanceSessionState.CLOSED and access.has("ATTENDANCE_REOPEN_SESSION") and (central or own_correct),
            unlock=session.state == AttendanceSessionState.LOCKED and central and access.has("ATTENDANCE_REOPEN_SESSION") and access.has("ATTENDANCE_UNLOCK_SESSION"),
            lock=session.state == AttendanceSessionState.CLOSED and access.has("ATTENDANCE_LOCK_SESSION") and (central or own_correct))

    def transition(self, session_id, action, *, reason=None, expected_updated_at=None):
        with self._db() as (db, access):
            session = self._get(db, access, session_id, lock=True)
            if expected_updated_at is not None and session.updated_at != expected_updated_at:
                raise AttendanceConflict("This attendance session changed. Refresh before continuing.")
            if not self._session_actions(access, session).get(action):
                raise AttendanceAuthorizationError("This session transition is unavailable or unauthorized.")
            if action in {"reopen", "unlock", "lock"} and not (reason and reason.strip()):
                raise AttendanceServiceError("Enter a reason for this session change.")
            old, now = session.state.value, datetime.now(timezone.utc)
            if action == "close":
                existing = select(AttendanceRecord.member_id).where(AttendanceRecord.session_id == session.id)
                missing = db.scalars(select(AttendanceRosterMember.member_id).where(
                    AttendanceRosterMember.session_id == session.id,
                    AttendanceRosterMember.member_id.not_in(existing))).all()
                records = [AttendanceRecord(session_id=session.id, member_id=mid, status=AttendanceStatus.ABSENT,
                           marked_by_user_id=access.user_id, marked_at=now, updated_at=now,
                           notes="Unmarked when session closed.") for mid in missing]
                db.add_all(records)
                db.flush()
                for record in records:
                    self._audit(db, access, session, "CREATED", record, new="ABSENT", reason="Unmarked when session closed.")
                session.state = AttendanceSessionState.CLOSED
                session.closed_at, session.closed_by_user_id = now, access.user_id
            elif action == "lock":
                session.state = AttendanceSessionState.LOCKED
                session.locked_at, session.locked_by_user_id = now, access.user_id
            else:
                session.state = AttendanceSessionState.OPEN
                if action == "open":
                    session.opened_at = now
                else:
                    session.reopened_at, session.reopened_by_user_id = now, access.user_id
            session.updated_at = now
            audit_action = {"open": "SESSION_OPENED", "close": "SESSION_CLOSED", "lock": "SESSION_LOCKED",
                            "reopen": "SESSION_REOPENED", "unlock": "SESSION_UNLOCKED"}[action]
            self._audit(db, access, session, audit_action, old=old, new=session.state.value,
                        reason=reason.strip() if reason else None)
            db.commit()

    def close_session(self, session_id):
        return self.transition(session_id, "close")

    def audit_history(self, session_id, member_id=None, offset=0, limit=100):
        with self._db() as (db, access):
            session = self._get(db, access, session_id)
            if not access.has("ATTENDANCE_VIEW_AUDIT"):
                self._deny()
            allowed = self._member_query(access, session)
            stmt = select(AttendanceAuditLog, User.username, Member.first_name, Member.last_name).outerjoin(
                User, User.id == AttendanceAuditLog.changed_by_user_id).outerjoin(
                Member, Member.id == AttendanceAuditLog.member_id).where(
                    AttendanceAuditLog.session_id == session.id,
                    or_(AttendanceAuditLog.member_id.is_(None), AttendanceAuditLog.member_id.in_(allowed)))
            if member_id:
                stmt = stmt.where(AttendanceAuditLog.member_id == as_uuid(member_id))
            rows = db.execute(stmt.order_by(AttendanceAuditLog.changed_at.desc(), AttendanceAuditLog.id)
                              .limit(min(limit, 200)).offset(max(offset, 0))).all()
            return [dict(action=log.action_type, member=" ".join(p for p in (first, last) if p),
                         old_status=log.old_status, new_status=log.new_status,
                         reason=log.reason or "", changed_by=username or "Legacy / unavailable",
                         changed_at=log.changed_at) for log, username, first, last in rows]

    def overview(self):
        """Bounded queries for role-aware dashboard and attendance landing cards."""
        with self._db() as (db, access):
            visible = self._visible_sessions(access).subquery()
            counts = db.execute(select(
                func.count().filter(visible.c.session_date == date.today()),
                func.count().filter(visible.c.state == AttendanceSessionState.OPEN),
                func.count().filter(visible.c.state.in_([AttendanceSessionState.CLOSED, AttendanceSessionState.LOCKED])),
                func.count().filter(visible.c.scope_type == AttendanceScopeType.MINISTRY),
            )).one()
            latest = db.scalar(self._visible_sessions(access).where(
                AttendanceSession.session_type == AttendanceSessionType.SUNDAY_SERVICE,
                AttendanceSession.session_date <= date.today(),
                AttendanceSession.state != AttendanceSessionState.DRAFT).order_by(
                    AttendanceSession.session_date.desc(), AttendanceSession.created_at.desc()).limit(1))
            recent = db.scalars(self._visible_sessions(access).where(
                AttendanceSession.scope_type == AttendanceScopeType.MINISTRY,
                AttendanceSession.session_date <= date.today(),
                AttendanceSession.state.in_([AttendanceSessionState.CLOSED, AttendanceSessionState.LOCKED]),
            ).order_by(AttendanceSession.session_date.desc(), AttendanceSession.created_at.desc()).limit(6)).all()
            summaries = self._summaries(db, access, [s.id for s in recent] + ([latest.id] if latest else []))
            sunday = summaries.get(latest.id, self._empty_stats()) if latest else self._empty_stats()
            sunday = dict(sunday, count=sunday['PRESENT']+sunday['LATE'], date=latest.session_date if latest else None)
            eligible = sum(summaries.get(s.id, self._empty_stats())['eligible'] for s in recent)
            attended = sum(summaries.get(s.id, self._empty_stats())['PRESENT']+summaries.get(s.id, self._empty_stats())['LATE'] for s in recent)
            return dict(today=counts[0], open=counts[1], completed=counts[2], meetings=counts[3],
                rate=round(attended*100/eligible, 1) if eligible else None, sunday=sunday,
                trend=[dict(title=s.name, date=s.session_date, rate=summaries.get(s.id, self._empty_stats())['rate']) for s in reversed(recent)])

    def latest_sunday_count(self):
        with self._db() as (db, access):
            session = db.scalar(self._visible_sessions(access).where(
                AttendanceSession.session_type == AttendanceSessionType.SUNDAY_SERVICE,
                AttendanceSession.session_date <= date.today(),
                AttendanceSession.state != AttendanceSessionState.DRAFT).order_by(
                    AttendanceSession.session_date.desc(), AttendanceSession.created_at.desc()).limit(1))
            if session is None:
                return dict(self._empty_stats(), count=0, date=None)
            counts = self._summaries(db, access, [session.id]).get(session.id, self._empty_stats())
            return dict(counts, count=counts["PRESENT"]+counts["LATE"], date=session.session_date)

    def access_configuration(self):
        with self._db() as (db, access):
            if not access.has("ATTENDANCE_SCOPE_MANAGE"):
                self._deny()
            users = db.scalars(select(User).options(selectinload(User.roles)).order_by(User.username)).all()
            ministries = db.scalars(select(Ministry).where(Ministry.is_active.is_(True)).order_by(Ministry.name)).all()
            grants = db.scalars(select(UserMinistryScope)).all()
            fields = ["can_view_attendance", "can_create_attendance", "can_record_attendance",
                      "can_correct_attendance", "can_close_attendance", "can_view_reports", "is_active"]
            return {"users": [{"id": str(u.id), "name": u.username, "roles": [r.code for r in u.roles]} for u in users],
                    "ministries": [{"id": str(m.id), "name": m.name} for m in ministries],
                    "scopes": [{"user_id": str(g.user_id), "ministry_id": str(g.ministry_id),
                                **{field: getattr(g, field) for field in fields}} for g in grants]}

    def set_ministry_scope(self, user_id, ministry_id, grants, *, assign_leader_role=False):
        with self._db() as (db, access):
            if not access.has("ATTENDANCE_SCOPE_MANAGE"):
                self._deny()
            target = db.scalar(select(User).where(User.id == as_uuid(user_id)).options(selectinload(User.roles)).with_for_update())
            ministry = db.get(Ministry, as_uuid(ministry_id))
            if not target or not ministry or not ministry.is_active:
                raise AttendanceServiceError("Select a valid user and active ministry.")
            fields = ["can_view_attendance", "can_create_attendance", "can_record_attendance",
                      "can_correct_attendance", "can_close_attendance", "can_view_reports", "is_active"]
            if any(type(grants.get(field, False)) is not bool for field in fields):
                raise AttendanceServiceError("Scope grants must be true or false.")
            scope = db.scalar(select(UserMinistryScope).where(UserMinistryScope.user_id == target.id,
                                                              UserMinistryScope.ministry_id == ministry.id))
            old = {f: getattr(scope, f) for f in fields} if scope else None
            if scope is None:
                scope = UserMinistryScope(user_id=target.id, ministry_id=ministry.id, created_by_user_id=access.user_id)
                db.add(scope)
            scope.legacy_attendance_limits = True
            for field in fields:
                setattr(scope, field, grants.get(field, False))
            if assign_leader_role:
                role = db.scalar(select(Role).where(Role.code == "MINISTRY_ATTENDANCE_LEADER"))
                if role is None:
                    raise AttendanceServiceError("Attendance role has not been seeded. Run the migration.")
                if any(p.is_active and not access.has(p.code) for p in role.permissions):
                    self._deny()
                if role not in target.roles:
                    target.roles.append(role)
                    db.add(AuthorizationAuditLog(changed_by_user_id=access.user_id, target_user_id=target.id,
                        ministry_id=ministry.id, action_type="ROLE_GRANTED", new_values=json.dumps({"role": role.code})))
            db.add(AuthorizationAuditLog(changed_by_user_id=access.user_id, target_user_id=target.id,
                ministry_id=ministry.id, action_type="MINISTRY_SCOPE_CHANGED", old_values=json.dumps(old),
                new_values=json.dumps({f: getattr(scope, f) for f in fields}, sort_keys=True)))
            db.commit()
