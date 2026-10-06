"""Phase 4 real PG business reads, counts, privacy, IDOR and bounded queries."""
import json
from datetime import date
from pathlib import Path
from uuid import uuid4
import pytest
from sqlalchemy import event, select
from PIL import Image
from src.models import Member, MemberStatus, MemberMinistry, Role, Permission
from tests.test_web_auth import security_database, credential_hash, environment, client, login

@pytest.fixture
def business(environment):
    with environment.factory() as db:
        officer=db.scalar(select(Role).where(Role.code=='TEST_MINISTRY_OFFICER'))
        officer.permissions.append(db.scalar(select(Permission).where(Permission.code=='MINISTRY_LEADERSHIP_VIEW')))
        secretary=environment.users['secretary']
        secretary=db.get(type(secretary),secretary.id)
        permission=db.scalar(select(Permission).where(Permission.code=='MEMBERS_VIEW_ALL'))
        secretary_role=Role(code='CHURCH_SECRETARY',name='Secretary',is_active=True,permissions=[permission])
        db.add(secretary_role);db.flush();secretary.roles=[secretary_role]
        rows=[]
        for i in range(125):
            member=Member(member_no=f'READ-{i:04}',first_name='Youth' if i<75 else 'Women',
                          last_name=f'Person{i:04}',phone=f'024000{i:04}',date_joined=date(2026,1,1),
                          status=MemberStatus.INACTIVE if i==1 else MemberStatus.ACTIVE)
            db.add(member);db.flush();rows.append(member)
            mid=environment.ministries['Youth' if i<75 else 'Women'].id
            db.add(MemberMinistry(member_id=member.id,ministry_id=mid,is_active=True))
            if i==0:db.add(MemberMinistry(member_id=member.id,ministry_id=environment.ministries['Choir'].id,is_active=True))
        db.add(MemberMinistry(member_id=environment.member.id,ministry_id=environment.ministries['Youth'].id,is_active=True))
        db.commit()
        environment.rows=rows
    return environment

@pytest.mark.parametrize('name,total', [('admin',126),('secretary',126),('youth',76),('women',50),('treasurer',76)])
def test_directory_scope_pagination_counts_and_safe_fields(business,client,name,total):
    assert login(client,name).status_code==200
    response=client.get('/api/v1/members?page_size=25')
    assert response.status_code==200,response.text
    data=response.json();assert data['total']==total
    assert len(data['items'])==25 and data['pages']==(total+24)//25
    assert all(set(row)=={'id','member_no','full_name','gender','phone','status','photo_url','ministries'} for row in data['items'])
    page2=client.get('/api/v1/members?page=2&page_size=25').json()
    assert not {x['id'] for x in data['items']}&{x['id'] for x in page2['items']}
    assert client.get('/api/v1/members?page_size=101').status_code==422
    assert client.get('/api/v1/members?sort=password_hash').status_code==422
    assert client.get('/api/v1/members?search=READ-0000').json()['total']==(0 if name=='women' else 1)
    assert client.get('/api/v1/members?search=0240000000').json()['total']==(0 if name=='women' else 1)
    assert client.get('/api/v1/members?search=%25').json()['total']==0
    assert client.get('/api/v1/members?search=Youth%20Person0000').json()['total']==(0 if name=='women' else 1)
    if name in {'youth','treasurer'}:
        assert client.get('/api/v1/members?status=INACTIVE').json()['total']==1
        assert client.get('/api/v1/members?ministry_id='+str(business.ministries['Women'].id)).status_code==403

@pytest.mark.parametrize('path', ['members','ministries','dashboard'])
def test_anonymous_business_access_is_401(client,path):
    assert client.get('/api/v1/'+path).status_code==401

@pytest.mark.parametrize('name', ['youth','treasurer'])
def test_direct_member_ministry_roster_leadership_photo_idor(business,client,name):
    login(client,name)
    women=business.ministries['Women'].id
    for path in [f'members/{business.rows[100].id}',f'media/member-photo/{business.rows[100].id}',
                 f'ministries/{women}',f'ministries/{women}/members',f'ministries/{women}/leadership',
                 f'dashboard?ministry_id={women}']:
        assert client.get('/api/v1/'+path).status_code==403,path
    data=client.get('/api/v1/members/'+str(business.rows[0].id)).json()
    assert len(data['ministries'])==(2 if name=='treasurer' else 1)
    assert 'household' not in data and 'sunday_school' not in data
    assert 'photo_path' not in json.dumps(data) and 'password' not in json.dumps(data)
    if name=='treasurer':assert client.get('/api/v1/ministries/'+str(business.ministries['Choir'].id)).status_code==200

