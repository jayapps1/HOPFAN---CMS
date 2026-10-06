"""Sunday School domain and privacy rules in private PostgreSQL fixtures."""
from datetime import date,timedelta
import unittest
import uuid
from sqlalchemy import select,func,event,delete
from sqlalchemy.exc import IntegrityError
from tests import test_attendance as fixtures
from src.models import (Member,User,Role,Permission,SundaySchoolClass as SchoolClass,
    SundaySchoolEnrollment as Enrollment,SundaySchoolStudent as Student,SundaySchoolTeacherAssignment as Teacher,
    SundaySchoolGuardian as Guardian,SundaySchoolUserClassScope as ClassScope,SundaySchoolAttendanceSession as Session,
    SundaySchoolAttendanceRecord as Record,SundaySchoolRosterMember as Roster,SundaySchoolAuditLog as Audit,SundaySchoolLesson as Lesson)
from src.services.sunday_school_service import SundaySchoolService
from src.services.sunday_school_attendance_service import SundaySchoolAttendanceService
from src.services.sunday_school_lesson_service import SundaySchoolLessonService
from src.services.sunday_school_report_service import SundaySchoolReportService
from src.services.sunday_school_base import SundaySchoolError,SundaySchoolDenied,EnrollmentMoveRequired,AgeRangeWarning,today
from src.security.sunday_school_permissions import TEACHER_PERMISSIONS
from src.security.administration_permissions import PERMISSIONS as ADMIN_PERMISSIONS
from src.services.household_service import HouseholdService
from src.services.user_service import UserService


class SundaySchoolTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.AttendanceTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.AttendanceTests.tearDownClass.__func__)
    tearDown=fixtures.AttendanceTests.tearDown

    def setUp(self):
        fixtures.AttendanceTests.setUp(self)
        existing={row.code:row for row in self.db.scalars(select(Permission))}
        for code,name in ADMIN_PERMISSIONS.items():
            if code not in existing:
                existing[code]=Permission(code=code,name=name,module='Administration',is_active=True);self.db.add(existing[code])
        self.db.scalar(select(Role).where(Role.code=='TEST_ADMIN')).permissions=list(existing.values());self.db.commit()
        self.actor=self.users['Admin'].id
        self.service=SundaySchoolService(self.actor,self.factory)
        self.attendance=SundaySchoolAttendanceService(self.actor,self.factory)
        self.lessons=SundaySchoolLessonService(self.actor,self.factory)
        self.reports=SundaySchoolReportService(self.actor,self.factory)
        self.primary=self.service.create_class(dict(name='Primary',code='PRIMARY',minimum_age=4,maximum_age=12,capacity=30))
        self.other=self.service.create_class(dict(name='Juniors',code='JUNIORS',minimum_age=8,maximum_age=17))
        self.members['Ama'].date_of_birth=date(today().year-8,1,1)
        self.members['Yaw'].date_of_birth=date(today().year-9,1,1)
        self.db.commit()

    def enroll(self,member='Ama',school_class=None,**kwargs):
        return self.service.enroll_student((school_class or self.primary)['id'],self.members[member].id,**dict(dict(start_date=today()-timedelta(days=30)),**kwargs))

    def scoped_actor(self,classes=None,extra=()):
        permissions=self.db.scalars(select(Permission).where(Permission.code.in_(TEACHER_PERMISSIONS|set(extra)))).all()
        role=Role(code='TEST_SCHOOL_'+uuid.uuid4().hex[:8],name='School test '+uuid.uuid4().hex[:8],is_active=True,permissions=permissions)
        self.users['Youth'].roles=[role]
        self.db.add_all([ClassScope(user_id=self.users['Youth'].id,class_id=uuid.UUID(cls['id']),created_by_user_id=self.actor) for cls in (classes if classes is not None else [self.primary])])
        self.db.commit()
        return self.users['Youth'].id

    def test_master_identity_current_class_move_and_history(self):
        count=self.db.scalar(select(func.count()).select_from(Member))
        enrollment=self.enroll()
        with self.assertRaises(SundaySchoolError): self.enroll()
        with self.assertRaises(EnrollmentMoveRequired): self.enroll(school_class=self.other)
        moved=self.service.move_student(enrollment['id'],self.other['id'],today(),expected_updated_at=enrollment['updated_at'])
        student=self.service.get_student(self.members['Ama'].id)
        self.assertEqual(student['class_id'],self.other['id']); self.assertEqual(len(student['history']),2)
        self.assertEqual(sum(row['is_current'] for row in student['history']),1)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Member)),count)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Student)),1)

    def test_age_warning_capacity_and_failed_move_roll_back(self):
        enrollment=self.enroll()
        tiny=self.service.create_class(dict(name='Small',code='SMALL',maximum_age=3,capacity=1))
        with self.assertRaises(AgeRangeWarning): self.service.move_student(enrollment['id'],tiny['id'],today())
        self.assertEqual(self.service.get_student(self.members['Ama'].id)['class_id'],self.primary['id'])
        self.service.enroll_student(tiny['id'],self.members['Yaw'].id,allow_age_override=True)
        with self.assertRaisesRegex(SundaySchoolError,'capacity'): self.service.move_student(enrollment['id'],tiny['id'],today(),allow_age_override=True)
        self.assertEqual(self.service.get_student(self.members['Ama'].id)['class_id'],self.primary['id'])

    def test_teacher_identity_multiple_assignments_and_no_login_changes(self):
        before=self.db.scalar(select(func.count()).select_from(User))
        first=self.service.assign_teacher(self.primary['id'],self.members['Esi'].id)
        self.service.assign_teacher(self.primary['id'],self.members['Kofi'].id,'ASSISTANT_TEACHER')
        self.assertEqual(self.service.get_class(self.primary['id'])['teachers'],2)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(User)),before)
        with self.assertRaises(SundaySchoolError): self.service.assign_teacher(self.primary['id'],self.members['Esi'].id)
        self.service.end_teacher_assignment(first['id'],today())
        self.assertEqual(self.service.list_teachers(history=True)['total'],1)

    def test_class_scope_is_explicit_and_service_enforced(self):
        self.enroll(); self.enroll('Yaw',self.other)
        actor=self.scoped_actor()
        service=SundaySchoolService(actor,self.factory); attendance=SundaySchoolAttendanceService(actor,self.factory)
        self.assertEqual(service.list_classes()['total'],1); self.assertEqual(service.list_students()['total'],1)
        with self.assertRaises(SundaySchoolDenied): service.get_student(self.members['Yaw'].id)
        with self.assertRaises(SundaySchoolDenied): attendance.create_session(self.other['id'],today())
        with self.assertRaises(SundaySchoolDenied): service.create_class(dict(name='Forbidden',code='FORBIDDEN'))
        self.db.execute(delete(ClassScope).where(ClassScope.user_id==actor)); self.db.commit()
        self.service.assign_teacher(self.primary['id'],self.members['Esi'].id)
        self.assertEqual(service.list_classes()['total'],0)

    def test_scoped_move_requires_both_classes_and_no_master_directory_grant(self):
        enrollment=self.enroll()
        actor=self.scoped_actor(extra={'SUNDAY_SCHOOL_STUDENT_MOVE'})
        service=SundaySchoolService(actor,self.factory)
        with self.assertRaises(SundaySchoolDenied): service.move_student(enrollment['id'],self.other['id'],today())
        self.db.add(ClassScope(user_id=actor,class_id=uuid.UUID(self.other['id']))); self.db.commit()
        service.move_student(enrollment['id'],self.other['id'],today())
        self.assertEqual(service.get_student(self.members['Ama'].id)['class_id'],self.other['id'])

    def test_attendance_single_record_correction_preserves_original_marker(self):
        self.enroll(); session=self.attendance.create_session(self.primary['id'],today())
        first=self.attendance.mark(session['id'],self.members['Ama'].id,'ABSENT')
        self.assertEqual(self.attendance.mark(session['id'],self.members['Ama'].id,'ABSENT')['id'],first['id'])
        with self.assertRaises(SundaySchoolError): self.attendance.mark(session['id'],self.members['Ama'].id,'PRESENT')
        original=self.db.get(Record,uuid.UUID(first['id'])); marker,marked_at=original.marked_by_user_id,original.marked_at
        self.attendance.correct(first['id'],'PRESENT','Incorrect initial mark')
        self.db.expire_all(); original=self.db.get(Record,uuid.UUID(first['id']))
        self.assertEqual(original.marked_by_user_id,marker); self.assertEqual(original.marked_at,marked_at)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Record)),1)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Audit).where(Audit.action=='ATTENDANCE_CORRECTED')),1)

    def test_roster_freezes_and_close_only_marks_that_class_absent(self):
        enrollment=self.enroll(); self.enroll('Yaw',self.other)
        session=self.attendance.create_session(self.primary['id'],today())
        self.service.move_student(enrollment['id'],self.other['id'],today())
        self.enroll('Esi')
        self.attendance.close_session(session['id'])
        roster=self.attendance.get_roster(session['id'])
        self.assertEqual(roster['total'],1); self.assertEqual(roster['rows'][0]['member_id'],str(self.members['Ama'].id))
        self.assertEqual(roster['rows'][0]['status'],'ABSENT')
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Record)),1)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(fixtures.AttendanceRecord)),0)

    def test_database_unique_record_enrollment_and_roster_constraints(self):
        self.enroll(); session=self.attendance.create_session(self.primary['id'],today())
        self.attendance.mark(session['id'],self.members['Ama'].id,'PRESENT')
        values=dict(session_id=uuid.UUID(session['id']),member_id=self.members['Ama'].id,status='PRESENT')
        with self.assertRaises(IntegrityError):
            with self.db.begin_nested(): self.db.add(Record(**values)); self.db.flush()
        with self.assertRaises(IntegrityError):
            with self.db.begin_nested(): self.db.add(Record(**dict(values,member_id=self.members['Yaw'].id))); self.db.flush()
        with self.assertRaises(IntegrityError):
            with self.db.begin_nested():
                self.db.add(Enrollment(class_id=uuid.UUID(self.other['id']),member_id=self.members['Ama'].id,class_name='Other',class_code='OTHER',start_date=today())); self.db.flush()

    def test_guardian_contacts_live_household_suggestions_and_consent(self):
        family=HouseholdService(self.actor,self.factory).create_household(dict(household_name='Test family'))
        households=HouseholdService(self.actor,self.factory)
        households.add_member(family['id'],self.members['Ama'].id,'CHILD')
        households.add_member(family['id'],self.members['Esi'].id,'HEAD')
        self.members['Esi'].phone='0549911000'; self.db.commit(); self.enroll()
        self.assertEqual(self.service.get_student(self.members['Ama'].id)['guardian_name'],'')
        self.assertEqual(self.service.guardian_candidates(self.members['Ama'].id)['rows'][0]['member_id'],str(self.members['Esi'].id))
        self.service.set_guardian(self.members['Ama'].id,self.members['Esi'].id,'GUARDIAN',is_primary=True)
        self.assertEqual(self.service.list_students(search='0549911000')['total'],1)
        self.assertEqual(self.service.resolve_recipients(),[])
        self.service.set_guardian(self.members['Ama'].id,self.members['Esi'].id,'GUARDIAN',is_primary=True,can_receive_sms=True)
        self.members['Esi'].phone='0549922000'; self.db.commit()
        self.assertEqual(self.service.get_student(self.members['Ama'].id)['guardian_phone'],'0549922000')
        self.assertEqual(self.service.resolve_recipients()[0]['phone'],'0549922000')

    def test_lessons_multi_class_and_partial_scope_edit_denied(self):
        lesson=self.lessons.create_lesson(dict(title='Test lesson',lesson_date=today(),status='PUBLISHED'),[self.primary['id'],self.other['id']])
        actor=self.scoped_actor(extra={'SUNDAY_SCHOOL_LESSON_EDIT'})
        lessons=SundaySchoolLessonService(actor,self.factory)
        self.assertEqual(lessons.list_lessons()['total'],1)
        with self.assertRaises(SundaySchoolDenied): lessons.update_lesson(lesson['id'],dict(title='No',lesson_date=today()),[self.primary['id']])
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Lesson)),1)
        session=self.attendance.create_session(self.primary['id'],today(),lesson_id=lesson['id'])
        with self.assertRaises(SundaySchoolError): self.lessons.update_lesson(lesson['id'],dict(title='Changed',lesson_date=today()+timedelta(days=1)),[self.primary['id'],self.other['id']])

    def test_planned_sessions_open_later_and_closed_teacher_correction_denied(self):
        self.enroll(); future=self.attendance.create_session(self.other['id'],today()+timedelta(days=1),open_now=False)
        with self.assertRaises(SundaySchoolError): self.attendance.open_session(future['id'])
        session=self.attendance.create_session(self.primary['id'],today()); self.attendance.close_session(session['id'])
        record=self.attendance.get_roster(session['id'])['rows'][0]
        actor=self.scoped_actor(); attendance=SundaySchoolAttendanceService(actor,self.factory)
        with self.assertRaises(SundaySchoolDenied): attendance.correct(record['record_id'],'PRESENT','Test')
        with self.assertRaises(SundaySchoolDenied): attendance.reopen_session(session['id'],'Test')

    def test_reports_counts_rates_unassigned_and_csv(self):
        self.enroll(); self.service.register_student(self.members['Esi'].id)
        session=self.attendance.create_session(self.primary['id'],today())
        self.attendance.mark(session['id'],self.members['Ama'].id,'LATE'); self.attendance.close_session(session['id'])
        self.assertEqual(self.reports.report('students')['rows'][0]['rate'],100)
        self.assertEqual(self.reports.report('unassigned')['total'],1)
        self.assertIn('class_name',self.reports.export_csv())
        dashboard=self.reports.dashboard(); self.assertEqual(dashboard['students'],2); self.assertEqual(dashboard['rate'],100)

    def test_class_directory_query_count_constant_and_sensitive_notes_hidden(self):
        self.enroll(); self.service.update_student(self.members['Ama'].id,special_notes='Private admission note')
        calls=[]
        def counted(*_args): calls.append(1)
        event.listen(self.connection,'before_cursor_execute',counted); self.service.list_classes(); before=len(calls)
        event.remove(self.connection,'before_cursor_execute',counted)
        for index in range(20): self.service.create_class(dict(name='Configured '+str(index),code='CONFIGURED_'+str(index)))
        calls.clear(); event.listen(self.connection,'before_cursor_execute',counted)
        try: self.service.list_classes(); self.assertEqual(len(calls),before)
        finally: event.remove(self.connection,'before_cursor_execute',counted)
        actor=self.scoped_actor(); service=SundaySchoolService(actor,self.factory)
        self.assertEqual(service.get_student(self.members['Ama'].id)['special_notes'],'')
        self.assertNotIn('Private admission note',str(self.db.scalars(select(Audit)).all()))

    def test_account_class_scopes_and_profile_integration_are_explicit(self):
        self.enroll();self.service.assign_teacher(self.primary['id'],self.members['Esi'].id)
        account=UserService(self.actor,self.factory)
        actor=self.scoped_actor(classes=[])
        before=self.users['Youth'].auth_revision
        account.update_access(actor,class_ids=[self.primary['id']])
        self.db.refresh(self.users['Youth']);self.assertGreater(self.users['Youth'].auth_revision,before)
        self.assertEqual(account.get_user(actor)['school_scopes'][0]['id'],self.primary['id'])
        self.assertEqual(SundaySchoolService(actor,self.factory).list_classes()['total'],1)
        from src.services.member_service import MemberService
        profile=MemberService(self.actor,self.factory).get_member(self.members['Ama'].id)
        self.assertEqual(profile['sunday_school']['class_id'],self.primary['id'])
        self.assertTrue(profile['sunday_school']['class_teachers'])
        options=account.access_options(actor);self.assertEqual(len(options['school_classes']),2)


if __name__=='__main__': unittest.main()
