"""Publication, private intake, consent, scope and conversion in private PostgreSQL."""
from datetime import datetime,timedelta,timezone
import base64,io,shutil
from pathlib import Path
from uuid import uuid4
import pytest
from PIL import Image
from sqlalchemy import select,func
from src.models import Role,Permission,Member,ContentEntry,Event,Announcement,PublicInquiry,WebsiteMedia,ContentAudit
from src.services.website_media_service import LocalWebsiteStorage
from tests.test_web_auth import security_database,credential_hash,environment,client,login,ORIGIN

@pytest.fixture
def publishing(environment):
    media_dir=Path(__file__).resolve().parents[1]/'logs'/('content_test_assets_'+uuid4().hex)
    media_dir.mkdir(parents=True)
    assert media_dir.resolve().is_relative_to((Path(__file__).resolve().parents[1]/'logs').resolve())
    environment.app.state.website_storage=LocalWebsiteStorage(media_dir)
    with environment.factory() as db:
        role=db.scalar(select(Role).where(Role.code=='TEST_MINISTRY_OFFICER'))
        for kind in ('EVENT','ANNOUNCEMENT'):
            for suffix in ('VIEW_OWN_MINISTRY','CREATE_OWN_MINISTRY','EDIT_OWN_MINISTRY','SUBMIT'):
                role.permissions.append(db.scalar(select(Permission).where(Permission.code==kind+'_'+suffix)))
        db.commit()
    try:yield environment
    finally:
        assert media_dir.resolve().is_relative_to((Path(__file__).resolve().parents[1]/'logs').resolve())
        shutil.rmtree(media_dir)

def auth(client,name='admin'):
    response=login(client,name);assert response.status_code==200,response.text
    return {'Origin':ORIGIN,'X-CSRF-Token':response.json()['csrf_token']}
def page_data(kind='PAGE',slug='about',**changes):
    return dict(kind=kind,slug=slug,title='Synthetic content',summary='Safe public summary',body='Plain editorial text',data={},**changes)
def create(client,headers,data):
    response=client.post('/api/v1/website/content',headers=headers,json=data)
    assert response.status_code==201,response.text
    return response.json()
def publish(client,headers,row):
    response=client.post('/api/v1/website/content/'+row['id']+'/publish',headers=headers,json={'expected_updated_at':row['updated_at']})
    assert response.status_code==200,response.text
    return response.json()

def test_public_drafts_snapshots_unpublish_and_slug_stability(publishing,client):
    h=auth(client);row=create(client,h,page_data())
    assert client.get('/api/v1/public/pages/about').status_code==404
    row=publish(client,h,row)
    assert client.get('/api/v1/public/pages/about').json()['title']=='Synthetic content'
    data=page_data();data['title']='Unpublished edit';data['expected_updated_at']=row['updated_at']
    changed=client.patch('/api/v1/website/content/'+row['id'],headers=h,json=data)
    assert changed.status_code==200,changed.text
    assert client.get('/api/v1/public/pages/about').json()['title']=='Synthetic content'
    row=publish(client,h,changed.json())
    assert client.get('/api/v1/public/pages/about').json()['title']=='Unpublished edit'
    data.update(slug='changed-url',expected_updated_at=row['updated_at'])
    assert client.patch('/api/v1/website/content/'+row['id'],headers=h,json=data).status_code==409
    response=client.post('/api/v1/website/content/'+row['id']+'/unpublish',headers=h,json={'expected_updated_at':row['updated_at']})
    assert response.status_code==200
    assert client.get('/api/v1/public/pages/about').status_code==404

def test_public_ministry_and_leadership_never_project_private_fields(publishing,client):
    h=auth(client)
    for kind,slug,target in [('MINISTRY','youth','ministries'),('LEADERSHIP','public-leader','leadership')]:
        data=page_data(kind,slug)
        if kind=='MINISTRY':data['ministry_id']=str(publishing.ministries['Youth'].id)
        else:data['member_id']=str(publishing.member.id)
        row=publish(client,h,create(client,h,data))
        response=client.get('/api/v1/public/'+target+'/'+slug)
        assert response.status_code==200,response.text
        for name in ('member_id','member_no','ministry_id','permissions','roles','scope','household','attendance','photo_path'):
            assert name not in response.text
    assert client.get('/api/v1/public/site').status_code==200
    assert client.get('/api/v1/public/students').status_code==404
    assert client.get('/api/v1/public/members').status_code==404
    client.cookies.clear()
    assert client.get('/api/v1/members').status_code==401
    assert client.get('/api/v1/public/ministries').status_code==200

def test_scoped_event_approval_publication_and_idor(publishing,client):
    h=auth(client,'youth')
    data=dict(slug='youth-event',title='Youth event',scope='MINISTRY',ministry_id=str(publishing.ministries['Youth'].id),
        visibility='PUBLIC',start_datetime=(datetime.now(timezone.utc)+timedelta(days=3)).isoformat())
    response=client.post('/api/v1/events',headers=h,json=data)
    assert response.status_code==201,response.text
    row=response.json();url='/api/v1/events/'+row['id']
    assert client.get('/api/v1/public/events/youth-event').status_code==404
    assert client.post(url+'/publish',headers=h,json={'expected_updated_at':row['updated_at']}).status_code==403
    submitted=client.post(url+'/submit',headers=h,json={'expected_updated_at':row['updated_at']}).json()
    auth(client,'women');assert client.get(url).status_code==403
    h=auth(client)
    approved=client.post(url+'/approve',headers=h,json={'expected_updated_at':submitted['updated_at']})
    assert approved.status_code==200,approved.text
    published=client.post(url+'/publish',headers=h,json={'expected_updated_at':approved.json()['updated_at']})
    assert published.status_code==200,published.text
    public=client.get('/api/v1/public/events/youth-event')
    assert public.status_code==200 and 'ministry_id' not in public.text
    assert client.patch(url,headers=h,json=dict(data,expected_updated_at=published.json()['updated_at'])).status_code==409

