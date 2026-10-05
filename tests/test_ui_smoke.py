"""Run on a Windows desktop. Uses synthetic attendance and membership data."""
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import time
import unittest
from unittest.mock import Mock, patch
import uuid

import customtkinter as ctk
from PIL import ImageGrab

from src.ui import theme
from src.ui.attendance.attendance_view import AttendanceView
from src.ui.attendance.dialogs import (
    AttendanceAuditDialog, CorrectAttendanceDialog, CreateAttendanceDialog,
    MemberSelectionDialog, MinistryAccessDialog,
)
from src.ui.components.date_picker import DatePickerDialog
from src.ui.components.modern import ConfirmationDialog
from src.ui.login.login_view import LoginView
from src.ui.dashboard.dashboard_view import DashboardView
from src.ui.members.member_form_dialog import MemberFormDialog
from src.ui.login.forgot_password_dialog import ForgotPasswordDialog
from src.services.member_service import MemberServiceError
from tests.ministry_preview import PreviewMinistryService
from src.security.attendance_permissions import PERMISSIONS
from src.security.application_permissions import PERMISSIONS as APP_PERMISSIONS, LEADER_PERMISSIONS as APP_LEADER_PERMISSIONS
from src.security.attendance_permissions import LEADER_PERMISSIONS


class PreviewService:
    def __init__(self, central=True):
        self.central = central
        self.ministry_id = str(uuid.uuid4())
        self.session = dict(id=str(uuid.uuid4()), title="Youth Weekly Meeting", name="Youth Weekly Meeting",
            description="Weekly fellowship, worship and planning meeting.", session_type="MINISTRY_MEETING",
            scope_type="MINISTRY", roster_type="ALL_MINISTRY_MEMBERS", session_date=date(2026, 10, 8),
            start_time=None, end_time=None, state="OPEN", ministry_id=self.ministry_id,
            ministry_name="Youth Ministry", created_by="Youth Leader",
            actions=dict(open=False, close=True, reopen=False, lock=False, unlock=False))
        self.members = [dict(id=str(uuid.uuid4()), member_no=f"HOPFAN-2026-{i+1:04d}",
            full_name=("Ama Mensah" if i == 0 else f"Member {i+1} Mensah"), phone="020 000 0000",
            photo_path="", ministries=["Youth", "Choir"], attendance_status="PRESENT" if i < 10 else None,
            marked_by="Youth Leader" if i < 10 else "", marked_at=datetime.now(timezone.utc) if i < 10 else None,
            updated_by=None, updated_at=None, notes=None, can_record=True, can_correct=True) for i in range(30)]
        self.stats = dict(eligible=30, PRESENT=10, LATE=0, EXCUSED=0, ABSENT=0, unmarked=20, rate=33.3)

    def capabilities(self):
        permissions = list(PERMISSIONS | APP_PERMISSIONS) if self.central else list(LEADER_PERMISSIONS | APP_LEADER_PERMISSIONS)
        return dict(permissions=permissions, can_create=True, can_view=True, can_manage_access=self.central,
                    can_report=True, church_wide=self.central, scope_ids=[] if self.central else [self.ministry_id])

    def list_ministries(self, action="view"):
        return [dict(id=self.ministry_id, name="Youth Ministry")]

    def list_sessions(self, *args, **kwargs):
        return dict(total=1, rows=[dict(self.session, stats=self.stats)])

    def get_session(self, session_id):
        return dict(self.session)

    def roster(self, *args, **kwargs):
        return dict(total=len(self.members), rows=self.members, stats=self.stats)

    def candidate_members(self, *args, **kwargs):
        return dict(total=30, rows=self.members)

    def audit_history(self, *args, **kwargs):
        return [dict(action="CORRECTED", member="Ama Mensah", old_status="ABSENT", new_status="PRESENT",
                     reason="Presence confirmed after roll verification.", changed_by="Youth Leader",
                     changed_at=datetime.now(timezone.utc))]

    def access_configuration(self):
        return dict(users=[dict(id="preview-user", name="Youth Leader", roles=[])],
                    ministries=self.list_ministries(), scopes=[])

    def latest_sunday_count(self):
        return dict(self.stats, count=10, date=date(2026,10,4))

    def overview(self):
        return dict(today=1, open=2, completed=3, meetings=4, rate=33.3,
                    sunday=self.latest_sunday_count(), trend=[dict(date=date(2026,10,1), title='Youth Meeting', rate=66.7)])


class UiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ctk.set_widget_scaling(1)
        ctk.set_window_scaling(1)
        cls.root = ctk.CTk()
        theme.configure_typography(cls.root)

    @classmethod
    def tearDownClass(cls):
        for timer in cls.root.tk.call("after", "info"):
            cls.root.after_cancel(timer)
        cls.root.destroy()

    def setUp(self):
        scale = self.root._get_window_scaling()
        self.root.geometry(f"{int(1336/scale)}x{int(698/scale)}+0+0")
        self.root.title("HOPFAN UI validation — synthetic data")
        self.errors = []
        self.root.report_callback_exception = lambda kind, value, tb: self.errors.append((kind.__name__, str(value)))
        self.service = PreviewService()
        self.user = SimpleNamespace(id="preview", username="Youth Leader", email="preview@example.invalid",
                                    roles=[SimpleNamespace(name="Ministry Attendance Leader")])
        self.pump(0.1)

    def tearDown(self):
        for child in list(self.root.winfo_children()):
            child.destroy()
        self.pump(0.1)
        self.assertEqual(self.errors, [])

    def pump(self, seconds=0.15):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.005)

    def wait_for(self, predicate, timeout=3):
        deadline = time.monotonic()+timeout
        while not predicate() and time.monotonic() < deadline:
            self.pump(0.03)
        self.assertTrue(predicate(), "UI did not finish loading")

    def assert_visible_in(self, widget, parent):
        self.assertTrue(widget.winfo_ismapped())
        self.assertGreaterEqual(widget.winfo_rootx(), parent.winfo_rootx())
        self.assertGreaterEqual(widget.winfo_rooty(), parent.winfo_rooty())
        self.assertLessEqual(widget.winfo_rootx()+widget.winfo_width(), parent.winfo_rootx()+parent.winfo_width()+1)
        self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(), parent.winfo_rooty()+parent.winfo_height()+1)

    def capture(self, name):
        folder = Path("logs/ui_smoke")
        folder.mkdir(parents=True, exist_ok=True)
        x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
        # Capture the rendered window, including portions taller than this desktop.
        # Bounding-box grabs would capture the taskbar over a simulated 1080p viewport.
        import ctypes
        from ctypes import wintypes
        get_parent = ctypes.windll.user32.GetParent
        get_parent.restype = wintypes.HWND
        get_parent.argtypes = [wintypes.HWND]
        target = self.root.grab_current() or self.root
        hwnd = get_parent(target.winfo_id())
        ImageGrab.grab(window=hwnd).save(folder/(name+".png"))

    def test_attendance_resolutions_themes_and_modal_footers(self):
        for width, height in ((1366,768),(1600,900),(1920,1080)):
            scale = self.root._get_window_scaling()
            self.root.geometry(f"{int((width-30)/scale)}x{int((height-70)/scale)}+0+0")
            for mode in ("light", "dark"):
                ctk.set_appearance_mode(mode)
                shell = ctk.CTkFrame(self.root, fg_color=theme.BACKGROUND)
                shell.pack(fill="both", expand=True)
                sidebar = ctk.CTkFrame(shell, width=theme.SIDEBAR_WIDTH, fg_color=theme.SIDEBAR, corner_radius=0)
                sidebar.pack(side="left", fill="y")
                sidebar.pack_propagate(False)
                view = AttendanceView(shell, self.user, service=self.service)
                view.pack(fill="both", expand=True)
                self.wait_for(lambda: hasattr(view, "session_next"))
                self.pump()
                self.assert_visible_in(view.create_button, self.root)
                self.assert_visible_in(view.session_next, self.root)
                view.open_session(self.service.session["id"])
                self.wait_for(lambda: hasattr(view, "roster_next"))
                self.wait_for(lambda: len(view.roster_rows.winfo_children()) == 30)
                self.assert_visible_in(view.roster_next, self.root)
                self.assert_visible_in(view.search, self.root)
                self.assert_visible_in(view.status_filter, self.root)
                self.capture(f"attendance_{width}_{mode}")
                dialog = CreateAttendanceDialog(view, self.service, self.service.list_ministries(),
                                                 self.service.capabilities(), lambda _s: None)
                self.pump()
                self.assert_visible_in(dialog.save_button, dialog)
                self.assert_visible_in(dialog.cancel_button, dialog)
                self.assert_visible_in(dialog.save_button, self.root)
                self.assert_visible_in(dialog.cancel_button, self.root)
                self.capture(f"create_{width}_{mode}")
                dialog.destroy()
                view.destroy()
                shell.destroy()
                self.pump(0.1)

    def test_all_attendance_dialogs_and_direct_birth_year(self):
        for mode in ("light", "dark"):
            ctk.set_appearance_mode(mode)
            creator = CreateAttendanceDialog(self.root, self.service, self.service.list_ministries(), self.service.capabilities(), lambda _s: None)
            self.pump()
            selected = []
            calendar = DatePickerDialog(creator, date(2026,10,5), selected.append)
            self.pump()
            calendar.year_changed("1994")
            calendar.month_changed("October")
            calendar.select(date(calendar.year, calendar.month, 5))
            self.assertEqual(selected, [date(1994,10,5)])
            self.assertEqual(creator.grab_current(), creator)
            creator.destroy()
            dialogs = [
                CorrectAttendanceDialog(self.root, self.service, self.service.session["id"], self.service.members[0], lambda: None),
                AttendanceAuditDialog(self.root, self.service, self.service.session["id"]),
                MemberSelectionDialog(self.root, self.service, self.service.ministry_id, set(), lambda _s: None),
                MinistryAccessDialog(self.root, self.service),
                ConfirmationDialog(self.root, "Close session", "Unmarked eligible members become absent.", lambda _r,_d: None),
                ForgotPasswordDialog(self.root, Mock()),
            ]
            self.pump(0.3)
            for dialog in dialogs:
                self.assert_visible_in(dialog.cancel_button, dialog)
                dialog.destroy()

    def test_members_form_dates_fixed_footer_and_safe_destruction(self):
        for mode in ("light", "dark"):
            ctk.set_appearance_mode(mode)
            dialog = MemberFormDialog(self.root, self.service, lambda: None)
            self.pump()
            self.assert_visible_in(dialog.save_button, dialog)
            self.assert_visible_in(dialog.save_button, self.root)
            dialog.variables["date_of_birth"].set("05/10/1994")
            self.assertEqual(dialog.storage_date(dialog.variables["date_of_birth"].get()), "1994-10-05")
            self.capture("member_form_"+mode)
            dialog.destroy()
            self.pump()
        # Photo failures occur after profile commit; retry must retain member identity.
        service = Mock()
        service.list_ministries.return_value = []
        saved = dict(id='saved-preview', full_name='Ama Mensah', ministry_ids=[], first_name='Ama', last_name='Mensah')
        service.create_member.return_value = saved
        service.update_member.return_value = saved
        service.set_photo.side_effect = MemberServiceError('Photo unavailable.')
        dialog = MemberFormDialog(self.root, service, lambda: None)
        self.pump()
        dialog.variables['first_name'].set('Ama')
        dialog.variables['last_name'].set('Mensah')
        dialog.photo_source = 'synthetic-photo.png'
        dialog.save()
        self.wait_for(lambda: dialog.member is not None)
        self.assertIn('Member saved.', dialog.error_var.get())
        dialog.save()
        self.wait_for(lambda: service.update_member.call_count == 1)
        self.assertEqual(service.create_member.call_count, 1)
        dialog.destroy()

    def test_password_and_totp_are_alternative_signin_paths(self):
        ctk.set_appearance_mode('light')
        successes = []
        view = LoginView(self.root, on_login_success=successes.append, on_toggle_theme=lambda: "light")
        self.pump()
        self.assert_visible_in(view.signin_button, self.root)
        self.capture('login_password_1366_light')
        view.auth_service = Mock()
        password_user, totp_user = object(), object()
        view.auth_service.authenticate_password.return_value = password_user
        view.auth_service.authenticate_totp_only.return_value = totp_user
        view.email_var.set("test@example.invalid")
        view.password_var.set("synthetic-password")
        view.login_with_password()
        self.wait_for(lambda: len(successes) == 1)
        self.assertEqual(successes, [password_user])
        view.auth_service.authenticate_totp_only.assert_not_called()
        view.show_totp_form()
        self.pump()
        self.capture('login_totp_1366_light')
        view.totp_input.set_code("123456")
        self.wait_for(lambda: len(successes) == 2)
        self.assertEqual(successes, [password_user, totp_user])
        view.auth_service.authenticate_totp_only.assert_called_once_with(email="test@example.invalid", code="123456")
        view.on_toggle_theme = lambda: ctk.set_appearance_mode('dark')
        view.change_theme()
        self.pump()
        self.capture('login_totp_1366_dark')
        view.show_password_form()
        self.pump()
        self.capture('login_password_1366_dark')
        view.destroy()

    def test_full_dashboard_shell_navigation_and_attendance_metrics(self):
        members = Mock()
        members.stats.return_value = dict(total=30, active=30, inactive=0, baptized=15)
        with patch("src.ui.dashboard.dashboard_view.MemberService", return_value=members), \
             patch("src.ui.dashboard.dashboard_view.AttendanceService", return_value=self.service), \
             patch("src.ui.attendance.attendance_view.AttendanceService", return_value=self.service):
            dashboard = DashboardView(self.root, self.user, on_logout=lambda: None, on_toggle_theme=lambda: None)
            self.wait_for(lambda: dashboard.attendance_metric.value.cget("text") == "10")
            for mode in ("light", "dark"):
                ctk.set_appearance_mode(mode)
                dashboard.select_menu("Attendance")
                view = dashboard.body_frame
                self.wait_for(lambda: hasattr(view, "session_next"))
                self.pump()
                self.assert_visible_in(view.create_button, self.root)
                view.open_session(self.service.session["id"])
                self.wait_for(lambda: hasattr(view, "roster_next"))
                self.wait_for(lambda: len(view.roster_rows.winfo_children()) == 30)
                self.assert_visible_in(view.roster_next, self.root)
                self.assertGreater(view.roster_rows._parent_canvas.winfo_height(), 120)
                self.capture("full_dashboard_1366_"+mode)
                dashboard.select_menu("Dashboard")
                self.pump()
                self.assertEqual(len(dashboard.page_actions.winfo_children()), 0)
            dashboard.destroy()


    def test_role_aware_sunday_and_creation_defaults(self):
        for central in (True, False):
            service = PreviewService(central)
            service.members = service.members[:4]
            service.session.update(title='Sunday Worship Service', session_type='SUNDAY_SERVICE', scope_type='GLOBAL',
                                   ministry_id=None, ministry_name='Whole church', roster_type='WHOLE_CHURCH')
            view = AttendanceView(self.root, self.user, service=service)
            view.pack(fill='both', expand=True)
            self.wait_for(lambda: hasattr(view, 'session_next'))
            if not central:
                self.assertIsNone(view.session_ministry)
            view.open_session(service.session['id'])
            self.wait_for(lambda: hasattr(view, 'roster_next'))
            self.wait_for(lambda: len(view.rendered_rows) == 4)
            if central:
                self.assertEqual(view.ministry_filter.get(), 'All Members')
                self.assertEqual(view.roster_ministry_id(), None)
                view.ministry_filter.set('Youth Ministry')
                view.refresh_roster()
                self.pump()
                self.assertEqual(view.current_session['id'], service.session['id'])
                self.assertEqual(view.roster_ministry_id(), service.ministry_id)
            else:
                self.assertIsNone(view.ministry_filter)
                self.assertEqual(view.roster_ministry_id(), service.ministry_id)
            original_rows = dict(view.rendered_rows)
            view.refresh_roster()
            self.pump()
            self.assertEqual(view.rendered_rows, original_rows)
            creator = CreateAttendanceDialog(view, service, service.list_ministries(), service.capabilities(), lambda _s: None)
            self.pump()
            self.capture(('admin' if central else 'leader')+'_create_default_1366_'+ctk.get_appearance_mode().lower())
            self.assertFalse(creator.roster_box.winfo_ismapped())
            if central:
                self.assertFalse(creator.advanced_button.winfo_ismapped())
                self.assertEqual(creator.roster_box.get(), 'Whole Church')
            else:
                self.assertFalse(creator.scope_box.winfo_ismapped())
                self.assertFalse(creator.ministry_box.winfo_ismapped())
                self.assertEqual(creator.ministry_id(), service.ministry_id)
                self.assertEqual(creator.roster_box.get(), 'All Ministry Members')
            creator.type_box.set('Leadership Meeting')
            creator.type_changed('Leadership Meeting')
            self.assertEqual(creator.roster_box.get(), 'Ministry Leadership')
            self.assertFalse(creator.roster_box.winfo_ismapped())
            creator.toggle_advanced()
            self.pump()
            # Advanced controls may be below the visible scroll area; they are in the form.
            self.assertEqual(creator.roster_shell.winfo_manager(), 'grid')
            creator.destroy()
            view.destroy()
            self.pump()

    def test_admin_and_leader_shells_at_all_resolutions(self):
        for width, height in ((1366,768),(1600,900),(1920,1080)):
            scale = self.root._get_window_scaling()
            self.root.geometry(f'{int((width-30)/scale)}x{int((height-70)/scale)}+0+0')
            for mode in ('light','dark'):
                ctk.set_appearance_mode(mode)
                for central in (True,False):
                    service = PreviewService(central)
                    service.members = service.members[:4]
                    members = Mock()
                    members.stats.return_value = dict(total=4,active=4,inactive=0,baptized=2)
                    profiles = [dict(row, first_name='Ama', middle_name='', last_name='Mensah', gender='FEMALE',
                        date_of_birth='1994-10-05', alternate_phone='', email='preview@example.invalid', address='Accra',
                        occupation='Teacher', marital_status='SINGLE', date_joined='2020-01-12', baptized=True,
                        baptism_date='2020-02-16', status='ACTIVE', ministry_ids=[service.ministry_id]) for row in service.members]
                    members.list_members.return_value = profiles
                    members.get_member.return_value = profiles[0]
                    members.list_ministries.return_value = [dict(id=service.ministry_id,code='YOUTH',name='Youth Ministry')]
                    user = SimpleNamespace(id='preview',username='Administrator' if central else 'Youth Leader',email='preview@example.invalid',roles=[])
                    with patch('src.ui.dashboard.dashboard_view.MemberService',return_value=members), \
                         patch('src.ui.dashboard.dashboard_view.AttendanceService',return_value=service), \
                         patch('src.ui.dashboard.dashboard_view.MinistryService',return_value=PreviewMinistryService(central)):
                        dashboard = DashboardView(self.root,user,on_logout=lambda:None,on_toggle_theme=lambda:None)
                        self.wait_for(lambda:dashboard.attendance_metric.value.cget('text')=='10')
                        self.pump()
                        role = 'admin' if central else 'leader'
                        if not central:
                            self.assertNotIn('Finance',dashboard.menu_buttons)
                            self.assertNotIn('Welfare',dashboard.menu_buttons)
                            self.assertNotIn('Administration',dashboard.menu_buttons)
                        for card in dashboard.body_frame.cards.values():
                            self.assert_visible_in(card,dashboard.body_frame)
                        rows = dashboard.body_frame.upcoming_rows.winfo_children()
                        self.capture(f'{role}_home_{width}_{mode}')
                        # Dashboard sections scroll; bring the upcoming row into its viewport.
                        canvas = dashboard.body_frame._parent_canvas
                        bottom = rows[0].open_button.winfo_rooty()+rows[0].open_button.winfo_height()
                        excess = bottom-(canvas.winfo_rooty()+canvas.winfo_height())+12
                        if excess > 0:
                            canvas.yview_moveto(excess/canvas.bbox('all')[3])
                            self.pump()
                        self.assert_visible_in(rows[0].open_button,self.root)
                        dashboard.select_menu('Attendance')
                        view = dashboard.body_frame
                        self.wait_for(lambda:hasattr(view,'session_next'))
                        self.wait_for(lambda:len(view.session_rows.winfo_children())==1)
                        self.pump()
                        self.assert_visible_in(view.session_next,self.root)
                        self.assert_visible_in(view.create_button,self.root)
                        self.assert_visible_in(view.date_to,self.root)
                        self.assert_visible_in(view.session_rows.winfo_children()[0].open_button,self.root)
                        self.capture(f'{role}_attendance_landing_{width}_{mode}')
                        if width == 1366:
                            dashboard.select_menu('Members')
                            self.wait_for(lambda:len(dashboard.body_frame.rows.winfo_children())==4)
                            self.pump()
                            self.assert_visible_in(dashboard.body_frame.next_button,self.root)
                            self.capture(f'{role}_members_{width}_{mode}')
                            profile = dashboard.body_frame.view_member(profiles[0]['id'])
                            self.wait_for(lambda: profile.member is not None)
                            self.pump()
                            self.assert_visible_in(profile.cancel_button,self.root)
                            self.capture(f'{role}_member_profile_{width}_{mode}')
                            profile.destroy()
                            for page in ('SMS','Finance','Welfare','Sunday School','Reports','Ministries','Administration'):
                                if page in dashboard.allowed_pages:
                                    dashboard.select_menu(page)
                                    self.pump()
                                    self.capture(f'{role}_{page.lower().replace(" ","_")}_{mode}')
                        dashboard.destroy()
                        self.pump(.05)


if __name__ == "__main__":
    unittest.main()
