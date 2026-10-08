"""Typed sermon metadata on the existing editorial content record."""
from datetime import date
from typing import Literal
from uuid import UUID
from pydantic import Field,AwareDatetime,StrictBool,model_validator,field_validator
from src.services.content_contracts import Contract,EditorialData,ContentWrite,safe_link,embed_video

class SermonWrite(Contract):
    title:str=Field(min_length=1,max_length=200)
    slug:str=Field(min_length=1,max_length=160,pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
    subtitle:str=Field(default='',max_length=300)
    description:str=Field(default='',max_length=50000)
    short_description:str=Field(default='',max_length=2000)
    sermon_date:date
    speaker_name:str=Field(min_length=1,max_length=200)
    speaker_member_id:UUID|None=None
    speaker_profile_slug:str=Field(default='',max_length=160,pattern=r'^(?:[a-z0-9]+(?:-[a-z0-9]+)*)?$')
    scripture_reference:str=Field(default='',max_length=300)
    series_id:UUID|None=None
    category_id:UUID|None=None
    ministry_id:UUID|None=None
    service_type:str=Field(default='',max_length=100)
    tags:list[str]=Field(default_factory=list,max_length=30)
    transcript:str=Field(default='',max_length=100000)
    thumbnail_media_id:UUID|None=None
    visibility:Literal['PUBLIC','PORTAL_ONLY','PRIVATE']='PRIVATE'
    featured:StrictBool=False
    video_source_type:Literal['NONE','UPLOADED','YOUTUBE','VIMEO','EXTERNAL']='NONE'
    external_video_url:str=Field(default='',max_length=1000)
    external_audio_url:str=Field(default='',max_length=1000)
    video_asset_id:UUID|None=None
    audio_asset_id:UUID|None=None
    thumbnail_asset_id:UUID|None=None
    caption_asset_id:UUID|None=None
    transcript_asset_id:UUID|None=None
    document_asset_id:UUID|None=None
    allow_audio_download:StrictBool=False
    allow_video_download:StrictBool=False
    seo_title:str=Field(default='',max_length=200)
    seo_description:str=Field(default='',max_length=320)
    expected_updated_at:AwareDatetime|None=None
    @field_validator('tags')
    @classmethod
    def tag_names(cls,values):
        result=list(dict.fromkeys(value.strip().lower() for value in values if value.strip()))
        if any(len(value)>50 for value in result):raise ValueError('Tags must be short.')
        return result
    @model_validator(mode='after')
    def metadata(self):
        if not self.title.strip() or not self.speaker_name.strip():raise ValueError('Enter a title and speaker.')
        if self.video_source_type in {'YOUTUBE','VIMEO'}:
            embed=embed_video(self.external_video_url)
            if self.video_source_type=='YOUTUBE' and 'youtube-nocookie.com' not in embed or self.video_source_type=='VIMEO' and 'player.vimeo.com' not in embed:raise ValueError('Choose the matching video provider.')
        elif self.video_source_type=='EXTERNAL':safe_link(self.external_video_url)
        elif self.external_video_url:raise ValueError('Choose an external source for this URL.')
        if self.external_audio_url:safe_link(self.external_audio_url)
        return self
    def editorial(self):
        values=self.model_dump(exclude={'title','slug','description','short_description','sermon_date','speaker_name','thumbnail_media_id','ministry_id','visibility','external_audio_url','expected_updated_at','seo_title','seo_description'})
        values.update(speaker=self.speaker_name,sermon_date=self.sermon_date,image_id=self.thumbnail_media_id,
            sermon_ministry_id=self.ministry_id,sermon_visibility=self.visibility,audio_url=self.external_audio_url,
            youtube_url=self.external_video_url if self.video_source_type in {'YOUTUBE','VIMEO'} else '')
        return ContentWrite(kind='SERMON',title=self.title,slug=self.slug,body=self.description,summary=self.short_description,
            seo_title=self.seo_title,seo_description=self.seo_description,data=EditorialData.model_validate(values),expected_updated_at=self.expected_updated_at)
class TaxonomyWrite(Contract):
    name:str=Field(min_length=1,max_length=200)
    slug:str=Field(min_length=1,max_length=160,pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
    description:str=Field(default='',max_length=10000)
    cover_image_id:UUID|None=None
    display_order:int=Field(default=0,ge=0,le=100000)
    expected_updated_at:AwareDatetime|None=None
class SermonAction(Contract):
    expected_updated_at:AwareDatetime
    scheduled_publish_at:AwareDatetime|None=None
class PlaybackWrite(Contract):
    event:Literal['VIDEO_PLAY','AUDIO_PLAY']
    token:UUID
    elapsed_seconds:int=Field(ge=10,le=604800)
class MediaDelete(Contract):
    expected_updated_at:AwareDatetime
    confirmed:Literal[True]

class AssetPermissions(Contract):
    expected_updated_at:AwareDatetime
    download_allowed:StrictBool
