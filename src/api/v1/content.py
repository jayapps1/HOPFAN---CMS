"""Thin authenticated editorial/intake routes and separate public read contracts."""
from contextlib import contextmanager
from datetime import datetime
from typing import Annotated,Literal
from uuid import UUID
from fastapi import APIRouter,Depends,Query,Request,Response
from sqlalchemy.orm import Session
from src.api.dependencies import get_db,get_current_user
from src.api.security.csrf import require_trusted_origin
from src.api.schemas.workspace import Page,MinistrySummary
from src.api.schemas.content import *
from src.services.content_contracts import (ContentWrite,SettingsWrite,ActionRequest,EventWrite,AnnouncementWrite,IntakeWrite,InquiryUpdate,Conversion,MediaUpload,MediaReview)
from src.services.web_session_service import WebPrincipal
from src.services.web_security import WebSecurityError
from src.api.v1 import API_PREFIX

router=APIRouter(prefix=API_PREFIX,tags=['Publishing and public website'])
DB=Annotated[Session,Depends(get_db,scope='function')]
Principal=Annotated[WebPrincipal,Depends(get_current_user)]
Number=Annotated[int,Query(ge=1,le=100000)]
Size=Annotated[int,Query(ge=1,le=100)]
Search=Annotated[str,Query(max_length=200)]
Kind=Literal['PAGE','HOMEPAGE','MINISTRY','LEADERSHIP','SERMON','GALLERY','TESTIMONY']
@contextmanager
def safe_content_errors():
    from src.services.content_base import ContentError
    from src.services.authorization_service import AuthorizationDenied
    from src.services.operation_errors import OperationConflict,OperationNotFound
    from sqlalchemy.exc import IntegrityError,SQLAlchemyError
    from pydantic import ValidationError
    try:yield
    except AuthorizationDenied:raise WebSecurityError(403,'ACCESS_DENIED','Access to this resource is denied.') from None
    except OperationConflict:raise WebSecurityError(409,'OPERATION_CONFLICT','This record changed or already exists. Refresh and try again.') from None
    except OperationNotFound:raise WebSecurityError(404,'RESOURCE_NOT_FOUND','The requested resource was not found.') from None
    except ValidationError:raise WebSecurityError(422,'VALIDATION_ERROR','The request contains invalid data.') from None
    except ContentError as error:
        if isinstance(error.__cause__,IntegrityError):raise WebSecurityError(409,'OPERATION_CONFLICT','This record changed or already exists. Refresh and try again.') from None
        if isinstance(error.__cause__,SQLAlchemyError):raise WebSecurityError(503,'DATABASE_UNAVAILABLE','HOPFAN is temporarily unavailable.') from None
        raise WebSecurityError(400,'BUSINESS_RULE_VIOLATION','Check the fields and the publication state before retrying.') from None
class ContentFacade:
    def __init__(self,db,principal,storage=None):
        from src.services.publishing_service import PublishingService,CommunicationService
        from src.services.inquiry_service import InquiryService
        from src.services.website_media_service import WebsiteMediaService
        @contextmanager
        def borrowed():yield db
        self.publishing=PublishingService(principal.user.id,borrowed)
        self.communications=CommunicationService(principal.user.id,borrowed)
        self.inquiries=InquiryService(principal.user.id,borrowed)
        self.media=WebsiteMediaService(principal.user.id,borrowed,storage)
def content_dependency(request:Request,db:DB,principal:Principal):
    with safe_content_errors():yield ContentFacade(db,principal,getattr(request.app.state,'website_storage',None))
def public_dependency(request:Request,db:DB):
    from src.services.public_site_service import PublicSiteService
    with safe_content_errors():yield PublicSiteService(db,getattr(request.app.state,'website_storage',None))
Cms=Annotated[ContentFacade,Depends(content_dependency,scope='function')]
Public=Annotated[object,Depends(public_dependency,scope='function')]
def page(result,page,page_size):
    from src.services.online_workspace_service import OnlineWorkspaceService
    return OnlineWorkspaceService.page(result,page,page_size,lambda row:row)

