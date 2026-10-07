"""Public giving uses one payment record; donor identity is private finance data."""
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String,Text,Numeric,Integer,Boolean,DateTime,ForeignKey,CheckConstraint,func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped,mapped_column
from src.database.base import Base


class DonationCategory(Base):
    __tablename__='donation_categories'
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    name:Mapped[str]=mapped_column(String(100),nullable=False,unique=True)
    is_active:Mapped[bool]=mapped_column(Boolean,default=True,server_default='true',nullable=False)
    display_order:Mapped[int]=mapped_column(Integer,default=0,server_default='0',nullable=False)


class Donation(Base):
    __tablename__='donations'
    __table_args__=(
        CheckConstraint('amount>0',name='ck_donation_positive_amount'),
        CheckConstraint("payment_mode='TEST'",name='ck_donation_test_mode'),
        CheckConstraint("status IN ('INITIALIZING','PENDING','SUCCESS','FAILED','CANCELLED','INITIALIZATION_FAILED')",name='ck_donation_status'),
        CheckConstraint("status!='SUCCESS' OR (paid_at IS NOT NULL AND provider_transaction_id IS NOT NULL)",name='ck_donation_paid'),
    )
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    request_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False,unique=True)
    request_hash:Mapped[str]=mapped_column(String(64),nullable=False)
    receipt_nonce:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),nullable=False,default=uuid.uuid4)
    reference:Mapped[str]=mapped_column(String(64),nullable=False,unique=True)
    donor_name:Mapped[str]=mapped_column(String(200),nullable=False)
    email:Mapped[str]=mapped_column(String(254),nullable=False)
    phone:Mapped[str]=mapped_column(String(40),nullable=False,default='')
    amount:Mapped[Decimal]=mapped_column(Numeric(12,2),nullable=False)
    currency:Mapped[str]=mapped_column(String(3),nullable=False)
    category_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('donation_categories.id',ondelete='RESTRICT'),nullable=False,index=True)
    category_name:Mapped[str]=mapped_column(String(100),nullable=False)
    note:Mapped[str]=mapped_column(Text,nullable=False,default='')
    provider:Mapped[str]=mapped_column(String(20),nullable=False,default='PAYSTACK')
    payment_mode:Mapped[str]=mapped_column(String(4),nullable=False,default='TEST',server_default='TEST')
    provider_reference:Mapped[str]=mapped_column(String(64),nullable=False,unique=True)
    provider_transaction_id:Mapped[str|None]=mapped_column(String(100),unique=True)
    authorization_url:Mapped[str|None]=mapped_column(String(500))
    status:Mapped[str]=mapped_column(String(30),nullable=False,default='INITIALIZING',index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False,index=True)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)
    paid_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
