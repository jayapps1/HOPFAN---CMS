"""Real playable fixture media, publication/privacy, streaming and download authority."""
from datetime import datetime,timedelta,timezone
from dataclasses import replace
from pathlib import Path
from uuid import uuid4
import subprocess,os,shutil,json
import pytest
from PIL import Image
from sqlalchemy import select,func
from src.models import ContentEntry
from src.models.sermon import SermonMediaAsset,SermonMetric
from src.services.sermon_storage import MediaStorageService,SermonStorageSettings
from src.services.sermon_service import SermonService
from src.services.content_base import ident
from tests.test_web_auth import security_database,credential_hash,environment,client,login,ORIGIN

@pytest.fixture
def media(environment):
    root=Path(__file__).resolve().parents[1]/'logs'/('sermon_test_'+uuid4().hex);root.mkdir(parents=True)
    environment.app.state.sermon_storage=MediaStorageService(SermonStorageSettings(root=root))
    video=root/'fixture.mp4';audio=root/'fixture.wav';image=root/'fixture.png'
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    for args in [['-f','lavfi','-i','color=c=navy:s=320x180:d=2','-f','lavfi','-i','sine=frequency=440:duration=2','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart','-shortest',str(video)],['-f','lavfi','-i','sine=frequency=440:duration=2','-c:a','pcm_s16le',str(audio)]]:
        subprocess.run(['ffmpeg','-v','error','-y',*args],capture_output=True,check=True,timeout=20,creationflags=flags)
    Image.new('RGB',(640,360),'#0b3151').save(image)
    environment.files={'VIDEO':video,'AUDIO':audio,'THUMBNAIL':image}
    try:yield environment
    finally:
        assert root.resolve().is_relative_to((Path(__file__).resolve().parents[1]/'logs').resolve());shutil.rmtree(root)

def auth(client,name='admin'):
    result=login(client,name);assert result.status_code==200,result.text
    return {'Origin':ORIGIN,'X-CSRF-Token':result.json()['csrf_token']}
def payload(**changes):
    values=dict(title='Synthetic sermon',slug='synthetic-sermon-'+uuid4().hex[:8],speaker_name='Synthetic speaker',sermon_date='2026-10-07',visibility='PUBLIC',description='Approved synthetic sermon description')
    values.update(changes);return values
def create(client,headers,**changes):
    result=client.post('/api/v1/sermons',json=payload(**changes),headers=headers);assert result.status_code==201,result.text;return result.json()
def upload(client,headers,row,kind,path,download=True):
    mime={'VIDEO':'video/mp4','AUDIO':'audio/wav','THUMBNAIL':'image/png'}[kind]
    result=client.post('/api/v1/sermons/'+row['id']+'/media',params={'media_type':kind,'filename':path.name,'rights_attested':'true','download_allowed':str(download).lower()},content=path.read_bytes(),headers=dict(headers,**{'Content-Type':mime}))
    assert result.status_code==202,result.text
    current=client.get('/api/v1/sermons/'+row['id']).json();assert current['assets'][-1]['processing_status']=='READY',current
    return current

