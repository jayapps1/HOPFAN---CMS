"""Configurable church offices and dated appointments, independent of access roles."""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from src.database.base import Base


class MinistryPosition(Base):
    __tablename__ = 'ministry_positions'
    __table_args__ = (
        UniqueConstraint('id', 'ministry_id', name='uq_position_ministry'),
        CheckConstraint('sort_order >= 0', name='ck_position_sort_order'),
        CheckConstraint('max_current_holders IS NULL OR max_current_holders > 0', name='ck_position_holders'),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ministry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('ministries.id', ondelete='RESTRICT'), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default='0', nullable=False)
    is_leadership: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true', nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true', nullable=False)
    max_current_holders: Mapped[int | None] = mapped_column(Integer)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


Index('uq_position_code_case', MinistryPosition.ministry_id, func.upper(MinistryPosition.code), unique=True)
Index('uq_position_name_case', MinistryPosition.ministry_id, func.lower(MinistryPosition.name), unique=True)


class MinistryLeadershipAssignment(Base):
    __tablename__ = 'ministry_leadership_assignments'
    __table_args__ = (
        ForeignKeyConstraint(['position_id', 'ministry_id'], ['ministry_positions.id', 'ministry_positions.ministry_id'], ondelete='RESTRICT', name='fk_assignment_position_ministry'),
        CheckConstraint('end_date IS NULL OR end_date >= start_date', name='ck_assignment_dates'),
        CheckConstraint('(is_current AND end_date IS NULL) OR (NOT is_current AND end_date IS NOT NULL)', name='ck_assignment_current_dates'),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ministry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('ministries.id', ondelete='RESTRICT'), nullable=False, index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('members.id', ondelete='RESTRICT'), nullable=False, index=True)
    position_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # Appointment snapshots preserve historical titles after a position is renamed.
    position_name: Mapped[str] = mapped_column(String(150), nullable=False)
    position_code: Mapped[str] = mapped_column(String(60), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


Index('uq_assignment_current_member_position', MinistryLeadershipAssignment.position_id, MinistryLeadershipAssignment.member_id,
      unique=True, postgresql_where=MinistryLeadershipAssignment.is_current.is_(True))


class MinistryLeadershipAuditLog(Base):
    __tablename__ = 'ministry_leadership_audit_logs'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ministry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('ministries.id', ondelete='RESTRICT'), nullable=False, index=True)
    position_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    old_values: Mapped[dict | None] = mapped_column(JSONB)
    new_values: Mapped[dict | None] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
