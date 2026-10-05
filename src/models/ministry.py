import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class Ministry(Base):
    __tablename__ = "ministries"
    __table_args__ = (
        CheckConstraint("category IN ('MINISTRY','FELLOWSHIP','DEPARTMENT','UNIT','OTHER')", name='ck_ministry_category'),
        CheckConstraint('archived_at IS NULL OR NOT is_active', name='ck_ministry_archive_inactive'),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    code: Mapped[str] = mapped_column(
        String(60),
        unique=True,
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    category: Mapped[str] = mapped_column(String(20), nullable=False, default='MINISTRY', server_default='MINISTRY', index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    archived_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))

    @property
    def status(self):
        return 'ARCHIVED' if self.archived_at is not None else 'ACTIVE' if self.is_active else 'INACTIVE'

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

    member_memberships = relationship(
        "MemberMinistry",
        back_populates="ministry",
        passive_deletes='all',
    )


Index('uq_ministry_code_case', func.upper(Ministry.code), unique=True)
Index('uq_ministry_name_case', func.lower(Ministry.name), unique=True)
