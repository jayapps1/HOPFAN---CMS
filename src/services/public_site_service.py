"""Anonymous reads select published snapshots and approved linked website assets."""
from sqlalchemy import select,or_,func,case,Integer,cast,String
from src.models.content import ContentEntry,ContentMediaLink,WebsiteSettings,WebsiteMedia,Event,Announcement
from src.services.content_base import ContentMissing,ident,now
from src.services.content_contracts import SiteConfiguration,EditorialData,HOME_SECTIONS,embed_video,safe_link
from src.services.website_media_service import LocalWebsiteStorage

class PublicSiteService:
    def __init__(self,db,storage=None):self.db=db;self.storage=storage or LocalWebsiteStorage()
    @staticmethod
    def approved_query():
        link=select(ContentMediaLink.media_id).join(ContentEntry,ContentEntry.id==ContentMediaLink.content_id).where(
            ContentMediaLink.media_id==WebsiteMedia.id,ContentEntry.status=='PUBLISHED').exists()
        event=select(Event.id).where(Event.image_id==WebsiteMedia.id,Event.status=='PUBLISHED',Event.visibility.in_(('PUBLIC','BOTH'))).exists()
        from src.models.sermon import SermonSeries
        series=select(SermonSeries.id).where(SermonSeries.status=='PUBLISHED',SermonSeries.published_data['cover_image_id'].astext==cast(WebsiteMedia.id,String)).exists()
        return select(WebsiteMedia).where(WebsiteMedia.status=='PUBLISHED',WebsiteMedia.consent_attested.is_(True),or_(link,event,series))
    def assets(self,ids):
        return {row.id:row for row in self.db.scalars(self.approved_query().where(WebsiteMedia.id.in_(ids)))} if ids else {}
    @staticmethod
    def image(row,size=960,caption=None,alt=None):
        return dict(url=f'/api/v1/public/media/{row.id}?size={size}',alt_text=alt or row.alt_text,
            width=min(size,row.width),height=max(1,round(row.height*min(size,row.width)/row.width)),caption=row.caption if caption is None else caption)
    def project(self,row,assets,gallery_limit=None):
        saved=row.published_data;data=saved.get('data',{})
        image=assets.get(ident(data['image_id'])) if data.get('image_id') else None
        result={key:saved.get(key,'') for key in ('slug','title','summary','body','seo_title','seo_description')}
        result['image']=self.image(image,1920) if image else None
        if row.kind=='MINISTRY':result.update(public_name=data.get('public_name') or result['title'],meeting_information=data.get('meeting_information',''),public_contact=data.get('public_contact',''))
        elif row.kind=='LEADERSHIP':result.update(public_name=data.get('public_name') or result['title'],public_title=data.get('public_title',''))
        elif row.kind=='SERMON':result.update(speaker=data.get('speaker',''),sermon_date=data.get('sermon_date'),scripture_reference=data.get('scripture_reference',''),
            series=data.get('series',''),video_embed_url=embed_video(data.get('youtube_url','')),audio_url=safe_link(data.get('audio_url','')))
        elif row.kind=='GALLERY':
            result['images']=[self.image(assets[ident(item['asset_id'])],960,item.get('caption',''),item['alt_text'])
                for item in data.get('images',[])[:gallery_limit] if ident(item['asset_id']) in assets]
        return result
    @staticmethod
    def references(rows,gallery_limit=None):
        result=set()
        for row in rows:
            data=row.published_data.get('data',{})
            if data.get('image_id'):result.add(ident(data['image_id']))
            result.update(ident(item['asset_id']) for item in data.get('images',[])[:gallery_limit])
        return result
    def list_content(self,kind,search='',series='',speaker='',limit=25,offset=0):
        if kind=='SERMON':
            from src.services.sermon_public_service import PublicSermonService
            return PublicSermonService(self.db,self).list(search=search,series=series,speaker=speaker,limit=limit,offset=offset)
        stmt=select(ContentEntry).where(ContentEntry.kind==kind,ContentEntry.status=='PUBLISHED',ContentEntry.published_data.is_not(None))
        if search:stmt=stmt.where(ContentEntry.published_data['title'].astext.ilike('%'+search.replace('%','\\%').replace('_','\\_')+'%',escape='\\'))
        if series:stmt=stmt.where(ContentEntry.published_data['data']['series'].astext==series)
        if speaker:stmt=stmt.where(ContentEntry.published_data['data']['speaker'].astext==speaker)
        total=self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        ordering=(self.display_order(),ContentEntry.slug,ContentEntry.id) if kind=='LEADERSHIP' else (ContentEntry.published_at.desc(),ContentEntry.id)
        rows=self.db.scalars(stmt.order_by(*ordering).limit(min(limit,100)).offset(offset)).all()
        assets=self.assets(self.references(rows))
        return dict(total=total,rows=[self.project(row,assets) for row in rows])
    def content(self,kind,slug):
        if kind=='SERMON':
            from src.services.sermon_public_service import PublicSermonService
            return PublicSermonService(self.db,self).detail(slug)
        row=self.db.scalar(select(ContentEntry).where(ContentEntry.kind==kind,ContentEntry.slug==slug,ContentEntry.status=='PUBLISHED',ContentEntry.published_data.is_not(None)))
        if not row:raise ContentMissing('Published content not found.')
        return self.project(row,self.assets(self.references([row])))
    def configuration(self):
        row=self.db.get(WebsiteSettings,1)
        configuration=SiteConfiguration.model_validate(row.published_data if row and row.published_data else {}).model_dump(mode='json')
        configuration['service_times']=sorted((item for item in configuration['service_times'] if item['active']),key=lambda item:(item['display_order'],item['name']))
        return configuration
    def events(self,past=False,limit=25,offset=0,future_only=False):
        stmt=select(Event).where(Event.status=='PUBLISHED',Event.visibility.in_(('PUBLIC','BOTH')))
        end=func.coalesce(Event.end_datetime,Event.start_datetime)
        stmt=stmt.where(Event.start_datetime>=now() if future_only else end<now() if past else end>=now())
        total=self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows=self.db.scalars(stmt.order_by(Event.start_datetime.desc() if past else Event.start_datetime,Event.id).limit(min(limit,100)).offset(offset)).all()
        assets=self.assets({row.image_id for row in rows if row.image_id})
        return dict(total=total,rows=[self.event_projection(row,assets) for row in rows])
    def event_projection(self,row,assets):
        return dict(slug=row.slug,title=row.title,description=row.description,start_datetime=row.start_datetime,end_datetime=row.end_datetime,
            location=row.location,event_type=row.event_type,image=self.image(assets[row.image_id]) if row.image_id in assets else None)
    def event(self,slug):
        row=self.db.scalar(select(Event).where(Event.slug==slug,Event.status=='PUBLISHED',Event.visibility.in_(('PUBLIC','BOTH'))))
        if not row:raise ContentMissing('Published event not found.')
        return self.event_projection(row,self.assets({row.image_id} if row.image_id else set()))
    def announcements(self,limit=25,offset=0):
        stmt=select(Announcement).where(Announcement.status=='PUBLISHED',Announcement.audience.in_(('PUBLIC','BOTH')),
            or_(Announcement.publish_from.is_(None),Announcement.publish_from<=now()),or_(Announcement.publish_until.is_(None),Announcement.publish_until>=now()))
        total=self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows=self.db.scalars(stmt.order_by(Announcement.priority.desc(),Announcement.published_at.desc(),Announcement.id).limit(min(limit,100)).offset(offset))
        return dict(total=total,rows=[{key:getattr(row,key) for key in ('slug','title','body','publish_from','publish_until','priority','published_at')} for row in rows])
    def media(self,media_id,size=960):
        row=self.db.scalar(self.approved_query().where(WebsiteMedia.id==ident(media_id)))
        if not row:raise ContentMissing('Published media not found.')
        try:return self.storage.read(row.storage_key,size)
        except OSError:raise ContentMissing('Media file not found.') from None
    def site(self):
        homepage=self.db.scalar(select(ContentEntry).where(ContentEntry.kind=='HOMEPAGE',ContentEntry.slug=='home',ContentEntry.status=='PUBLISHED'))
        preview=EditorialData.model_validate(homepage.published_data.get('data',{}) if homepage else {})
        featured=homepage.published_data.get('data',{}).get('featured_slugs',[]) if homepage else []
        leadership_order=case((ContentEntry.kind=='LEADERSHIP',self.display_order()),else_=0)
        publication_order=case((ContentEntry.kind=='LEADERSHIP',None),else_=ContentEntry.published_at)
        ranks=select(ContentEntry.id,func.row_number().over(partition_by=ContentEntry.kind,
            order_by=(case((ContentEntry.slug.in_(featured),0),else_=1),leadership_order,publication_order.desc(),ContentEntry.slug,ContentEntry.id)).label('rank'))\
            .where(ContentEntry.status=='PUBLISHED',ContentEntry.published_data.is_not(None)).subquery()
        rows=self.db.scalars(select(ContentEntry).where(or_(ContentEntry.id.in_(select(ranks.c.id).join(ContentEntry,ContentEntry.id==ranks.c.id)
            .where(ranks.c.rank<=case((ContentEntry.kind=='LEADERSHIP',8),(ContentEntry.kind=='GALLERY',2),(ContentEntry.kind=='SERMON',1),else_=6))),
            (ContentEntry.kind=='PAGE')&(ContentEntry.slug.in_(('about','sunday-school')))&(ContentEntry.status=='PUBLISHED')))
            .order_by(case((ContentEntry.slug.in_(featured),0),else_=1),leadership_order,publication_order.desc(),ContentEntry.slug,ContentEntry.id)).all()
        assets=self.assets(self.references(rows,gallery_limit=preview.gallery_count));group={}
        for row in rows:
            dto=self.project(row,assets,gallery_limit=preview.gallery_count)
            dto['body']=dto['body'][:1400] if row.kind=='PAGE' else ''
            dto['summary']=dto['summary'][:1000]
            group.setdefault(row.kind,[]).append((row,dto))
        home=next((row for row,_ in group.get('HOMEPAGE',[]) if row.slug=='home'),None)
        data=EditorialData.model_validate(home.published_data.get('data',{}) if home else {}).model_dump(mode='json')
        image=assets.get(ident(data['image_id'])) if data.get('image_id') else None
        welcome=next((dto for row,dto in group.get('PAGE',[]) if row.slug=='about'),None)
        # Isolate a failed events query in a savepoint so other Home content survives.
        events_available=True
        try:
            with self.db.begin_nested():events=self.events(limit=data['events_count'],future_only=True)['rows']
        except Exception:
            events=[];events_available=False
        return dict(configuration=self.configuration(),seo_title=home.published_data.get('seo_title','') if home else '',
            seo_description=home.published_data.get('seo_description','') if home else '',
            sunday_school=next((dto for row,dto in group.get('PAGE',[]) if row.slug=='sunday-school'),None),
            events_available=events_available,gallery_count=data['gallery_count'],hero=dict(headline=data.get('hero_headline') or 'Welcome to HOPFAN.',
            text=data.get('hero_text') or '',primary_label=data.get('primary_label','Plan your visit'),primary_href=safe_link(data.get('primary_href','/new-here')),
            secondary_label=data.get('secondary_label','Explore ministries'),secondary_href=safe_link(data.get('secondary_href','/ministries')),image=self.image(image,1920) if image else None),
            section_order=data.get('section_order',list(HOME_SECTIONS)),
            welcome=welcome,ministries=[dto for _,dto in group.get('MINISTRY',[])][:data['ministries_count']],leadership=[dto for _,dto in group.get('LEADERSHIP',[])],
            sermons=__import__('src.services.sermon_public_service',fromlist=['PublicSermonService']).PublicSermonService(self.db,self).list(sort='featured',limit=1)['rows'],galleries=[dto for _,dto in group.get('GALLERY',[])][:2],
            events=events,announcements=self.announcements(limit=data['announcements_count'])['rows'])

    @staticmethod
    def display_order():return func.coalesce(cast(ContentEntry.published_data['data']['display_order'].astext,Integer),0)
