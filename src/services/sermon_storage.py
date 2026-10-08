"""Single storage boundary; local development and private S3-compatible delivery."""
from dataclasses import dataclass,field
from pathlib import Path
from urllib.parse import urlsplit
import os,re,shutil
from src.config.environment import load_environment
from src.services.content_base import ContentError

KEY=re.compile(r'^sermons/[a-f0-9-]{36}/[a-f0-9-]{36}\.(?:mp4|webm|mp3|m4a|wav|jpg|png|webp|vtt|txt|pdf)$')
@dataclass(frozen=True)
class SermonStorageSettings:
    provider:str='LOCAL'
    root:Path=field(default_factory=lambda:Path(__file__).resolve().parents[2]/'storage'/'dev'/'sermons')
    bucket:str=''
    endpoint:str=''
    region:str='us-east-1'
    access_key:str=field(default='',repr=False)
    secret_key:str=field(default='',repr=False)
    signed_seconds:int=300
    video_limit:int=2*1024**3
    audio_limit:int=200*1024**2
    thumbnail_limit:int=8*1024**2
    document_limit:int=20*1024**2
    text_limit:int=2*1024**2
    ffprobe:str='ffprobe'
    allowed_audio_hosts:tuple[str,...]=()
    allowed_video_hosts:tuple[str,...]=()
    @classmethod
    def from_environment(cls):
        load_environment();provider=os.getenv('SERMON_STORAGE_PROVIDER','LOCAL' if os.getenv('APP_ENV','development')=='development' else 'S3').upper()
        if provider not in {'LOCAL','S3'}:raise ContentError('Configure a supported sermon storage provider.')
        if provider=='LOCAL' and os.getenv('APP_ENV','development')!='development':raise ContentError('Configure private object storage for hosted production media.')
        endpoint=os.getenv('SERMON_S3_ENDPOINT','')
        if endpoint:
            url=urlsplit(endpoint)
            if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment:raise ContentError('Use an approved HTTPS storage endpoint.')
        values=dict(provider=provider,root=Path(os.getenv('SERMON_LOCAL_ROOT',str(cls().root))).resolve(),bucket=os.getenv('SERMON_S3_BUCKET',''),endpoint=endpoint,
            region=os.getenv('SERMON_S3_REGION','us-east-1'),access_key=os.getenv('SERMON_S3_ACCESS_KEY',''),secret_key=os.getenv('SERMON_S3_SECRET_KEY',''),
            signed_seconds=int(os.getenv('SERMON_SIGNED_URL_SECONDS','300')),ffprobe=os.getenv('SERMON_FFPROBE','ffprobe'),
            video_limit=int(os.getenv('SERMON_VIDEO_MAX_BYTES',str(2*1024**3))),audio_limit=int(os.getenv('SERMON_AUDIO_MAX_BYTES',str(200*1024**2))),
            thumbnail_limit=int(os.getenv('SERMON_THUMBNAIL_MAX_BYTES',str(8*1024**2))),document_limit=int(os.getenv('SERMON_DOCUMENT_MAX_BYTES',str(20*1024**2))),
            text_limit=int(os.getenv('SERMON_TEXT_MAX_BYTES',str(2*1024**2))),
            allowed_audio_hosts=tuple(host.strip().lower() for host in os.getenv('SERMON_ALLOWED_AUDIO_HOSTS','').split(',') if host.strip()),
            allowed_video_hosts=tuple(host.strip().lower() for host in os.getenv('SERMON_ALLOWED_VIDEO_HOSTS','').split(',') if host.strip()))
        if not 30<=values['signed_seconds']<=900 or any(not 1<=values[key]<=10*1024**3 for key in ('video_limit','audio_limit','thumbnail_limit','document_limit','text_limit')):raise ContentError('Media limits are outside supported ranges.')
        return cls(**values)
    def limit(self,kind):return {'VIDEO':self.video_limit,'AUDIO':self.audio_limit,'THUMBNAIL':self.thumbnail_limit,'DOCUMENT':self.document_limit,'CAPTION':self.text_limit,'TRANSCRIPT':self.text_limit}[kind]
class MediaStorageService:
    def __init__(self,settings=None):self.settings=settings or SermonStorageSettings.from_environment();self.root=self.settings.root.resolve()
    def key(self,key):
        if not KEY.fullmatch(key):raise ContentError('Invalid media reference.')
        return key
    def staging_path(self,asset_id):
        if not re.fullmatch(r'[a-f0-9-]{36}',str(asset_id)):raise ContentError('Invalid media reference.')
        target=(self.root/'.staging'/(str(asset_id)+'.part')).resolve()
        if not target.is_relative_to(self.root):raise ContentError('Invalid staging path.')
        target.parent.mkdir(parents=True,exist_ok=True);return target
    def local_path(self,key):
        target=(self.root/'objects'/self.key(key)).resolve()
        if not target.is_relative_to(self.root/'objects'):raise ContentError('Invalid media reference.')
        return target
    def client(self):
        import boto3
        from botocore.config import Config
        if not self.settings.bucket:raise ContentError('Configure the private sermon bucket.')
        return boto3.client('s3',endpoint_url=self.settings.endpoint or None,region_name=self.settings.region,
            aws_access_key_id=self.settings.access_key or None,aws_secret_access_key=self.settings.secret_key or None,
            config=Config(signature_version='s3v4',s3={'addressing_style':'path'},connect_timeout=10,read_timeout=30,retries={'max_attempts':3}))
    def upload(self,key,path,mime):
        self.key(key)
        if self.settings.provider=='LOCAL':
            target=self.local_path(key);target.parent.mkdir(parents=True,exist_ok=True)
            with path.open('rb') as source,target.open('xb') as output:shutil.copyfileobj(source,output,length=1024*1024)
        else:
            with path.open('rb') as source:self.client().upload_fileobj(source,self.settings.bucket,key,ExtraArgs={'ContentType':mime})
    def delete(self,key):
        self.key(key)
        if self.settings.provider=='LOCAL':self.local_path(key).unlink(missing_ok=True)
        else:self.client().delete_object(Bucket=self.settings.bucket,Key=key)
    def open_stream(self,key):
        self.key(key)
        return self.local_path(key).open('rb') if self.settings.provider=='LOCAL' else self.client().get_object(Bucket=self.settings.bucket,Key=key)['Body']
    def generate_signed_url(self,key,mime,filename,disposition='inline'):
        self.key(key)
        if self.settings.provider!='S3':return None
        return self.client().generate_presigned_url('get_object',Params={'Bucket':self.settings.bucket,'Key':key,'ResponseContentType':mime,
            'ResponseContentDisposition':disposition+'; filename="'+filename+'"'},ExpiresIn=self.settings.signed_seconds)
    def get_public_url(self,*args):
        # Private objects are delivered only after application authorization.
        return None
