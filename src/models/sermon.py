"""Sermons remain ContentEntry records; these are attached media and organization."""
import uuid
from datetime import datetime
from sqlalchemy import String,Text,Integer,BigInteger,Boolean,DateTime,ForeignKey,CheckConstraint,UniqueConstraint,func,Index
from sqlalchemy.dialects.postgresql import UUID,JSONB
from sqlalchemy.orm import Mapped,mapped_column
from src.database.base import Base
from src.models.content import ContentTimes

class SermonTaxonomy(ContentTimes):
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    name:Mapped[str]=mapped_column(String(200),nullable=False)
    slug:Mapped[str]=mapped_column(String(160),nullable=False,unique=True)
    description:Mapped[str]=mapped_column(Text,nullable=False,default='')
    status:Mapped[str]=mapped_column(String(20),nullable=False,default='DRAFT')
    display_order:Mapped[int]=mapped_column(Integer,nullable=False,default=0,server_default='0')
    cover_image_id:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('website_media.id',ondelete='RESTRICT'))
    published_data:Mapped[dict|None]=mapped_column(JSONB)
    published_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
class SermonSeries(SermonTaxonomy,Base):
    __tablename__='sermon_series'
    __table_args__=(CheckConstraint("status IN ('DRAFT','PUBLISHED','ARCHIVED')",name='ck_sermon_series_status'),)
class SermonCategory(SermonTaxonomy,Base):
    __tablename__='sermon_categories'
    __table_args__=(CheckConstraint("status IN ('DRAFT','PUBLISHED','ARCHIVED')",name='ck_sermon_category_status'),)
class SermonMediaAsset(ContentTimes,Base):
    __tablename__='sermon_media_assets'
    __table_args__=(CheckConstraint("media_type IN ('VIDEO','AUDIO','THUMBNAIL','CAPTION','TRANSCRIPT','DOCUMENT')",name='ck_sermon_media_type'),
        CheckConstraint("processing_status IN ('UPLOADED','QUEUED','PROCESSING','READY','FAILED','DELETE_PENDING','DELETED')",name='ck_sermon_processing_status'),
        CheckConstraint('file_size>=0',name='ck_sermon_asset_size'),Index('ix_sermon_asset_owner_status','sermon_id','processing_status'))
    id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    sermon_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('website_content.id',ondelete='RESTRICT'),nullable=False)
    media_type:Mapped[str]=mapped_column(String(20),nullable=False)
    storage_provider:Mapped[str]=mapped_column(String(10),nullable=False)
    storage_key:Mapped[str]=mapped_column(String(160),nullable=False,unique=True)
    original_filename:Mapped[str]=mapped_column(String(200),nullable=False)
    mime_type:Mapped[str]=mapped_column(String(100),nullable=False)
    file_size:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0)
    sha256:Mapped[str]=mapped_column(String(64),nullable=False,default='')
    duration_seconds:Mapped[int|None]=mapped_column(Integer)
    width:Mapped[int|None]=mapped_column(Integer)
    height:Mapped[int|None]=mapped_column(Integer)
    bitrate:Mapped[int|None]=mapped_column(Integer)
    quality_label:Mapped[str]=mapped_column(String(30),default='',nullable=False)
    format:Mapped[str]=mapped_column(String(20),nullable=False)
    download_allowed:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False,server_default='false')
    rights_attested:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False,server_default='false')
    processing_status:Mapped[str]=mapped_column(String(20),nullable=False,default='UPLOADED')
    error_summary:Mapped[str]=mapped_column(String(300),nullable=False,default='')
    uploaded_by:Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('users.id',ondelete='SET NULL'))
class SermonMetric(Base):
    __tablename__='sermon_metrics'
    __table_args__=(CheckConstraint("event IN ('VIDEO_PLAY','AUDIO_PLAY','AUDIO_DOWNLOAD','VIDEO_DOWNLOAD')",name='ck_sermon_metric_event'),)
    sermon_id:Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('website_content.id',ondelete='RESTRICT'),primary_key=True)
    event:Mapped[str]=mapped_column(String(30),primary_key=True)
    count:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0,server_default='0')
class SermonPlaybackReceipt(Base):
    __tablename__='sermon_playback_receipts'
    __table_args__=(Index('ix_sermon_receipt_expiry','expires_at'),)
    token_hash:Mapped[str]=mapped_column(String(64),primary_key=True)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
