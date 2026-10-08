"""Sermon media authority: typed public reads and authenticated streamed uploads."""
import hashlib,re,json
from contextlib import contextmanager
from pathlib import PurePosixPath
from typing import Annotated,Literal
from uuid import UUID,uuid4
from datetime import timedelta
from fastapi import APIRouter,Depends,Request,Query,BackgroundTasks
from starlette.responses import FileResponse,RedirectResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select,delete
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert
from src.api.v1 import API_PREFIX
from src.api.dependencies import get_db,get_current_user
from src.api.security.csrf import require_trusted_origin
from src.api.v1.content import safe_content_errors,page
from src.api.schemas.workspace import Page
from src.api.schemas.sermon import PublicSermonRecord,PublicSermonTaxonomy
from src.services.sermon_contracts import SermonWrite,TaxonomyWrite,SermonAction,MediaDelete,PlaybackWrite,AssetPermissions
from src.services.sermon_service import SermonService,ASSET_FIELDS
from src.services.sermon_public_service import PublicSermonService
from src.services.sermon_storage import MediaStorageService
from src.services.sermon_processing import SermonProcessingService,EXTENSIONS
from src.services.content_base import ContentError,ContentMissing,ContentConflict,now,ident,check_version
from src.services.web_security import WebSecurityError
from src.services.web_rate_limit_service import WebRateLimitService
from src.models import ContentEntry
from src.models.sermon import SermonMediaAsset,SermonMetric,SermonPlaybackReceipt

router=APIRouter(prefix=API_PREFIX,tags=['Sermon media platform'])
DB=Annotated[object,Depends(get_db,scope='function')]
Principal=Annotated[object,Depends(get_current_user)]
Number=Annotated[int,Query(ge=1,le=100000)]
Size=Annotated[int,Query(ge=1,le=100)]
Search=Annotated[str,Query(max_length=200)]

def service(db:DB,principal:Principal):
    @contextmanager
    def borrowed():yield db
    with safe_content_errors():yield SermonService(principal.user.id,borrowed)
Service=Annotated[SermonService,Depends(service,scope='function')]
def public(db:DB):
    with safe_content_errors():yield PublicSermonService(db)
Public=Annotated[PublicSermonService,Depends(public,scope='function')]
def media_storage(request):return getattr(request.app.state,'sermon_storage',None) or MediaStorageService()

@router.get('/sermons/overview')
def overview(service:Service):return service.overview()
@router.get('/sermons/options')
def options(service:Service):return service.options()
@router.get('/sermons')
def listing(service:Service,search:Search='',status:Literal['ALL','DRAFT','PROCESSING','READY','SCHEDULED','PUBLISHED','ARCHIVED','FAILED']='ALL',page_number:Number=1,page_size:Size=25):
    return page(service.list(search,status,page_size,(page_number-1)*page_size),page_number,page_size)
@router.post('/sermons',status_code=201)
def create(service:Service,body:SermonWrite):return service.save(body)
@router.get('/sermons/{sermon_id}')
def detail(service:Service,sermon_id:UUID):return service.get(sermon_id)
@router.patch('/sermons/{sermon_id}')
def update(service:Service,sermon_id:UUID,body:SermonWrite):return service.save(body,sermon_id)
@router.post('/sermons/{sermon_id}/actions/{action}')
def transition(service:Service,sermon_id:UUID,action:Literal['ready','publish','unpublish','archive','schedule','cancel-schedule'],body:SermonAction):
    return service.action(sermon_id,action,body.expected_updated_at,body.scheduled_publish_at)

def collection_routes(kind):
    def listing(service:Service):return service.taxonomy_list(kind)
    def create(service:Service,body:TaxonomyWrite):return service.taxonomy_save(kind,body)
    def update(service:Service,entity_id:UUID,body:TaxonomyWrite):return service.taxonomy_save(kind,body,entity_id)
    def action(service:Service,entity_id:UUID,action:Literal['publish','archive'],body:SermonAction):return service.taxonomy_action(kind,entity_id,action,body.expected_updated_at)
    prefix='/sermon-'+kind
    router.add_api_route(prefix,listing,methods=['GET'])
    router.add_api_route(prefix,create,methods=['POST'],status_code=201)
    router.add_api_route(prefix+'/{entity_id}',update,methods=['PATCH'])
    router.add_api_route(prefix+'/{entity_id}/{action}',action,methods=['POST'])
