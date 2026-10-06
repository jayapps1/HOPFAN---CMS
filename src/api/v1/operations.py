from typing import Annotated,Literal
from uuid import UUID
from datetime import date
from fastapi import APIRouter,Depends,Query,Response
from src.api.dependencies import get_operations
from src.api.schemas.workspace import Page,MinistrySummary
from src.api.schemas.operations import (SessionRow,SessionDetail,RosterRow,MarkResult,CreateSession,MarkRequest,
    CorrectionRequest,TransitionRequest,Stats,ClassRow,StudentRow,StudentDetail,TeacherRow,LessonRow,LessonWrite,
    SchoolSessionRow,SchoolSessionDetail,CreateSchoolSession,SchoolDashboard,ReportRow,ApiResponse,SessionType)
from src.api.v1 import API_PREFIX

router=APIRouter(prefix=API_PREFIX,tags=['Attendance and Sunday School'])
Ops=Annotated[object,Depends(get_operations,scope='function')]
PageNo=Annotated[int,Query(ge=1,le=100000)]
Size=Annotated[int,Query(ge=1,le=100)]
Search=Annotated[str,Query(max_length=200)]
MainState=Literal['ALL','DRAFT','OPEN','CLOSED','LOCKED']
SchoolState=Literal['ALL','DRAFT','OPEN','CLOSED']
RosterStatus=Literal['ALL','UNMARKED','PRESENT','LATE','EXCUSED','ABSENT']
class AttendanceOptions(ApiResponse):
    can_create:bool
    can_create_global:bool
    ministries:list[MinistrySummary]
    create_ministries:list[MinistrySummary]
    session_types:list[str]
    statuses:list[str]

@router.get('/attendance/options',response_model=AttendanceOptions)
def attendance_options(service:Ops):return service.attendance_options()
@router.get('/attendance/sessions',response_model=Page[SessionRow])
def sessions(service:Ops,page:PageNo=1,page_size:Size=25,search:Search='',state:MainState='ALL',
    ministry_id:UUID|None=None,session_type:SessionType|None=None,date_from:date|None=None,date_to:date|None=None,
    section:Literal['ALL','UPCOMING','MEETINGS','RECENT','SUNDAY']='ALL'):
    return service.list_sessions(page,page_size,search=search,state=state,ministry_id=ministry_id,session_type=session_type,date_from=date_from,date_to=date_to,section=section)
@router.post('/attendance/sessions',response_model=SessionDetail,status_code=201)
def create_session(service:Ops,body:CreateSession):return service.create_session(body.model_dump())
@router.get('/attendance/sessions/{session_id}',response_model=SessionDetail)
def session(service:Ops,session_id:UUID,ministry_id:UUID|None=None):return service.session(session_id,ministry_id)
@router.get('/attendance/sessions/{session_id}/roster',response_model=Page[RosterRow])
def roster(service:Ops,session_id:UUID,page:PageNo=1,page_size:Size=25,search:Search='',status:RosterStatus='ALL',ministry_id:UUID|None=None):
    return service.roster(session_id,page,page_size,search=search,status=status,ministry_id=ministry_id)
@router.post('/attendance/sessions/{session_id}/mark',response_model=MarkResult)
def mark(service:Ops,session_id:UUID,body:MarkRequest,ministry_id:UUID|None=None):return service.mark(session_id,body.model_dump(),ministry_id)
@router.post('/attendance/records/{record_id}/correct',response_model=MarkResult)
def correct(service:Ops,record_id:UUID,body:CorrectionRequest,ministry_id:UUID|None=None):return service.correct(record_id,body.model_dump(),ministry_id)
@router.get('/attendance/sessions/{session_id}/summary',response_model=Stats)
def summary(service:Ops,session_id:UUID,ministry_id:UUID|None=None):return service.summary(session_id,ministry_id)
@router.post('/attendance/sessions/{session_id}/{action}',response_model=SessionDetail)
def transition(service:Ops,session_id:UUID,action:Literal['open','close','reopen','lock','unlock'],body:TransitionRequest):
    return service.transition(session_id,action,body.model_dump())
@router.get('/attendance/sessions/{session_id}/photo/{member_id}')
def photo(service:Ops,session_id:UUID,member_id:UUID):return Response(service.photo(session_id,member_id),media_type='image/jpeg')

@router.get('/sunday-school/options',response_model=Page[MinistrySummary])
def class_options(service:Ops,page:PageNo=1,page_size:Size=100):return service.class_options(page,page_size)
@router.get('/sunday-school/dashboard',response_model=SchoolDashboard)
def school_dashboard(service:Ops,class_id:UUID|None=None):return service.school_dashboard(class_id)
@router.get('/sunday-school/classes',response_model=Page[ClassRow])
def classes(service:Ops,page:PageNo=1,page_size:Size=25,search:Search='',status:Literal['ALL','ACTIVE','INACTIVE']='ALL',class_id:UUID|None=None):
    return service.classes(page,page_size,search=search,status=status,class_id=class_id)
