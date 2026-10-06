"""Editorial content and private inquiries remain separate from church identities."""
import uuid
from datetime import date,datetime
from sqlalchemy import String,Text,Date,DateTime,Boolean,Integer,ForeignKey,CheckConstraint,UniqueConstraint,Index,func
from sqlalchemy.dialects.postgresql import UUID,JSONB
from sqlalchemy.orm import Mapped,mapped_column
from src.database.base import Base

class ContentTimes:
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)

class ContentEntry(ContentTimes,Base):
    __tablename__='website_content'
    __table_args__=(UniqueConstraint('kind','slug',name='uq_website_kind_slug'),
        CheckConstraint("kind IN ('PAGE','HOMEPAGE','MINISTRY','LEADERSHIP','SERMON','GALLERY','TESTIMONY')",name='ck_website_kind'),
        CheckConstraint("status IN ('DRAFT','PUBLISHED','ARCHIVED')",name='ck_website_status'),
        CheckConstraint("status!='PUBLISHED' OR published_data IS NOT NULL",name='ck_website_public_snapshot'),
        Index('ix_website_kind_status','kind','status'))
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    kind:Mapped[str]=mapped_column(String(20),nullable=False)
    slug:Mapped[str]=mapped_column(String(160),nullable=False)
    title:Mapped[str]=mapped_column(String(200),nullable=False)
    status:Mapped[str]=mapped_column(String(20),server_default='DRAFT',default='DRAFT',nullable=False)
    draft_data:Mapped[dict]=mapped_column(JSONB,nullable=False)
    published_data:Mapped[dict|None]=mapped_column(JSONB)
    ministry_id:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('ministries.id',ondelete='RESTRICT'))
    member_id:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('members.id',ondelete='RESTRICT'))
    published_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    created_by:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('users.id',ondelete='SET NULL'))
    updated_by:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('users.id',ondelete='SET NULL'))
    published_by:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('users.id',ondelete='SET NULL'))

class WebsiteSettings(ContentTimes,Base):
    __tablename__='website_settings'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    draft_data:Mapped[dict]=mapped_column(JSONB,nullable=False)
    published_data:Mapped[dict|None]=mapped_column(JSONB)
    updated_by:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('users.id',ondelete='SET NULL'))
    published_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

class WebsiteMedia(ContentTimes,Base):
    __tablename__='website_media'
    __table_args__=(CheckConstraint("status IN ('DRAFT','PUBLISHED','ARCHIVED')",name='ck_site_media_status'),
        CheckConstraint("status!='PUBLISHED' OR (consent_attested AND length(alt_text)>0)",name='ck_site_media_approval'),)
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    storage_key:Mapped[str]=mapped_column(String(40),nullable=False,unique=True)
    alt_text:Mapped[str]=mapped_column(String(500),default='',nullable=False)
    caption:Mapped[str]=mapped_column(String(1000),default='',nullable=False)
    width:Mapped[int]=mapped_column(Integer,nullable=False)
    height:Mapped[int]=mapped_column(Integer,nullable=False)
    status:Mapped[str]=mapped_column(String(20),default='DRAFT',server_default='DRAFT',nullable=False)
    contains_children:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false',nullable=False)
    consent_attested:Mapped[bool]=mapped_column(Boolean,default=False,server_default='false',nullable=False)
    consent_reference:Mapped[str]=mapped_column(String(300),default='',nullable=False)
    uploaded_by:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('users.id',ondelete='SET NULL'))
    approved_by:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('users.id',ondelete='SET NULL'))

class ContentMediaLink(Base):
    __tablename__='website_content_media'
    __table_args__=(Index('ix_website_media_link_media','media_id'),)
    content_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('website_content.id',ondelete='RESTRICT'),primary_key=True)
    media_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('website_media.id',ondelete='RESTRICT'),primary_key=True)

class Event(ContentTimes,Base):
    __tablename__='church_events'
    __table_args__=(CheckConstraint("status IN ('DRAFT','SUBMITTED','APPROVED','PUBLISHED','CANCELLED','ARCHIVED')",name='ck_event_status'),
        CheckConstraint("visibility IN ('INTERNAL','PUBLIC','BOTH')",name='ck_event_visibility'),
        CheckConstraint("(scope='CHURCH_WIDE' AND ministry_id IS NULL) OR (scope='MINISTRY' AND ministry_id IS NOT NULL)",name='ck_event_scope'),
        CheckConstraint('end_datetime IS NULL OR end_datetime>=start_datetime',name='ck_event_dates'),)
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    slug:Mapped[str]=mapped_column(String(160),nullable=False,unique=True)
    title:Mapped[str]=mapped_column(String(200),nullable=False)
    description:Mapped[str]=mapped_column(Text,default='',nullable=False)
    event_type:Mapped[str]=mapped_column(String(30),default='OTHER',nullable=False)
    scope:Mapped[str]=mapped_column(String(20),nullable=False)
    ministry_id:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('ministries.id',ondelete='RESTRICT'),index=True)
    visibility:Mapped[str]=mapped_column(String(20),default='INTERNAL',nullable=False)
    status:Mapped[str]=mapped_column(String(20),default='DRAFT',server_default='DRAFT',nullable=False,index=True)
    start_datetime:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,index=True)
    end_datetime:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    location:Mapped[str]=mapped_column(String(500),default='',nullable=False)
    image_id:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('website_media.id',ondelete='RESTRICT'))
    created_by:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('users.id',ondelete='SET NULL'))
    approved_by:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('users.id',ondelete='SET NULL'))
    published_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