def test_configured_leadership_and_real_dashboard(business,client):
    login(client,'youth');mid=business.ministries['Youth'].id
    leaders=client.get(f'/api/v1/ministries/{mid}/leadership').json()
    assert leaders['total']==1 and leaders['items'][0]['position_name']=='Youth Leader'
    assert 'has_system_account' not in json.dumps(leaders) and 'notes' not in json.dumps(leaders)
    detail=client.get(f'/api/v1/ministries/{mid}').json()
    assert detail['member_count']==76 and detail['leadership']['current']==1
    dash=client.get(f'/api/v1/dashboard?ministry_id={mid}').json()
    metrics={row['key']:row['value'] for row in dash['metrics']}
    assert metrics['members']==76 and metrics['active_members']==75 and metrics['appointments']==1
    assert all('finance' not in key and 'school' not in key for key in metrics)

def test_global_without_scopes_and_secretary_permission_boundary(business,client):
    login(client,'secretary')
    assert client.get('/api/v1/members/options').status_code==200
    assert client.get('/api/v1/ministries').status_code==403
    metrics=client.get('/api/v1/dashboard').json()['metrics']
    assert {row['key'] for row in metrics}=={'members','active_members','new_members'}
    assert metrics[0]['value']==126

@pytest.mark.parametrize('name',['teacher','position_only'])
def test_class_or_church_position_does_not_grant_members(business,client,name):
    login(client,name)
    assert client.get('/api/v1/members').status_code==403
    assert client.get('/api/v1/ministries').status_code==403
    assert client.get('/api/v1/members/'+str(business.member.id)).status_code==403
    dash=client.get('/api/v1/dashboard').json()
    assert not dash['recent_members']
    if name=='teacher': assert any(row['key']=='classes' and row['value']==1 for row in dash['metrics'])
    else:assert not dash['metrics']

def test_large_directory_query_count_is_bounded(business,client):
    with business.factory() as db:
        db.add_all([Member(member_no=f'BULK-{i:05}',first_name='Bulk',last_name='Synthetic',status=MemberStatus.ACTIVE) for i in range(2000)])
        db.commit()
    login(client)
    connection_engine=business.factory.kw['bind'];statements=[]
    def collect(*args):statements.append(args[2])
    event.listen(connection_engine,'before_cursor_execute',collect)
    try:
        response=client.get('/api/v1/members?page_size=100&page=15')
        assert response.status_code==200,response.text
        assert response.json()['total']==2126 and len(response.json()['items'])==100
        assert len(statements)<=25, len(statements)
        assert any('LIMIT' in s and 'OFFSET' in s for s in statements)
    finally:event.remove(connection_engine,'before_cursor_execute',collect)

def test_photo_authorized_bounded_and_path_safe(business,client):
    from src.services.member_service import MEMBER_PHOTO_DIR
    MEMBER_PHOTO_DIR.mkdir(exist_ok=True)
    photo=MEMBER_PHOTO_DIR/(uuid4().hex+'.png')
    try:
        Image.new('RGB',(800,600),'blue').save(photo)
        with business.factory() as db:
            row=db.get(Member,business.rows[0].id);row.photo_path=str(photo);db.commit()
        login(client,'youth')
        url='/api/v1/media/member-photo/'+str(business.rows[0].id)
        response=client.get(url)
        assert response.status_code==200 and response.headers['content-type']=='image/jpeg'
        assert response.headers['cache-control']=='no-store'
        import io
        assert max(Image.open(io.BytesIO(response.content)).size)<=512
        for stored in [str(Path('.env').resolve()),'../../.env','assets/member_photos/missing.png']:
            with business.factory() as db:db.get(Member,business.rows[0].id).photo_path=stored;db.commit()
            assert client.get(url).status_code==404
        photo.write_bytes(b'not an image')
        with business.factory() as db:db.get(Member,business.rows[0].id).photo_path=str(photo);db.commit()
        assert client.get(url).status_code==404
    finally:photo.unlink(missing_ok=True)

