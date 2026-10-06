"""Public projections are distinct from authenticated editorial contracts."""
from datetime import datetime,date
from typing import Literal
from pydantic import Field
from src.api.schemas.common import ApiResponse
from src.services.content_contracts import ContentWrite,SiteConfiguration

class ContentRecord(ApiResponse):
    id:str
    kind:str
    slug:str
    title:str
    status:str
    draft:dict
    ministry_id:str|None
    member_id:str|None
    updated_at:datetime
    published_at:datetime|None
    has_unpublished_changes:bool
class SettingsRecord(ApiResponse):
    data:SiteConfiguration
    updated_at:datetime|None
    published_at:datetime|None
class MediaRecord(ApiResponse):
    id:str
    alt_text:str
    caption:str
    status:str
    width:int
    height:int
    contains_children:bool
    consent_attested:bool
    consent_reference:str
    updated_at:datetime
    preview_url:str
class EventRecord(ApiResponse):
    id:str
    slug:str
    title:str
    description:str
    event_type:str
    scope:str
    ministry_id:str|None
    visibility:str
    start_datetime:datetime
    end_datetime:datetime|None
    location:str
    image_id:str|None
    status:str
    updated_at:datetime
    published_at:datetime|None
class AnnouncementRecord(ApiResponse):
    id:str
    slug:str
    title:str
    body:str
    scope:str
    ministry_id:str|None
    audience:str
    publish_from:datetime|None
    publish_until:datetime|None
    priority:int
    status:str
    updated_at:datetime
    published_at:datetime|None
class InquiryRecord(ApiResponse):
    id:str
    kind:str
    first_name:str
    last_name:str
    phone:str
    email:str
    message:str
    private_notes:str
    status:str
    contact_permission:bool
    preferred_contact:str
    visit_date:date|None
    assigned_to:str|None
    converted_member_id:str|None
    created_at:datetime
    updated_at:datetime
class Candidate(ApiResponse):
    id:str
    name:str
    member_no:str|None=None
class PublicImage(ApiResponse):
    url:str
    alt_text:str
    width:int
    height:int
    caption:str=''
class PublicPage(ApiResponse):
    slug:str
    title:str
    summary:str
    body:str
    seo_title:str
    seo_description:str
    image:PublicImage|None=None
class PublicMinistry(PublicPage):
    public_name:str
    meeting_information:str
    public_contact:str
class PublicLeadership(PublicPage):
    public_name:str
    public_title:str
class PublicSermon(PublicPage):
    speaker:str
    sermon_date:date
    scripture_reference:str
    series:str
    video_embed_url:str
    audio_url:str
class PublicGallery(PublicPage):
    images:list[PublicImage]
class PublicEvent(ApiResponse):
    slug:str
    title:str
    description:str
    start_datetime:datetime
    end_datetime:datetime|None
    location:str
    event_type:str
    image:PublicImage|None
class PublicAnnouncement(ApiResponse):
    slug:str
    title:str
    body:str
    publish_from:datetime|None
    publish_until:datetime|None
class PublicHero(ApiResponse):
    headline:str
    text:str
    primary_label:str
    primary_href:str
    secondary_label:str
    secondary_href:str
    image:PublicImage|None
class PublicSite(ApiResponse):
    configuration:SiteConfiguration
    hero:PublicHero
    section_order:list[str]
    welcome:PublicPage|None
    ministries:list[PublicMinistry]
    leadership:list[PublicLeadership]
    sermons:list[PublicSermon]
    galleries:list[PublicGallery]
    events:list[PublicEvent]
    announcements:list[PublicAnnouncement]
class IntakeAccepted(ApiResponse):
    status:Literal['received']='received'