class Announcement(ContentTimes,Base):
    __tablename__='church_announcements'
    __table_args__=(CheckConstraint("status IN ('DRAFT','SUBMITTED','APPROVED','PUBLISHED','CANCELLED','ARCHIVED')",name='ck_announcement_status'),
        CheckConstraint("audience IN ('INTERNAL','PUBLIC','BOTH')",name='ck_announcement_audience'),
        CheckConstraint("(scope='CHURCH_WIDE' AND ministry_id IS NULL) OR (scope='MINISTRY' AND ministry_id IS NOT NULL)",name='ck_announcement_scope'),
        CheckConstraint('publish_until IS NULL OR publish_from IS NULL OR publish_until>=publish_from',name='ck_announcement_dates'),)
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    slug:Mapped[str]=mapped_column(String(160),nullable=False,unique=True)
    title:Mapped[str]=mapped_column(String(200),nullable=False)
    body:Mapped[str]=mapped_column(Text,default='',nullable=False)
    scope:Mapped[str]=mapped_column(String(20),nullable=False)
    ministry_id:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('ministries.id',ondelete='RESTRICT'),index=True)
    audience:Mapped[str]=mapped_column(String(20),default='INTERNAL',nullable=False)
    status:Mapped[str]=mapped_column(String(20),default='DRAFT',server_default='DRAFT',nullable=False,index=True)
    publish_from:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),index=True)
    publish_until:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    priority:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
    created_by:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('users.id',ondelete='SET NULL'))
    approved_by:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('users.id',ondelete='SET NULL'))
    published_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

class PublicInquiry(ContentTimes,Base):
    __tablename__='public_inquiries'
    __table_args__=(CheckConstraint("kind IN ('VISITOR','CONTACT','PRAYER')",name='ck_inquiry_kind'),
        CheckConstraint("status IN ('NEW','CONTACTED','FOLLOW_UP','VISITED','CONVERTED','CLOSED')",name='ck_inquiry_status'),
        CheckConstraint("status!='CONVERTED' OR (kind='VISITOR' AND converted_member_id IS NOT NULL)",name='ck_inquiry_conversion'),
        Index('ix_inquiry_kind_status','kind','status'))
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    kind:Mapped[str]=mapped_column(String(20),nullable=False)
    first_name:Mapped[str]=mapped_column(String(100),default='',nullable=False)
    last_name:Mapped[str]=mapped_column(String(100),default='',nullable=False)
    phone:Mapped[str]=mapped_column(String(40),default='',nullable=False)
    email:Mapped[str]=mapped_column(String(254),default='',nullable=False)
    message:Mapped[str]=mapped_column(Text,default='',nullable=False)
    private_notes:Mapped[str]=mapped_column(Text,default='',nullable=False)
    contact_permission:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)
    preferred_contact:Mapped[str]=mapped_column(String(10),default='NONE',nullable=False)
    privacy:Mapped[str]=mapped_column(String(30),default='PRIVATE',nullable=False)
    visit_date:Mapped[date|None]=mapped_column(Date)
    status:Mapped[str]=mapped_column(String(20),default='NEW',server_default='NEW',nullable=False)
    dedupe_key:Mapped[str]=mapped_column(String(64),unique=True,nullable=False)
    assigned_to:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('users.id',ondelete='SET NULL'),index=True)
    converted_member_id:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('members.id',ondelete='RESTRICT'))

class ContentAudit(Base):
    __tablename__='content_audit_logs'
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    entity_kind:Mapped[str]=mapped_column(String(30),nullable=False)
    entity_id:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),index=True)
    action:Mapped[str]=mapped_column(String(64),nullable=False)
    actor_user_id:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('users.id',ondelete='SET NULL'))
    details:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False)
    occurred_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False)

CONTENT_TABLES=[ContentEntry,WebsiteSettings,WebsiteMedia,ContentMediaLink,Event,Announcement,PublicInquiry,ContentAudit]
