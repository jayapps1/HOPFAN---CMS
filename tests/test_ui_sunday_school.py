"""Sunday School UI against synthetic data committed only in a private schema."""
from datetime import date,timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import re
import gc
import unittest
import uuid
import customtkinter as ctk
from PIL import ImageGrab
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema,DropSchema
from tests import test_ui_smoke as smoke
from src.config.database import engine
from src.database.base import Base
from src.models import Member,MemberStatus,User,UserStatus,Role,Permission,SundaySchoolUserClassScope
from src.security.application_permissions import PERMISSIONS as APP
from src.security.attendance_permissions import PERMISSIONS as ATT
from src.security.administration_permissions import PERMISSIONS as ADMIN
from src.security.sunday_school_permissions import TEACHER_PERMISSIONS
from src.services.sunday_school_service import SundaySchoolService
from src.services.sunday_school_attendance_service import SundaySchoolAttendanceService
from src.services.sunday_school_lesson_service import SundaySchoolLessonService
from src.services.sunday_school_report_service import SundaySchoolReportService
from src.services.household_service import HouseholdService
from src.services.member_service import MemberService
from src.services.user_service import UserService
from src.ui.sunday_school.workspace import SundaySchoolWorkspace,SchoolClasses,SchoolStudents,SchoolLessons,SchoolTeachers,SchoolAttendance,SchoolReports,SchoolRosterDialog
from src.ui.sunday_school.dialogs import ClassFormDialog,EnrollStudentDialog,AssignTeacherDialog,LessonFormDialog,CreateSchoolAttendanceDialog
from src.ui.components.modern import ConfirmationDialog
from src.ui.administration.dialogs import UserAccessDialog


