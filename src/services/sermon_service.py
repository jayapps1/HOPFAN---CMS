"""Explicit sermon management on the existing content/snapshot lifecycle."""
from copy import deepcopy
from uuid import uuid4
from sqlalchemy import select,func,or_,cast,DateTime
from src.models import ContentEntry,ContentMediaLink,WebsiteMedia,Member,Ministry
from src.models.sermon import SermonSeries,SermonCategory,SermonMediaAsset,SermonMetric
from src.services.content_base import ContentBase,ContentError,ContentMissing,ContentConflict,now,ident,check_version
from src.services.content_contracts import ContentWrite,EditorialData,embed_video
from src.services.sermon_contracts import SermonWrite,TaxonomyWrite
from src.services.sermon_storage import SermonStorageSettings
from urllib.parse import urlsplit

ASSET_FIELDS={'video_asset_id':'VIDEO','audio_asset_id':'AUDIO','thumbnail_asset_id':'THUMBNAIL','caption_asset_id':'CAPTION','transcript_asset_id':'TRANSCRIPT','document_asset_id':'DOCUMENT'}
TAXONOMY={'series':(SermonSeries,'SERMON_MANAGE_SERIES'),'categories':(SermonCategory,'SERMON_MANAGE_CATEGORIES')}

def external_approved(value,hosts):
    if not value:return
    url=urlsplit(value)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.hostname.lower() not in hosts:raise ContentError('Use an external media host approved in the backend configuration.')

def metadata_from_snapshot(snapshot):
    d=EditorialData.model_validate(snapshot.get('data',{})).model_dump(mode='json')
    video_type=d['video_source_type']
    if video_type=='NONE' and d['youtube_url']:video_type='VIMEO' if 'vimeo.com' in d['youtube_url'] else 'YOUTUBE'
    return dict(title=snapshot['title'],slug=snapshot['slug'],description=snapshot.get('body',''),short_description=snapshot.get('summary',''),
        sermon_date=d['sermon_date'],speaker_name=d['speaker'],scripture_reference=d['scripture_reference'],thumbnail_media_id=d['image_id'],visibility=d['sermon_visibility'],
        external_audio_url=d['audio_url'],external_video_url=d['youtube_url'] or d['external_video_url'],video_source_type=video_type,
        seo_title=snapshot.get('seo_title',''),seo_description=snapshot.get('seo_description',''),
        **{key:d[key] for key in ('subtitle','speaker_member_id','speaker_profile_slug','series_id','category_id','service_type','tags','transcript',
            'featured','video_asset_id','audio_asset_id','thumbnail_asset_id','caption_asset_id','transcript_asset_id','document_asset_id','allow_audio_download','allow_video_download')},ministry_id=d['sermon_ministry_id'])