def test_one_sermon_attaches_multiple_real_assets_and_public_range_download_rules(media,client):
    headers=auth(client);row=create(client,headers,allow_audio_download=True,allow_video_download=False)
    for kind,path in media.files.items():row=upload(client,headers,row,kind,path)
    with media.factory() as db:assert db.scalar(select(func.count()).select_from(ContentEntry).where(ContentEntry.kind=='SERMON'))==1
    assert 'scripture_reference' in row['metadata']
    assert len(row['assets'])==3 and client.get('/api/v1/public/sermons/'+row['slug']).status_code==404
    result=client.post('/api/v1/sermons/'+row['id']+'/actions/publish',headers=headers,json={'expected_updated_at':row['updated_at']})
    assert result.status_code==200,result.text
    public=client.get('/api/v1/public/sermons/'+row['slug']);assert public.status_code==200,public.text
    assert not any(word in public.text for word in ('storage_key','original_filename','uploaded_by','D:\\','secret_key'))
    video=next(asset for asset in public.json()['media'] if asset['media_type']=='VIDEO')
    partial=client.get(video['url'],headers={'Range':'bytes=0-99'});assert partial.status_code==206 and len(partial.content)==100
    assert partial.headers['accept-ranges']=='bytes' and partial.headers['content-range'].startswith('bytes 0-99/')
    assert client.get(video['url'],headers={'Range':'bytes=99999999-'}).status_code==416
    assert client.get('/api/v1/public/sermons/'+row['slug']+'/download/video').status_code==404
    audio=client.get('/api/v1/public/sermons/'+row['slug']+'/download/audio');assert audio.status_code==200
    assert 'attachment' in audio.headers['content-disposition'] and 'HOPFAN-' in audio.headers['content-disposition']
    assert len(audio.content)>100
    asset=next(item for item in row['assets'] if item['media_type']=='AUDIO')
    permission_path='/api/v1/sermons/'+row['id']+'/media/'+asset['id']+'/permissions'
    revoked=client.post(permission_path,headers=headers,json={'expected_updated_at':asset['updated_at'],'download_allowed':False});assert revoked.status_code==200,revoked.text
    assert client.get('/api/v1/public/sermons/'+row['slug']+'/download/audio').status_code==404
    assert client.post(permission_path,headers=headers,json={'expected_updated_at':asset['updated_at'],'download_allowed':True}).status_code==409
    assert client.post(permission_path,headers=headers,json={'expected_updated_at':revoked.json()['updated_at'],'download_allowed':True}).status_code==200
    assert client.get('/api/v1/public/sermons/'+row['slug']+'/download/audio').status_code==200
    assert client.post('/api/v1/sermons/'+row['id']+'/media/'+asset['id']+'/delete',headers=headers,json={'expected_updated_at':result.json()['updated_at'],'confirmed':True}).status_code==409
    result=client.post('/api/v1/sermons/'+row['id']+'/actions/archive',headers=headers,json={'expected_updated_at':result.json()['updated_at']});assert result.status_code==200
    assert client.get(video['url']).status_code==404 and client.get('/api/v1/public/sermons/'+row['slug']).status_code==404