@router.get('/sunday-school/classes/{class_id}',response_model=ClassRow)
def school_class(service:Ops,class_id:UUID):return service.class_detail(class_id)
@router.get('/sunday-school/students',response_model=Page[StudentRow],response_model_exclude_none=True)
def students(service:Ops,page:PageNo=1,page_size:Size=25,search:Search='',class_id:UUID|None=None,
    status:Literal['ALL','ACTIVE','INACTIVE']='ACTIVE',minimum_age:Annotated[int|None,Query(ge=0,le=125)]=None,
    maximum_age:Annotated[int|None,Query(ge=0,le=125)]=None,gender:Literal['MALE','FEMALE']|None=None):
    return service.students(page,page_size,search=search,class_id=class_id,status=status,minimum_age=minimum_age,maximum_age=maximum_age,gender=gender)
@router.get('/sunday-school/students/{member_id}',response_model=StudentDetail,response_model_exclude_none=True)
def student(service:Ops,member_id:UUID):return service.student(member_id)
@router.get('/sunday-school/teachers',response_model=Page[TeacherRow])
def teachers(service:Ops,page:PageNo=1,page_size:Size=25,search:Search='',class_id:UUID|None=None):
    return service.teachers(page,page_size,search=search,class_id=class_id)
@router.get('/sunday-school/lessons',response_model=Page[LessonRow])
def lessons(service:Ops,page:PageNo=1,page_size:Size=25,search:Search='',class_id:UUID|None=None,view:Literal['ALL','DRAFT','PUBLISHED','ARCHIVED','UPCOMING','RECENT']='ALL'):
    return service.lesson_list(page,page_size,search=search,class_id=class_id,view=view)
@router.post('/sunday-school/lessons',response_model=LessonRow,status_code=201)
def create_lesson(service:Ops,body:LessonWrite):return service.save_lesson(body.model_dump())
@router.get('/sunday-school/lessons/{lesson_id}',response_model=LessonRow)
def lesson(service:Ops,lesson_id:UUID):return service.lesson(lesson_id)
@router.patch('/sunday-school/lessons/{lesson_id}',response_model=LessonRow)
def update_lesson(service:Ops,lesson_id:UUID,body:LessonWrite):return service.save_lesson(body.model_dump(),lesson_id)
@router.get('/sunday-school/attendance/sessions',response_model=Page[SchoolSessionRow])
def school_sessions(service:Ops,page:PageNo=1,page_size:Size=25,class_id:UUID|None=None,search:Search='',state:SchoolState='ALL',
    date_from:date|None=None,date_to:date|None=None):
    return service.school_sessions(page,page_size,class_id=class_id,search=search,state=state,date_from=date_from,date_to=date_to)
@router.post('/sunday-school/attendance/sessions',response_model=SchoolSessionDetail,status_code=201)
def create_school_attendance(service:Ops,body:CreateSchoolSession):return service.create_school_session(body.model_dump())
@router.get('/sunday-school/attendance/sessions/{session_id}',response_model=SchoolSessionDetail)
def school_session(service:Ops,session_id:UUID):return service.school_session(session_id)
@router.get('/sunday-school/attendance/sessions/{session_id}/roster',response_model=Page[RosterRow])
def school_roster(service:Ops,session_id:UUID,page:PageNo=1,page_size:Size=25,search:Search='',status:RosterStatus='ALL'):
    return service.school_roster(session_id,page,page_size,search=search,status=status)
@router.post('/sunday-school/attendance/sessions/{session_id}/mark',response_model=MarkResult)
def school_mark(service:Ops,session_id:UUID,body:MarkRequest):return service.school_mark(session_id,body.model_dump())
@router.post('/sunday-school/attendance/records/{record_id}/correct',response_model=MarkResult)
def school_correct(service:Ops,record_id:UUID,body:CorrectionRequest):return service.school_correct(record_id,body.model_dump())
@router.post('/sunday-school/attendance/sessions/{session_id}/{action}',response_model=SchoolSessionDetail)
def school_transition(service:Ops,session_id:UUID,action:Literal['open','close','reopen'],body:TransitionRequest):
    return service.school_transition(session_id,action,body.model_dump())
@router.get('/sunday-school/attendance/sessions/{session_id}/photo/{member_id}')
def school_photo(service:Ops,session_id:UUID,member_id:UUID):return Response(service.photo(session_id,member_id,True),media_type='image/jpeg')
@router.get('/sunday-school/reports/summary',response_model=SchoolDashboard)
def school_report_summary(service:Ops,class_id:UUID|None=None):return service.school_dashboard(class_id,True)
@router.get('/sunday-school/reports/attendance',response_model=Page[ReportRow])
def school_report(service:Ops,kind:Literal['classes','dates','students']='classes',page:PageNo=1,page_size:Size=25,
    class_id:UUID|None=None,start_date:date|None=None,end_date:date|None=None):
    return service.school_report(kind,page,page_size,class_id=class_id,start_date=start_date,end_date=end_date)

@router.get('/sunday-school/reports/attendance.csv')
def school_report_csv(service:Ops,kind:Literal['classes','dates','students']='classes',
    class_id:UUID|None=None,start_date:date|None=None,end_date:date|None=None):
    data=service.reports.online_attendance_csv(kind,class_id=class_id,start_date=start_date,end_date=end_date)
    return Response(data,media_type='text/csv',headers={'Content-Disposition':'attachment; filename="sunday-school-attendance.csv"'})
