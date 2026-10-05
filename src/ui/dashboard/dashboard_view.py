"""Application navigation controller with separate shell and page components."""
import customtkinter as ctk
from src.services.member_service import MemberService
from src.services.attendance_service import AttendanceService
from src.security.application_permissions import navigation
from src.ui import theme
from src.ui.components.app_shell import AppShell
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.future_workspace import FutureWorkspace
from src.ui.components.modern import ActionButton, AppCard, label
from src.ui.dashboard.home_view import HomeView
from src.ui.members.members_view import MembersView
from src.ui.attendance.attendance_view import AttendanceView
from src.ui.attendance.dialogs import MinistryAccessDialog


class DashboardView(ctk.CTkFrame):
    def __init__(self, master, user, on_logout, on_toggle_theme=None):
        super().__init__(master, fg_color=theme.BACKGROUND, corner_radius=0)
        self.user = user
        self.member_service = MemberService(user.id)
        self.attendance_service = AttendanceService(user.id)
        self.attendance_capabilities = self.attendance_service.capabilities()
        self.permissions = set(self.attendance_capabilities['permissions'])
        destinations = navigation(self.attendance_capabilities)
        self.allowed_pages = dict(destinations)
        self.ministries = self.attendance_service.list_ministries() if self.attendance_capabilities['can_view'] else []
        self.central = self.attendance_capabilities.get('church_wide', 'ATTENDANCE_VIEW_ALL' in self.permissions)
        self.context = 'Church-wide operations' if self.central else ', '.join(m['name'] for m in self.ministries) or 'Assigned workspace'
        self.pack(fill='both', expand=True)
        self.shell = AppShell(self, user, destinations, self.context, self.select_menu, on_logout, on_toggle_theme)
        self.shell.pack(fill='both', expand=True)
        self.menu_buttons = self.shell.sidebar.buttons
        self.sidebar = self.shell.sidebar
        self.body_frame = None
        self.active_menu = 'Dashboard'
        self.show_dashboard()

    def page(self, title, subtitle):
        if self.body_frame is not None:
            self.body_frame.destroy()
        self.page_actions = self.shell.page(title, subtitle)
        self.shell.sidebar.select(self.active_menu)

    def mount(self, view):
        self.body_frame = view
        view.pack(fill='both', expand=True)

    def show_dashboard(self):
        self.page('Dashboard' if self.central else 'Ministry dashboard', self.context)
        view = HomeView(self.shell.content, self.member_service, self.attendance_service,
            self.attendance_capabilities, self.allowed_pages, self.select_menu, self.open_session)
        self.attendance_metric = view.cards['sunday']
        self.mount(view)

    def show_members(self):
        self.page('Members' if self.central else 'Ministry members', self.context)
        self.mount(MembersView(self.shell.content, self.user, service=self.member_service,
                               permissions=self.permissions, action_master=self.page_actions))

    def show_attendance(self):
        self.page('Attendance' if self.central else 'Ministry attendance', self.context)
        self.mount(AttendanceView(self.shell.content, self.user, service=self.attendance_service,
                                  action_master=self.page_actions))

    def open_session(self, session_id):
        self.select_menu('Attendance')
        self.body_frame.open_session(session_id)

    def show_ministries(self):
        self.page('Ministries', self.context)
        view = ctk.CTkScrollableFrame(self.shell.content, fg_color='transparent')
        self.mount(view)
        loader = AsyncLoader(view)
        def ready(rows):
            for ministry in rows:
                card = AppCard(view)
                card.pack(fill='x', padx=20, pady=6)
                label(card, ministry['name'], 18, True).pack(anchor='w', padx=16, pady=(14, 4))
                label(card, ministry['code'], 12, muted=True).pack(anchor='w', padx=16, pady=(0, 14))
            if not rows:
                label(view, 'No ministries are assigned to your account.', muted=True).pack(pady=32)
        loader.submit('ministries', self.member_service.list_ministries, ready,
                      lambda error: label(view, str(error), muted=True).pack(pady=20))

    def show_future(self, name):
        self.page(name, self.context)
        features = {
            'Sunday School': ['Class enrollment and teacher assignments', 'Class attendance and progress reports'],
            'Finance': ['Income, expenses and ministry accounts', 'Payment approvals and financial reports'],
            'Welfare': ['Member support and assistance requests', 'Authorized welfare case records'],
            'SMS': ['Messages to permitted members', 'Delivery history and ministry announcements'],
        }
        self.mount(FutureWorkspace(self.shell.content, name, self.allowed_pages[name], self.context, features[name]))

    def show_reports(self):
        self.page('Reports', 'Export attendance from a permitted session and ministry view.')
        view = ctk.CTkFrame(self.shell.content, fg_color='transparent')
        self.mount(view)
        card = AppCard(view)
        card.pack(fill='x', padx=24, pady=8)
        label(card, 'Attendance reports', 20, True).pack(anchor='w', padx=20, pady=(20, 6))
        label(card, 'Open a session, choose your member view, then use Export CSV. Original markers and times are retained.',
              wraplength=650, anchor='w', justify='left').pack(fill='x', padx=20, pady=(0, 16))
        ActionButton(card, 'Browse attendance', lambda: self.select_menu('Attendance'), 'primary').pack(anchor='w', padx=20, pady=(0, 20))

    def show_administration(self):
        self.page('Administration', 'Roles, assigned ministry scopes and attendance access')
        view = ctk.CTkFrame(self.shell.content, fg_color='transparent')
        self.mount(view)
        card = AppCard(view)
        card.pack(fill='x', padx=24, pady=8)
        label(card, 'Ministry attendance access', 20, True).pack(anchor='w', padx=20, pady=(20, 6))
        label(card, 'Assign an existing account to a ministry and audit its attendance grants.', muted=True).pack(anchor='w', padx=20, pady=(0, 16))
        if self.attendance_capabilities.get('can_manage_access'):
            ActionButton(card, 'Manage access', lambda: MinistryAccessDialog(self, self.attendance_service), 'primary').pack(anchor='w', padx=20, pady=(0, 20))

    def select_menu(self, name):
        if name not in self.allowed_pages:
            return
        self.active_menu = name
        routes = {'Dashboard': self.show_dashboard, 'Members': self.show_members,
                  'Attendance': self.show_attendance, 'Ministries': self.show_ministries,
                  'Reports': self.show_reports, 'Administration': self.show_administration}
        routes.get(name, lambda: self.show_future(name))()