class SundaySchoolUiTests(unittest.TestCase):
    pump=smoke.UiSmokeTests.pump
    wait_for=smoke.UiSmokeTests.wait_for
    assert_visible_in=smoke.UiSmokeTests.assert_visible_in

    @classmethod
    def setUpClass(cls):
        cls.gc_was_enabled=gc.isenabled();gc.disable()
        smoke.UiSmokeTests.setUpClass.__func__(cls)
        cls.schema='hcms_school_ui_'+uuid.uuid4().hex
        cls.test_engine=engine.execution_options(schema_translate_map={None:cls.schema})
        with engine.begin() as connection:connection.execute(CreateSchema(cls.schema))
        Base.metadata.create_all(cls.test_engine)
        cls.factory=sessionmaker(bind=cls.test_engine,expire_on_commit=False)

    @classmethod
    def tearDownClass(cls):
        gc.collect()
        smoke.UiSmokeTests.tearDownClass.__func__(cls)
        assert re.fullmatch(r'hcms_school_ui_[a-f0-9]{32}',cls.schema)
        with engine.begin() as connection:connection.execute(DropSchema(cls.schema,cascade=True))
        gc.collect()
        if cls.gc_was_enabled:gc.enable()

    def setUp(self):
        smoke.UiSmokeTests.setUp(self)
        with self.test_engine.begin() as connection:
            for table in reversed(Base.metadata.sorted_tables):connection.execute(table.delete())
        with self.factory() as db:
            permissions={code:Permission(code=code,name=name,module='Sunday School' if code.startswith('SUNDAY_SCHOOL') else 'Test',is_active=True) for code,name in (APP|ATT|ADMIN).items()}
            db.add_all(permissions.values())
            admin_role=Role(code='UI_ADMIN',name='Synthetic administrator',is_active=True,permissions=list(permissions.values()))
            teacher_role=Role(code='UI_TEACHER',name='Synthetic teacher',is_active=True,permissions=[permissions[code] for code in TEACHER_PERMISSIONS])
            db.add_all([admin_role,teacher_role])
            self.members=[Member(member_no=f'PREVIEW-SS-{index+1:04d}',first_name=f'Student {index+1}',last_name='Synthetic',date_of_birth=date(2018,1,1),status=MemberStatus.ACTIVE,baptized=False) for index in range(30)]
            self.teacher=Member(member_no='PREVIEW-TEACHER',first_name='Ama',last_name='Synthetic',status=MemberStatus.ACTIVE,baptized=False,phone='054 000 0000')
            self.guardian=Member(member_no='PREVIEW-GUARDIAN',first_name='Daniel',last_name='Synthetic',status=MemberStatus.ACTIVE,baptized=False,phone='054 000 1111')
            db.add_all(self.members+[self.teacher,self.guardian]);db.flush()
            self.admin=User(username='preview-admin',password_hash='unused',status=UserStatus.ACTIVE,roles=[admin_role])
            self.teacher_user=User(username='preview-teacher',password_hash='unused',status=UserStatus.ACTIVE,roles=[teacher_role],member_id=self.teacher.id)
            db.add_all([self.admin,self.teacher_user]);db.commit()
        self.service=SundaySchoolService(self.admin.id,self.factory)
        self.attendance=SundaySchoolAttendanceService(self.admin.id,self.factory)
        self.lessons=SundaySchoolLessonService(self.admin.id,self.factory)
        self.reports=SundaySchoolReportService(self.admin.id,self.factory)
        self.member_service=MemberService(self.admin.id,self.factory)
        self.primary=self.service.create_class(dict(name='Primary',code='PRIMARY',minimum_age=4,maximum_age=12,room_location='Room 2',capacity=40))
        self.juniors=self.service.create_class(dict(name='Juniors',code='JUNIORS',minimum_age=8,maximum_age=17,room_location='Room 3'))
        for index,member in enumerate(self.members):self.service.enroll_student(self.primary['id'] if index<25 else self.juniors['id'],member.id,start_date=date.today())
        self.service.assign_teacher(self.primary['id'],self.teacher.id)
        household_service=HouseholdService(self.admin.id,self.factory)
        household=household_service.create_household(dict(household_name='Synthetic family'),self.guardian.id)
        household_service.add_member(household['id'],self.members[0].id,'CHILD')
        self.service.set_guardian(self.members[0].id,self.guardian.id,'GUARDIAN',is_primary=True)
        with self.factory() as db:db.add(SundaySchoolUserClassScope(user_id=self.teacher_user.id,class_id=uuid.UUID(self.primary['id']),created_by_user_id=self.admin.id));db.commit()
        self.lesson=self.lessons.create_lesson(dict(title='Faith and provision',lesson_date=date.today(),topic='Faith',scripture_reference='John 6:1–14',status='PUBLISHED'),[self.primary['id'],self.juniors['id']])

    def tearDown(self):
        # Finish synthetic database work while the Tk owner thread/root is still
        # alive, then release callback/widget cycles on that owner thread.
        loaders=[]
        def collect(widget):
            loader=getattr(widget,'loader',None)
            if loader and loader not in loaders:loaders.append(loader)
            for child in widget.winfo_children():collect(child)
        collect(self.root)
        for loader in loaders:loader.close()
        for loader in loaders:loader.executor.shutdown(wait=True,cancel_futures=True)
        for child in list(self.root.winfo_children()):child.destroy()
        gc.collect();self.pump(.1);self.assertEqual(self.errors,[])

    def mount(self,teacher=False):
        user=self.teacher_user if teacher else self.admin
        shell=ctk.CTkFrame(self.root,fg_color='#F3F6FB');shell.pack(fill='both',expand=True)
        sidebar=ctk.CTkFrame(shell,width=220,fg_color='#0C2E49');sidebar.pack(side='left',fill='y');sidebar.pack_propagate(False)
        workspace=SundaySchoolWorkspace(shell,SimpleNamespace(id=user.id),service=SundaySchoolService(user.id,self.factory),
            attendance=SundaySchoolAttendanceService(user.id,self.factory),lessons=SundaySchoolLessonService(user.id,self.factory),
            reports=SundaySchoolReportService(user.id,self.factory),member_service=MemberService(user.id,self.factory))
        workspace.pack(side='left',fill='both',expand=True)
        self.wait_for(lambda:workspace.body is not None,timeout=12);self.pump()
        return shell,workspace

    def capture(self,name):
        import ctypes
        from ctypes import wintypes
        path=Path('docs/screenshots/sunday_school');path.mkdir(parents=True,exist_ok=True)
        self.pump();get_parent=ctypes.windll.user32.GetParent;get_parent.restype=wintypes.HWND;get_parent.argtypes=[wintypes.HWND]
        target=self.root.grab_current() or self.root
        ImageGrab.grab(window=get_parent(target.winfo_id())).save(path/(name+'.png'))

    def test_all_workspaces_themes_sizes_and_form_footers(self):
        session=self.attendance.create_session(self.primary['id'],date.today(),lesson_id=self.lesson['id'])
        for width,height in ((1366,768),(1600,900),(1920,1080)):
            scale=self.root._get_window_scaling();self.root.geometry(f'{int((width-30)/scale)}x{int((height-70)/scale)}+0+0')
            for mode in ('light','dark'):
                with self.subTest(width=width,mode=mode):
                    ctk.set_appearance_mode(mode)
                    try:
                        shell,workspace=self.mount()
                        for name in ('Overview','Classes','Students','Teachers','Lessons','Attendance','Reports'):
                            workspace.select(name);self.pump(.3)
                            if hasattr(workspace.body,'records'):self.wait_for(lambda:bool(workspace.body.records),timeout=12)
                            self.assert_visible_in(workspace.nav,self.root)
                            if hasattr(workspace.body,'next_button'):self.assert_visible_in(workspace.body.next_button,self.root)
                            if getattr(workspace.body,'add_button',None):self.assert_visible_in(workspace.body.add_button,self.root)
                            self.capture(f'{name.lower()}_{width}_{mode}')
                        roster=workspace.open_attendance(session['id']);self.wait_for(lambda:roster.session is not None,timeout=12)
                        self.assert_visible_in(roster.lifecycle_button,roster);self.assert_visible_in(roster.next_button,roster)
                        first=roster.content.winfo_children()[0];self.assert_visible_in(first.mark_button,roster.content._parent_canvas)
                        self.capture(f'roster_{width}_{mode}');roster.destroy()
                        for title,create in (('class_form',lambda:ClassFormDialog(workspace,self.service,Mock())),
                            ('enrollment',lambda:EnrollStudentDialog(workspace,self.service,self.member_service,workspace.classes,workspace.capabilities,Mock())),
                            ('teacher_form',lambda:AssignTeacherDialog(workspace,self.service,workspace.classes,Mock())),
                            ('lesson_form',lambda:LessonFormDialog(workspace,self.lessons,workspace.classes,workspace.capabilities,Mock()))):
                            form=create()
                            self.pump();self.assert_visible_in(form.save_button,form);self.assert_visible_in(form.cancel_button,form);self.capture(f'{title}_{width}_{mode}');form.destroy()
                    finally:
                        for child in list(self.root.winfo_children()):child.destroy()
                        self.pump()

    def test_enrollment_picker_register_move_guardian_and_teacher_flows(self):
        shell,workspace=self.mount()
        form=ClassFormDialog(workspace,self.service,workspace.changed)
        form.fields['name'].insert(0,'Configured class');form.suggest();form.fields['maximum_age'].insert(0,'12');form.save()
        self.wait_for(lambda:not form.winfo_exists(),timeout=12)
        new=self.service.list_classes(search='Configured')['rows'][0]
        student=self.service.get_student(self.members[0].id)
        form=EnrollStudentDialog(workspace,self.service,self.member_service,self.service.list_classes()['rows'],workspace.capabilities,workspace.changed,student)
        form.class_select.set(new['name']);form.save();self.wait_for(lambda:not form.winfo_exists(),timeout=12)
        self.assertEqual(self.service.get_student(self.members[0].id)['class_id'],new['id'])
        form=workspace.enroll();picker=form.person.winfo_children()[-1];picker.invoke()
        self.wait_for(lambda:self.root.grab_current() is not form,timeout=8);member_picker=self.root.grab_current()
        member_picker.search.insert(0,'PREVIEW-GUARDIAN');member_picker.search.submit();self.wait_for(lambda:member_picker.total==1,timeout=12)
        member_picker.content.winfo_children()[0].select_button.invoke();form.class_select.set('No class yet');form.save()
        self.wait_for(lambda:not form.winfo_exists(),timeout=12)
        self.assertIsNone(self.service.get_student(self.guardian.id)['class_id'])
        assignment=AssignTeacherDialog(workspace,self.service,workspace.classes,workspace.changed)
        assignment.selected(dict(member_id=str(self.guardian.id),full_name=self.guardian.full_name));assignment.class_select.set(self.juniors['name']);assignment.role.set('Assistant teacher');assignment.save()
        self.wait_for(lambda:not assignment.winfo_exists(),timeout=12)
        self.assertEqual(self.service.get_class(self.juniors['id'])['teachers'],1)
        shell.destroy()

    def test_create_attendance_window_state_and_modes_survive_dpi_timer(self):
        for index,mode in enumerate(('light','dark')):
            with self.subTest(mode=mode):
                ctk.set_appearance_mode(mode)
                shell,workspace=self.mount()
                workspace.select('Attendance');self.pump(.3)
                for choice,expected_state in (('Open now','OPEN'),('Planned','DRAFT')):
                    # Use the actual Attendance toolbar action, including modal
                    # activation and the asynchronous lesson choices.
                    workspace.body.add_button.invoke();self.pump(.2)
                    form=self.root.grab_current()
                    self.assertIsInstance(form,CreateSchoolAttendanceDialog)
                    self.assertTrue(callable(form.state))
                    self.assertEqual(form.state(),'normal')
                    self.assertEqual(form.session_state_select.cget('values'),['Open now','Planned'])
                    form.session_state_select.set(choice)
                    if choice=='Open now':
                        # Exercise the real recurring CustomTkinter DPI timer
                        # while the dialog remains open in each theme.
                        self.pump(15.1)
                    selected_date=date.today()+timedelta(days=-index if choice=='Open now' else index+1)
                    form.selected_date.variable.set(selected_date.strftime('%d/%m/%Y'))
                    title=f'{mode} {choice} window-state regression'
                    form.title_entry.insert(0,title);form.save_button.invoke()
                    self.wait_for(lambda:not form.winfo_exists(),timeout=12)
                    rows=self.attendance.list_sessions(search=title)['rows']
                    self.assertEqual(len(rows),1)
                    self.assertEqual(rows[0]['state'],expected_state)
                    self.assertEqual(self.errors,[])
                # Reopening/cancelling must keep Tk window state callable too.
                workspace.body.add_button.invoke();self.pump(.2)
                form=self.root.grab_current();self.assertEqual(form.state(),'normal')
                form.cancel_button.invoke();self.pump(.2)
                self.assertFalse(form.winfo_exists());shell.destroy();self.pump(.2)

    def test_roster_mark_correct_close_reopen_and_scoped_teacher_controls(self):
        session=self.attendance.create_session(self.primary['id'],date.today())
        shell,workspace=self.mount(teacher=True)
        self.assertEqual(len(workspace.classes),1)
        workspace.select('Classes');self.wait_for(lambda:bool(workspace.body.records),timeout=12)
        self.assertIsNone(workspace.body.add_button)
        roster=workspace.open_attendance(session['id']);self.wait_for(lambda:roster.session is not None,timeout=12)
        first=roster.content.winfo_children()[0];mid=first.student['member_id'];first.mark_button.invoke()
        self.wait_for(lambda:roster.session['stats']['present']==1,timeout=12)
        first=roster.content.winfo_children()[0];correction=roster.correct(first.student);correction.status.set('Late');correction.reason.insert(0,'Synthetic correction');correction.save()
        self.wait_for(lambda:not correction.winfo_exists(),timeout=12);self.wait_for(lambda:roster.session['stats']['late']==1,timeout=12)
        confirm=roster.lifecycle();self.pump();confirm.confirm();self.wait_for(lambda:roster.session['state']=='CLOSED',timeout=12)
        self.assertEqual(roster.session['stats']['absent'],24);self.assertFalse(roster.lifecycle_button.winfo_ismapped())
        roster.destroy();shell.destroy()
        self.attendance.reopen_session(session['id'],'Office correction')
        self.assertEqual(self.attendance.get_session(session['id'])['state'],'OPEN')

    def test_user_administration_class_scope_selection(self):
        user_service=UserService(self.admin.id,self.factory);user=user_service.get_user(self.teacher_user.id)
        permissions=set(APP)|set(ATT)|set(ADMIN)
        form=UserAccessDialog(self.root,user_service,user,Mock(),permissions)
        self.wait_for(lambda:form.save_button.cget('state')=='normal',timeout=12)
        self.assertTrue(form.school_options_ready)
        form.school_scopes.set_selected_ids([self.juniors['id']]);form.save()
        self.wait_for(lambda:not form.winfo_exists(),timeout=12)
        scopes=user_service.get_user(self.teacher_user.id)['school_scopes']
        self.assertEqual([scope['id'] for scope in scopes],[self.juniors['id']])


if __name__=='__main__':unittest.main()
