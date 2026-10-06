"""Application navigation controller with separate shell and page components."""
import customtkinter as ctk
from src.services.member_service import MemberService
from src.services.attendance_service import AttendanceService
from src.services.ministry_service import MinistryService
from src.services.user_service import UserService
from src.services.household_service import HouseholdService
from src.ui.components.async_loader import AsyncLoader
from src.security.application_permissions import navigation
from src.ui import theme
from src.ui.components.app_shell import AppShell
from src.ui.components.future_workspace import FutureWorkspace
from src.ui.components.modern import ActionButton, AppCard, StatCard, label
from src.ui.dashboard.home_view import HomeView
from src.ui.members.members_view import MembersView
from src.ui.attendance.attendance_view import AttendanceView
from src.ui.administration.administration_view import AdministrationView
from src.ui.ministries.ministries_view import MinistriesView


class DashboardView(ctk.CTkFrame):
    def __init__(self, master, user, on_logout, on_toggle_theme=None):
        super().__init__(master, fg_color=theme.BACKGROUND, corner_radius=0)
        self.user = user
        self.member_service = MemberService(user.id)
        self.attendance_service = AttendanceService(user.id)
        self.ministry_service = MinistryService(user.id)
        self.household_service = HouseholdService(user.id)
        self.attendance_capabilities = self.attendance_service.capabilities()
        self.permissions = set(self.attendance_capabilities['permissions'])
        self.can_member_directory = 'MEMBERS_VIEW_ALL' in self.permissions or ('MEMBERS_VIEW_OWN_MINISTRY' in self.permissions and bool(self.attendance_capabilities.get('scope_ids')))
        destinations = navigation(self.attendance_capabilities)
        self.allowed_pages = dict(destinations)
        self.ministries = self.attendance_service.list_ministries() if self.attendance_capabilities['can_view'] else []
        self.central = self.attendance_capabilities.get('church_wide', 'ATTENDANCE_VIEW_ALL' in self.permissions)
        self.context = 'Church-wide operations' if self.central else ', '.join(m['name'] for m in self.ministries) or 'Assigned workspace'
        if 'Administration' in self.allowed_pages and not any(page in self.allowed_pages for page in ('Members','Attendance','Ministries')):
            self.context='Account and access administration'
        self.pack(fill='both', expand=True)
        self.shell = AppShell(self, user, destinations, self.context, self.select_menu, on_logout, on_toggle_theme)
        self.shell.pack(fill='both', expand=True)
        self.authenticator_button=ActionButton(self.shell.topbar, 'My authenticator', self.authenticator, width=140)
        self.authenticator_button.grid(row=0, column=4, padx=(0,16))
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
        operational=self.can_member_directory or any(page in self.allowed_pages for page in ('Attendance','Ministries'))
        self.page('Dashboard' if self.central or not operational else 'Ministry dashboard', self.context)
        if not operational:
            view=ctk.CTkFrame(self.shell.content,fg_color='transparent')
            self.mount(view)
            card=AppCard(view)
            card.pack(fill='x',padx=24,pady=12)
            label(card,'Your workspace',20,True).pack(anchor='w',padx=18,pady=(16,6))
            label(card,'Open a workspace assigned to your account.',muted=True).pack(anchor='w',padx=18,pady=(0,12))
            for destination in self.allowed_pages:
                if destination!='Dashboard':
                    ActionButton(card,destination,lambda name=destination:self.select_menu(name),'primary').pack(anchor='w',padx=18,pady=6)
            if 'USER_VIEW' in self.permissions:
                summary=ctk.CTkFrame(view,fg_color='transparent')
                summary.pack(fill='x',padx=24,pady=12)
                cards={}
                for index,(key,title) in enumerate((('total','System users'),('active','Active users'),('locked','Locked users'),('inactive','Inactive users'))):
                    summary.grid_columnconfigure(index,weight=1,uniform='stats')
                    cards[key]=StatCard(summary,title)
                    cards[key].grid(row=0,column=index,sticky='ew',padx=4)
                loader=AsyncLoader(view)
                loader.submit('accounts',UserService(self.user.id).stats,
                    lambda stats:[card.set(stats[key]) for key,card in cards.items()],
                    lambda _:None)
            self.attendance_metric=None
            return
        view = HomeView(self.shell.content, self.member_service, self.attendance_service,
            self.attendance_capabilities, self.allowed_pages, self.select_menu, self.open_session,
            member_directory=self.can_member_directory)
        self.attendance_metric = view.cards['sunday']
        self.mount(view)

    def show_members(self):
        if not self.can_member_directory:
            return self.show_households()
        self.page('Members' if self.central else 'Ministry members', self.context)
        self.mount(MembersView(self.shell.content, self.user, service=self.member_service,
                               permissions=self.permissions, action_master=self.page_actions, on_households=self.show_households))

    def show_households(self):
        from src.ui.households.households_view import HouseholdsView
        self.page('Households', 'Manage HOPFAN families and household relationships')
        self.mount(HouseholdsView(self.shell.content, self.household_service, self.member_service,
            on_members=self.show_members if self.can_member_directory else None, action_master=self.page_actions))

    def show_attendance(self):
        self.page('Attendance' if self.central else 'Ministry attendance', self.context)
        self.mount(AttendanceView(self.shell.content, self.user, service=self.attendance_service,
                                  action_master=self.page_actions))

    def open_session(self, session_id):
        self.select_menu('Attendance')
        self.body_frame.open_session(session_id)

    def show_ministries(self):
        self.page('Ministries','Manage HOPFAN ministries, fellowships and departments' if 'MINISTRIES_VIEW_ALL' in self.permissions else 'Your assigned ministry workspaces')
        self.mount(MinistriesView(self.shell.content,self.user,service=self.ministry_service,action_master=self.page_actions))

    def show_sunday_school(self):
        from src.ui.sunday_school.workspace import SundaySchoolWorkspace
        self.page('Sunday School','Classes, students, lessons and class attendance')
        self.mount(SundaySchoolWorkspace(self.shell.content,self.user,member_service=self.member_service))

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
        self.page('Administration', 'Manage accounts, software roles and ministry scopes')
        self.mount(AdministrationView(self.shell.content, self.user, self.permissions,
            on_ministries=lambda:self.select_menu('Ministries')))

    def authenticator(self):
        from src.ui.login.account_security_dialogs import AuthenticatorSetupDialog
        from src.services.auth_service import AuthService
        service=getattr(self.user, '_auth_service', None) or AuthService()
        return AuthenticatorSetupDialog(self, service, self.user)

    def select_menu(self, name):
        if name not in self.allowed_pages:
            return
        self.active_menu = name
        routes = {'Dashboard': self.show_dashboard, 'Members': self.show_members,
                  'Attendance': self.show_attendance, 'Ministries': self.show_ministries,
                  'Reports': self.show_reports, 'Administration': self.show_administration,
                  'Sunday School':self.show_sunday_school}
        routes.get(name, lambda: self.show_future(name))()
