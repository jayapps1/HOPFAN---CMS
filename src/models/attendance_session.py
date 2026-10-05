import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from src.database.base import Base


class AttendanceSessionType(str, enum.Enum):
    SUNDAY_SERVICE = "SUNDAY_SERVICE"
    MINISTRY_MEETING = "MINISTRY_MEETING"
    SUNDAY_SCHOOL = "SUNDAY_SCHOOL"
    SPECIAL_EVENT = "SPECIAL_EVENT"
    PRAYER_MEETING = "PRAYER_MEETING"
    CHURCH_MEETING = "CHURCH_MEETING"
    LEADERSHIP_MEETING = "LEADERSHIP_MEETING"
    OTHER = "OTHER"


class AttendanceScopeType(str, enum.Enum):
    GLOBAL = "GLOBAL"
    MINISTRY = "MINISTRY"


class AttendanceRosterType(str, enum.Enum):
    WHOLE_CHURCH = "WHOLE_CHURCH"
    ALL_MINISTRY_MEMBERS = "ALL_MINISTRY_MEMBERS"
    SELECTED_MEMBERS = "SELECTED_MEMBERS"
    MINISTRY_LEADERSHIP = "MINISTRY_LEADERSHIP"
    EXECUTIVES = "MINISTRY_LEADERSHIP"  # compatibility for existing Python callers


class AttendanceSessionState(str, enum.Enum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    LOCKED = "LOCKED"


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"
    __table_args__ = (
        CheckConstraint("(scope_type = 'GLOBAL' AND ministry_id IS NULL) OR (scope_type = 'MINISTRY' AND ministry_id IS NOT NULL)", name="ck_attendance_scope_ministry"),
        CheckConstraint("session_type != 'SUNDAY_SERVICE' OR (scope_type = 'GLOBAL' AND roster_type = 'WHOLE_CHURCH')", name="ck_attendance_sunday_global"),
        CheckConstraint("end_time IS NULL OR start_time IS NULL OR end_time >= start_time", name="ck_attendance_time_order"),
        CheckConstraint("(scope_type = 'GLOBAL' AND roster_type IN ('WHOLE_CHURCH', 'SELECTED_MEMBERS')) OR (scope_type = 'MINISTRY' AND roster_type IN ('ALL_MINISTRY_MEMBERS', 'SELECTED_MEMBERS', 'MINISTRY_LEADERSHIP'))", name="ck_attendance_roster_scope"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    # Preserve the existing column and callers while exposing the new vocabulary.
    title = synonym("name")
    description: Mapped[str | None] = mapped_column(Text)
    scope_type: Mapped[AttendanceScopeType] = mapped_column(
        Enum(AttendanceScopeType, name="attendance_scope_type", native_enum=False),
        nullable=False, default=AttendanceScopeType.GLOBAL, index=True,
    )
    roster_type: Mapped[AttendanceRosterType] = mapped_column(
        Enum(AttendanceRosterType, name="attendance_roster_type", native_enum=False),
        nullable=False, default=AttendanceRosterType.WHOLE_CHURCH,
    )
    start_time = mapped_column(Time, nullable=True)
    end_time = mapped_column(Time, nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
    )
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reopened_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
    )

    session_type: Mapped[AttendanceSessionType] = mapped_column(
        Enum(
            AttendanceSessionType,
            name="attendance_session_type",
            native_enum=False,
        ),
        nullable=False,
        index=True,
    )

    session_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    ministry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "ministries.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    state: Mapped[AttendanceSessionState] = mapped_column(
        Enum(
            AttendanceSessionState,
            name="attendance_session_state",
            native_enum=False,
        ),
        default=AttendanceSessionState.OPEN,
        nullable=False,
        index=True,
    )

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    records = relationship(
        "AttendanceRecord",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    ministry = relationship(
        "Ministry",
    )