@router.get('/website/overview')
def website_overview(service:Cms):return service.publishing.overview()
@router.get('/website/options')
def website_options(service:Cms):return service.publishing.options()
@router.get('/website/content',response_model=Page[ContentRecord])
def content_list(service:Cms,kind:Kind|None=None,search:Search='',status:Literal['ALL','DRAFT','PUBLISHED','ARCHIVED']='ALL',page_number:Number=1,page_size:Size=25):
    return page(service.publishing.list_content(kind,search,status,page_size,(page_number-1)*page_size),page_number,page_size)
@router.post('/website/content',response_model=ContentRecord,status_code=201)
def content_create(service:Cms,body:ContentWrite):return service.publishing.save_content(body.model_dump())
@router.get('/website/content/{entry_id}',response_model=ContentRecord)
def content_detail(service:Cms,entry_id:UUID):return service.publishing.get_content(entry_id)
@router.patch('/website/content/{entry_id}',response_model=ContentRecord)
def content_edit(service:Cms,entry_id:UUID,body:ContentWrite):return service.publishing.save_content(body.model_dump(),entry_id)
@router.post('/website/content/{entry_id}/{action}',response_model=ContentRecord)
def content_action(service:Cms,entry_id:UUID,action:Literal['publish','unpublish','archive'],body:ActionRequest):
    return service.publishing.content_action(entry_id,action,body.expected_updated_at)
@router.get('/website/settings',response_model=SettingsRecord)
def settings(service:Cms):return service.publishing.settings()
@router.patch('/website/settings',response_model=SettingsRecord)
def settings_edit(service:Cms,body:SettingsWrite):return service.publishing.save_settings(body.data.model_dump(),body.expected_updated_at)
@router.post('/website/settings/publish',response_model=SettingsRecord)
def settings_publish(service:Cms,body:ActionRequest):return service.publishing.publish_settings(body.expected_updated_at)
@router.get('/website/media',response_model=Page[MediaRecord])
def media_list(service:Cms,page_number:Number=1,page_size:Size=25):
    return page(service.media.list(page_size,(page_number-1)*page_size),page_number,page_size)
@router.post('/website/media',response_model=MediaRecord,status_code=201)
def media_upload(service:Cms,body:MediaUpload):return service.media.upload(body.model_dump())
@router.post('/website/media/{media_id}/approve',response_model=MediaRecord)
def media_review(service:Cms,media_id:UUID,body:MediaReview):return service.media.review(media_id,body.model_dump())
@router.get('/website/media/{media_id}/preview')
def media_preview(service:Cms,media_id:UUID,size:Literal['320','960','1920']='320'):return Response(service.media.preview(media_id,int(size)),media_type='image/jpeg')
@router.post('/website/media/{media_id}/archive',response_model=MediaRecord)
def media_archive(service:Cms,media_id:UUID,body:ActionRequest):return service.media.archive(media_id,body.expected_updated_at)

def communication_routes(kind,path,write_model,response_model):
    def options(service:Cms):return service.communications.options(kind)
    def listing(service:Cms,search:Search='',status:Literal['ALL','DRAFT','SUBMITTED','APPROVED','PUBLISHED','CANCELLED','ARCHIVED']='ALL',
        ministry_id:UUID|None=None,page_number:Number=1,page_size:Size=25):
        return page(service.communications.list(kind,search,status,ministry_id,page_size,(page_number-1)*page_size),page_number,page_size)
    def create(service:Cms,body:write_model):return service.communications.save(kind,body.model_dump())
    def detail(service:Cms,entity_id:UUID):return service.communications.get(kind,entity_id)
    def update(service:Cms,entity_id:UUID,body:write_model):return service.communications.save(kind,body.model_dump(),entity_id)
    def transition(service:Cms,entity_id:UUID,action:Literal['submit','approve','publish','unpublish','cancel','archive'],body:ActionRequest):
        return service.communications.action(kind,entity_id,action,body.expected_updated_at)
    router.add_api_route('/'+path+'/options',options,methods=['GET'],name=path+'_options')
    router.add_api_route('/'+path,listing,methods=['GET'],response_model=Page[response_model],name=path+'_list')
    router.add_api_route('/'+path,create,methods=['POST'],response_model=response_model,status_code=201,name=path+'_create')
    router.add_api_route('/'+path+'/{entity_id}',detail,methods=['GET'],response_model=response_model,name=path+'_detail')
    router.add_api_route('/'+path+'/{entity_id}',update,methods=['PATCH'],response_model=response_model,name=path+'_update')
    router.add_api_route('/'+path+'/{entity_id}/{action}',transition,methods=['POST'],response_model=response_model,name=path+'_transition')
