"""Households reference master members; ended memberships remain historical."""
import uuid
from datetime import date, datetime
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from src.database.base import Base


class Household(Base):
    __tablename__ = 'households'
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','INACTIVE','ARCHIVED')", name='ck_household_status'),
        CheckConstraint("(status='ARCHIVED') = (archived_at IS NOT NULL)", name='ck_household_archive'),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    household_code: Mapped[str | None] = mapped_column(String(40), unique=True)
    primary_address: Mapped[str | None] = mapped_column(Text)
    primary_phone: Mapped[str | None] = mapped_column(String(30))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default='ACTIVE', server_default='ACTIVE', nullable=False, index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HouseholdMember(Base):
    __tablename__ = 'household_members'
    __table_args__ = (
        CheckConstraint("relationship IN ('HEAD','SPOUSE','SON','DAUGHTER','CHILD','FATHER','MOTHER','BROTHER','SISTER','DEPENDANT','GUARDIAN','RELATIVE','OTHER')", name='ck_household_relationship'),
        CheckConstraint("is_household_head = (relationship='HEAD')", name='ck_household_head_relationship'),
        CheckConstraint('left_at IS NULL OR joined_at IS NULL OR left_at >= joined_at', name='ck_household_member_dates'),
        CheckConstraint('(is_active AND left_at IS NULL) OR (NOT is_active AND left_at IS NOT NULL)', name='ck_household_member_current'),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('households.id', ondelete='RESTRICT'), nullable=False, index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('members.id', ondelete='RESTRICT'), nullable=False, index=True)
    relationship: Mapped[str] = mapped_column(String(20), nullable=False)
    is_household_head: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false', nullable=False)
    joined_at: Mapped[date | None] = mapped_column(Date)
    left_at: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true', nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


Index('uq_household_member_current', HouseholdMember.member_id, unique=True, postgresql_where=HouseholdMember.is_active.is_(True))
Index('uq_household_current_head', HouseholdMember.household_id, unique=True,
    postgresql_where=HouseholdMember.is_active.is_(True) & HouseholdMember.is_household_head.is_(True))


class HouseholdAuditLog(Base):
    __tablename__ = 'household_audit_logs'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Snapshot identifiers allow deletion of an unused household without deleting
    # the audit event. Membership/member references are retained as identifiers.
    household_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    membership_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    action: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    old_values: Mapped[dict | None] = mapped_column(JSONB)
    new_values: Mapped[dict | None] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
