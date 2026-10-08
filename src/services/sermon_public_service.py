"""Public sermons use published snapshots, never editable drafts or member records."""
from uuid import UUID
from sqlalchemy import select,func,or_,case,Integer,cast,String,and_,literal
from src.models import ContentEntry,WebsiteMedia
from src.models.sermon import SermonSeries,SermonCategory,SermonMediaAsset,SermonMetric
from src.services.content_base import ContentMissing,ident
from src.services.content_contracts import embed_video,safe_link
from src.services.sermon_service import ASSET_FIELDS

class PublicSermonService:
    def __init__(self,db,website=None):
        self.db=db
        if website is None:
            from src.services.public_site_service import PublicSiteService
            website=PublicSiteService(db)
        self.website=website
    @staticmethod
    def query():return select(ContentEntry).where(ContentEntry.kind=='SERMON',ContentEntry.status=='PUBLISHED',ContentEntry.published_data.is_not(None),func.coalesce(ContentEntry.published_data['data']['sermon_visibility'].astext,'PUBLIC')=='PUBLIC')
    def record(self,slug):
        row=self.db.scalar(self.query().where(ContentEntry.slug==slug))
        if not row:raise ContentMissing('Published sermon not found.')
        return row
    def assets(self,rows):
        ids={ident(row.published_data['data'][field]) for row in rows for field in ASSET_FIELDS if row.published_data.get('data',{}).get(field)}
        return {asset.id:asset for asset in self.db.scalars(select(SermonMediaAsset).where(SermonMediaAsset.id.in_(ids),SermonMediaAsset.processing_status=='READY',SermonMediaAsset.rights_attested.is_(True)))} if ids else {}
    def project(self,row,assets=None,detail=False):
        saved=row.published_data;d=saved.get('data',{});assets=assets if assets is not None else self.assets([row])
        image=None
        if d.get('image_id'):
            source=self.website.assets({ident(d['image_id'])}).get(ident(d['image_id']))
            if source:image=self.website.image(source,960)
        media=[]
        for field,kind in ASSET_FIELDS.items():
            asset=assets.get(ident(d[field])) if d.get(field) else None
            if not asset or asset.sermon_id!=row.id:continue
            url=f'/api/v1/public/sermons/{row.slug}/media/{asset.id}'
            allowed=asset.download_allowed and (d.get('allow_audio_download',False) if kind=='AUDIO' else d.get('allow_video_download',False) if kind=='VIDEO' else True)
            media.append(dict(id=str(asset.id),media_type=kind,mime_type=asset.mime_type,file_size=asset.file_size,duration_seconds=asset.duration_seconds,
                width=asset.width,height=asset.height,quality_label=asset.quality_label,url=url,
                download_url=f'/api/v1/public/sermons/{row.slug}/download/'+kind.lower() if allowed else None))
            if kind=='THUMBNAIL':image=dict(url=url,alt_text='Thumbnail for '+saved['title'],width=asset.width or 1280,height=asset.height or 720,caption='')
        collections={}
        for key,model in (('series',SermonSeries),('category',SermonCategory)):
            tax=self.db.get(model,ident(d[key+'_id'])) if d.get(key+'_id') else None
            collections[key]=dict(id=str(tax.id),name=tax.published_data['name'],slug=tax.slug) if tax and tax.status=='PUBLISHED' and tax.published_data else None
        source=d.get('video_source_type','NONE')
        youtube=d.get('youtube_url','')
        embed=embed_video(youtube) if youtube else ''
        if source=='NONE' and youtube:source='VIMEO' if 'vimeo.com' in youtube else 'YOUTUBE'
        metrics=dict(self.db.execute(select(SermonMetric.event,SermonMetric.count).where(SermonMetric.sermon_id==row.id)).all())
        duration=d.get('duration_seconds') or next((asset['duration_seconds'] for asset in media if asset['duration_seconds']),None)
        return dict(slug=row.slug,title=saved['title'],summary=saved.get('summary',''),body=saved.get('body','') if detail else '',
            seo_title=saved.get('seo_title',''),seo_description=saved.get('seo_description',''),image=image,
            subtitle=d.get('subtitle',''),speaker=d.get('speaker',''),sermon_date=d.get('sermon_date'),scripture_reference=d.get('scripture_reference',''),
            series=collections['series']['name'] if collections['series'] else d.get('series',''),series_info=collections['series'],category=collections['category'],
            tags=d.get('tags',[]),service_type=d.get('service_type',''),featured=d.get('featured',False),duration_seconds=duration,
            video_source_type=source,video_embed_url=embed,external_video_url=safe_link(d.get('external_video_url','')) if source=='EXTERNAL' else '',
            audio_url=safe_link(d.get('audio_url','')),media=media,transcript=d.get('transcript','') if detail else '',
            speaker_profile_slug=d.get('speaker_profile_slug',''),published_at=row.published_at,
            views=metrics.get('VIDEO_PLAY',0)+metrics.get('AUDIO_PLAY',0),audio_plays=metrics.get('AUDIO_PLAY',0),video_plays=metrics.get('VIDEO_PLAY',0))
    def list(self,search='',series='',speaker='',category='',year=None,media_type='',sort='latest',limit=24,offset=0):
        stmt=self.query();data=ContentEntry.published_data['data']
        if search:
            term='%'+search.replace('%','\\%').replace('_','\\_')+'%'
            terms=[ContentEntry.published_data['title'].astext,ContentEntry.published_data['summary'].astext,ContentEntry.published_data['body'].astext,
                data['speaker'].astext,data['scripture_reference'].astext,data['series'].astext,data['tags'].astext]
            stmt=stmt.where(or_(*(field.ilike(term,escape='\\') for field in terms),
                data['series_id'].astext.in_(select(cast(SermonSeries.id,String)).where(SermonSeries.status=='PUBLISHED',SermonSeries.published_data['name'].astext.ilike(term,escape='\\'))),
                data['category_id'].astext.in_(select(cast(SermonCategory.id,String)).where(SermonCategory.status=='PUBLISHED',SermonCategory.published_data['name'].astext.ilike(term,escape='\\')))))
        if series:
            ids=select(cast(SermonSeries.id,String)).where(or_(SermonSeries.slug==series,SermonSeries.published_data['name'].astext==series))
            stmt=stmt.where(or_(data['series'].astext==series,data['series_id'].astext==series,data['series_id'].astext.in_(ids)))
        if speaker:stmt=stmt.where(data['speaker'].astext==speaker)
        if category:
            ids=select(cast(SermonCategory.id,String)).where(SermonCategory.slug==category)
            stmt=stmt.where(or_(data['category_id'].astext==category,data['category_id'].astext.in_(ids)))
        if year:stmt=stmt.where(data['sermon_date'].astext.startswith(str(year)+'-'))
        if media_type=='VIDEO':stmt=stmt.where(or_(data['video_asset_id'].astext.is_not(None),data['youtube_url'].astext!='',data['external_video_url'].astext!=''))
        if media_type=='AUDIO':stmt=stmt.where(or_(data['audio_asset_id'].astext.is_not(None),data['audio_url'].astext!=''))
        total=self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        if sort=='popular':
            aggregate=select(SermonMetric.sermon_id,func.sum(SermonMetric.count).label('plays')).where(SermonMetric.event.in_(('VIDEO_PLAY','AUDIO_PLAY'))).group_by(SermonMetric.sermon_id).subquery()
            stmt=stmt.outerjoin(aggregate,aggregate.c.sermon_id==ContentEntry.id).order_by(func.coalesce(aggregate.c.plays,0).desc())
        elif sort=='featured':stmt=stmt.order_by(func.coalesce(data['featured'].astext,'false').desc())
        rows=self.db.scalars(stmt.order_by(data['sermon_date'].astext.desc(),ContentEntry.published_at.desc(),ContentEntry.id).limit(min(limit,100)).offset(offset)).all()
        assets=self.assets(rows)
        return dict(total=total,rows=[self.project(row,assets) for row in rows])
    def detail(self,slug):return self.project(self.record(slug),detail=True)
    def related(self,slug,limit=6):
        row=self.record(slug);d=row.published_data.get('data',{});data=ContentEntry.published_data['data']
        same_series=data['series_id'].astext==d['series_id'] if d.get('series_id') else data['series'].astext==d['series'] if d.get('series') else literal(False)
        next_in_series=and_(same_series,data['sermon_date'].astext>(d.get('sermon_date') or ''))
        rows=self.db.scalars(self.query().where(ContentEntry.id!=row.id).order_by(case((next_in_series,0),else_=1),case((same_series,0),else_=1),
            case((data['category_id'].astext==d.get('category_id'),0),else_=1),case((data['speaker'].astext==d.get('speaker'),0),else_=1),
            case((next_in_series,data['sermon_date'].astext),else_=None),data['sermon_date'].astext.desc(),ContentEntry.id).limit(limit)).all()
        assets=self.assets(rows);return [self.project(item,assets) for item in rows]
    def media_asset(self,slug,asset_id=None,kind=None,download=False):
        row=self.record(slug);d=row.published_data.get('data',{})
        field=next((field for field,value in ASSET_FIELDS.items() if value==kind),None) if kind else None
        candidate=ident(d[field]) if field and d.get(field) else ident(asset_id) if asset_id else None
        permitted={ident(d[field]) for field in ASSET_FIELDS if d.get(field)}
        asset=self.db.get(SermonMediaAsset,candidate) if candidate else None
        if not asset or asset.id not in permitted or asset.sermon_id!=row.id or asset.processing_status!='READY' or not asset.rights_attested:raise ContentMissing('Published media not found.')
        if download and (not asset.download_allowed or asset.media_type=='AUDIO' and not d.get('allow_audio_download') or asset.media_type=='VIDEO' and not d.get('allow_video_download')):raise ContentMissing('Download is not enabled.')
        return row,asset
    def taxonomy(self,kind,slug=None):
        model=SermonSeries if kind=='series' else SermonCategory
        rows=self.db.scalars(select(model).where(model.status=='PUBLISHED',model.published_data.is_not(None),*( [model.slug==slug] if slug else [])).order_by(model.display_order,model.name)).all()
        if slug and not rows:raise ContentMissing('Published collection not found.')
        values=[]
        for row in rows:
            d=row.published_data;image=None
            if d.get('cover_image_id'):
                cover=self.website.assets({ident(d['cover_image_id'])}).get(ident(d['cover_image_id']))
                if cover:image=self.website.image(cover,960)
            count=self.db.scalar(select(func.count()).select_from(self.query().where(ContentEntry.published_data['data'][('series_id' if kind=='series' else 'category_id')].astext==str(row.id)).subquery()))
            values.append(dict(id=str(row.id),name=d['name'],slug=row.slug,description=d.get('description',''),image=image,sermon_count=count))
        return values[0] if slug else values
    def filters(self):
        rows=self.db.execute(select(ContentEntry.published_data['data']['speaker'].astext,ContentEntry.published_data['data']['sermon_date'].astext).where(ContentEntry.id.in_(select(self.query().subquery().c.id)))).all()
        return dict(series=self.taxonomy('series'),categories=self.taxonomy('categories'),speakers=sorted({row[0] for row in rows if row[0]}),years=sorted({int(row[1][:4]) for row in rows if row[1]},reverse=True))
