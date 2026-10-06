
"""Actual operational APIs use real auth and disposable PostgreSQL business data."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import date,timedelta,datetime
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,func,event
from src.models import (Role,Permission,Member,MemberStatus,MemberMinistry,AttendanceRecord,AttendanceAuditLog,
    SundaySchoolClass,SundaySchoolStudent,SundaySchoolEnrollment,SundaySchoolAttendanceRecord,SundaySchoolAuditLog,
    SundaySchoolGuardian,SundaySchoolLesson,SundaySchoolLessonClass)
from tests.test_online_workspace import business
from tests.test_web_auth import security_database,credential_hash,environment,client,login,ORIGIN

@pytest.fixture
def operational(business):
    with business.factory() as db:
        role=db.scalar(select(Role).where(Role.code=='TEST_MINISTRY_OFFICER'))
        for code in ('ATTENDANCE_CREATE_OWN_MINISTRY','ATTENDANCE_CORRECT_OWN_MINISTRY','ATTENDANCE_CLOSE_SESSION','ATTENDANCE_VIEW_AUDIT','ATTENDANCE_EXPORT'):
            role.permissions.append(db.scalar(select(Permission).where(Permission.code==code)))
        other=SundaySchoolClass(name='Other class',code='OPS_OTHER',status='ACTIVE')
        db.add(other);db.flush()
        for index in (0,1,100):
            cls=business.school if index<2 else other
            student=SundaySchoolStudent(member_id=business.rows[index].id,status='ACTIVE',special_notes='PRIVATE-NOTES')
            db.add(student);db.flush()
            db.add(SundaySchoolEnrollment(member_id=student.member_id,class_id=cls.id,class_name=cls.name,class_code=cls.code,start_date=date(2026,1,1)))
            if index==0:
                db.add(SundaySchoolGuardian(student_id=student.id,guardian_member_id=business.rows[10].id,relationship='PARENT',is_primary=True,can_receive_sms=True))
        db.commit();business.other=other
    return business

def authenticated(client,name='admin'):
    response=login(client,name);assert response.status_code==200,response.text
    return {'Origin':ORIGIN,'X-CSRF-Token':response.json()['csrf_token']}
def sunday(client,headers,state='OPEN'):
    response=client.post('/api/v1/attendance/sessions',headers=headers,json=dict(title='Shared Sunday',session_type='SUNDAY_SERVICE',
        scope_type='GLOBAL',session_date=date.today().isoformat(),state=state))
    assert response.status_code==201,response.text
    return response.json()
def school_session(client,headers,cls,open_now=True,delta=0):
    response=client.post('/api/v1/sunday-school/attendance/sessions',headers=headers,json=dict(class_id=str(cls.id),title='Class attendance',
        session_date=(date.today()+timedelta(days=delta)).isoformat(),open_now=open_now))
    assert response.status_code==201,response.text
    return response.json()
def correction(row,status='LATE'):
    return dict(status=status,reason='Checked with the usher',expected_status=row['status'],expected_updated_at=row['updated_at'])

def test_shared_sunday_one_record_across_ministry_views(operational,client):
    headers=authenticated(client);session=sunday(client,headers);sid=session['id'];mid=operational.rows[0].id
    youth=authenticated(client,'youth')
    url=f'/api/v1/attendance/sessions/{sid}'
    roster=client.get(url+'/roster',params={'ministry_id':str(operational.ministries['Youth'].id)}).json()
    assert roster['total']==75 # inactive row is not added to the saved roster
    mark=client.post(url+'/mark',headers=youth,json={'member_id':str(mid),'status':'PRESENT'})
    assert mark.status_code==200,mark.text
    assert mark.json()['row']['status']=='PRESENT'
    authenticated(client)
    all_members=client.get(url+'/roster',params={'search':'READ-0000'}).json()
    assert all_members['items'][0]['record_id']==mark.json()['row']['record_id']
    choir=client.get(url+'/roster',params={'ministry_id':str(operational.ministries['Choir'].id)}).json()
    assert choir['total']==1 and choir['items'][0]['status']=='PRESENT'
    with operational.factory() as db:
        assert db.scalar(select(func.count()).select_from(AttendanceRecord).where(AttendanceRecord.member_id==mid))==1

def test_csrf_and_sunday_scope_payloads_are_enforced(operational,client):
    headers=authenticated(client)
    data=dict(title='Bad Sunday',session_type='SUNDAY_SERVICE',scope_type='MINISTRY',ministry_id=str(operational.ministries['Youth'].id),session_date=date.today().isoformat())
    assert client.post('/api/v1/attendance/sessions',headers=headers,json=data).status_code==422
    data.update(session_type='MINISTRY_MEETING',scope_type='GLOBAL',ministry_id=None)
    assert client.post('/api/v1/attendance/sessions',headers=headers,json=data).status_code==422
    data.update(session_type='SUNDAY_SERVICE')
    assert client.post('/api/v1/attendance/sessions',headers={'Origin':ORIGIN},json=data).status_code==403
    assert client.post('/api/v1/attendance/sessions',headers={**headers,'Origin':'https://foreign.invalid'},json=data).status_code==403

def test_ministry_create_open_scope_and_forged_member(operational,client):
    headers=authenticated(client,'youth');mid=operational.ministries['Youth'].id
    data=dict(title='Youth meeting',session_type='MINISTRY_MEETING',scope_type='MINISTRY',ministry_id=str(mid),session_date=date.today().isoformat(),state='DRAFT')
    response=client.post('/api/v1/attendance/sessions',headers=headers,json=data)
    assert response.status_code==201,response.text
    session=response.json();url='/api/v1/attendance/sessions/'+session['id']
    assert client.post(url+'/mark',headers=headers,json={'member_id':str(operational.rows[0].id),'status':'PRESENT'}).status_code==400
    opened=client.post(url+'/open',headers=headers,json={'expected_updated_at':session['updated_at']})
    assert opened.status_code==200,opened.text
    assert client.post(url+'/mark',headers=headers,json={'member_id':str(operational.rows[100].id),'status':'PRESENT'}).status_code==403
    authenticated(client,'women')
    for path in ('','/roster','/summary'):
        assert client.get(url+path).status_code==403
    assert not client.get('/api/v1/attendance/sessions').json()['items']

def test_correction_audit_versions_closed_and_locked(operational,client):
    headers=authenticated(client);session=sunday(client,headers);url='/api/v1/attendance/sessions/'+session['id']
    initial=client.post(url+'/mark',headers=headers,json={'member_id':str(operational.rows[0].id),'status':'PRESENT'}).json()['row']
    corrected=client.post('/api/v1/attendance/records/'+initial['record_id']+'/correct',headers=headers,json=correction(initial))
    assert corrected.status_code==200,corrected.text
    assert client.post('/api/v1/attendance/records/'+initial['record_id']+'/correct',headers=headers,json=correction(initial,'ABSENT')).status_code==409
    with operational.factory() as db:
        row=db.get(AttendanceRecord,initial['record_id'])
        assert row.marked_at==datetime.fromisoformat(initial['marked_at']) and row.marked_by_user_id==operational.users['admin'].id
        audit=db.scalar(select(AttendanceAuditLog).where(AttendanceAuditLog.action_type=='CORRECTED'))
        assert audit.old_status=='PRESENT' and audit.new_status=='LATE' and audit.reason and audit.changed_by_user_id
    session=client.get(url).json()
    closed=client.post(url+'/close',headers=headers,json={'expected_updated_at':session['updated_at']})
    assert closed.status_code==200
    assert client.post(url+'/mark',headers=headers,json={'member_id':str(operational.rows[1].id),'status':'PRESENT'}).status_code in (403,400)
    row=client.get(url+'/roster?search=READ-0000').json()['items'][0]
    assert client.post('/api/v1/attendance/records/'+row['record_id']+'/correct',headers=headers,json=correction(row,'EXCUSED')).status_code==200
    locked=client.post(url+'/lock',headers=headers,json={'expected_updated_at':closed.json()['updated_at'],'reason':'Verified and finalized'})
    assert locked.status_code==200,locked.text
    row=client.get(url+'/roster?search=READ-0000').json()['items'][0]
    assert client.post('/api/v1/attendance/records/'+row['record_id']+'/correct',headers=headers,json=correction(row,'PRESENT')).status_code==400

@pytest.mark.parametrize('school',[False,True])
def test_concurrent_initial_marks_preserve_one_record(operational,client,school):
    headers=authenticated(client)
    session=school_session(client,headers,operational.school) if school else sunday(client,headers)
    prefix='/api/v1/sunday-school/attendance' if school else '/api/v1/attendance'
    barrier=Barrier(2)
    def submit(name,status):
        with TestClient(operational.app,base_url='http://localhost') as browser:
            h=authenticated(browser,name);barrier.wait(timeout=15)
            return browser.post(prefix+'/sessions/'+session['id']+'/mark',headers=h,json={'member_id':str(operational.rows[0].id),'status':status}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(submit,'teacher' if school else 'youth','PRESENT'),pool.submit(submit,'admin','ABSENT')]
        assert sorted(f.result(timeout=25) for f in futures)==[200,409]
    with operational.factory() as db:
        model=SundaySchoolAttendanceRecord if school else AttendanceRecord
        assert db.scalar(select(func.count()).select_from(model))==1

def test_teacher_scope_privacy_and_lesson_permissions(operational,client):
    headers=authenticated(client,'teacher')
    assert client.get('/api/v1/sunday-school/classes').json()['total']==1
    assert client.get('/api/v1/sunday-school/students').json()['total']==2
    assert client.get('/api/v1/sunday-school/classes/'+str(operational.other.id)).status_code==403
    assert client.get('/api/v1/sunday-school/students/'+str(operational.rows[100].id)).status_code==403
    response=client.get('/api/v1/sunday-school/students/'+str(operational.rows[0].id))
    assert response.status_code==200
    assert response.json()['guardians'][0]['phone']==operational.rows[10].phone
    for name in ('photo_path','date_of_birth','household','special_notes','password_hash','PRIVATE-'):
        assert name not in response.text
    lesson=dict(title='Teacher lesson',lesson_date=date.today().isoformat(),class_ids=[str(operational.school.id)])
    assert client.post('/api/v1/sunday-school/lessons',headers=headers,json=lesson).status_code==403

def test_lesson_create_edit_publish_scope_and_stale_version(operational,client):
    headers=authenticated(client)
    data=dict(title='Class lesson',lesson_date=date.today().isoformat(),class_ids=[str(operational.school.id)],status='DRAFT')
    created=client.post('/api/v1/sunday-school/lessons',headers=headers,json=data)
    assert created.status_code==201,created.text
    row=created.json();url='/api/v1/sunday-school/lessons/'+row['id']
    data.update(status='PUBLISHED',expected_updated_at=row['updated_at'])
    changed=client.patch(url,headers=headers,json=data)
    assert changed.status_code==200,changed.text
    assert client.patch(url,headers=headers,json=data).status_code==409
    authenticated(client,'teacher')
    assert client.get('/api/v1/sunday-school/lessons').json()['total']==1
    with operational.factory() as db:
        role=db.scalar(select(Role).where(Role.code=='TEST_SCHOOL_TEACHER'))
        for code in ('SUNDAY_SCHOOL_LESSON_CREATE','SUNDAY_SCHOOL_LESSON_EDIT'):
            role.permissions.append(db.scalar(select(Permission).where(Permission.code==code)))
        db.commit()
    h=authenticated(client,'teacher')
    bad=dict(title='Forbidden lesson',lesson_date=date.today().isoformat(),class_ids=[str(operational.other.id)])
    assert client.post('/api/v1/sunday-school/lessons',headers=h,json=bad).status_code==403

def test_school_roster_state_correction_reports_and_duplicate_session(operational,client):
    headers=authenticated(client,'teacher');session=school_session(client,headers,operational.school,False)
    url='/api/v1/sunday-school/attendance/sessions/'+session['id']
    assert client.post(url+'/mark',headers=headers,json={'member_id':str(operational.rows[0].id),'status':'PRESENT'}).status_code==400
    session=client.post(url+'/open',headers=headers,json={'expected_updated_at':session['updated_at']}).json()
    assert client.get(url+'/roster').json()['total']==1 # inactive master member excluded on open
    saved=client.post(url+'/mark',headers=headers,json={'member_id':str(operational.rows[0].id),'status':'ABSENT'})
    assert saved.status_code==200,saved.text
    row=saved.json()['row'];correct_url='/api/v1/sunday-school/attendance/records/'+row['record_id']+'/correct'
    corrected=client.post(correct_url,headers=headers,json=correction(row,'PRESENT'))
    assert corrected.status_code==200,corrected.text
    assert client.post(correct_url,headers=headers,json=correction(row,'LATE')).status_code==409
    closed=client.post(url+'/close',headers=headers,json={'expected_updated_at':session['updated_at']})
    assert closed.status_code==200,closed.text
    row=corrected.json()['row']
    assert client.post(correct_url,headers=headers,json=correction(row,'LATE')).status_code==403
    report=client.get('/api/v1/sunday-school/reports/attendance?kind=students')
    assert report.status_code==200,report.text
    assert report.json()['items'][0]['rate']==100
    assert client.post('/api/v1/sunday-school/attendance/sessions',headers=headers,json=dict(class_id=str(operational.school.id),session_date=date.today().isoformat())).status_code==409
    with operational.factory() as db:
        log=db.scalar(select(SundaySchoolAuditLog).where(SundaySchoolAuditLog.action=='ATTENDANCE_CORRECTED'))
        assert log.reason and log.old_values['status']=='ABSENT' and log.new_values['status']=='PRESENT'

def test_school_foreign_session_roster_mark_correction_and_photo(operational,client):
    headers=authenticated(client);session=school_session(client,headers,operational.other)
    url='/api/v1/sunday-school/attendance/sessions/'+session['id']
    saved=client.post(url+'/mark',headers=headers,json={'member_id':str(operational.rows[100].id),'status':'PRESENT'}).json()['row']
    h=authenticated(client,'teacher')
    for path in ('','/roster','/photo/'+str(operational.rows[100].id)):
        assert client.get(url+path).status_code==403
    assert client.post(url+'/mark',headers=h,json={'member_id':str(operational.rows[100].id),'status':'PRESENT'}).status_code==403
    assert client.post('/api/v1/sunday-school/attendance/records/'+saved['record_id']+'/correct',headers=h,json=correction(saved)).status_code==403
    assert client.get('/api/v1/sunday-school/reports/attendance?class_id='+str(operational.other.id)).status_code==403

def test_large_rosters_use_bounded_set_queries(operational,client):
    with operational.factory() as db:
        db.add_all(Member(member_no=f'OPS-BULK-{index}',first_name='Bulk',last_name='Synthetic',status=MemberStatus.ACTIVE) for index in range(800))
        db.commit()
    headers=authenticated(client);session=sunday(client,headers);statements=[]
    def collect(*args):statements.append(args[2])
    test_engine=operational.factory.kw['bind'];event.listen(test_engine,'before_cursor_execute',collect)
    try:
        response=client.get('/api/v1/attendance/sessions/'+session['id']+'/roster?page_size=100&page=8')
        assert response.status_code==200,response.text
        assert len(response.json()['items'])==100 and response.json()['total']==925
        assert len(statements)<=30,len(statements)
        assert any('LIMIT' in stmt and 'OFFSET' in stmt for stmt in statements)
    finally:event.remove(test_engine,'before_cursor_execute',collect)

def test_csv_export_requires_permission_and_escapes_formulas(operational,client):
    headers=authenticated(client)
    session=school_session(client,headers,operational.school)
    url='/api/v1/sunday-school/attendance/sessions/'+session['id']
    client.post(url+'/close',headers=headers,json={'expected_updated_at':session['updated_at']})
    with operational.factory() as db:
        db.get(SundaySchoolClass,operational.school.id).name='=PRIVATE-FORMULA'
        db.commit()
    response=client.get('/api/v1/sunday-school/reports/attendance.csv')
    assert response.status_code==200,response.text
    assert response.headers['cache-control']=='no-store'
    assert "'=PRIVATE-FORMULA" in response.text
    authenticated(client,'teacher')
    assert client.get('/api/v1/sunday-school/reports/attendance.csv').status_code==403

def test_multi_scope_mark_cannot_escape_requested_ministry_context(operational,client):
    headers=authenticated(client);session=sunday(client,headers)
    with operational.factory() as db:
        db.add(MemberMinistry(member_id=operational.rows[50].id,ministry_id=operational.ministries['Choir'].id,is_active=True))
        # Existing roster member becomes Choir-only, while still in the saved global roster.
        membership=db.scalar(select(MemberMinistry).where(MemberMinistry.member_id==operational.rows[50].id,MemberMinistry.ministry_id==operational.ministries['Youth'].id))
        membership.is_active=False;db.commit()
    h=authenticated(client,'treasurer')
    url='/api/v1/attendance/sessions/'+session['id']+'/mark?ministry_id='+str(operational.ministries['Youth'].id)
    assert client.post(url,headers=h,json={'member_id':str(operational.rows[50].id),'status':'PRESENT'}).status_code==403


def test_scoped_archiving_returns_confirmed_write_even_if_lesson_leaves_visible_list(operational,client):
    headers=authenticated(client)
    data=dict(title='Shared published lesson',lesson_date=date.today().isoformat(),class_ids=[str(operational.school.id)],status='PUBLISHED')
    row=client.post('/api/v1/sunday-school/lessons',headers=headers,json=data).json()
    with operational.factory() as db:
        role=db.scalar(select(Role).where(Role.code=='TEST_SCHOOL_TEACHER'))
        role.permissions.append(db.scalar(select(Permission).where(Permission.code=='SUNDAY_SCHOOL_LESSON_EDIT')))
        db.commit()
    headers=authenticated(client,'teacher')
    data.update(status='ARCHIVED',expected_updated_at=row['updated_at'])
    response=client.patch('/api/v1/sunday-school/lessons/'+row['id'],headers=headers,json=data)
    assert response.status_code==200,response.text
    assert response.json()['status']=='ARCHIVED'
    assert client.get('/api/v1/sunday-school/lessons/'+row['id']).status_code==403


def test_large_school_roster_paginates_without_per_student_queries(operational,client):
    with operational.factory() as db:
        for index in range(300):
            member=Member(member_no=f'CLASS-BULK-{index:04}',first_name='Class',last_name=f'Person{index:04}',status=MemberStatus.ACTIVE)
            db.add(member);db.flush()
            db.add(SundaySchoolStudent(member_id=member.id,status='ACTIVE'));db.flush()
            db.add(SundaySchoolEnrollment(member_id=member.id,class_id=operational.school.id,class_name=operational.school.name,class_code=operational.school.code,start_date=date(2026,1,1)))
        db.commit()
    headers=authenticated(client,'teacher');session=school_session(client,headers,operational.school)
    statements=[];test_engine=operational.factory.kw['bind']
    def collect(*args):statements.append(args[2])
    event.listen(test_engine,'before_cursor_execute',collect)
    try:
        response=client.get('/api/v1/sunday-school/attendance/sessions/'+session['id']+'/roster?page=2&page_size=100')
        assert response.status_code==200,response.text
        assert response.json()['total']==301 and len(response.json()['items'])==100
        assert len(statements)<=25,len(statements)
        assert 'date_of_birth' not in response.text and 'household' not in response.text
    finally:event.remove(test_engine,'before_cursor_execute',collect)


def test_unassigned_teacher_cannot_read_all_school_published_lessons(operational,client):
    from sqlalchemy import delete
    from src.models import SundaySchoolUserClassScope
    headers=authenticated(client)
    lesson=client.post('/api/v1/sunday-school/lessons',headers=headers,json=dict(title='All school lesson',lesson_date=date.today().isoformat(),status='PUBLISHED',all_classes=True)).json()
    with operational.factory() as db:
        db.execute(delete(SundaySchoolUserClassScope).where(SundaySchoolUserClassScope.user_id==operational.users['teacher'].id))
        db.commit()
    authenticated(client,'teacher')
    assert client.get('/api/v1/sunday-school/lessons').json()['total']==0
    assert client.get('/api/v1/sunday-school/lessons/'+lesson['id']).status_code==403