def test_optional_sections_and_school_counts_require_explicit_permissions(business,client):
    from src.models import (Household,HouseholdMember,SundaySchoolClass,SundaySchoolStudent,SundaySchoolEnrollment)
    with business.factory() as db:
        household=Household(household_name='Read family',household_code='READ_FAMILY',notes='PRIVATE-NOTES',primary_phone='PRIVATE-CONTACT')
        other=SundaySchoolClass(name='Other class',code='READ_OTHER',status='ACTIVE')
        db.add_all([household,other]);db.flush()
        db.add(HouseholdMember(household_id=household.id,member_id=business.rows[0].id,relationship='CHILD',is_household_head=False,is_active=True))
        for member,school in [(business.rows[0],business.school),(business.rows[100],other)]:
            db.add(SundaySchoolStudent(member_id=member.id,status='ACTIVE',special_notes='PRIVATE-SCHOOL-NOTES'));db.flush()
            db.add(SundaySchoolEnrollment(member_id=member.id,class_id=school.id,class_name=school.name,class_code=school.code,start_date=date(2026,1,1)))
        db.commit()
    login(client)
    response=client.get('/api/v1/members/'+str(business.rows[0].id))
    assert response.status_code==200,response.text
    assert response.json()['household']['household_name']=='Read family'
    assert response.json()['sunday_school']['class_name']==business.school.name
    assert 'PRIVATE-' not in response.text and 'notes' not in response.text
    selected=client.get('/api/v1/dashboard?class_id='+str(other.id))
    assert selected.status_code==200,selected.text
    metrics={row['key']:row['value'] for row in selected.json()['metrics']}
    assert metrics['classes']==1 and metrics['students']==1 and 'members' not in metrics
    login(client,'teacher')
    assert client.get('/api/v1/dashboard?class_id='+str(other.id)).status_code==403
    metrics={row['key']:row['value'] for row in client.get('/api/v1/dashboard').json()['metrics']}
    assert metrics['classes']==1 and metrics['students']==1

def test_ministry_permission_does_not_disclose_ungranted_member_counts(business,client):
    login(client)
    with business.factory() as db:
        role=db.scalar(select(Role).where(Role.code=='TEST_CHURCH_ADMIN'))
        role.permissions=[db.scalar(select(Permission).where(Permission.code=='MINISTRIES_VIEW_ALL'))]
        db.commit()
    response=client.get('/api/v1/ministries')
    assert response.status_code==200
    assert all(row['member_count'] is None for row in response.json()['items'])
    detail=client.get('/api/v1/ministries/'+str(business.ministries['Youth'].id)).json()
    assert detail['can_view_members'] is False and detail['can_view_leadership'] is False
    assert client.get('/api/v1/members').status_code==403
    assert {row['key'] for row in client.get('/api/v1/dashboard').json()['metrics']}=={'active_ministries'}

def test_shared_sunday_attendance_summary_counts_only_authorized_members(business,client):
    from src.models import (AttendanceSession,AttendanceRosterMember,AttendanceRecord,AttendanceSessionType,
        AttendanceScopeType,AttendanceRosterType,AttendanceSessionState,AttendanceStatus)
    with business.factory() as db:
        service=AttendanceSession(name='Read Sunday',session_type=AttendanceSessionType.SUNDAY_SERVICE,
            scope_type=AttendanceScopeType.GLOBAL,roster_type=AttendanceRosterType.WHOLE_CHURCH,
            state=AttendanceSessionState.CLOSED,session_date=date(2026,10,4))
        db.add(service);db.flush()
        for member in (business.rows[0],business.rows[100]):
            db.add(AttendanceRosterMember(session_id=service.id,member_id=member.id))
            db.add(AttendanceRecord(session_id=service.id,member_id=member.id,status=AttendanceStatus.PRESENT))
        db.commit()
    login(client,'youth');mid=business.ministries['Youth'].id
    response=client.get('/api/v1/dashboard?ministry_id='+str(mid))
    assert response.status_code==200,response.text
    metrics={row['key']:row['value'] for row in response.json()['metrics']}
    assert metrics['sunday_attendance']==1 and metrics['attendance_sessions']==1
    login(client)
    metrics={row['key']:row['value'] for row in client.get('/api/v1/dashboard').json()['metrics']}
    assert metrics['sunday_attendance']==2

def test_ministry_directory_filters_pagination_and_current_roster(business,client):
    login(client)
    first=client.get('/api/v1/ministries?page_size=2').json()
    second=client.get('/api/v1/ministries?page_size=2&page=2').json()
    assert first['total']==4 and first['pages']==2
    assert not {x['id'] for x in first['items']}&{x['id'] for x in second['items']}
    assert client.get('/api/v1/ministries?search=Youth').json()['total']==1
    assert client.get('/api/v1/ministries?status=WRONG').status_code==422
    choir=business.ministries['Choir'].id
    assert client.get('/api/v1/ministries?ministry_id='+str(choir)).json()['total']==1
    roster=client.get(f'/api/v1/ministries/{choir}/members').json()
    assert roster['total']==1 and roster['items'][0]['id']==str(business.rows[0].id)
    with business.factory() as db:
        row=db.scalar(select(MemberMinistry).where(MemberMinistry.member_id==business.rows[0].id,MemberMinistry.ministry_id==choir))
        row.is_active=False;db.commit()
    assert client.get(f'/api/v1/ministries/{choir}/members').json()['total']==0
