import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class AttendanceSessionType(str, enum.Enum):
    SUNDAY_SERVICE = "SUNDAY_SERVICE"
    MINISTRY_MEETING = "MINISTRY_MEETING"
    SUNDAY_SCHOOL = "SUNDAY_SCHOOL"
    SPECIAL_EVENT = "SPECIAL_EVENT"


class AttendanceSessionState(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
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
