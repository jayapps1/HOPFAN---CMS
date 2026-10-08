"""Bounded media inspection jobs; never transcodes in an HTTP request."""
import json,math,subprocess,os,warnings
from PIL import Image,ImageOps
from sqlalchemy import select
from src.models import ContentEntry
from src.models.sermon import SermonMediaAsset
from src.services.content_base import ContentError,ident,now
from src.services.sermon_service import ASSET_FIELDS

EXTENSIONS={'VIDEO':{'mp4':'video/mp4','webm':'video/webm'},'AUDIO':{'mp3':'audio/mpeg','m4a':'audio/mp4','wav':'audio/wav'},
    'THUMBNAIL':{'jpg':'image/jpeg','jpeg':'image/jpeg','png':'image/png','webp':'image/webp'},'CAPTION':{'vtt':'text/vtt'},'TRANSCRIPT':{'txt':'text/plain'},'DOCUMENT':{'pdf':'application/pdf'}}

def inspect_file(path,asset,settings):
    with path.open('rb') as file:header=file.read(512)
    if asset.media_type in {'VIDEO','AUDIO'}:
        result=subprocess.run([settings.ffprobe,'-v','error','-protocol_whitelist','file','-format_whitelist','mov,mp3,wav,matroska,webm',
            '-show_entries','format=format_name,duration,bit_rate:stream=codec_type,codec_name,width,height','-of','json',str(path)],
            capture_output=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if result.returncode!=0 or len(result.stdout)>262144:raise ContentError('Media inspection failed. Use a browser-compatible MP4/WebM video or MP3/M4A/WAV audio file.')
        value=json.loads(result.stdout);info=value.get('format',{});streams=value.get('streams',[])
        duration=float(info.get('duration',0))
        if not math.isfinite(duration) or not 0<duration<=604800:raise ContentError('Use media with a valid duration of at most seven days.')
        wanted='video' if asset.media_type=='VIDEO' else 'audio'
        stream=next((item for item in streams if item.get('codec_type')==wanted),None)
        if not stream:raise ContentError('The uploaded file does not contain the selected media type.')
        allowed={'mp4':{'h264'},'webm':{'vp8','vp9','av1'},'mp3':{'mp3'},'m4a':{'aac'},'wav':{'pcm_s16le','pcm_s24le','pcm_s32le','pcm_f32le','pcm_u8'}}
        if stream.get('codec_name') not in allowed.get(asset.format,set()):raise ContentError('This codec needs conversion before browser playback. Upload a supported format.')
        container=info.get('format_name','')
        if asset.format in {'mp4','m4a'} and 'mov' not in container or asset.format in {'mp3','wav'} and asset.format not in container or asset.format=='webm' and 'matroska' not in container:raise ContentError('The media container does not match its file type.')
        if asset.media_type=='VIDEO':
            audio_codecs={'mp4':{'aac','mp3'},'webm':{'opus','vorbis'}}[asset.format]
            if any(item.get('codec_name') not in audio_codecs for item in streams if item.get('codec_type')=='audio'):raise ContentError('The video audio codec needs conversion before browser playback.')
        asset.duration_seconds=math.ceil(duration);asset.bitrate=int(info.get('bit_rate') or 0) or None
        asset.width=stream.get('width');asset.height=stream.get('height');asset.quality_label=str(asset.height)+'p' if asset.height else ''
    elif asset.media_type=='THUMBNAIL':
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(path) as image:
                image.load()
                if image.format not in {'JPEG','PNG','WEBP'}:raise ContentError('Use a JPEG, PNG or WebP thumbnail.')
                width=min(1280,image.width,int(image.height*16/9));height=max(1,round(width*9/16))
                image=ImageOps.fit(ImageOps.exif_transpose(image).convert('RGB'),(width,height))
                image.save(path,format='JPEG',quality=85,optimize=True)
                asset.width,asset.height=image.size
                asset.mime_type='image/jpeg';asset.format='jpg'
    elif asset.media_type in {'CAPTION','TRANSCRIPT'}:
        text=path.read_bytes().decode('utf-8-sig')
        if '\x00' in text or any(token in text.lower() for token in ('<script','<iframe','<!doctype','<html','javascript:')):raise ContentError('Upload safe UTF-8 caption or transcript text.')
        if asset.media_type=='CAPTION' and not text.startswith('WEBVTT'):raise ContentError('Use a valid WebVTT caption file.')
    elif asset.media_type=='DOCUMENT':
        if not header.startswith(b'%PDF-'):raise ContentError('Upload a PDF document.')
        with path.open('rb') as file:
            tail=b''
            while chunk:=file.read(65536):
                data=tail+chunk
                if any(token in data for token in (b'/JavaScript',b'/OpenAction',b'/Launch',b'/EmbeddedFile')):raise ContentError('Upload a PDF without active scripts or embedded programs.')
                tail=data[-64:]

class SermonProcessingService:
    @staticmethod
    def process(factory,storage,asset_id):
        path=storage.staging_path(asset_id)
        with factory() as db:
            asset=db.scalar(select(SermonMediaAsset).where(SermonMediaAsset.id==ident(asset_id)).with_for_update())
            if not asset or asset.processing_status not in {'QUEUED','FAILED'}:return
            retrying=asset.processing_status=='FAILED'
            asset.processing_status='PROCESSING';asset.error_summary='';db.commit()
            if retrying:
                try:storage.delete(asset.storage_key)
                except Exception:pass
            try:
                inspect_file(path,asset,storage.settings)
                # Thumbnail bytes are rewritten to compressed JPEG, under a generated key.
                if asset.media_type=='THUMBNAIL':asset.storage_key=asset.storage_key.rsplit('.',1)[0]+'.jpg'
                storage.upload(asset.storage_key,path,asset.mime_type)
                asset.file_size=path.stat().st_size;asset.processing_status='READY';asset.updated_at=now()
            except Exception as error:
                asset.processing_status='FAILED';asset.error_summary=str(error) if isinstance(error,ContentError) else 'Media inspection/storage failed. Check storage and ffprobe configuration, then retry.'
                asset.updated_at=now();row=db.get(ContentEntry,asset.sermon_id)
                if row and row.status=='PROCESSING':row.status='FAILED';row.updated_at=now()
                db.commit();return
            row=db.get(ContentEntry,asset.sermon_id)
            if row and row.status in {'DRAFT','PROCESSING','FAILED','READY'}:row.status='READY';row.updated_at=now()
            db.commit();path.unlink(missing_ok=True)
