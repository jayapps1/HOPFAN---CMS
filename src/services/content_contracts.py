"""Validated structured editorial data shared by API and services."""
import re
from datetime import date,time
from typing import Literal
from uuid import UUID
from urllib.parse import urlsplit,parse_qs
from pydantic import BaseModel,ConfigDict,Field,AwareDatetime,StrictBool,field_validator,model_validator

class Contract(BaseModel):model_config=ConfigDict(extra='forbid')
def safe_link(value):
    if not value:return ''
    if value.startswith('/') and not value.startswith('//') and not re.search(r'[\\\x00-\x20]',value):return value
    parsed=urlsplit(value)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or re.search(r'[\x00-\x20]',value):raise ValueError('Use an approved HTTPS URL or a local path.')
    return value
def embed_video(value):
    if not value:return ''
    safe_link(value);url=urlsplit(value);host=url.hostname.lower()
    if host in ('youtube.com','www.youtube.com','m.youtube.com'):code=parse_qs(url.query).get('v',[''])[0]
    elif host=='youtu.be':code=url.path.strip('/')
    elif host in ('vimeo.com','www.vimeo.com') and re.fullmatch(r'/[0-9]+',url.path):return 'https://player.vimeo.com/video/'+url.path.strip('/')
    else:raise ValueError('Use a YouTube or Vimeo video link.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}',code):raise ValueError('Use a valid video link.')
    return 'https://www.youtube-nocookie.com/embed/'+code

class GalleryImage(Contract):
    asset_id:UUID
    caption:str=Field(default='',max_length=1000)
    alt_text:str=Field(min_length=1,max_length=500)
HOME_SECTIONS=['services','events','welcome','ministries','leadership','sermons','sunday-school','announcements','gallery','donate','prayer','visit','contact']

class EditorialData(Contract):
    image_id:UUID|None=None
    public_name:str=Field(default='',max_length=200)
    public_title:str=Field(default='',max_length=200)
    meeting_information:str=Field(default='',max_length=2000)
    public_contact:str=Field(default='',max_length=500)
    speaker:str=Field(default='',max_length=200)
    sermon_date:date|None=None
    scripture_reference:str=Field(default='',max_length=300)
    series:str=Field(default='',max_length=200)
    youtube_url:str=Field(default='',max_length=1000)
    audio_url:str=Field(default='',max_length=1000)
    images:list[GalleryImage]=Field(default_factory=list,max_length=100)
    subtitle:str=Field(default='',max_length=300)
    speaker_member_id:UUID|None=None
    speaker_profile_slug:str=Field(default='',max_length=160)
    series_id:UUID|None=None
    category_id:UUID|None=None
    sermon_ministry_id:UUID|None=None
    service_type:str=Field(default='',max_length=100)
    duration_seconds:int|None=Field(default=None,ge=0,le=604800)
    sermon_visibility:Literal['PUBLIC','PORTAL_ONLY','PRIVATE']='PUBLIC'
    featured:StrictBool=False
    video_source_type:Literal['NONE','UPLOADED','YOUTUBE','VIMEO','EXTERNAL']='NONE'
    video_asset_id:UUID|None=None
    audio_asset_id:UUID|None=None
    thumbnail_asset_id:UUID|None=None
    caption_asset_id:UUID|None=None
    transcript_asset_id:UUID|None=None
    document_asset_id:UUID|None=None
    external_video_url:str=Field(default='',max_length=1000)
    allow_audio_download:StrictBool=False
    allow_video_download:StrictBool=False
    tags:list[str]=Field(default_factory=list,max_length=30)
    transcript:str=Field(default='',max_length=100000)
    scheduled_publish_at:AwareDatetime|None=None
    display_order:int=Field(default=0,ge=0,le=100000)
    hero_headline:str=Field(default='',max_length=200)
    hero_text:str=Field(default='',max_length=1000)
    primary_label:str=Field(default='Plan your visit',max_length=100)
    primary_href:str=Field(default='/new-here',max_length=1000)
    secondary_label:str=Field(default='Explore ministries',max_length=100)
    secondary_href:str=Field(default='/ministries',max_length=1000)
    section_order:list[Literal['welcome','services','events','sermons','ministries','leadership','sunday-school','announcements','gallery','donate','prayer','visit','contact']]=Field(default_factory=lambda:list(HOME_SECTIONS),max_length=13)
    events_count:int=Field(default=6,ge=1,le=8)
    ministries_count:int=Field(default=3,ge=1,le=4)
    announcements_count:int=Field(default=3,ge=1,le=3)
    gallery_count:int=Field(default=5,ge=1,le=5)
    featured_slugs:list[str]=Field(default_factory=list,max_length=20)
    consent_reference:str=Field(default='',max_length=300)
    @field_validator('youtube_url')
    @classmethod
    def video(cls,value):embed_video(value);return value
    @field_validator('audio_url','primary_href','secondary_href')
    @classmethod
    def links(cls,value):return safe_link(value)
