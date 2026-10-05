import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class MemberStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    TRANSFERRED = "TRANSFERRED"
    DECEASED = "DECEASED"


class Gender(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class MaritalStatus(str, enum.Enum):
    SINGLE = "SINGLE"
    MARRIED = "MARRIED"
    DIVORCED = "DIVORCED"
    WIDOWED = "WIDOWED"


class Member(Base):
    __tablename__ = "members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    member_no: Mapped[str] = mapped_column(
        String(40),
        unique=True,
        nullable=False,
        index=True,
    )

    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    middle_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    gender: Mapped[Gender | None] = mapped_column(
        Enum(
            Gender,
            name="member_gender",
            native_enum=False,
        ),
        nullable=True,
    )

    date_of_birth: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        index=True,
    )

    alternate_phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    occupation: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    marital_status: Mapped[MaritalStatus | None] = mapped_column(
        Enum(
            MaritalStatus,
            name="member_marital_status",
            native_enum=False,
        ),
        nullable=True,
    )

    date_joined: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    baptized: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    baptism_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    status: Mapped[MemberStatus] = mapped_column(
        Enum(
            MemberStatus,
            name="member_status",
            native_enum=False,
        ),
        default=MemberStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    photo_path: Mapped[str | None] = mapped_column(
        String(500),
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

    ministry_memberships = relationship(
        "MemberMinistry",
        back_populates="member",
        cascade="all, delete-orphan",
    )

    user_accounts = relationship(
        "User",
        back_populates="member",
    )

    @property
    def full_name(self) -> str:
        values = [
            self.first_name,
            self.middle_name,
            self.last_name,
        ]

        return " ".join(
            value
            for value in values
            if value
        )
