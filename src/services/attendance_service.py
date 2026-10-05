from datetime import date
import uuid

from sqlalchemy import (
    func,
    or_,
    select,
)
from sqlalchemy.orm import selectinload

from src.config.database import SessionLocal

from src.models.attendance_record import (
    AttendanceRecord,
    AttendanceStatus,
)

from src.models.attendance_session import (
    AttendanceSession,
    AttendanceSessionState,
    AttendanceSessionType,
)

from src.models.member import (
    Member,
    MemberStatus,
)

from src.models.member_ministry import (
    MemberMinistry,
)

from src.models.ministry import Ministry


class AttendanceServiceError(Exception):
    pass


class AttendanceService:

    # -----------------------------------------------------
    # SERIALIZATION
    # -----------------------------------------------------

    @staticmethod
    def _session_dict(session):
        return {
            "id": str(session.id),
            "name": session.name,
            "session_type": session.session_type.value,
            "session_date": session.session_date.isoformat(),
            "state": session.state.value,
            "ministry_id": (
                str(session.ministry_id)
                if session.ministry_id
                else None
            ),
        }

    # -----------------------------------------------------
    # SUNDAY SESSION
    # -----------------------------------------------------

    def open_sunday_session(
        self,
        session_date=None,
        name="Sunday Service",
        user_id=None,
    ):
        session_date = (
            session_date
            or date.today()
        )

        with SessionLocal() as db:
            session = db.scalar(
                select(AttendanceSession)
                .where(
                    AttendanceSession.session_type
                    == AttendanceSessionType.SUNDAY_SERVICE,
                    AttendanceSession.session_date
                    == session_date,
                    AttendanceSession.name
                    == name,
                )
            )

            if session is None:
                session = AttendanceSession(
                    name=name,
                    session_type=(
                        AttendanceSessionType.SUNDAY_SERVICE
                    ),
                    session_date=session_date,
                    state=(
                        AttendanceSessionState.OPEN
                    ),
                    created_by_user_id=(
                        uuid.UUID(str(user_id))
                        if user_id
                        else None
                    ),
                )

                db.add(session)
                db.commit()
                db.refresh(session)

            return self._session_dict(
                session
            )

    # -----------------------------------------------------
    # SESSIONS
    # -----------------------------------------------------

    def list_sessions(
        self,
        limit=30,
    ):
        with SessionLocal() as db:
            sessions = db.scalars(
                select(AttendanceSession)
                .order_by(
                    AttendanceSession.session_date.desc(),
                    AttendanceSession.created_at.desc(),
                )
                .limit(limit)
            ).all()

            return [
                self._session_dict(
                    session
                )
                for session in sessions
            ]

    def get_session(
        self,
        session_id,
    ):
        with SessionLocal() as db:
            session = db.get(
                AttendanceSession,
                uuid.UUID(
                    str(session_id)
                ),
            )

            if session is None:
                raise AttendanceServiceError(
                    "Attendance session not found."
                )

            return self._session_dict(
                session
            )

    # -----------------------------------------------------
    # MINISTRIES
    # -----------------------------------------------------

    def list_ministries(self):
        with SessionLocal() as db:
            rows = db.scalars(
                select(Ministry)
                .where(
                    Ministry.is_active.is_(True)
                )
                .order_by(
                    Ministry.name
                )
            ).all()

            return [
                {
                    "id": str(item.id),
                    "name": item.name,
                }
                for item in rows
            ]

    # -----------------------------------------------------
    # ROSTER
    # -----------------------------------------------------

    def roster(
        self,
        session_id,
        search="",
        ministry_id=None,
    ):
        session_uuid = uuid.UUID(
            str(session_id)
        )

        with SessionLocal() as db:
            stmt = select(Member).where(
                Member.status
                == MemberStatus.ACTIVE
            )

            if ministry_id:
                stmt = (
                    stmt
                    .join(
                        MemberMinistry,
                        MemberMinistry.member_id
                        == Member.id,
                    )
                    .where(
                        MemberMinistry.ministry_id
                        == uuid.UUID(
                            str(ministry_id)
                        ),
                        MemberMinistry.is_active.is_(
                            True
                        ),
                    )
                )

            search = search.strip()

            if search:
                pattern = f"%{search}%"

                stmt = stmt.where(
                    or_(
                        Member.member_no.ilike(
                            pattern
                        ),
                        Member.first_name.ilike(
                            pattern
                        ),
                        Member.middle_name.ilike(
                            pattern
                        ),
                        Member.last_name.ilike(
                            pattern
                        ),
                        Member.phone.ilike(
                            pattern
                        ),
                        Member.email.ilike(
                            pattern
                        ),
                    )
                )

            stmt = (
                stmt
                .distinct()
                .order_by(
                    Member.last_name,
                    Member.first_name,
                )
            )

            members = db.scalars(
                stmt
            ).unique().all()

            records = db.scalars(
                select(AttendanceRecord)
                .where(
                    AttendanceRecord.session_id
                    == session_uuid
                )
            ).all()

            record_map = {
                record.member_id: record.status.value
                for record in records
            }

            result = []

            for member in members:
                ministries = db.scalars(
                    select(Ministry.name)
                    .join(
                        MemberMinistry,
                        MemberMinistry.ministry_id
                        == Ministry.id,
                    )
                    .where(
                        MemberMinistry.member_id
                        == member.id,
                        MemberMinistry.is_active.is_(
                            True
                        ),
                    )
                    .order_by(
                        Ministry.name
                    )
                ).all()

                result.append(
                    {
                        "id": str(member.id),
                        "member_no": member.member_no,
                        "full_name": member.full_name,
                        "phone": member.phone or "",
                        "photo_path": member.photo_path or "",
                        "ministries": list(ministries),
                        "attendance_status": (
                            record_map.get(
                                member.id
                            )
                        ),
                    }
                )

            return result

    # -----------------------------------------------------
    # MARK ATTENDANCE
    # -----------------------------------------------------

    def mark(
        self,
        session_id,
        member_id,
        status,
        user_id=None,
    ):
        try:
            attendance_status = (
                AttendanceStatus(
                    status
                )
            )
        except ValueError as exc:
            raise AttendanceServiceError(
                "Invalid attendance status."
            ) from exc

        session_uuid = uuid.UUID(
            str(session_id)
        )

        member_uuid = uuid.UUID(
            str(member_id)
        )

        with SessionLocal() as db:
            session = db.get(
                AttendanceSession,
                session_uuid,
            )

            if session is None:
                raise AttendanceServiceError(
                    "Attendance session not found."
                )

            if (
                session.state
                == AttendanceSessionState.CLOSED
            ):
                raise AttendanceServiceError(
                    "This attendance session is closed."
                )

            record = db.scalar(
                select(AttendanceRecord)
                .where(
                    AttendanceRecord.session_id
                    == session_uuid,
                    AttendanceRecord.member_id
                    == member_uuid,
                )
            )

            if record is None:
                record = AttendanceRecord(
                    session_id=session_uuid,
                    member_id=member_uuid,
                    status=attendance_status,
                    marked_by_user_id=(
                        uuid.UUID(str(user_id))
                        if user_id
                        else None
                    ),
                )

                db.add(record)

            else:
                record.status = (
                    attendance_status
                )

                record.marked_by_user_id = (
                    uuid.UUID(str(user_id))
                    if user_id
                    else None
                )

            db.commit()

    # -----------------------------------------------------
    # SESSION COUNTS
    # -----------------------------------------------------

    def session_counts(
        self,
        session_id,
    ):
        session_uuid = uuid.UUID(
            str(session_id)
        )

        with SessionLocal() as db:
            rows = db.execute(
                select(
                    AttendanceRecord.status,
                    func.count(
                        AttendanceRecord.id
                    ),
                )
                .where(
                    AttendanceRecord.session_id
                    == session_uuid
                )
                .group_by(
                    AttendanceRecord.status
                )
            ).all()

            counts = {
                "PRESENT": 0,
                "LATE": 0,
                "EXCUSED": 0,
                "ABSENT": 0,
            }

            for status, count in rows:
                counts[
                    status.value
                ] = count

            return counts

    # -----------------------------------------------------
    # CLOSE SESSION
    # -----------------------------------------------------

    def close_session(
        self,
        session_id,
    ):
        session_uuid = uuid.UUID(
            str(session_id)
        )

        with SessionLocal() as db:
            session = db.get(
                AttendanceSession,
                session_uuid,
            )

            if session is None:
                raise AttendanceServiceError(
                    "Attendance session not found."
                )

            if (
                session.state
                == AttendanceSessionState.CLOSED
            ):
                return

            member_stmt = select(
                Member.id
            ).where(
                Member.status
                == MemberStatus.ACTIVE
            )

            if session.ministry_id:
                member_stmt = (
                    member_stmt
                    .join(
                        MemberMinistry,
                        MemberMinistry.member_id
                        == Member.id,
                    )
                    .where(
                        MemberMinistry.ministry_id
                        == session.ministry_id,
                        MemberMinistry.is_active.is_(
                            True
                        ),
                    )
                    .distinct()
                )

            member_ids = db.scalars(
                member_stmt
            ).all()

            existing_ids = set(
                db.scalars(
                    select(
                        AttendanceRecord.member_id
                    )
                    .where(
                        AttendanceRecord.session_id
                        == session_uuid
                    )
                ).all()
            )

            for member_id in member_ids:
                if member_id not in existing_ids:
                    db.add(
                        AttendanceRecord(
                            session_id=session_uuid,
                            member_id=member_id,
                            status=(
                                AttendanceStatus.ABSENT
                            ),
                        )
                    )

            session.state = (
                AttendanceSessionState.CLOSED
            )

            db.commit()

    # -----------------------------------------------------
    # DASHBOARD
    # -----------------------------------------------------

    def latest_sunday_count(self):
        with SessionLocal() as db:
            session = db.scalar(
                select(AttendanceSession)
                .where(
                    AttendanceSession.session_type
                    == AttendanceSessionType.SUNDAY_SERVICE
                )
                .order_by(
                    AttendanceSession.session_date.desc(),
                    AttendanceSession.created_at.desc(),
                )
                .limit(1)
            )

            if session is None:
                return {
                    "count": 0,
                    "date": None,
                }

            count = db.scalar(
                select(
                    func.count(
                        AttendanceRecord.id
                    )
                )
                .where(
                    AttendanceRecord.session_id
                    == session.id,
                    AttendanceRecord.status.in_(
                        [
                            AttendanceStatus.PRESENT,
                            AttendanceStatus.LATE,
                        ]
                    ),
                )
            ) or 0

            return {
                "count": count,
                "date": session.session_date,
            }