class ContentWrite(Contract):
    kind:Literal['PAGE','HOMEPAGE','MINISTRY','LEADERSHIP','SERMON','GALLERY','TESTIMONY']
    slug:str=Field(min_length=1,max_length=160,pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
    title:str=Field(min_length=1,max_length=200)
    summary:str=Field(default='',max_length=2000)
    body:str=Field(default='',max_length=50000)
    seo_title:str=Field(default='',max_length=200)
    seo_description:str=Field(default='',max_length=320)
    data:EditorialData=Field(default_factory=EditorialData)
    ministry_id:UUID|None=None
    member_id:UUID|None=None
    expected_updated_at:AwareDatetime|None=None
    @model_validator(mode='after')
    def kind_rules(self):
        if not self.title.strip():raise ValueError('Enter a title.')
        if self.kind=='HOMEPAGE' and self.slug!='home':raise ValueError('The homepage uses the home slug.')
        if self.kind=='MINISTRY' and not self.ministry_id:raise ValueError('Link an existing ministry explicitly.')
        if self.kind!='MINISTRY' and self.ministry_id:raise ValueError('Only ministry profiles link an internal ministry.')
        if self.kind!='LEADERSHIP' and self.member_id:raise ValueError('Only approved leadership profiles may link a member.')
        if self.kind=='SERMON' and (not self.data.speaker or not self.data.sermon_date):raise ValueError('Sermons need a speaker and date.')
        return self
class ServiceTime(Contract):
    id:UUID|None=None
    name:str=Field(min_length=1,max_length=100)
    schedule:str=Field(default='',max_length=300)
    day_of_week:Literal['MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY','SUNDAY']|None=None
    start_time:time|None=None
    end_time:time|None=None
    description:str=Field(default='',max_length=1000)
    location:str=Field(default='',max_length=500)
    display_order:int=Field(default=0,ge=0,le=100000)
    active:StrictBool=True
    featured:StrictBool=True
    created_at:AwareDatetime|None=None
    updated_at:AwareDatetime|None=None
    @model_validator(mode='after')
    def times(self):
        if not self.name.strip():raise ValueError('Enter a service name.')
        if any(value is not None for value in (self.day_of_week,self.start_time,self.end_time)):
            if not all(value is not None for value in (self.day_of_week,self.start_time,self.end_time)):raise ValueError('Choose a weekday, start and end time.')
            if self.start_time.tzinfo or self.end_time.tzinfo or self.end_time<=self.start_time:raise ValueError('End time must follow start time, using local church time.')
            def clock(value):return f'{value.hour%12 or 12}:{value.minute:02d} '+('AM' if value.hour<12 else 'PM')
            self.schedule=self.day_of_week.title()+' '+clock(self.start_time)+' \u2013 '+clock(self.end_time)
        elif not self.schedule.strip():raise ValueError('Configure structured times or retain a valid legacy schedule.')
        return self
class SocialLink(Contract):
    label:str=Field(min_length=1,max_length=100)
    url:str=Field(max_length=1000)
    _url=field_validator('url')(safe_link)
class SiteConfiguration(Contract):
    church_name:str=Field(default='HOPFAN',min_length=1,max_length=200)
    full_name:str=Field(default='House of Prayer for All Nations',max_length=300)
    tagline:str=Field(default='',max_length=500)
    address:str=Field(default='',max_length=1000)
    public_phone:str=Field(default='',max_length=100)
    public_email:str=Field(default='',max_length=254)
    timezone:str=Field(default='UTC',max_length=100)
    service_times:list[ServiceTime]=Field(default_factory=list,max_length=20)
    social_links:list[SocialLink]=Field(default_factory=list,max_length=10)
    map_url:str=Field(default='',max_length=1000)
    footer_text:str=Field(default='',max_length=1000)
    contact_form_enabled:StrictBool=True
    visitor_form_enabled:StrictBool=True
    prayer_form_enabled:StrictBool=True
    _url=field_validator('map_url')(safe_link)
    @field_validator('timezone')
    @classmethod
    def church_timezone(cls,value):
        from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
        try:ZoneInfo(value)
        except (ValueError,ZoneInfoNotFoundError):raise ValueError('Choose a valid IANA church timezone.') from None
        return value
    @model_validator(mode='after')
    def service_ids(self):
        ids=[service.id for service in self.service_times if service.id]
        if len(ids)!=len(set(ids)):raise ValueError('Service IDs must be unique.')
        return self
class SettingsWrite(Contract):
    data:SiteConfiguration
    expected_updated_at:AwareDatetime|None=None
class ActionRequest(Contract):
    expected_updated_at:AwareDatetime
class ScopedWrite(Contract):
    slug:str=Field(min_length=1,max_length=160,pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
    title:str=Field(min_length=1,max_length=200)
    scope:Literal['CHURCH_WIDE','MINISTRY']='CHURCH_WIDE'
    ministry_id:UUID|None=None
    expected_updated_at:AwareDatetime|None=None
    @model_validator(mode='after')
    def scope_rules(self):
        if not self.title.strip() or (self.scope=='MINISTRY')!=bool(self.ministry_id):raise ValueError('Choose a valid scope and title.')
        return self
class EventWrite(ScopedWrite):
    description:str=Field(default='',max_length=30000)
    event_type:Literal['SERVICE','CONFERENCE','MEETING','OUTREACH','OTHER']='OTHER'
    visibility:Literal['INTERNAL','PUBLIC','BOTH']='INTERNAL'
    start_datetime:AwareDatetime
    end_datetime:AwareDatetime|None=None
    location:str=Field(default='',max_length=500)
    image_id:UUID|None=None
    @model_validator(mode='after')
    def dates(self):
        if self.end_datetime and self.end_datetime<self.start_datetime:raise ValueError('Invalid event dates.')
        return self
class AnnouncementWrite(ScopedWrite):
    body:str=Field(default='',max_length=30000)
    audience:Literal['INTERNAL','PUBLIC','BOTH']='INTERNAL'
    publish_from:AwareDatetime|None=None
    publish_until:AwareDatetime|None=None
    priority:int=Field(default=0,ge=0,le=100)
    @model_validator(mode='after')
    def dates(self):
        if self.publish_from and self.publish_until and self.publish_until<self.publish_from:raise ValueError('Invalid publication period.')
        return self
class IntakeWrite(Contract):
    first_name:str=Field(default='',max_length=100)
    last_name:str=Field(default='',max_length=100)
    email:str=Field(default='',max_length=254)
    phone:str=Field(default='',max_length=40)
    message:str=Field(default='',max_length=10000)
    contact_permission:StrictBool=False
    preferred_contact:Literal['NONE','EMAIL','PHONE']='NONE'
    privacy:Literal['PRIVATE','PASTORAL_ONLY']='PRIVATE'
    visit_date:date|None=None
    website:str=Field(default='',max_length=200)
    @field_validator('email')
    @classmethod
    def email_format(cls,value):
        value=value.strip().lower()
        if value and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise ValueError('Enter a valid email.')
        return value
class InquiryUpdate(Contract):
    status:Literal['NEW','CONTACTED','FOLLOW_UP','VISITED','CLOSED']
    private_notes:str=Field(default='',max_length=10000)
    assigned_to:UUID|None=None
    expected_updated_at:AwareDatetime
class Conversion(Contract):
    existing_member_id:UUID|None=None
    confirm:StrictBool
    expected_updated_at:AwareDatetime
class MediaUpload(Contract):
    image_base64:str=Field(min_length=4,max_length=11_200_000)
    alt_text:str=Field(default='',max_length=500)
    caption:str=Field(default='',max_length=1000)
    contains_children:StrictBool=False
class MediaReview(Contract):
    alt_text:str=Field(min_length=1,max_length=500)
    caption:str=Field(default='',max_length=1000)
    contains_children:StrictBool=False
    consent_attested:StrictBool
    consent_reference:str=Field(default='',max_length=300)
    expected_updated_at:AwareDatetime
    @model_validator(mode='after')
    def consent(self):
        if not self.consent_attested or not self.alt_text.strip():raise ValueError('Public approval and alt text are required.')
        if self.contains_children and not self.consent_reference.strip():raise ValueError('Record the approved child-image consent reference.')
        return self