collection_routes('series');collection_routes('categories')

@router.post('/sermons/{sermon_id}/media',status_code=202)
async def upload(request:Request,db:DB,principal:Principal,sermon_id:UUID,background:BackgroundTasks,
    media_type:Literal['VIDEO','AUDIO','THUMBNAIL','CAPTION','TRANSCRIPT','DOCUMENT'],filename:Annotated[str,Query(max_length=200)],
    rights_attested:bool=False,download_allowed:bool=False):
    with safe_content_errors():
        principal.authorization.require_permission('SERMON_UPLOAD_MEDIA');principal.authorization.require_permission('SERMON_VIEW')
        if not rights_attested:raise ContentError('Confirm HOPFAN is authorized to manage and distribute this media.')
        row=SermonService.record(db,sermon_id)
        if row.status=='SCHEDULED':raise ContentConflict('Cancel scheduling before replacing its frozen media.')
        name=filename.replace('\\','/').split('/')[-1]
        if not name or re.search(r'[\x00-\x1f\x7f]',name):raise ContentError('Use a valid media filename.')
        extension=name.rsplit('.',1)[-1].lower()
        if extension not in EXTENSIONS[media_type]:raise ContentError('Use a supported file extension for this media type.')
        mime=EXTENSIONS[media_type][extension];declared=request.headers.get('content-type','').split(';',1)[0].lower()
        if declared not in {mime,'application/octet-stream','audio/mp3','audio/x-wav','audio/x-m4a'}:raise ContentError('The declared file type does not match supported media.')
        storage=media_storage(request);limit=storage.settings.limit(media_type)
        try:length=int(request.headers.get('content-length','0'))
        except ValueError:length=0
        if length>limit:raise WebSecurityError(413,'REQUEST_TOO_LARGE','The uploaded media exceeds its configured size limit.')
        aid=uuid4();suffix='jpg' if media_type=='THUMBNAIL' else extension
        asset=SermonMediaAsset(id=aid,sermon_id=row.id,media_type=media_type,storage_provider=storage.settings.provider,
            storage_key=f'sermons/{row.id}/{aid}.{suffix}',original_filename=name,mime_type=mime,format=extension,
            rights_attested=True,download_allowed=download_allowed,uploaded_by=principal.user.id)
        db.add(asset);db.commit()
        path=storage.staging_path(aid);size=0;digest=hashlib.sha256()
        try:
            with path.open('xb') as output:
                async for chunk in request.stream():
                    size+=len(chunk)
                    if size>limit:raise WebSecurityError(413,'REQUEST_TOO_LARGE','The uploaded media exceeds its configured size limit.')
                    digest.update(chunk);await run_in_threadpool(output.write,chunk)
            if not size:raise ContentError('Choose a nonempty media file.')
            asset.file_size=size;asset.sha256=digest.hexdigest();asset.processing_status='QUEUED';asset.updated_at=now()
            row=SermonService.record(db,sermon_id);snapshot=dict(row.draft_data);data=dict(snapshot.get('data',{}))
            field=next(field for field,kind in ASSET_FIELDS.items() if kind==media_type)
            data[field]=str(aid)
            if media_type=='VIDEO':data['video_source_type']='UPLOADED';data['youtube_url']='';data['external_video_url']=''
            snapshot['data']=data;row.draft_data=snapshot;row.updated_at=now();row.updated_by=principal.user.id
            if row.status!='PUBLISHED':row.status='PROCESSING'
            db.commit()
        except Exception:
            path.unlink(missing_ok=True);asset.processing_status='FAILED';asset.error_summary='Upload did not finish. Upload the file again.';db.commit();raise
        factory=sessionmaker(bind=db.get_bind(),expire_on_commit=False)
        background.add_task(SermonProcessingService.process,factory,storage,aid)
        return SermonService.asset_dto(asset)

