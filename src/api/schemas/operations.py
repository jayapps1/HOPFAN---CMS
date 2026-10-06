"""Explicit online operational contracts; no ORM/private child-field dumps."""
from datetime import date
from typing import Literal
from uuid import UUID
from pydantic import AwareDatetime, Field, model_validator
from src.api.schemas.common import ApiResponse
from src.api.schemas.workspace import MinistrySummary

Status=Literal['PRESENT','LATE','EXCUSED','ABSENT']
SessionType=Literal['SUNDAY_SERVICE','MINISTRY_MEETING','SUNDAY_SCHOOL','SPECIAL_EVENT','PRAYER_MEETING','CHURCH_MEETING','LEADERSHIP_MEETING','OTHER']
class Stats(ApiResponse):
    eligible:int
    present:int
    late:int
    excused:int
    absent:int
    unmarked:int
    rate:float|None
class SessionRow(ApiResponse):
    id:str
    title:str
    session_date:date
    state:str
    updated_at:AwareDatetime
    session_type:str
    scope_type:str
    ministry_id:str|None
    ministry_name:str
    stats:Stats|None=None
class SessionDetail(SessionRow):
    description:str
    actions:dict[str,bool]
class RosterRow(ApiResponse):
    id:str
    member_no:str
    full_name:str
    photo_url:str|None
    record_id:str|None
    status:Status|None
    updated_at:AwareDatetime|None
    marked_at:AwareDatetime|None
    marked_by:str
    can_mark:bool
    can_correct:bool
class MarkResult(ApiResponse):
    row:RosterRow
    summary:Stats
class CreateSession(ApiResponse):
    title:str=Field(min_length=1,max_length=150)
    description:str=Field(default='',max_length=10000)
    session_type:SessionType
    scope_type:Literal['GLOBAL','MINISTRY']
    ministry_id:UUID|None=None
    session_date:date
    state:Literal['DRAFT','OPEN']='OPEN'
    @model_validator(mode='after')
    def valid_scope(self):
        if self.session_type=='SUNDAY_SERVICE' and (self.scope_type!='GLOBAL' or self.ministry_id):
            raise ValueError('Sunday Service uses a global roster.')
        if self.session_type=='MINISTRY_MEETING' and self.scope_type!='MINISTRY':
            raise ValueError('A ministry meeting needs a ministry.')
        if (self.scope_type=='MINISTRY')!=bool(self.ministry_id):raise ValueError('Invalid ministry scope.')
        return self
class MarkRequest(ApiResponse):
    member_id:UUID
    status:Status
class CorrectionRequest(ApiResponse):
    status:Status
    reason:str=Field(min_length=1,max_length=1000)
    expected_updated_at:AwareDatetime
    expected_status:Status|None=None
    @model_validator(mode='after')
    def reason_required(self):
        if not self.reason.strip():raise ValueError('Enter a correction reason.')
        return self
class TransitionRequest(ApiResponse):
    expected_updated_at:AwareDatetime
    reason:str=Field(default='',max_length=1000)
class SchoolSessionRow(ApiResponse):
    id:str
    title:str
    class_id:str
    class_name:str
    lesson_title:str
    session_date:date
    state:str
    eligible:int=0
    updated_at:AwareDatetime
class SchoolSessionDetail(SchoolSessionRow):
    stats:Stats
    actions:dict[str,bool]
class CreateSchoolSession(ApiResponse):
    class_id:UUID
    session_date:date
    title:str=Field(default='',max_length=200)
    lesson_id:UUID|None=None
    open_now:bool=True
class ClassRow(ApiResponse):
    id:str
    name:str
    code:str
    description:str
    minimum_age:int|None
    maximum_age:int|None
    room_location:str
    capacity:int|None
    status:str
    students:int|None
    teachers:int|None
class Guardian(ApiResponse):
    full_name:str
    relationship:str
    phone:str
    can_receive_sms:bool
class StudentRow(ApiResponse):
    id:str
    member_id:str
    full_name:str
    member_no:str
    age:int|None
    status:str
    class_id:str|None
    class_name:str
    guardians:list[Guardian]|None=None
class Enrollment(ApiResponse):
    class_id:str
    class_name:str
    start_date:date
    end_date:date|None
    is_current:bool
class StudentDetail(StudentRow):
    history:list[Enrollment]
    attendance_rate:float|None
class TeacherRow(ApiResponse):
    id:str
    member_id:str
    full_name:str
    member_no:str
    class_id:str
    class_name:str
    role_label:str
    start_date:date
    end_date:date|None
class LessonRow(ApiResponse):
    id:str
    title:str
    lesson_date:date
    topic:str
    scripture_reference:str
    objective:str
    lesson_summary:str
    teacher_notes:str
    status:str
    applies_to_all:bool
    classes:list[MinistrySummary]
    updated_at:AwareDatetime
    can_edit:bool=False
class LessonWrite(ApiResponse):
    title:str=Field(min_length=1,max_length=200)
    lesson_date:date
    topic:str=Field(default='',max_length=200)
    scripture_reference:str=Field(default='',max_length=200)
    objective:str=Field(default='',max_length=10000)
    lesson_summary:str=Field(default='',max_length=10000)
    teacher_notes:str=Field(default='',max_length=10000)
    status:Literal['DRAFT','PUBLISHED','ARCHIVED']='DRAFT'
    class_ids:list[UUID]=Field(default_factory=list,max_length=100)
    all_classes:bool=False
    expected_updated_at:AwareDatetime|None=None
class SchoolDashboard(ApiResponse):
    classes:int
    active_classes:int
    students:int|None
    teachers:int|None
    present_last_sunday:int|None
    rate:float|None
class ReportRow(ApiResponse):
    id:str
    label:str
    member_no:str|None=None
    eligible:int
    present:int
    late:int
    excused:int
    absent:int
    rate:float|None
