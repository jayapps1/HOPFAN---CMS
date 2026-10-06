"""Versioned editorial drafts, public snapshots and scoped approval workflows."""
from copy import deepcopy
from sqlalchemy import select,func,or_,delete
from src.models import Ministry,Member
from src.models.content import ContentEntry,ContentMediaLink,WebsiteMedia,WebsiteSettings,Event,Announcement
from src.services.content_base import ContentBase,ContentError,ContentDenied,ContentConflict,ContentMissing,check_version,now,ident
from src.services.content_contracts import ContentWrite,SiteConfiguration,EventWrite,AnnouncementWrite

class PublishingService(ContentBase):
    def options(self):
        with self._db('WEBSITE_PAGE_VIEW') as (db,access):
            return dict(ministries=[dict(id=str(row.id),name=row.name) for row in db.scalars(select(Ministry).where(Ministry.is_active.is_(True)).order_by(Ministry.name))])
    @staticmethod
    def entry_dto(row):
        return dict(id=str(row.id),kind=row.kind,slug=row.slug,title=row.title,status=row.status,
            draft=row.draft_data,ministry_id=str(row.ministry_id) if row.ministry_id else None,
            member_id=str(row.member_id) if row.member_id else None,updated_at=row.updated_at,published_at=row.published_at,
            has_unpublished_changes=row.published_data!=row.draft_data)
    def list_content(self,kind=None,search='',status='ALL',limit=25,offset=0):
        with self._db('WEBSITE_PAGE_VIEW') as (db,access):
            stmt=select(ContentEntry)
            if kind:stmt=stmt.where(ContentEntry.kind==kind)
            if status!='ALL':stmt=stmt.where(ContentEntry.status==status)
            if search:stmt=stmt.where(ContentEntry.title.ilike('%'+search.replace('%','\\%').replace('_','\\_')+'%',escape='\\'))
            total=db.scalar(select(func.count()).select_from(stmt.subquery()))
            rows=db.scalars(stmt.order_by(ContentEntry.updated_at.desc(),ContentEntry.id).limit(min(limit,100)).offset(offset))
            return dict(total=total,rows=[self.entry_dto(row) for row in rows])
    @staticmethod
    def _entry(db,entry_id):
        row=db.scalar(select(ContentEntry).where(ContentEntry.id==ident(entry_id)).with_for_update().execution_options(populate_existing=True))
        if not row:raise ContentMissing('Content not found.')
        return row
    def get_content(self,entry_id):
        with self._db('WEBSITE_PAGE_VIEW') as (db,access):return self.entry_dto(self._entry(db,entry_id))
    def save_content(self,data,entry_id=None):
        values=ContentWrite.model_validate(data)
        with self._db('WEBSITE_PAGE_EDIT' if entry_id else 'WEBSITE_PAGE_CREATE') as (db,access):
            access.require_permission('WEBSITE_PAGE_VIEW')
            row=self._entry(db,entry_id) if entry_id else None
            if row:
                check_version(row,values.expected_updated_at)
                if row.kind!=values.kind:raise ContentError('Content type cannot be changed.')
                if row.published_at and row.slug!=values.slug:raise ContentConflict('A published URL cannot be changed silently.')
            if values.ministry_id and not db.get(Ministry,values.ministry_id):raise ContentMissing('Ministry not found.')
            if values.member_id:
                access.require_permission('MEMBERS_VIEW_ALL')
                if not db.get(Member,values.member_id):raise ContentMissing('Member not found.')
            snapshot=values.model_dump(mode='json',exclude={'expected_updated_at','member_id','ministry_id'})
            if row is None:row=ContentEntry(kind=values.kind,slug=values.slug,title=values.title,draft_data=snapshot,created_by=access.user_id);db.add(row)
            row.slug=values.slug;row.title=values.title;row.draft_data=snapshot
            row.ministry_id=values.ministry_id;row.member_id=values.member_id;row.updated_by=access.user_id;row.updated_at=now()
            db.flush();self.audit(db,access,'CONTENT',row.id,'CONTENT_UPDATED' if entry_id else 'CONTENT_CREATED',content_kind=values.kind)
            db.commit();return self.entry_dto(row)
    @staticmethod
    def media_ids(snapshot):
        data=snapshot.get('data',{})
        return {ident(value) for value in ([data.get('image_id')]+[item['asset_id'] for item in data.get('images',[])]) if value}
    @staticmethod
    def approved_media(db,ids):
        if not ids:return
        valid=set(db.scalars(select(WebsiteMedia.id).where(WebsiteMedia.id.in_(ids),WebsiteMedia.status=='PUBLISHED',WebsiteMedia.consent_attested.is_(True))))
        if valid!=set(ids):raise ContentError('Review and approve every selected image before publishing.')
    def content_action(self,entry_id,action,expected):
        with self._db('WEBSITE_PAGE_PUBLISH') as (db,access):
            access.require_permission('WEBSITE_PAGE_VIEW');row=self._entry(db,entry_id);check_version(row,expected)
            if action=='publish':
                ContentWrite.model_validate(dict(row.draft_data,ministry_id=row.ministry_id,member_id=row.member_id))
                if row.kind=='LEADERSHIP' and row.member_id:
                    from src.services.household_service import age_on
                    member=db.get(Member,row.member_id);age=age_on(member.date_of_birth,now().date())
                    if age is not None and age<18 and not row.draft_data['data'].get('consent_reference'):
                        raise ContentError('A child public-profile consent reference is required.')
                ids=self.media_ids(row.draft_data);self.approved_media(db,ids)
                row.published_data=deepcopy(row.draft_data);row.status='PUBLISHED';row.published_at=now();row.published_by=access.user_id
                db.execute(delete(ContentMediaLink).where(ContentMediaLink.content_id==row.id))
                for mid in ids:db.add(ContentMediaLink(content_id=row.id,media_id=mid))
            elif action=='unpublish':row.status='DRAFT'
            elif action=='archive':row.status='ARCHIVED'
            else:raise ContentError('Unsupported content action.')
            row.updated_at=now();row.updated_by=access.user_id
            self.audit(db,access,'CONTENT',row.id,'CONTENT_'+action.upper(),content_kind=row.kind)
            db.commit();return self.entry_dto(row)
    def settings(self):
        with self._db('WEBSITE_PAGE_VIEW') as (db,access):
            row=db.get(WebsiteSettings,1)
            return dict(data=row.draft_data if row else SiteConfiguration().model_dump(mode='json'),
                updated_at=row.updated_at if row else None,published_at=row.published_at if row else None)
    def save_settings(self,data,expected):
        values=SiteConfiguration.model_validate(data)
        with self._db('WEBSITE_SETTINGS_MANAGE') as (db,access):
            row=db.scalar(select(WebsiteSettings).where(WebsiteSettings.id==1).with_for_update().execution_options(populate_existing=True))
            if row:check_version(row,expected)
            else:row=WebsiteSettings(id=1,draft_data={});db.add(row)
            row.draft_data=values.model_dump(mode='json');row.updated_by=access.user_id;row.updated_at=now()
            self.audit(db,access,'SETTINGS',None,'SETTINGS_DRAFT_UPDATED');db.commit()
            return dict(data=row.draft_data,updated_at=row.updated_at,published_at=row.published_at)
    def publish_settings(self,expected):
        with self._db('WEBSITE_SETTINGS_MANAGE') as (db,access):
            access.require_permission('WEBSITE_PAGE_PUBLISH')
            row=db.scalar(select(WebsiteSettings).where(WebsiteSettings.id==1).with_for_update().execution_options(populate_existing=True))
            if not row:raise ContentMissing('Save website settings first.')
            check_version(row,expected);SiteConfiguration.model_validate(row.draft_data)
            row.published_data=deepcopy(row.draft_data);row.published_at=now();row.updated_at=now()
            self.audit(db,access,'SETTINGS',None,'SETTINGS_PUBLISHED');db.commit()
            return dict(data=row.draft_data,updated_at=row.updated_at,published_at=row.published_at)
    def overview(self):
        with self._db('WEBSITE_PAGE_VIEW') as (db,access):
            rows=db.execute(select(ContentEntry.kind,ContentEntry.status,func.count()).group_by(ContentEntry.kind,ContentEntry.status))
            return dict(counts=[dict(kind=kind,status=status,total=count) for kind,status,count in rows])