@router.post('/sermons/{sermon_id}/media/{asset_id}/permissions')
def asset_permissions(db:DB,principal:Principal,sermon_id:UUID,asset_id:UUID,body:AssetPermissions):
    with safe_content_errors():
        principal.authorization.require_permission('SERMON_EDIT');SermonService.record(db,sermon_id)
        asset=db.scalar(select(SermonMediaAsset).where(SermonMediaAsset.id==asset_id).with_for_update())
        if not asset or asset.sermon_id!=sermon_id or asset.processing_status in {'DELETED','DELETE_PENDING'}:raise ContentMissing('Media not found.')
        check_version(asset,body.expected_updated_at)
        if not asset.rights_attested:raise ContentError('Media distribution must be authorized.')
        asset.download_allowed=body.download_allowed;asset.updated_at=now();SermonService.audit(db,principal.authorization,'SERMON_MEDIA',asset.id,'DOWNLOAD_PERMISSION_CHANGED',download_allowed=body.download_allowed);db.commit()
        return SermonService.asset_dto(asset)

@router.post('/sermons/{sermon_id}/media/{asset_id}/retry')
def retry(request:Request,db:DB,principal:Principal,sermon_id:UUID,asset_id:UUID,background:BackgroundTasks):
    with safe_content_errors():
        principal.authorization.require_permission('SERMON_UPLOAD_MEDIA');SermonService.record(db,sermon_id)
        asset=db.get(SermonMediaAsset,asset_id);storage=media_storage(request)
        if not asset or asset.sermon_id!=sermon_id or asset.processing_status!='FAILED' or not storage.staging_path(asset_id).exists():raise ContentConflict('This upload needs a replacement file.')
        asset.processing_status='QUEUED';asset.error_summary='';db.commit()
        background.add_task(SermonProcessingService.process,sessionmaker(bind=db.get_bind(),expire_on_commit=False),storage,asset_id)
        return SermonService.asset_dto(asset)

@router.post('/sermons/{sermon_id}/media/{asset_id}/delete')
def remove(request:Request,db:DB,principal:Principal,sermon_id:UUID,asset_id:UUID,body:MediaDelete):
    with safe_content_errors():
        principal.authorization.require_permission('SERMON_DELETE_MEDIA');row=SermonService.record(db,sermon_id);check_version(row,body.expected_updated_at)
        asset=db.get(SermonMediaAsset,asset_id)
        if not asset or asset.sermon_id!=sermon_id:raise ContentMissing('Media not found.')
        if asset.processing_status in {'QUEUED','PROCESSING'}:raise ContentConflict('Wait for the media job before removal.')
        if row.status in {'PUBLISHED','SCHEDULED'} and str(asset.id) in [str((row.published_data or {}).get('data',{}).get(field)) for field in ASSET_FIELDS]:raise ContentConflict('Publish a replacement or unpublish this sermon before deleting active media.')
        asset.processing_status='DELETE_PENDING';db.commit();storage=media_storage(request)
        storage.delete(asset.storage_key);storage.staging_path(asset.id).unlink(missing_ok=True)
        asset.processing_status='DELETED';data=dict(row.draft_data['data'])
        for field in ASSET_FIELDS:
            if data.get(field)==str(asset.id):data[field]=None
        row.draft_data=dict(row.draft_data,data=data);row.updated_at=now();db.commit();return {'deleted':True}

def delivery(request,row,asset,storage,download=False):
    range_header=request.headers.get('range','')
    if len(range_header)>128 or ',' in range_header:raise WebSecurityError(416,'INVALID_RANGE','Request a single byte range.')
    speaker=(row.published_data or row.draft_data).get('data',{}).get('speaker','')
    speaker=re.sub(r'[^A-Za-z0-9-]+','-',speaker).strip('-')[:60]
    filename='HOPFAN-'+row.slug+('-'+speaker if speaker else '')+'.'+asset.format
    disposition='attachment' if download else 'inline'
    signed=storage.generate_signed_url(asset.storage_key,asset.mime_type,filename,disposition)
    if signed:return RedirectResponse(signed,status_code=307)
    path=storage.local_path(asset.storage_key)
    if not path.is_file():raise ContentMissing('Media file is unavailable.')
    return FileResponse(path,media_type=asset.mime_type,filename=filename,content_disposition_type=disposition,headers={'X-Content-Type-Options':'nosniff'})
