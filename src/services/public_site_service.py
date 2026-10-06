"""Anonymous reads select published snapshots and approved linked website assets."""
from sqlalchemy import select,or_,func,case
from src.models.content import ContentEntry,ContentMediaLink,WebsiteSettings,WebsiteMedia,Event,Announcement
from src.services.content_base import ContentMissing,ident,now
from src.services.content_contracts import SiteConfiguration,embed_video,safe_link
from src.services.website_media_service import LocalWebsiteStorage

class PublicSiteService:
    def __init__(self,db,storage=None):self.db=db;self.storage=storage or LocalWebsiteStorage()
    @staticmethod
    def approved_query():
        link=select(ContentMediaLink.media_id).join(ContentEntry,ContentEntry.id==ContentMediaLink.content_id).where(
            ContentMediaLink.media_id==WebsiteMedia.id,ContentEntry.status=='PUBLISHED').exists()
        event=select(Event.id).where(Event.image_id==WebsiteMedia.id,Event.status=='PUBLISHED',Event.visibility.in_(('PUBLIC','BOTH'))).exists()
        return select(WebsiteMedia).where(WebsiteMedia.status=='PUBLISHED',WebsiteMedia.consent_attested.is_(True),or_(link,event))
    def assets(self,ids):
        return {row.id:row for row in self.db.scalars(self.approved_query().where(WebsiteMedia.id.in_(ids)))} if ids else {}
    @staticmethod
    def image(row,size=960,caption=None,alt=None):
        return dict(url=f'/api/v1/public/media/{row.id}?size={size}',alt_text=alt or row.alt_text,
            width=min(size,row.width),height=max(1,round(row.height*min(size,row.width)/row.width)),caption=row.caption if caption is None else caption)
    def project(self,row,assets):
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
                for item in data.get('images',[]) if ident(item['asset_id']) in assets]
        return result
    @staticmethod
    def references(rows):
        result=set()
        for row in rows:
            data=row.published_data.get('data',{})
            if data.get('image_id'):result.add(ident(data['image_id']))
            result.update(ident(item['asset_id']) for item in data.get('images',[]))
        return result
    def list_content(self,kind,search='',series='',speaker='',limit=25,offset=0):
        stmt=select(ContentEntry).where(ContentEntry.kind==kind,ContentEntry.status=='PUBLISHED',ContentEntry.published_data.is_not(None))
        if search:stmt=stmt.where(ContentEntry.published_data['title'].astext.ilike('%'+search.replace('%','\\%').replace('_','\\_')+'%',escape='\\'))
        if series:stmt=stmt.where(ContentEntry.published_data['data']['series'].astext==series)
        if speaker:stmt=stmt.where(ContentEntry.published_data['data']['speaker'].astext==speaker)
        total=self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows=self.db.scalars(stmt.order_by(ContentEntry.published_at.desc(),ContentEntry.id).limit(min(limit,100)).offset(offset)).all()
        assets=self.assets(self.references(rows))
        return dict(total=total,rows=[self.project(row,assets) for row in rows])
    def content(self,kind,slug):
        row=self.db.scalar(select(ContentEntry).where(ContentEntry.kind==kind,ContentEntry.slug==slug,ContentEntry.status=='PUBLISHED',ContentEntry.published_data.is_not(None)))
        if not row:raise ContentMissing('Published content not found.')
        return self.project(row,self.assets(self.references([row])))
    def configuration(self):
        row=self.db.get(WebsiteSettings,1)
        return SiteConfiguration.model_validate(row.published_data if row and row.published_data else {}).model_dump(mode='json')
    def events(self,past=False,limit=25,offset=0):
        stmt=select(Event).where(Event.status=='PUBLISHED',Event.visibility.in_(('PUBLIC','BOTH')))
        end=func.coalesce(Event.end_datetime,Event.start_datetime)
        stmt=stmt.where(end<now() if past else end>=now())
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
        return dict(total=total,rows=[{key:getattr(row,key) for key in ('slug','title','body','publish_from','publish_until')} for row in rows])
    def media(self,media_id,size=960):
        row=self.db.scalar(self.approved_query().where(WebsiteMedia.id==ident(media_id)))
        if not row:raise ContentMissing('Published media not found.')
        try:return self.storage.read(row.storage_key,size)
        except OSError:raise ContentMissing('Media file not found.') from None
    def site(self):
        homepage=self.db.scalar(select(ContentEntry).where(ContentEntry.kind=='HOMEPAGE',ContentEntry.slug=='home',ContentEntry.status=='PUBLISHED'))
        featured=homepage.published_data.get('data',{}).get('featured_slugs',[]) if homepage else []
        ranks=select(ContentEntry.id,func.row_number().over(partition_by=ContentEntry.kind,
            order_by=(case((ContentEntry.slug.in_(featured),0),else_=1),ContentEntry.published_at.desc())).label('rank'))\
            .where(ContentEntry.status=='PUBLISHED',ContentEntry.published_data.is_not(None)).subquery()
        rows=self.db.scalars(select(ContentEntry).where(or_(ContentEntry.id.in_(select(ranks.c.id).where(ranks.c.rank<=6)),(ContentEntry.kind=='PAGE')&(ContentEntry.slug=='about')&(ContentEntry.status=='PUBLISHED')))).all()
        assets=self.assets(self.references(rows));group={}
        for row in rows:group.setdefault(row.kind,[]).append((row,self.project(row,assets)))
        home=next((row for row,_ in group.get('HOMEPAGE',[]) if row.slug=='home'),None)
        data=home.published_data['data'] if home else {}
        image=assets.get(ident(data['image_id'])) if data.get('image_id') else None
        welcome=next((dto for row,dto in group.get('PAGE',[]) if row.slug=='about'),None)
        return dict(configuration=self.configuration(),hero=dict(headline=data.get('hero_headline') or 'Welcome to HOPFAN.',
            text=data.get('hero_text') or '',primary_label=data.get('primary_label','Plan your visit'),primary_href=safe_link(data.get('primary_href','/new-here')),
            secondary_label=data.get('secondary_label','Explore ministries'),secondary_href=safe_link(data.get('secondary_href','/ministries')),image=self.image(image,1920) if image else None),
            section_order=data.get('section_order',['welcome','services','events','sermons','ministries','sunday-school','announcements','gallery','prayer','visit','contact']),
            welcome=welcome,ministries=[dto for _,dto in group.get('MINISTRY',[])],leadership=[dto for _,dto in group.get('LEADERSHIP',[])],
            sermons=[dto for _,dto in group.get('SERMON',[])],galleries=[dto for _,dto in group.get('GALLERY',[])],
            events=self.events(limit=6)['rows'],announcements=self.announcements(limit=6)['rows'])