communication_routes('EVENT','events',EventWrite,EventRecord)
communication_routes('ANNOUNCEMENT','announcements',AnnouncementWrite,AnnouncementRecord)

@router.get('/visitor-inquiries/assignees',response_model=list[MinistrySummary])
def assignees(service:Cms):return service.inquiries.assignees()
@router.get('/visitor-inquiries',response_model=Page[InquiryRecord])
def inquiries(service:Cms,kind:Literal['VISITOR','CONTACT','PRAYER']='VISITOR',search:Search='',status:Literal['ALL','NEW','CONTACTED','FOLLOW_UP','VISITED','CONVERTED','CLOSED']='ALL',page_number:Number=1,page_size:Size=25):
    return page(service.inquiries.list(kind,search,status,page_size,(page_number-1)*page_size),page_number,page_size)
@router.get('/visitor-inquiries/{inquiry_id}',response_model=InquiryRecord)
def inquiry(service:Cms,inquiry_id:UUID):return service.inquiries.get(inquiry_id)
@router.patch('/visitor-inquiries/{inquiry_id}',response_model=InquiryRecord)
def inquiry_update(service:Cms,inquiry_id:UUID,body:InquiryUpdate):return service.inquiries.update(inquiry_id,body.model_dump())
@router.get('/visitor-inquiries/{inquiry_id}/matches',response_model=list[Candidate])
def inquiry_matches(service:Cms,inquiry_id:UUID):return service.inquiries.candidates(inquiry_id)
@router.post('/visitor-inquiries/{inquiry_id}/convert',response_model=InquiryRecord)
def inquiry_convert(service:Cms,inquiry_id:UUID,body:Conversion):return service.inquiries.convert(inquiry_id,body.model_dump())

@router.get('/public/site',response_model=PublicSite)
def site(service:Public):return service.site()
def public_content_routes(kind,path,response_model):
    def listing(service:Public,search:Search='',series:Search='',speaker:Search='',page_number:Number=1,page_size:Size=25):
        return page(service.list_content(kind,search,series,speaker,page_size,(page_number-1)*page_size),page_number,page_size)
    def detail(service:Public,slug:str):return service.content(kind,slug)
    router.add_api_route('/public/'+path,listing,methods=['GET'],response_model=Page[response_model],name='public_'+path+'_list')
    router.add_api_route('/public/'+path+'/{slug}',detail,methods=['GET'],response_model=response_model,name='public_'+path+'_detail')
for kind,path,schema in [('PAGE','pages',PublicPage),('MINISTRY','ministries',PublicMinistry),('LEADERSHIP','leadership',PublicLeadership),
    ('GALLERY','gallery',PublicGallery),('TESTIMONY','testimonies',PublicPage)]:
    public_content_routes(kind,path,schema)
@router.get('/public/events',response_model=Page[PublicEvent])
def public_events(service:Public,past:bool=False,page_number:Number=1,page_size:Size=25):
    return page(service.events(past,page_size,(page_number-1)*page_size),page_number,page_size)
@router.get('/public/events/{slug}',response_model=PublicEvent)
def public_event(service:Public,slug:str):return service.event(slug)
@router.get('/public/announcements',response_model=Page[PublicAnnouncement])
def public_announcements(service:Public,page_number:Number=1,page_size:Size=25):
    return page(service.announcements(page_size,(page_number-1)*page_size),page_number,page_size)
@router.get('/public/media/{media_id}')
def public_media(service:Public,media_id:UUID,size:Literal['320','960','1920']='960'):return Response(service.media(media_id,int(size)),media_type='image/jpeg')
def intake_routes(path,kind):
    def intake(request:Request,db:DB,origin:Annotated[None,Depends(require_trusted_origin)],body:IntakeWrite):
        from src.services.inquiry_service import InquiryService
        with safe_content_errors():
            InquiryService.submit(db,kind,body.model_dump(),request.client.host if request.client else 'unknown')
        return IntakeAccepted()
    router.add_api_route('/public/'+path,intake,methods=['POST'],response_model=IntakeAccepted,status_code=202,name='public_'+path+'_submit')
intake_routes('visitor-inquiries','VISITOR')
intake_routes('contact','CONTACT')
intake_routes('prayer-requests','PRAYER')