@router.get('/sermons/{sermon_id}/media/{asset_id}/preview')
def preview(request:Request,db:DB,principal:Principal,sermon_id:UUID,asset_id:UUID):
    with safe_content_errors():
        principal.authorization.require_permission('SERMON_VIEW');row=SermonService.record(db,sermon_id,False);asset=db.get(SermonMediaAsset,asset_id)
        if not asset or asset.sermon_id!=sermon_id or asset.processing_status!='READY':raise ContentMissing('Preview not found.')
        return delivery(request,row,asset,media_storage(request))

@router.get('/public/sermons/filters')
def filters(service:Public):return service.filters()
@router.get('/public/sermons',response_model=Page[PublicSermonRecord])
def public_list(service:Public,search:Search='',series:Search='',speaker:Search='',category:Search='',year:Annotated[int|None,Query(ge=1900,le=2200)]=None,
    media_type:Literal['','VIDEO','AUDIO']='',sort:Literal['latest','featured','popular']='latest',page_number:Number=1,page_size:Size=24):
    return page(service.list(search,series,speaker,category,year,media_type,sort,page_size,(page_number-1)*page_size),page_number,page_size)
@router.get('/public/sermons/{slug}',response_model=PublicSermonRecord)
def public_detail(service:Public,slug:str):return service.detail(slug)
@router.get('/public/sermons/{slug}/related',response_model=list[PublicSermonRecord])
def related(service:Public,slug:str):return service.related(slug)
@router.get('/public/sermons/{slug}/media')
def public_assets(service:Public,slug:str):return service.detail(slug)['media']
@router.get('/public/sermons/{slug}/media/{asset_id}')
def public_media(request:Request,service:Public,slug:str,asset_id:UUID):
    row,asset=service.media_asset(slug,asset_id);return delivery(request,row,asset,media_storage(request))
def increment(db,sermon_id,event):
    table=SermonMetric.__table__;stmt=insert(table).values(sermon_id=sermon_id,event=event,count=1)
    db.execute(stmt.on_conflict_do_update(index_elements=[table.c.sermon_id,table.c.event],set_={'count':table.c.count+1}));db.commit()
@router.get('/public/sermons/{slug}/download/{media_type}')
def download(request:Request,service:Public,slug:str,media_type:Literal['audio','video','document','transcript','caption','thumbnail']):
    row,asset=service.media_asset(slug,kind=media_type.upper(),download=True)
    response=delivery(request,row,asset,media_storage(request),True)
    if media_type in {'audio','video'} and not request.headers.get('range'):increment(service.db,row.id,media_type.upper()+'_DOWNLOAD')
    return response
@router.post('/public/sermons/{slug}/playback',dependencies=[Depends(require_trusted_origin)])
def playback(request:Request,service:Public,slug:str,body:PlaybackWrite):
    row=service.record(slug);d=row.published_data['data']
    if body.event=='AUDIO_PLAY' and not (d.get('audio_asset_id') or d.get('audio_url')) or body.event=='VIDEO_PLAY' and not (d.get('video_asset_id') or d.get('youtube_url') or d.get('external_video_url')):raise ContentMissing('Playback source not found.')
    WebRateLimitService.consume(service.db,[('sermon-plays',request.client.host if request.client else 'unknown',60,60)])
    key=hashlib.sha256((str(row.id)+body.event+str(body.token)).encode()).hexdigest();table=SermonPlaybackReceipt.__table__
    service.db.execute(delete(table).where(table.c.expires_at<now()))
    accepted=service.db.execute(insert(table).values(token_hash=key,expires_at=now()+timedelta(days=1)).on_conflict_do_nothing().returning(table.c.token_hash)).scalar()
    if accepted:increment(service.db,row.id,body.event)
    else:service.db.commit()
    return {'recorded':bool(accepted)}
@router.get('/public/sermon-series',response_model=list[PublicSermonTaxonomy])
def series(service:Public):return service.taxonomy('series')
@router.get('/public/sermon-series/{slug}',response_model=PublicSermonTaxonomy)
def series_detail(service:Public,slug:str):return service.taxonomy('series',slug)
@router.get('/public/sermon-categories',response_model=list[PublicSermonTaxonomy])
def categories(service:Public):return service.taxonomy('categories')
@router.get('/public/sermon-speakers')
def speakers(service:Public):return service.filters()['speakers']