class CommunicationService(ContentBase):
    def options(self,kind):
        with self._db() as (db,access):
            self.visible(access,kind,select(self.model(kind)))
            stmt=select(Ministry).where(Ministry.is_active.is_(True))
            if not access.has(kind+'_VIEW_ALL'):stmt=stmt.where(Ministry.id.in_(access.ministry_ids(kind+'_VIEW_OWN_MINISTRY')))
            return dict(ministries=[dict(id=str(row.id),name=row.name) for row in db.scalars(stmt.order_by(Ministry.name))],
                global_create=access.has(kind+'_CREATE_GLOBAL'))
    @staticmethod
    def model(kind):return Event if kind=='EVENT' else Announcement
    @classmethod
    def visible(cls,access,kind,stmt):
        model=cls.model(kind)
        if access.has(kind+'_VIEW_ALL'):return stmt
        ids=access.ministry_ids(kind+'_VIEW_OWN_MINISTRY',include_inactive=True)
        if not ids:raise ContentDenied('Communication access is not assigned.')
        return stmt.where(or_(model.ministry_id.in_(ids),(model.ministry_id.is_(None))&(model.status=='PUBLISHED')))
    @staticmethod
    def authorize(access,kind,action,mid):
        global_code=kind+'_'+action+'_GLOBAL'
        if access.has(global_code):return
        own=kind+'_'+action+'_OWN_MINISTRY'
        if not mid or ident(mid) not in access.ministry_ids(own):raise ContentDenied('This ministry action is not assigned.')
    @classmethod
    def dto(cls,row):
        common=('id','slug','title','scope','ministry_id','status','updated_at','published_at')
        fields=('description','event_type','visibility','start_datetime','end_datetime','location','image_id') if isinstance(row,Event) else ('body','audience','publish_from','publish_until','priority')
        return {key:str(getattr(row,key)) if key in ('id','ministry_id','image_id') and getattr(row,key) is not None else getattr(row,key) for key in common+fields}
    def list(self,kind,search='',status='ALL',ministry_id=None,limit=25,offset=0):
        model=self.model(kind)
        with self._db() as (db,access):
            stmt=self.visible(access,kind,select(model))
            if ministry_id:
                if not access.can_access_ministry(ministry_id,kind+'_VIEW_OWN_MINISTRY',include_inactive=True):raise ContentDenied('Foreign ministry.')
                stmt=stmt.where(or_(model.ministry_id==ident(ministry_id),model.ministry_id.is_(None)))
            if status!='ALL':stmt=stmt.where(model.status==status)
            if search:stmt=stmt.where(model.title.ilike('%'+search.replace('%','\\%').replace('_','\\_')+'%',escape='\\'))
            total=db.scalar(select(func.count()).select_from(stmt.subquery()))
            rows=db.scalars(stmt.order_by(model.updated_at.desc(),model.id).limit(min(limit,100)).offset(offset))
            return dict(total=total,rows=[self.dto(row) for row in rows])
    def _get(self,db,access,kind,entity_id):
        model=self.model(kind)
        row=db.scalar(self.visible(access,kind,select(model)).where(model.id==ident(entity_id)).with_for_update().execution_options(populate_existing=True))
        if not row:raise ContentDenied('Resource unavailable or outside scope.')
        return row
    def get(self,kind,entity_id):
        with self._db() as (db,access):return self.dto(self._get(db,access,kind,entity_id))
    def save(self,kind,data,entity_id=None):
        values=(EventWrite if kind=='EVENT' else AnnouncementWrite).model_validate(data)
        with self._db() as (db,access):
            self.visible(access,kind,select(self.model(kind)))
            self.authorize(access,kind,'EDIT' if entity_id else 'CREATE',values.ministry_id)
            row=self._get(db,access,kind,entity_id) if entity_id else None
            if row:
                self.authorize(access,kind,'EDIT',row.ministry_id);check_version(row,values.expected_updated_at)
                if row.status in ('PUBLISHED','CANCELLED','ARCHIVED'):raise ContentConflict('Withdraw published content before editing.')
                if row.published_at and row.slug!=values.slug:raise ContentConflict('Published URLs remain stable.')
            if values.ministry_id:
                ministry=db.get(Ministry,values.ministry_id)
                if not ministry or not ministry.is_active:raise ContentError('Select an active permitted ministry.')
            raw=values.model_dump(exclude={'expected_updated_at'})
            if row is None:row=self.model(kind)(**raw,created_by=access.user_id);db.add(row)
            else:
                for key,value in raw.items():setattr(row,key,value)
                row.status='DRAFT';row.approved_by=None
            row.updated_at=now();db.flush();self.audit(db,access,kind,row.id,kind+'_UPDATED' if entity_id else kind+'_CREATED')
            db.commit();return self.dto(row)
    def action(self,kind,entity_id,action,expected):
        with self._db() as (db,access):
            row=self._get(db,access,kind,entity_id);check_version(row,expected)
            if action=='submit':
                access.require_permission(kind+'_SUBMIT');self.authorize(access,kind,'EDIT',row.ministry_id)
                if row.status!='DRAFT':raise ContentConflict('Submit a draft.')
                row.status='SUBMITTED'
            elif action=='approve':
                access.require_permission(kind+'_APPROVE')
                if not access.has(kind+'_VIEW_ALL'):raise ContentDenied('Approval requires global oversight.')
                if row.status!='SUBMITTED':raise ContentConflict('Approve submitted content.')
                row.status='APPROVED';row.approved_by=access.user_id
            elif action=='publish':
                access.require_permission(kind+'_PUBLISH')
                if not access.has(kind+'_VIEW_ALL'):raise ContentDenied('Publication requires global oversight.')
                if row.status!='APPROVED':raise ContentConflict('Approve content before publication.')
                if kind=='EVENT':PublishingService.approved_media(db,{row.image_id} if row.image_id else set())
                row.status='PUBLISHED';row.published_at=now()
            elif action in ('cancel','archive','unpublish'):
                access.require_permission(kind+'_CANCEL' if action!='unpublish' else kind+'_PUBLISH')
                if not access.has(kind+'_VIEW_ALL'):raise ContentDenied('Publication changes require global oversight.')
                row.status='DRAFT' if action=='unpublish' else action.upper()+'LED' if action=='cancel' else 'ARCHIVED'
                if action=='unpublish':row.approved_by=None
            else:raise ContentError('Unsupported transition.')
            row.updated_at=now();self.audit(db,access,kind,row.id,kind+'_'+action.upper());db.commit();return self.dto(row)
