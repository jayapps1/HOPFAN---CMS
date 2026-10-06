"""Read projections over shared desktop services; no second business store."""
from contextlib import contextmanager
from math import ceil
from src.services.member_service import MemberService
from src.services.ministry_service import MinistryService
from src.services.ministry_leadership_service import MinistryLeadershipService
from src.services.sunday_school_report_service import SundaySchoolReportService
from src.services.web_security import WebSecurityError

DENIED = ("ACCESS_DENIED", "Access to this resource is denied.")

class OnlineWorkspaceService:
    def __init__(self, db, principal):
        self.db, self.access = db, principal.authorization
        @contextmanager
        def borrowed():
            yield db
        self.members = MemberService(principal.user.id, borrowed)
        self.ministries = MinistryService(principal.user.id, borrowed)
        self.leaders = MinistryLeadershipService(principal.user.id, borrowed)
        self.school = SundaySchoolReportService(principal.user.id, borrowed)

    def allowed(self, ministry_id, permission):
        return self.access.can_access_ministry(ministry_id, permission,
            include_inactive=permission!='MEMBERS_VIEW_OWN_MINISTRY')

    def require(self, ministry_id, permission):
        if not self.allowed(ministry_id, permission):
            raise WebSecurityError(403, *DENIED)

    @staticmethod
    def page(result, page, page_size, project):
        total = result['total']
        return dict(items=[project(row) for row in result['rows']], page=page,
                    page_size=page_size, total=total, pages=ceil(total/page_size))

    def member_row(self, row):
        ministries = [dict(id=mid, name=name) for mid,name in zip(row['ministry_ids'],row['ministries'])
                      if self.access.has('MEMBERS_VIEW_ALL') or self.allowed(mid,'MEMBERS_VIEW_OWN_MINISTRY')]
        return dict(id=row['id'], member_no=row['member_no'], full_name=row['full_name'],
            gender=row['gender'], phone=row['phone'], status=row['status'], ministries=ministries,
            photo_url=f"/api/v1/media/member-photo/{row['id']}" if row['photo_path'] else None)

    @staticmethod
    def leadership_row(row):
        keys=('id','ministry_id','ministry_name','member_id','full_name','member_no',
              'position_id','position_name','position_code','is_leadership','is_current','start_date','end_date')
        return {key:row[key] for key in keys}

    def member_options(self):
        # This metadata permission follows the member directory, allowing a
        # global member reader to filter without granting ministry administration.
        self.members.stats()
        return [dict(id=row['id'],name=row['name']) for row in self.members.list_ministries()]

    def list_members(self, search='', status='ALL', ministry_id=None, page=1, page_size=25, sort='name', direction='asc'):
        if ministry_id: self.require(ministry_id,'MEMBERS_VIEW_OWN_MINISTRY')
        result=self.members.list_members_page(search=search,status=status,ministry_id=ministry_id,
            limit=page_size,offset=(page-1)*page_size,sort=sort,descending=direction=='desc')
        return self.page(result,page,page_size,self.member_row)

    def member_detail(self, member_id):
        row=self.members.get_member(member_id)
        result=self.member_row(row)
        result.update(identity={key:row[key] for key in ('first_name','middle_name','last_name','date_of_birth','marital_status')},
            contact={key:row[key] for key in ('phone','alternate_phone','email','address')},
            membership={key:row[key] for key in ('date_joined','baptized','baptism_date')})
        if self.access.has_any({'MINISTRY_LEADERSHIP_VIEW','MINISTRY_LEADERSHIP_VIEW_ALL'}):
            result['leadership']=[self.leadership_row(item) for item in row['leadership']]
        if row.get('household'):
            result['household']={key:row['household'][key] for key in ('id','household_name','household_code','status','relationship_label')}
        if row.get('sunday_school'):
            school=row['sunday_school']
            result['sunday_school']={key:school[key] for key in ('student','teachers','class_id','class_name','status') if key in school}
        return result

    def ministry_row(self, row):
        result={key:row[key] for key in ('id','code','name','description','category','status')}
        visible=self.allowed(row['id'],'MEMBERS_VIEW_OWN_MINISTRY')
        result.update(member_count=row['member_count'] if visible else None,
                      active_member_count=row['active_member_count'] if visible else None)
        return result

    def list_ministries(self, search='',status='ALL',category='ALL',page=1,page_size=25,ministry_id=None):
        if ministry_id: self.require(ministry_id,'MINISTRIES_VIEW_OWN')
        result=self.ministries.list_ministries(search,status,category,page_size,(page-1)*page_size,ministry_id=ministry_id)
        return self.page(result,page,page_size,self.ministry_row)

    def ministry_detail(self, ministry_id):
        self.require(ministry_id,'MINISTRIES_VIEW_OWN')
        row=self.ministries.get_ministry(ministry_id,include_dependencies=False)
        result=self.ministry_row(row)
        leadership=self.allowed(ministry_id,'MINISTRY_LEADERSHIP_VIEW')
        result.update(can_view_members=self.allowed(ministry_id,'MEMBERS_VIEW_OWN_MINISTRY'),
            can_view_leadership=leadership,
            leadership=self.leaders.leadership_stats(ministry_id) if leadership else None)
        return result

    def ministry_members(self, ministry_id, **filters):
        self.require(ministry_id,'MINISTRIES_VIEW_OWN')
        self.ministries.get_ministry(ministry_id,include_dependencies=False)
        return self.list_members(ministry_id=ministry_id,**filters)

    def leadership(self, ministry_id, page=1,page_size=25):
        self.require(ministry_id,'MINISTRIES_VIEW_OWN')
        self.require(ministry_id,'MINISTRY_LEADERSHIP_VIEW')
        result=self.leaders.list_leadership(ministry_id,status='CURRENT',limit=page_size,offset=(page-1)*page_size)
        return self.page(result,page,page_size,self.leadership_row)

    def dashboard(self, ministry_id=None, class_id=None):
        metrics=[]; recent=[]; unavailable=[]
        def metric(key,label,value,detail=''):
            metrics.append(dict(key=key,label=label,value=value,detail=detail))
        if ministry_id:
            # A requested workspace must be explicitly visible under at least
            # one real scoped capability. Each metric below has its own check.
            if not any(self.allowed(ministry_id,p) for p in ('MEMBERS_VIEW_OWN_MINISTRY','MINISTRIES_VIEW_OWN','ATTENDANCE_VIEW_OWN_MINISTRY')):
                raise WebSecurityError(403,*DENIED)
        member_access=self.access.has('MEMBERS_VIEW_ALL') or bool(self.access.ministry_ids('MEMBERS_VIEW_OWN_MINISTRY'))
        if member_access and (not ministry_id or self.allowed(ministry_id,'MEMBERS_VIEW_OWN_MINISTRY')) and not class_id:
            counts=self.members.stats(ministry_id,include_recent=True)
            metric('members','Members',counts['total']);metric('active_members','Active members',counts['active'])
            metric('new_members','New members',counts['recent'],'Added in the last 30 days')
            recent=self.list_members(ministry_id=ministry_id,page_size=5,sort='created_date',direction='desc')['items']
        else: unavailable.append('Member summaries')
        ministry_access=self.access.has('MINISTRIES_VIEW_ALL') or bool(self.access.ministry_ids('MINISTRIES_VIEW_OWN',include_inactive=True))
        if ministry_access and (not ministry_id or self.allowed(ministry_id,'MINISTRIES_VIEW_OWN')) and not class_id:
            counts=self.ministries.get_ministry_stats(ministry_id)
            metric('active_ministries','Active ministries',counts['active'])
            if ministry_id and self.allowed(ministry_id,'MINISTRY_LEADERSHIP_VIEW'):
                leaders=self.leaders.leadership_stats(ministry_id)
                metric('appointments','Current appointments',leaders['current'])
                metric('vacancies','Vacant positions',leaders['vacant'])
        else: unavailable.append('Ministry summaries')
        if not ministry_id and self.access.has('SUNDAY_SCHOOL_CLASS_VIEW') and self.access.has_any({'SUNDAY_SCHOOL_VIEW','SUNDAY_SCHOOL_VIEW_ALL'}):
            data=self.school.dashboard(class_id)
            metric('classes','Sunday School classes',data['classes'])
            if data['students'] is not None:metric('students','Active Sunday School students',data['students'])
            if data['teachers'] is not None:metric('teachers','Sunday School teachers',data['teachers'])
            if data['rate'] is not None:metric('school_attendance','School attendance rate',data['rate'],'Last 30 days (%)')
        else:
            if class_id: raise WebSecurityError(403,*DENIED)
            unavailable.append('Sunday School summaries')
        attendance_access=self.access.has('ATTENDANCE_VIEW_ALL') or bool(self.access.ministries('view'))
        if not class_id and attendance_access and (not ministry_id or self.allowed(ministry_id,'ATTENDANCE_VIEW_OWN_MINISTRY')):
            from src.services.attendance_service import AttendanceService
            attendance=AttendanceService(self.access.user_id,self.members.session_factory)
            if ministry_id:
                data=attendance.list_sessions(ministry_id=ministry_id,limit=1)
                metric('attendance_sessions','Visible attendance sessions',data['total'],'Includes permitted shared church services')
                sunday=attendance.list_sessions(ministry_id=ministry_id,section='SUNDAY',state='CLOSED',limit=1)
                if sunday['rows']:
                    row=sunday['rows'][0]
                    metric('sunday_attendance','Latest closed Sunday attendance',
                        row['stats']['PRESENT']+row['stats']['LATE'],str(row['session_date']))
            else:
                data=attendance.overview()
                metric('attendance_today','Attendance sessions today',data['today'])
                metric('attendance_open','Open attendance sessions',data['open'])
                if data['sunday']['date'] is not None:
                    metric('sunday_attendance','Latest Sunday attendance',data['sunday']['count'],str(data['sunday']['date']))
        else: unavailable.append('Attendance summaries')
        return dict(scope=str(class_id or ministry_id or 'all'),metrics=metrics,recent_members=recent,unavailable=unavailable)
