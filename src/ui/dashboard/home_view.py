"""Role-aware dashboard content with scoped database metrics."""
import customtkinter as ctk
from src.ui import theme
from src.ui.components.modern import ActionButton, AppCard, StatCard, label
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.date_picker import display_date
from src.ui.components.session_table import SessionRow


class HomeView(ctk.CTkScrollableFrame):
    def __init__(self, master, member_service, attendance_service, capabilities, destinations, navigate, open_session, member_directory=True):
        super().__init__(master, fg_color='transparent', corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.loader = AsyncLoader(self)
        self.cards = {}
        bar = ctk.CTkFrame(self, fg_color='transparent')
        bar.grid(row=0, column=0, sticky='ew', padx=20)
        central = capabilities.get('church_wide', False)
        titles = [('members', 'Total members' if central else 'Ministry members', 'users'),
                  ('sunday', 'Latest Sunday attendance', 'attendance'),
                  ('open', 'Open sessions', 'calendar'), ('meetings', 'Ministry meetings', 'ministries')]
        for index, (key, title, image) in enumerate(titles):
            bar.grid_columnconfigure(index, weight=1, uniform='metrics')
            card = StatCard(bar, title, icon_name=image)
            card.set('—')
            card.grid(row=0, column=index, sticky='nsew', padx=(0 if not index else 4, 4))
            self.cards[key] = card
        actions = AppCard(self)
        actions.grid(row=1, column=0, sticky='ew', padx=20, pady=16)
        label(actions, 'Quick actions', 16, True).pack(anchor='w', padx=16, pady=(12, 8))
        buttons = ctk.CTkFrame(actions, fg_color='transparent')
        buttons.pack(fill='x', padx=12, pady=(0, 12))
        for title, destination in [('View members' if member_directory else 'View households', 'Members'), ('Take attendance', 'Attendance'), ('Attendance reports', 'Reports')]:
            if destination in destinations:
                ActionButton(buttons, title, lambda d=destination: navigate(d),
                    'primary' if destination == 'Attendance' else 'secondary').pack(side='left', padx=4)
        self.sunday = AppCard(self)
        self.sunday.grid(row=2, column=0, sticky='ew', padx=20, pady=(0, 16))
        label(self.sunday, 'Latest Sunday Service', 16, True).pack(anchor='w', padx=16, pady=(12, 8))
        self.sunday_detail = label(self.sunday, 'Loading attendance…', muted=True, anchor='w', wraplength=650)
        self.sunday_detail.pack(fill='x', padx=16, pady=(0, 12))
        self.upcoming_rows = self.section(3, 'Upcoming services and meetings')
        self.recent_rows = self.section(4, 'Recent ministry attendance' if central else 'Your ministry meetings')
        self.trend_rows = self.section(5, 'Meeting attendance trend')
        self.notice = label(self, '', muted=True, wraplength=650)
        self.notice.grid(row=6, column=0, sticky='ew', padx=20)
        self.open_session = open_session
        def fetch():
            members = member_service.stats() if member_directory and 'Members' in destinations else None
            if not capabilities.get('can_view'):
                return members, None, [], []
            return (members, attendance_service.overview(),
                    attendance_service.list_sessions(limit=5, section='MEETINGS')['rows'],
                    attendance_service.list_sessions(limit=3, section='UPCOMING')['rows'])
        self.loader.submit('home', fetch, self.ready, self.failed)

    def section(self, row, title):
        panel = AppCard(self)
        panel.grid(row=row, column=0, sticky='ew', padx=20, pady=(0, 16))
        label(panel, title, 16, True).pack(anchor='w', padx=16, pady=(12, 8))
        content = ctk.CTkFrame(panel, fg_color='transparent')
        content.pack(fill='x', padx=12, pady=(0, 12))
        return content

    def ready(self, result):
        members, overview, recent, upcoming = result
        if members:
            self.cards['members'].set(members['total'])
            self.cards['members'].set_detail(f"{members['active']} active")
        if overview:
            sunday = overview['sunday']
            self.cards['sunday'].set(sunday['count'] if sunday['date'] else '—')
            self.cards['sunday'].set_detail(display_date(sunday['date']) if sunday['date'] else 'No service recorded yet')
            self.cards['open'].set(overview['open'])
            self.cards['meetings'].set(overview['meetings'])
            self.sunday_detail.configure(text=(
                f"{display_date(sunday['date'])}   ·   {sunday['PRESENT']} present   ·   {sunday['LATE']} late   ·   "
                f"{sunday['EXCUSED']} excused   ·   {sunday['ABSENT']} absent   ·   {sunday['rate']:g}% attendance"
            ) if sunday['date'] else 'No Sunday service has been recorded in your view.')
            for row in overview['trend']:
                strip = ctk.CTkFrame(self.trend_rows, fg_color='transparent')
                strip.pack(fill='x', pady=4)
                label(strip, display_date(row['date']), 12).pack(side='left')
                progress = ctk.CTkProgressBar(strip, fg_color=theme.SURFACE_ALT, progress_color=theme.SECONDARY)
                progress.pack(side='left', fill='x', expand=True, padx=16)
                progress.set(row['rate']/100)
                label(strip, f"{row['rate']:g}%", 12, True, width=60).pack(side='right')
            if not overview['trend']:
                label(self.trend_rows, 'Complete a ministry meeting to see its attendance trend.', muted=True).pack(anchor='w')
        else:
            self.sunday_detail.configure(text='Attendance access is not assigned to this account.')
        for parent, rows, empty in ((self.recent_rows, recent, 'No ministry meetings yet.'),
                                    (self.upcoming_rows, upcoming, 'No upcoming sessions in your view.')):
            for session in rows:
                SessionRow(parent, session, self.open_session).pack(fill='x', pady=4)
            if not rows:
                label(parent, empty, muted=True).pack(anchor='w', padx=4, pady=8)

    def failed(self, error):
        self.notice.configure(text=str(error), text_color=theme.DANGER)

    def destroy(self):
        self.loader.close()
        super().destroy()