@pytest.mark.parametrize('visibility',['PRIVATE','PORTAL_ONLY'])
def test_published_nonpublic_sermons_and_media_never_leak(media,client,visibility):
    headers=auth(client);row=create(client,headers,visibility=visibility,video_source_type='YOUTUBE',external_video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ')
    result=client.post('/api/v1/sermons/'+row['id']+'/actions/publish',headers=headers,json={'expected_updated_at':row['updated_at']});assert result.status_code==200,result.text
    assert client.get('/api/v1/public/sermons/'+row['slug']).status_code==404
    assert client.get('/api/v1/public/sermons').json()['total']==0
    assert client.get('/api/v1/public/site').json()['sermons']==[]

def test_metadata_edits_do_not_replace_published_snapshot_or_slug(media,client):
    headers=auth(client);row=create(client,headers,video_source_type='YOUTUBE',external_video_url='https://youtu.be/dQw4w9WgXcQ')
    published=client.post('/api/v1/sermons/'+row['id']+'/actions/publish',headers=headers,json={'expected_updated_at':row['updated_at']}).json()
    data=dict(published['metadata'],title='PRIVATE-DRAFT-TITLE',expected_updated_at=published['updated_at'])
    edited=client.patch('/api/v1/sermons/'+row['id'],headers=headers,json=data);assert edited.status_code==200,edited.text
    assert client.get('/api/v1/public/sermons/'+row['slug']).json()['title']=='Synthetic sermon'
    data['slug']='changed-public-slug';data['expected_updated_at']=edited.json()['updated_at']
    assert client.patch('/api/v1/sermons/'+row['id'],headers=headers,json=data).status_code==409
    assert client.get('/api/v1/public/sermons/'+row['slug']+'/download/video').status_code==404

def test_upload_permissions_inspection_and_limits(media,client):
    assert client.post('/api/v1/sermons',json=payload(),headers={'Origin':ORIGIN}).status_code==401
    headers=auth(client);row=create(client,headers)
    path='/api/v1/sermons/'+row['id']+'/media'
    bad=client.post(path,params={'media_type':'VIDEO','filename':'malicious.exe','rights_attested':'true'},content=b'MZ bad',headers=dict(headers,**{'Content-Type':'application/octet-stream'}));assert bad.status_code==400
    disguised=client.post(path,params={'media_type':'VIDEO','filename':'disguised.mp4','rights_attested':'true'},content=b'<script>evil</script>',headers=dict(headers,**{'Content-Type':'video/mp4'}));assert disguised.status_code==202
    current=client.get('/api/v1/sermons/'+row['id']).json();assert current['assets'][0]['processing_status']=='FAILED'
    assert client.post('/api/v1/sermons/'+row['id']+'/actions/publish',headers=headers,json={'expected_updated_at':current['updated_at']}).status_code==409
    media.app.state.sermon_storage=MediaStorageService(replace(media.app.state.sermon_storage.settings,video_limit=10))
    assert client.post(path,params={'media_type':'VIDEO','filename':'big.mp4','rights_attested':'true'},content=b'1'*11,headers=dict(headers,**{'Content-Type':'video/mp4'})).status_code==413
    officer=auth(client,'youth');assert client.post(path,params={'media_type':'VIDEO','filename':'video.mp4','rights_attested':'true'},content=b'123',headers=dict(officer,**{'Content-Type':'video/mp4'})).status_code==403
    with pytest.raises(Exception):media.app.state.sermon_storage.local_path('../../.env')

def test_schedule_publishes_only_when_due_and_analytics_count_playback_once(media,client):
    headers=auth(client);row=create(client,headers,video_source_type='YOUTUBE',external_video_url='https://youtu.be/dQw4w9WgXcQ')
    future=datetime.now(timezone.utc)+timedelta(hours=1)
    result=client.post('/api/v1/sermons/'+row['id']+'/actions/schedule',headers=headers,json={'expected_updated_at':row['updated_at'],'scheduled_publish_at':future.isoformat()});assert result.status_code==200,result.text
    assert client.get('/api/v1/public/sermons/'+row['slug']).status_code==404
    with media.factory() as db:
        assert SermonService.publish_due(db)==0
        entry=db.get(ContentEntry,ident(row['id']));saved=dict(entry.published_data);d=dict(saved['data']);d['scheduled_publish_at']=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat();entry.published_data=dict(saved,data=d);db.commit()
        assert SermonService.publish_due(db)==1 and SermonService.publish_due(db)==0
    body={'event':'VIDEO_PLAY','token':str(uuid4()),'elapsed_seconds':12}
    play=client.post('/api/v1/public/sermons/'+row['slug']+'/playback',headers={'Origin':ORIGIN},json=body);assert play.status_code==200 and play.json()['recorded'] is True
    assert client.post('/api/v1/public/sermons/'+row['slug']+'/playback',headers={'Origin':ORIGIN},json=body).json()['recorded'] is False
    assert client.get('/api/v1/public/sermons/'+row['slug']).json()['views']==1


def test_series_categories_search_and_ready_asset_deletion(media,client):
    headers=auth(client)
    series=client.post('/api/v1/sermon-series',headers=headers,json={'name':'Synthetic Prayer Series','slug':'synthetic-prayer','description':'Reviewed series'}).json()
    category=client.post('/api/v1/sermon-categories',headers=headers,json={'name':'Synthetic Faith','slug':'synthetic-faith'}).json()
    for kind,item in [('series',series),('categories',category)]:
        result=client.post('/api/v1/sermon-'+kind+'/'+item['id']+'/publish',headers=headers,json={'expected_updated_at':item['updated_at']});assert result.status_code==200,result.text
    rows=[]
    for index in range(3):
        row=create(client,headers,title='Synthetic message '+str(index),series_id=series['id'],category_id=category['id'],tags=['prayer'],scripture_reference='John 3:16',video_source_type='YOUTUBE',external_video_url='https://youtu.be/dQw4w9WgXcQ')
        if index<2:
            result=client.post('/api/v1/sermons/'+row['id']+'/actions/publish',headers=headers,json={'expected_updated_at':row['updated_at']});assert result.status_code==200,result.text
        rows.append(row)
    for query in ['search=Prayer','search=Faith','search=John','search=Synthetic','series=synthetic-prayer','category=synthetic-faith','media_type=VIDEO','year=2026']:
        response=client.get('/api/v1/public/sermons?'+query);assert response.status_code==200,response.text
        assert response.json()['total']==2
    assert client.get('/api/v1/public/sermon-series/synthetic-prayer').json()['sermon_count']==2
    assert len(client.get('/api/v1/public/sermons/'+rows[0]['slug']+'/related').json())==1
    draft=rows[2];draft=upload(client,headers,draft,'THUMBNAIL',media.files['THUMBNAIL'])
    asset=draft['assets'][0]
    result=client.post('/api/v1/sermons/'+draft['id']+'/media/'+asset['id']+'/delete',headers=headers,json={'confirmed':True,'expected_updated_at':draft['updated_at']})
    assert result.status_code==200,result.text
    assert not media.app.state.sermon_storage.local_path('sermons/'+draft['id']+'/'+asset['id']+'.jpg').exists()


def test_large_upload_crosses_json_limit_without_exposing_private_bytes(media,client):
    import wave
    path=media.files['AUDIO'].parent/'large.wav'
    with wave.open(str(path),'wb') as output:
        output.setnchannels(2);output.setsampwidth(2);output.setframerate(44100)
        for _ in range(90):output.writeframes(b'\x00'*176400)
    assert path.stat().st_size>12*1024**2
    headers=auth(client);row=create(client,headers);row=upload(client,headers,row,'AUDIO',path)
    assert row['assets'][0]['file_size']==path.stat().st_size and row['assets'][0]['duration_seconds']==90


def test_cms_analytics_permission_and_scoped_options(media,client):
    from src.models import Role,User
    headers=auth(client);row=create(client,headers)
    with media.factory() as db:
        db.add(SermonMetric(sermon_id=ident(row['id']),event='AUDIO_DOWNLOAD',count=7));db.commit()
    assert client.get('/api/v1/sermons/'+row['id']).json()['metrics']['AUDIO_DOWNLOAD']==7
    with media.factory() as db:
        role=db.scalar(select(Role).where(Role.code=='TEST_CHURCH_ADMIN'))
        role.permissions=[p for p in role.permissions if p.code not in {'SERMON_VIEW_ANALYTICS','MINISTRIES_VIEW_ALL','MINISTRIES_VIEW_OWN'}];db.commit()
    assert client.get('/api/v1/sermons/'+row['id']).json()['metrics']=={}
    assert client.get('/api/v1/sermons').json()['items'][0]['metrics']=={}
    options=client.get('/api/v1/sermons/options');assert options.status_code==200,options.text
    assert options.json()['ministries']==[]
    assert not any(key in options.text for key in ('storage_key','secret_key','D:\\'))


def test_interrupted_inspection_is_recoverable_without_publishing(media,client):
    from scripts.process_sermon_media import process_pending
    headers=auth(client);row=create(client,headers)
    storage=media.app.state.sermon_storage;aid=uuid4()
    storage.staging_path(aid).write_bytes(media.files['AUDIO'].read_bytes())
    with media.factory() as db:
        db.add(SermonMediaAsset(id=aid,sermon_id=ident(row['id']),media_type='AUDIO',storage_provider='LOCAL',storage_key=f'sermons/{row["id"]}/{aid}.wav',original_filename='interrupted.wav',mime_type='audio/wav',format='wav',rights_attested=True,processing_status='PROCESSING'))
        entry=db.get(ContentEntry,ident(row['id']));entry.status='PROCESSING';entry.draft_data=dict(entry.draft_data,data=dict(entry.draft_data['data'],audio_asset_id=str(aid)));db.commit()
    assert process_pending(media.factory,storage)==0
    assert process_pending(media.factory,storage,recover_interrupted=True)==1
    assert process_pending(media.factory,storage,recover_interrupted=True)==0
    current=client.get('/api/v1/sermons/'+row['id']).json()
    assert current['assets'][0]['processing_status']=='READY' and current['status']=='READY'
    assert client.get('/api/v1/public/sermons/'+row['slug']).status_code==404
