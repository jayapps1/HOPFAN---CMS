import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class MemberMinistry(Base):
    __tablename__ = "member_ministries"

    __table_args__ = (
        UniqueConstraint(
            "member_id",
            "ministry_id",
            name="uq_member_ministry",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "members.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    ministry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "ministries.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    position_title: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    joined_at: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    left_at: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
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

    member = relationship(
        "Member",
        back_populates="ministry_memberships",
    )

    ministry = relationship(
        "Ministry",
        back_populates="member_memberships",
    )
