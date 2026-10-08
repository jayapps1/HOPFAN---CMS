"""Published Home composition, structured services and safe schedule migration."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from importlib import import_module
from uuid import uuid4
from unittest.mock import patch
import pytest
from sqlalchemy import select,text
from alembic import command
from alembic.config import Config
from src.models import WebsiteSettings,ContentEntry,Event
from src.services.content_contracts import SiteConfiguration,ServiceTime,ContentWrite
from src.services.public_site_service import PublicSiteService
from src.config.database import engine
from tests.test_web_auth import security_database,credential_hash,environment,client,login,ORIGIN

@pytest.mark.parametrize('changes',[{'end_time':'06:00'},{'end_time':None},{'start_time':'07:00Z'},{'day_of_week':None}])
def test_structured_service_rejects_invalid_times(changes):
    values=dict(name='Sunday Service',day_of_week='SUNDAY',start_time='07:00',end_time='10:00')
    values.update(changes)
    with pytest.raises(ValueError):ServiceTime.model_validate(values)

def test_legacy_service_and_timezone_validation():
    assert ServiceTime(name='Legacy service',schedule='Existing reviewed schedule').schedule=='Existing reviewed schedule'
    assert ServiceTime(name='Sunday Service',day_of_week='SUNDAY',start_time='07:00',end_time='10:00').schedule=='Sunday 7:00 AM \u2013 10:00 AM'
    with pytest.raises(ValueError):SiteConfiguration(timezone='Invalid/Timezone')

@pytest.mark.parametrize('kind,count',[('events_count',9),('announcements_count',4),('ministries_count',5),('gallery_count',6)])
def test_home_preview_counts_are_bounded(kind,count):
    with pytest.raises(ValueError):ContentWrite.model_validate(dict(kind='HOMEPAGE',slug='home',title='Home',data={kind:count}))

def auth(client,name='admin'):
    response=login(client,name);assert response.status_code==200,response.text
    return {'Origin':ORIGIN,'X-CSRF-Token':response.json()['csrf_token']}

def test_service_edits_are_versioned_private_until_publish_and_require_permission(environment,client):
    headers=auth(client)
    initial=client.get('/api/v1/website/settings').json()
    data=initial['data'];data['timezone']='Africa/Accra';data['service_times']=[dict(id=str(uuid4()),name='Reviewed Sunday',day_of_week='SUNDAY',start_time='07:00',end_time='10:00',description='Approved service description',location='Approved public location',display_order=2,active=True,featured=True)]
    response=client.patch('/api/v1/website/settings',headers=headers,json={'data':data,'expected_updated_at':initial['updated_at']})
    assert response.status_code==200,response.text
    draft=response.json();assert client.get('/api/v1/public/site').json()['configuration']['service_times']==[]
    assert client.post('/api/v1/website/settings/publish',headers=headers,json={'expected_updated_at':draft['updated_at']}).status_code==200
    published=client.get('/api/v1/public/site').json()['configuration'];assert published['timezone']=='Africa/Accra'
    assert published['service_times'][0]['start_time']=='07:00:00'
    current=client.get('/api/v1/website/settings').json();created=current['data']['service_times'][0]['created_at']
    current['data']['service_times'][0]['start_time']='08:00'
    edited=client.patch('/api/v1/website/settings',headers=headers,json={'data':current['data'],'expected_updated_at':current['updated_at']})
    assert edited.status_code==200 and edited.json()['data']['service_times'][0]['created_at']==created
    assert client.get('/api/v1/public/site').json()['configuration']['service_times'][0]['start_time']=='07:00:00'
    assert client.patch('/api/v1/website/settings',headers=headers,json={'data':current['data'],'expected_updated_at':current['updated_at']}).status_code==409
    officer=auth(client,'youth')
    assert client.patch('/api/v1/website/settings',headers=officer,json={'data':data,'expected_updated_at':edited.json()['updated_at']}).status_code==403

def test_active_services_are_ordered_and_inactive_services_never_public(environment):
    with environment.factory() as db:
        values=SiteConfiguration(service_times=[dict(name='Later',schedule='Reviewed later',display_order=4),dict(name='Inactive',schedule='Reviewed inactive',active=False),dict(name='First',schedule='Reviewed first',display_order=0)])
        db.add(WebsiteSettings(id=1,draft_data=values.model_dump(mode='json'),published_data=values.model_dump(mode='json')));db.commit()
        assert [item['name'] for item in PublicSiteService(db).site()['configuration']['service_times']]==['First','Later']

def test_home_events_only_published_public_future_and_bounded(environment):
    with environment.factory() as db:
        home=ContentWrite(kind='HOMEPAGE',slug='home',title='Home',data={'events_count':2,'announcements_count':2,'gallery_count':3}).model_dump(mode='json')
        db.add(ContentEntry(kind='HOMEPAGE',slug='home',title='Home',status='PUBLISHED',draft_data=home,published_data=home,published_at=datetime.now(timezone.utc)))
        for index in reversed(range(5)):
            db.add(Event(slug='upcoming-'+str(index),title='Reviewed upcoming '+str(index),scope='CHURCH_WIDE',visibility='PUBLIC',status='PUBLISHED',start_datetime=datetime.now(timezone.utc)+timedelta(days=index+1)))
        for slug,status,visibility,delta in [('draft','DRAFT','PUBLIC',5),('internal','PUBLISHED','INTERNAL',5),('archived','ARCHIVED','PUBLIC',5),('past','PUBLISHED','PUBLIC',-5)]:
            db.add(Event(slug=slug,title='Private filtered '+slug,scope='CHURCH_WIDE',visibility=visibility,status=status,start_datetime=datetime.now(timezone.utc)+timedelta(days=delta)))
        db.commit();service=PublicSiteService(db);result=service.site()
        assert [item['slug'] for item in result['events']]==['upcoming-0','upcoming-1']
        assert result['gallery_count']==3 and result['events_available'] is True
        row=db.scalar(select(Event).where(Event.slug=='upcoming-0'));row.status='DRAFT';db.commit()
        assert [item['slug'] for item in service.site()['events']]==['upcoming-1','upcoming-2']
        with patch.object(service,'events',side_effect=RuntimeError('private failure')):
            fallback=service.site();assert fallback['events']==[] and fallback['events_available'] is False
            assert fallback['hero']['headline'] and 'private failure' not in str(fallback)

@pytest.mark.parametrize('existing', [False,True])
def test_schedule_migration_seeds_once_preserves_existing_edits_and_private_drafts(existing):
    schema='hcms_home_migration_'+uuid4().hex
    with engine.connect() as connection:
        transaction=connection.begin()
        try:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'));connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config=Config('alembic.ini');config.attributes['connection']=connection
            command.upgrade(config,'f8a62e931d04')
            if existing:
                connection.execute(text("INSERT INTO website_settings(id,draft_data,published_data) VALUES (1,cast(:draft AS jsonb),cast(:published AS jsonb))"),{'draft':'{"service_times":[{"name":"Admin edited","schedule":"Do not overwrite"}]}','published':'{"service_times":[{"name":"Admin edited","schedule":"Do not overwrite"}]}'})
            else:
                connection.execute(text("INSERT INTO website_settings(id,draft_data) VALUES (1,cast(:draft AS jsonb))"),{'draft':'{"public_email":"PRIVATE-DRAFT@example.invalid","service_times":[]}'})
            command.upgrade(config,'head')
            row=connection.execute(text('SELECT draft_data,published_data FROM website_settings WHERE id=1')).one()
            if existing:assert row.published_data['service_times']==[{'name':'Admin edited','schedule':'Do not overwrite'}]
            else:
                assert len(row.published_data['service_times'])==3
                assert [item['start_time'] for item in row.published_data['service_times']]==['07:00','09:00','18:30']
                assert 'PRIVATE-DRAFT' not in str(row.published_data)
                assert row.draft_data['public_email']=='PRIVATE-DRAFT@example.invalid'
            before=deepcopy(row.published_data);command.upgrade(config,'head')
            assert connection.scalar(text('SELECT published_data FROM website_settings WHERE id=1'))==before
            command.check(config)
        finally:transaction.rollback()


def test_home_gallery_and_text_previews_are_bounded_without_truncating_detail(environment):
    from src.models import WebsiteMedia,ContentMediaLink
    with environment.factory() as db:
        assets=[WebsiteMedia(storage_key=uuid4().hex,alt_text='Approved synthetic image '+str(index),caption='',width=1200,height=800,status='PUBLISHED',consent_attested=True,contains_children=False) for index in range(10)]
        db.add_all(assets);db.flush()
        home=ContentWrite(kind='HOMEPAGE',slug='home',title='Home',data={'gallery_count':3}).model_dump(mode='json')
        gallery=ContentWrite(kind='GALLERY',slug='preview-album',title='Synthetic album',data={'images':[{'asset_id':str(asset.id),'alt_text':asset.alt_text} for asset in assets]}).model_dump(mode='json')
        about=ContentWrite(kind='PAGE',slug='about',title='About',body='A'*5000).model_dump(mode='json')
        entries=[]
        for kind,slug,title,snapshot in [('HOMEPAGE','home','Home',home),('GALLERY','preview-album','Synthetic album',gallery),('PAGE','about','About',about)]:
            entry=ContentEntry(kind=kind,slug=slug,title=title,draft_data=snapshot,published_data=snapshot,status='PUBLISHED',published_at=datetime.now(timezone.utc));db.add(entry);entries.append(entry)
        db.flush()
        db.add_all(ContentMediaLink(content_id=entries[1].id,media_id=asset.id) for asset in assets);db.commit()
        service=PublicSiteService(db);site=service.site()
        assert len(site['galleries'][0]['images'])==3
        assert len(service.content('GALLERY','preview-album')['images'])==10
        assert len(site['welcome']['body'])==1400
        assert len(service.content('PAGE','about')['body'])==5000