class SermonService(ContentBase):
    @staticmethod
    def record(db,sermon_id,locked=True):
        stmt=select(ContentEntry).where(ContentEntry.id==ident(sermon_id),ContentEntry.kind=='SERMON')
        if locked:stmt=stmt.with_for_update().execution_options(populate_existing=True)
        row=db.scalar(stmt)
        if not row:raise ContentMissing('Sermon not found.')
        return row
    @staticmethod
    def asset_dto(asset):
        return dict(id=str(asset.id),media_type=asset.media_type,original_filename=asset.original_filename,mime_type=asset.mime_type,
            file_size=asset.file_size,duration_seconds=asset.duration_seconds,width=asset.width,height=asset.height,
            quality_label=asset.quality_label,format=asset.format,download_allowed=asset.download_allowed,
            processing_status=asset.processing_status,error_summary=asset.error_summary,updated_at=asset.updated_at,
            preview_url=f'/api/v1/sermons/{asset.sermon_id}/media/{asset.id}/preview')
    @classmethod
    def dto(cls,db,row,assets=None,include_analytics=False):
        assets=assets if assets is not None else db.scalars(select(SermonMediaAsset).where(SermonMediaAsset.sermon_id==row.id,SermonMediaAsset.processing_status!='DELETED').order_by(SermonMediaAsset.created_at)).all()
        metrics=dict(db.execute(select(SermonMetric.event,SermonMetric.count).where(SermonMetric.sermon_id==row.id)).all()) if include_analytics else {}
        return dict(id=str(row.id),title=row.title,slug=row.slug,status=row.status,metadata=metadata_from_snapshot(row.draft_data),
            updated_at=row.updated_at,published_at=row.published_at,has_unpublished_changes=row.draft_data!=row.published_data,
            assets=[cls.asset_dto(asset) for asset in assets],metrics=metrics,scheduled_publish_at=(row.published_data or row.draft_data).get('data',{}).get('scheduled_publish_at'))
    def get(self,sermon_id):
        with self._db('SERMON_VIEW') as (db,access):return self.dto(db,self.record(db,sermon_id,False),include_analytics=access.has('SERMON_VIEW_ANALYTICS'))
    def list(self,search='',status='ALL',limit=25,offset=0):
        with self._db('SERMON_VIEW') as (db,access):
            stmt=select(ContentEntry).where(ContentEntry.kind=='SERMON')
            if status!='ALL':stmt=stmt.where(ContentEntry.status==status)
            if search:stmt=stmt.where(or_(ContentEntry.title.ilike('%'+search+'%'),ContentEntry.draft_data['data']['speaker'].astext.ilike('%'+search+'%')))
            total=db.scalar(select(func.count()).select_from(stmt.subquery()))
            rows=db.scalars(stmt.order_by(ContentEntry.updated_at.desc(),ContentEntry.id).limit(min(limit,100)).offset(offset)).all()
            assets=db.scalars(select(SermonMediaAsset).where(SermonMediaAsset.sermon_id.in_([row.id for row in rows]),SermonMediaAsset.processing_status!='DELETED')).all() if rows else []
            return dict(total=total,rows=[self.dto(db,row,[asset for asset in assets if asset.sermon_id==row.id],access.has('SERMON_VIEW_ANALYTICS')) for row in rows])
    def overview(self):
        with self._db('SERMON_VIEW') as (db,access):
            counts=dict(db.execute(select(ContentEntry.status,func.count()).where(ContentEntry.kind=='SERMON').group_by(ContentEntry.status)).all())
            return dict(counts=counts,series=db.scalar(select(func.count()).select_from(SermonSeries)),categories=db.scalar(select(func.count()).select_from(SermonCategory)),recent_uploads=[dict(self.asset_dto(asset),sermon_title=title,sermon_id=str(asset.sermon_id)) for asset,title in db.execute(select(SermonMediaAsset,ContentEntry.title).join(ContentEntry,ContentEntry.id==SermonMediaAsset.sermon_id).where(SermonMediaAsset.processing_status!='DELETED').order_by(SermonMediaAsset.created_at.desc()).limit(5))])
    def options(self):
        settings=SermonStorageSettings.from_environment()
        with self._db('SERMON_VIEW') as (db,access):
            ministries=select(Ministry).where(Ministry.is_active.is_(True),Ministry.archived_at.is_(None)).order_by(Ministry.name)
            if not access.has('MINISTRIES_VIEW_ALL'):ministries=ministries.where(Ministry.id.in_(access.ministry_ids('MINISTRIES_VIEW_OWN')))
            return dict(ministries=[dict(id=str(row.id),name=row.name) for row in db.scalars(ministries)],
                approved_images=[dict(id=str(row.id),name=row.alt_text) for row in db.scalars(select(WebsiteMedia).where(WebsiteMedia.status=='PUBLISHED',WebsiteMedia.consent_attested.is_(True)).order_by(WebsiteMedia.created_at.desc()).limit(100))],
                series=[dict(id=str(row.id),name=row.name,status=row.status) for row in db.scalars(select(SermonSeries).where(SermonSeries.status!='ARCHIVED').order_by(SermonSeries.name))],
                categories=[dict(id=str(row.id),name=row.name,status=row.status) for row in db.scalars(select(SermonCategory).where(SermonCategory.status!='ARCHIVED').order_by(SermonCategory.name))],
                speaker_profiles=[dict(slug=row.slug,name=row.published_data.get('data',{}).get('public_name') or row.published_data['title']) for row in db.scalars(select(ContentEntry).where(ContentEntry.kind=='LEADERSHIP',ContentEntry.status=='PUBLISHED'))],
                limits={kind:settings.limit(kind) for kind in ('VIDEO','AUDIO','THUMBNAIL','CAPTION','TRANSCRIPT','DOCUMENT')},
                allowed_extensions={'VIDEO':['mp4','webm'],'AUDIO':['mp3','m4a','wav'],'THUMBNAIL':['jpg','jpeg','png','webp'],'CAPTION':['vtt'],'TRANSCRIPT':['txt'],'DOCUMENT':['pdf']})
    def save(self,body,sermon_id=None):
        editorial=body.editorial() if isinstance(body,SermonWrite) else ContentWrite.model_validate(body)
        snapshot=editorial.model_dump(mode='json',exclude={'expected_updated_at','member_id','ministry_id'})
        data=snapshot['data']
        settings=SermonStorageSettings.from_environment()
        external_approved(data['audio_url'],settings.allowed_audio_hosts)
        if data['video_source_type']=='EXTERNAL':external_approved(data['external_video_url'],settings.allowed_video_hosts)
        with self._db('SERMON_EDIT' if sermon_id else 'SERMON_CREATE') as (db,access):
            access.require_permission('SERMON_VIEW')
            row=self.record(db,sermon_id) if sermon_id else None
            if row:
                check_version(row,editorial.expected_updated_at)
                if row.published_at and row.slug!=editorial.slug:raise ContentConflict('A published sermon URL must remain stable.')
                if row.status=='SCHEDULED':raise ContentConflict('Cancel scheduled publication before editing its frozen draft.')
            if data.get('speaker_member_id'):
                access.require_permission('MEMBERS_VIEW_ALL')
                if not db.get(Member,ident(data['speaker_member_id'])):raise ContentMissing('Speaker not found.')
            if data.get('sermon_ministry_id') and not db.get(Ministry,ident(data['sermon_ministry_id'])):raise ContentMissing('Ministry not found.')
            for field,model in (('series_id',SermonSeries),('category_id',SermonCategory)):
                if data.get(field) and not db.get(model,ident(data[field])):raise ContentMissing('Collection not found.')
            if data.get('speaker_profile_slug') and not db.scalar(select(ContentEntry.id).where(ContentEntry.kind=='LEADERSHIP',ContentEntry.slug==data['speaker_profile_slug'],ContentEntry.status=='PUBLISHED')):raise ContentMissing('Approved speaker profile not found.')
            for field,kind in ASSET_FIELDS.items():
                if data.get(field):
                    asset=db.get(SermonMediaAsset,ident(data[field]))
                    if not row or not asset or asset.sermon_id!=row.id or asset.media_type!=kind or asset.processing_status in {'DELETED','DELETE_PENDING'}:raise ContentError('Select media attached to this sermon.')
            if row is None:row=ContentEntry(kind='SERMON',slug=editorial.slug,title=editorial.title,draft_data=snapshot,created_by=access.user_id);db.add(row)
            row.title=editorial.title;row.slug=editorial.slug;row.draft_data=snapshot;row.updated_by=access.user_id;row.updated_at=now()
            db.flush();self.audit(db,access,'SERMON',row.id,'SERMON_UPDATED' if sermon_id else 'SERMON_CREATED');db.commit()
            return self.dto(db,row,include_analytics=access.has('SERMON_VIEW_ANALYTICS'))
    @staticmethod
    def validate_ready(db,row,snapshot):
        d=EditorialData.model_validate(snapshot['data']).model_dump(mode='json')
        for field,kind in ASSET_FIELDS.items():
            if d.get(field):
                asset=db.get(SermonMediaAsset,ident(d[field]))
                if not asset or asset.sermon_id!=row.id or asset.media_type!=kind or asset.processing_status!='READY' or not asset.rights_attested:raise ContentConflict('Wait for all selected media to be ready and authorized.')
        if d.get('image_id'):
            image=db.get(WebsiteMedia,ident(d['image_id']))
            if not image or image.status!='PUBLISHED' or not image.consent_attested:raise ContentError('Review the selected thumbnail before publishing.')
        external=d['youtube_url'] or (d['external_video_url'] if d['video_source_type']=='EXTERNAL' else '')
        if not (external or d['video_asset_id'] or d['audio_asset_id'] or d['audio_url']):raise ContentConflict('Attach playable video or audio before publishing.')
        if external and d['video_source_type'] in {'NONE','YOUTUBE','VIMEO'}:embed_video(external)
        return d
    def action(self,sermon_id,action,expected,scheduled_at=None):
        permission='SERMON_ARCHIVE' if action in {'archive','unpublish','cancel-schedule'} else 'SERMON_PUBLISH'
        with self._db(permission) as (db,access):
            access.require_permission('SERMON_VIEW');row=self.record(db,sermon_id);check_version(row,expected)
            if action in {'ready','publish','schedule'}:
                self.validate_ready(db,row,row.draft_data)
                snapshot=deepcopy(row.draft_data)
                if action=='schedule':
                    if not scheduled_at or scheduled_at<=now():raise ContentError('Choose a future publication time.')
                    snapshot['data']['scheduled_publish_at']=scheduled_at.isoformat();row.status='SCHEDULED'
                    row.published_data=snapshot;row.published_by=access.user_id
                elif action=='publish':
                    snapshot['data']['scheduled_publish_at']=None
                    row.published_data=snapshot;row.status='PUBLISHED';row.published_at=now();row.published_by=access.user_id
                else:row.status='READY'
                if action=='publish':self.link_thumbnail(db,row,snapshot)
            elif action in {'unpublish','cancel-schedule'}:row.status='READY'
            elif action=='archive':row.status='ARCHIVED'
            else:raise ContentError('Unsupported sermon transition.')
            row.updated_at=now();row.updated_by=access.user_id
            self.audit(db,access,'SERMON',row.id,'SERMON_'+action.upper().replace('-','_'));db.commit();return self.dto(db,row,include_analytics=access.has('SERMON_VIEW_ANALYTICS'))
    @staticmethod
    def link_thumbnail(db,row,snapshot):
        if snapshot['data'].get('image_id'):
            key=ident(snapshot['data']['image_id'])
            if not db.get(ContentMediaLink,(row.id,key)):db.add(ContentMediaLink(content_id=row.id,media_id=key))
    @classmethod
    def publish_due(cls,db):
        from src.services.authorization_service import AuthorizationService,AuthorizationDenied
        due=db.scalars(select(ContentEntry).where(ContentEntry.kind=='SERMON',ContentEntry.status=='SCHEDULED',
            cast(ContentEntry.published_data['data']['scheduled_publish_at'].astext,DateTime(timezone=True))<=now()).with_for_update(skip_locked=True).limit(25)).all()
        published=0
        for row in due:
            try:
                access=AuthorizationService.load(db,row.published_by);access.require_permission('SERMON_PUBLISH')
                cls.validate_ready(db,row,row.published_data)
            except (AuthorizationDenied,ContentError):row.status='FAILED';row.updated_at=now();continue
            row.status='PUBLISHED';row.published_at=now();row.updated_at=now();cls.link_thumbnail(db,row,row.published_data)
            cls.audit(db,access,'SERMON',row.id,'SERMON_SCHEDULE_PUBLISHED');published+=1
        db.commit();return published
    def taxonomy_list(self,kind):
        model,permission=TAXONOMY[kind]
        with self._db('SERMON_VIEW') as (db,access):return [self.taxonomy_dto(row) for row in db.scalars(select(model).order_by(model.display_order,model.name))]
    @staticmethod
    def taxonomy_dto(row):return dict(id=str(row.id),name=row.name,slug=row.slug,description=row.description,cover_image_id=str(row.cover_image_id) if row.cover_image_id else None,status=row.status,display_order=row.display_order,updated_at=row.updated_at,published_at=row.published_at)
    def taxonomy_save(self,kind,body,entity_id=None):
        model,permission=TAXONOMY[kind]
        with self._db(permission) as (db,access):
            row=db.get(model,ident(entity_id)) if entity_id else None
            if entity_id and not row:raise ContentMissing('Collection not found.')
            if row:
                check_version(row,body.expected_updated_at)
                if row.published_at and body.slug!=row.slug:raise ContentConflict('Keep the published collection URL stable.')
            else:row=model(name=body.name,slug=body.slug);db.add(row)
            row.name=body.name;row.slug=body.slug;row.description=body.description;row.display_order=body.display_order;row.cover_image_id=body.cover_image_id;row.updated_at=now()
            db.flush();self.audit(db,access,'SERMON_'+kind.upper(),row.id,'COLLECTION_UPDATED');db.commit();return self.taxonomy_dto(row)
    def taxonomy_action(self,kind,entity_id,action,expected):
        model,permission=TAXONOMY[kind]
        with self._db(permission) as (db,access):
            row=db.scalar(select(model).where(model.id==ident(entity_id)).with_for_update())
            if not row:raise ContentMissing('Collection not found.')
            check_version(row,expected)
            if action=='publish':
                access.require_permission('SERMON_PUBLISH')
                if row.cover_image_id:
                    image=db.get(WebsiteMedia,row.cover_image_id)
                    if not image or image.status!='PUBLISHED' or not image.consent_attested:raise ContentError('Approve the collection artwork first.')
                row.published_data=dict(name=row.name,slug=row.slug,description=row.description,cover_image_id=str(row.cover_image_id) if row.cover_image_id else None,display_order=row.display_order)
                row.status='PUBLISHED';row.published_at=now()
            elif action=='archive':row.status='ARCHIVED'
            else:raise ContentError('Unsupported collection action.')
            row.updated_at=now();db.commit();return self.taxonomy_dto(row)