def test_expired_and_internal_announcements_are_not_public(publishing,client):
    h=auth(client)
    for slug,audience,end in [('internal','INTERNAL',None),('expired','PUBLIC',datetime.now(timezone.utc)-timedelta(days=1)),('current','BOTH',datetime.now(timezone.utc)+timedelta(days=1))]:
        row=client.post('/api/v1/announcements',headers=h,json=dict(slug=slug,title=slug,body='Synthetic notice',audience=audience,publish_until=end.isoformat() if end else None)).json()
        for action in ('submit','approve','publish'):
            result=client.post('/api/v1/announcements/'+row['id']+'/'+action,headers=h,json={'expected_updated_at':row['updated_at']})
            assert result.status_code==200,result.text
            row=result.json()
    assert [row['slug'] for row in client.get('/api/v1/public/announcements').json()['items']]==['current']

def test_prayer_and_visitor_intake_private_no_auto_member_and_rate_limit(publishing,client):
    with publishing.factory() as db:before=db.scalar(select(func.count()).select_from(Member))
    for endpoint,data in [('prayer-requests',{'message':'PRIVATE-PRAYER-BODY'}),('visitor-inquiries',{'first_name':'Visitor','last_name':'Synthetic','email':'visitor@example.invalid'})]:
        response=client.post('/api/v1/public/'+endpoint,headers={'Origin':ORIGIN},json=data)
        assert response.status_code==202,response.text
        assert response.json()=={'status':'received'}
    with publishing.factory() as db:
        assert db.scalar(select(func.count()).select_from(Member))==before
        assert db.scalar(select(func.count()).select_from(PublicInquiry))==2
    assert client.get('/api/v1/public/prayer-requests').status_code==405
    auth(client,'youth')
    assert client.get('/api/v1/visitor-inquiries?kind=PRAYER').status_code==403
    assert 'PRIVATE-PRAYER-BODY' not in client.get('/api/v1/public/site').text
    for i in range(3):assert client.post('/api/v1/public/contact',headers={'Origin':ORIGIN},json={'first_name':'Synthetic','message':str(i)}).status_code==202
    assert client.post('/api/v1/public/contact',headers={'Origin':ORIGIN},json={'first_name':'Synthetic'}).status_code==429

def test_visitor_duplicate_checks_and_atomic_conversion(publishing,client):
    client.post('/api/v1/public/visitor-inquiries',headers={'Origin':ORIGIN},json={'first_name':'Reviewed','last_name':'Visitor','email':'reviewed@example.invalid'})
    h=auth(client);row=client.get('/api/v1/visitor-inquiries').json()['items'][0]
    response=client.post('/api/v1/visitor-inquiries/'+row['id']+'/convert',headers=h,json={'confirm':True,'expected_updated_at':row['updated_at']})
    assert response.status_code==200,response.text
    assert response.json()['status']=='CONVERTED' and response.json()['converted_member_id']
    assert client.post('/api/v1/visitor-inquiries/'+row['id']+'/convert',headers=h,json={'confirm':True,'expected_updated_at':row['updated_at']}).status_code==409
    with publishing.factory() as db:
        assert db.scalar(select(func.count()).select_from(Member).where(Member.email=='reviewed@example.invalid'))==1

def test_images_require_review_consent_and_published_parent(publishing,client):
    h=auth(client);buffer=io.BytesIO();Image.new('RGB',(1600,900),'blue').save(buffer,format='PNG')
    row=client.post('/api/v1/website/media',headers=h,json={'image_base64':base64.b64encode(buffer.getvalue()).decode(),'alt_text':'Synthetic test image','contains_children':True}).json()
    assert row['status']=='DRAFT' and 'storage_key' not in row
    assert client.get('/api/v1/public/media/'+row['id']).status_code==404
    data=dict(alt_text='Synthetic test image',caption='Reviewed',contains_children=True,consent_attested=True,expected_updated_at=row['updated_at'])
    assert client.post('/api/v1/website/media/'+row['id']+'/approve',headers=h,json=data).status_code==422
    data['consent_reference']='Private fixture consent approval'
    review=client.post('/api/v1/website/media/'+row['id']+'/approve',headers=h,json=data)
    assert review.status_code==200,review.text
    assert client.get('/api/v1/public/media/'+row['id']).status_code==404
    content=page_data('GALLERY','reviewed-album');content['data']={'images':[{'asset_id':row['id'],'alt_text':'Approved photo'}]}
    album=publish(client,h,create(client,h,content))
    image=client.get('/api/v1/public/media/'+row['id']+'?size=320')
    assert image.status_code==200,image.text
    assert Image.open(io.BytesIO(image.content)).width<=320
    client.post('/api/v1/website/content/'+album['id']+'/archive',headers=h,json={'expected_updated_at':album['updated_at']})
    assert client.get('/api/v1/public/media/'+row['id']).status_code==404

def test_cms_xss_and_unsafe_media_links_are_rejected_or_rendered_as_plain_text(publishing,client):
    h=auth(client);data=page_data('SERMON','safe-sermon')
    data['data']={'speaker':'Synthetic speaker','sermon_date':'2026-10-04','youtube_url':'javascript:alert(1)'}
    assert client.post('/api/v1/website/content',headers=h,json=data).status_code==422
    data=page_data();data['body']='<script>PRIVATE-XSS-SENTINEL</script>'
    publish(client,h,create(client,h,data))
    assert client.get('/api/v1/public/pages/about').json()['body']==data['body']
    auth(client,'teacher')
    assert client.get('/api/v1/website/content').status_code==403
