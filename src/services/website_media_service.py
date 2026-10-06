"""Bounded, reviewed website assets; never reads the member photo directory."""
import base64,io,re,warnings
from pathlib import Path
from uuid import uuid4
from PIL import Image,ImageOps
from sqlalchemy import select,func
from src.models.content import WebsiteMedia
from src.services.content_base import ContentBase,ContentError,ContentMissing,check_version,ident,now

class LocalWebsiteStorage:
    def __init__(self,root=None):self.root=Path(root or Path(__file__).resolve().parents[2]/'assets'/'website_media').resolve()
    def path(self,key,size):
        if not re.fullmatch(r'[a-f0-9]{32}',key) or size not in (320,960,1920):raise ContentError('Invalid media reference.')
        path=(self.root/(key+'-'+str(size)+'.jpg')).resolve()
        if not path.is_relative_to(self.root):raise ContentError('Invalid media reference.')
        return path
    def put(self,key,image):
        self.root.mkdir(parents=True,exist_ok=True)
        for size in (320,960,1920):
            picture=image.copy();picture.thumbnail((size,size))
            picture.convert('RGB').save(self.path(key,size),format='JPEG',quality=85)
    def read(self,key,size):return self.path(key,size).read_bytes()

class WebsiteMediaService(ContentBase):
    def __init__(self,user_id=None,session_factory=None,storage=None):
        if session_factory is None:
            from src.config.database import SessionLocal
            session_factory=SessionLocal
        super().__init__(user_id,session_factory);self.storage=storage or LocalWebsiteStorage()
    @staticmethod
    def dto(row):
        return dict(id=str(row.id),alt_text=row.alt_text,caption=row.caption,status=row.status,width=row.width,height=row.height,
            contains_children=row.contains_children,consent_attested=row.consent_attested,consent_reference=row.consent_reference,
            updated_at=row.updated_at,preview_url=f'/api/v1/website/media/{row.id}/preview?size=320')
    def list(self,limit=25,offset=0):
        with self._db('WEBSITE_PAGE_VIEW') as (db,access):
            total=db.scalar(select(func.count()).select_from(WebsiteMedia))
            rows=db.scalars(select(WebsiteMedia).order_by(WebsiteMedia.created_at.desc(),WebsiteMedia.id).limit(min(limit,100)).offset(offset))
            return dict(total=total,rows=[self.dto(row) for row in rows])
    def upload(self,data):
        with self._db('WEBSITE_MEDIA_MANAGE') as (db,access):
            try:
                encoded=data['image_base64'].split(',',1)[-1];raw=base64.b64decode(encoded,validate=True)
                if not raw or len(raw)>8*1024*1024:raise ValueError()
                with warnings.catch_warnings():
                    warnings.simplefilter('error',Image.DecompressionBombWarning)
                    with Image.open(io.BytesIO(raw)) as original:
                        if original.format not in ('JPEG','PNG','WEBP') or original.width*original.height>16_000_000:raise ValueError()
                        original.load();picture=ImageOps.exif_transpose(original).convert('RGB')
                key=uuid4().hex;self.storage.put(key,picture)
            except Exception:
                raise ContentError('Upload a valid JPEG, PNG or WebP within the image size limits.') from None
            row=WebsiteMedia(storage_key=key,alt_text=data['alt_text'],caption=data['caption'],contains_children=data['contains_children'],
                width=picture.width,height=picture.height,uploaded_by=access.user_id)
            db.add(row);db.flush();self.audit(db,access,'MEDIA',row.id,'MEDIA_UPLOADED');db.commit();return self.dto(row)
    def review(self,media_id,data):
        with self._db('WEBSITE_MEDIA_PUBLISH') as (db,access):
            row=db.scalar(select(WebsiteMedia).where(WebsiteMedia.id==ident(media_id)).with_for_update().execution_options(populate_existing=True))
            if not row:raise ContentMissing('Media not found.')
            check_version(row,data.pop('expected_updated_at'))
            for key,value in data.items():setattr(row,key,value)
            row.status='PUBLISHED';row.approved_by=access.user_id;row.updated_at=now()
            self.audit(db,access,'MEDIA',row.id,'MEDIA_APPROVED',contains_children=row.contains_children)
            db.commit();return self.dto(row)
    def preview(self,media_id,size=320):
        with self._db('WEBSITE_PAGE_VIEW') as (db,access):
            row=db.get(WebsiteMedia,ident(media_id))
            if not row:raise ContentMissing('Media not found.')
            try:return self.storage.read(row.storage_key,size)
            except OSError:raise ContentMissing('Media file unavailable.') from None
    def archive(self,media_id,expected):
        with self._db('WEBSITE_MEDIA_PUBLISH') as (db,access):
            row=db.scalar(select(WebsiteMedia).where(WebsiteMedia.id==ident(media_id)).with_for_update().execution_options(populate_existing=True))
            if not row:raise ContentMissing('Media not found.')
            check_version(row,expected);row.status='ARCHIVED';row.updated_at=now()
            self.audit(db,access,'MEDIA',row.id,'MEDIA_ARCHIVED');db.commit();return self.dto(row)
