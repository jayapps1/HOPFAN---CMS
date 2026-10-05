"""Explicit ministry grants, stable session rosters and immutable attendance history."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base


class UserMinistryScope(Base):
    __tablename__ = "user_ministry_scopes"
    __table_args__ = (UniqueConstraint("user_id", "ministry_id", name="uq_user_ministry_scope"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    ministry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ministries.id", ondelete="CASCADE"), index=True)
    can_view_attendance: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_create_attendance: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_record_attendance: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_correct_attendance: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_close_attendance: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_view_reports: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AttendanceRosterMember(Base):
    __tablename__ = "attendance_roster_members"

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("attendance_sessions.id", ondelete="RESTRICT"), primary_key=True)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("members.id", ondelete="RESTRICT"), primary_key=True, index=True)


class AttendanceAuditLog(Base):
    __tablename__ = "attendance_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attendance_record_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("attendance_records.id", ondelete="RESTRICT"), index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("attendance_sessions.id", ondelete="RESTRICT"), index=True)
    member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("members.id", ondelete="RESTRICT"), index=True)
    old_status: Mapped[str | None] = mapped_column(String(20))
    new_status: Mapped[str | None] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(Text)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(40), nullable=False)


class AuthorizationAuditLog(Base):
    __tablename__ = "authorization_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    target_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    ministry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ministries.id", ondelete="RESTRICT"))
    action_type: Mapped[str] = mapped_column(String(40), nullable=False)
    old_values: Mapped[str | None] = mapped_column(Text)
    new_values: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
