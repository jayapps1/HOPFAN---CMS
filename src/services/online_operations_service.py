"""Authorized operational projections over existing attendance/school services."""
from contextlib import contextmanager
from src.models import AttendanceSessionType
from src.services.attendance_service import AttendanceService
from src.services.sunday_school_service import SundaySchoolService
from src.services.sunday_school_attendance_service import SundaySchoolAttendanceService
from src.services.sunday_school_lesson_service import SundaySchoolLessonService
from src.services.sunday_school_report_service import SundaySchoolReportService
from src.services.online_workspace_service import OnlineWorkspaceService
from src.services.web_security import WebSecurityError

class OnlineOperationsService:
    def __init__(self,db,principal):
        self.db,self.access=db,principal.authorization
        @contextmanager
        def borrowed():yield db
        self.attendance=AttendanceService(principal.user.id,borrowed)
        self.school=SundaySchoolService(principal.user.id,borrowed)
        self.school_attendance=SundaySchoolAttendanceService(principal.user.id,borrowed)
        self.lessons=SundaySchoolLessonService(principal.user.id,borrowed)
        self.reports=SundaySchoolReportService(principal.user.id,borrowed)

    page=staticmethod(OnlineWorkspaceService.page)
    @staticmethod
    def stats(row,school=False):
        return dict(eligible=row['eligible'],present=row['present' if school else 'PRESENT'],
            late=row['late' if school else 'LATE'],excused=row['excused' if school else 'EXCUSED'],
            absent=row['absent' if school else 'ABSENT'],unmarked=row['unmarked'],rate=row['rate'])
    def session_row(self,row):
        keys=('id','title','session_date','state','updated_at','session_type','scope_type','ministry_id','ministry_name')
        result={key:row[key] for key in keys}
        if 'stats' in row:result['stats']=self.stats(row['stats'])
        return result
    def roster_row(self,row,session_id,school=False):
        mid=row['member_id'] if school else row['id']
        return dict(id=mid,full_name=row['full_name'],member_no=row['member_no'],record_id=row['record_id'],
            status=row['status' if school else 'attendance_status'],updated_at=row['updated_at'],
            marked_at=row['marked_at'],marked_by=row['marked_by'],
            photo_url=f"/api/v1/{'sunday-school/attendance' if school else 'attendance'}/sessions/{session_id}/photo/{mid}" if row['photo_path'] else None,
            can_mark=row['can_mark'] if school else row['can_record'] and not row['attendance_status'],
            can_correct=row['can_correct'] if school else row['can_correct'] and bool(row['attendance_status']))
    def attendance_options(self):
        caps=self.attendance.capabilities()
        if not caps['can_view']:raise WebSecurityError(403,'ACCESS_DENIED','Access to this resource is denied.')
        return dict(can_create=caps['can_create'],can_create_global=self.access.has('ATTENDANCE_CREATE_GLOBAL'),
            ministries=self.attendance.list_ministries(),create_ministries=self.attendance.list_ministries('create'),
            session_types=[item.value for item in AttendanceSessionType],
            statuses=list(self.school_attendance.STATUSES))
    def list_sessions(self,page=1,page_size=25,**filters):
        return self.page(self.attendance.list_sessions(limit=page_size,offset=(page-1)*page_size,**filters),page,page_size,self.session_row)
    def session(self,session_id,ministry_id=None):
        row=self.attendance.get_session(session_id)
        result=self.session_row(row);result.update(description=row['description'],actions=row['actions'],
            stats=self.stats(self.attendance.session_counts(session_id,ministry_id)))
        return result
    def roster(self,session_id,page=1,page_size=25,**filters):
        rows=self.attendance.roster(session_id,limit=page_size,offset=(page-1)*page_size,**filters)
        return self.page(rows,page,page_size,lambda row:self.roster_row(row,session_id))
    def main_result(self,session_id,member_id,ministry_id=None):
        result=self.attendance.roster(session_id,member_id=member_id,ministry_id=ministry_id,limit=1)
        if not result['rows']:raise WebSecurityError(403,'ACCESS_DENIED','Access to this resource is denied.')
        return dict(row=self.roster_row(result['rows'][0],session_id),summary=self.stats(result['stats']))
    def create_session(self,data):
        if not self.attendance.capabilities()['can_view']:raise WebSecurityError(403,'ACCESS_DENIED','Access to this resource is denied.')
        row=self.attendance.create_session(**data)
        return self.session(row['id'])
    def mark(self,session_id,data,ministry_id=None):
        self.attendance.mark(session_id,**data,ministry_id=ministry_id)
        return self.main_result(session_id,data['member_id'],ministry_id)
    def correct(self,record_id,data,ministry_id=None):
        if data.get('expected_status') is None:raise WebSecurityError(422,'VALIDATION_ERROR','The request contains invalid data.')
        ids=self.attendance.correct_record(record_id,**data,ministry_id=ministry_id)
        return self.main_result(*ids,ministry_id=ministry_id)
    def transition(self,session_id,action,data):
        self.attendance.transition(session_id,action,**data)
        return self.session(session_id)
    def summary(self,session_id,ministry_id=None):
        return self.stats(self.attendance.session_counts(session_id,ministry_id))
    def class_row(self,row):
        keys=('id','name','code','description','minimum_age','maximum_age','room_location','capacity','status')
        return dict(**{key:row[key] for key in keys},
            students=row['students'] if self.access.has('SUNDAY_SCHOOL_STUDENT_VIEW') else None,
            teachers=row['teachers'] if self.access.has('SUNDAY_SCHOOL_TEACHER_VIEW') else None)
    def classes(self,page=1,page_size=25,**filters):
        return self.page(self.school.list_classes(limit=page_size,offset=(page-1)*page_size,**filters),page,page_size,self.class_row)
    def class_detail(self,class_id):return self.class_row(self.school.get_class(class_id))
    def class_options(self,page=1,page_size=100):
        return self.page(self.school.class_options(limit=page_size,offset=(page-1)*page_size),page,page_size,
            lambda row:dict(id=row['id'],name=row['name']))
    def student_row(self,row):
        result={key:row[key] for key in ('id','member_id','full_name','member_no','age','status','class_id','class_name')}
        if self.access.has('SUNDAY_SCHOOL_GUARDIAN_VIEW'):
            result['guardians']=[{key:contact[key] for key in ('full_name','relationship','phone','can_receive_sms')} for contact in row['guardians']]
        return result
    def students(self,page=1,page_size=25,**filters):
        return self.page(self.school.list_students(limit=page_size,offset=(page-1)*page_size,**filters),page,page_size,self.student_row)
    def student(self,member_id):
        row=self.school.get_student(member_id);result=self.student_row(row)
        result.update(history=[{key:item[key] for key in ('class_id','class_name','start_date','end_date','is_current')} for item in row['history']],
            attendance_rate=row['attendance_rate'])
        return result
    def teachers(self,page=1,page_size=25,**filters):
        keys=('id','member_id','full_name','member_no','class_id','class_name','role_label','start_date','end_date')
        return self.page(self.school.list_teachers(limit=page_size,offset=(page-1)*page_size,**filters),page,page_size,
            lambda row:{key:row[key] for key in keys})
    @staticmethod
    def lesson_row(row):
        keys=('id','title','lesson_date','topic','scripture_reference','objective','lesson_summary','teacher_notes','status','applies_to_all','classes','updated_at','can_edit')
        return {key:row[key] for key in keys}
    def lesson_list(self,page=1,page_size=25,**filters):
        return self.page(self.lessons.list_lessons(limit=page_size,offset=(page-1)*page_size,**filters),page,page_size,self.lesson_row)
    def lesson(self,lesson_id):return self.lesson_row(self.lessons.get_lesson(lesson_id))
    def save_lesson(self,data,lesson_id=None):
        self.access.require_permission('SUNDAY_SCHOOL_LESSON_VIEW')
        class_ids=data.pop('class_ids');all_classes=data.pop('all_classes');version=data.pop('expected_updated_at',None)
        if lesson_id:
            if version is None:raise WebSecurityError(422,'VALIDATION_ERROR','The request contains invalid data.')
            return self.lesson_row(self.lessons.update_lesson(lesson_id,data,class_ids,all_classes,version))
        else:
            lesson_id=self.lessons.create_lesson(data,class_ids,all_classes)['id']
        return self.lesson(lesson_id)
    @staticmethod
    def school_session_row(row):
        result={key:row[key] for key in ('id','title','class_id','class_name','lesson_title','session_date','state','updated_at')}
        result['eligible']=row.get('eligible',row.get('stats',{}).get('eligible',0))
        return result
    def school_sessions(self,page=1,page_size=25,**filters):
        return self.page(self.school_attendance.list_sessions(limit=page_size,offset=(page-1)*page_size,**filters),page,page_size,self.school_session_row)
    def school_session(self,session_id):
        row=self.school_attendance.get_session(session_id,include_teachers=False)
        return dict(self.school_session_row(row),stats=self.stats(row['stats'],True),actions=row['actions'])
    def create_school_session(self,data):
        self.access.require_permission('SUNDAY_SCHOOL_ATTENDANCE_VIEW')
        row=self.school_attendance.create_session(**data)
        return self.school_session(row['id'])
    def school_roster(self,session_id,page=1,page_size=25,**filters):
        result=self.school_attendance.get_roster(session_id,limit=page_size,offset=(page-1)*page_size,**filters)
        return self.page(result,page,page_size,lambda row:self.roster_row(row,session_id,True))
    def school_result(self,session_id,member_id):
        row=self.school_attendance.get_roster(session_id,member_id=member_id,limit=1)['rows'][0]
        return dict(row=self.roster_row(row,session_id,True),summary=self.school_session(session_id)['stats'])
    def school_mark(self,session_id,data):
        self.school_attendance.mark(session_id,**data)
        return self.school_result(session_id,data['member_id'])
    def school_correct(self,record_id,data):
        data.pop('expected_status',None)
        row=self.school_attendance.correct(record_id,**data)
        return self.school_result(row['session_id'],row['member_id'])
    def school_transition(self,session_id,action,data):
        if action=='reopen':self.school_attendance.reopen_session(session_id,**data)
        else:
            data.pop('reason',None)
            getattr(self.school_attendance,action+'_session')(session_id,**data)
        return self.school_session(session_id)
    def school_dashboard(self,class_id=None,report=False):
        if report:self.access.require_permission('SUNDAY_SCHOOL_REPORT_VIEW')
        row=self.reports.dashboard(class_id)
        return {key:row[key] for key in ('classes','active_classes','students','teachers','present_last_sunday','rate')}
    def school_report(self,kind='classes',page=1,page_size=25,**filters):
        return self.page(self.reports.online_attendance_report(kind,limit=page_size,offset=(page-1)*page_size,**filters),
            page,page_size,lambda row:row)
    def photo(self,session_id,member_id,school=False):
        from src.services.member_photo_service import safe_photo
        rows=self.school_attendance.get_roster(session_id,member_id=member_id,limit=1) if school else self.attendance.roster(session_id,member_id=member_id,limit=1)
        if not rows['rows']:raise WebSecurityError(403,'ACCESS_DENIED','Access to this resource is denied.')
        return safe_photo(rows['rows'][0]['photo_path'])
