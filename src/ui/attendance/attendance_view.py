"""Attendance operations console with history, fast rosters and controlled changes."""
import csv
from datetime import date
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from src.services.attendance_service import AttendanceService
from src.ui import theme
from src.ui.attendance.dialogs import (
    AttendanceAuditDialog, CorrectAttendanceDialog, CreateAttendanceDialog, MinistryAccessDialog,
)
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.date_picker import DatePicker, display_date
from src.ui.components.session_table import SessionRow
from src.ui.components.modern import (
    ActionButton, AppCard, Avatar, ConfirmationDialog, EmptyState, ModernComboBox,
    ModernEntry, StatCard, StatusBadge, FixedFooterDialog, font, label,
)


class AttendanceView(ctk.CTkFrame):
    PAGE_SIZE = 30

    def __init__(self, master, user, service=None, action_master=None):
        super().__init__(master, fg_color=theme.BACKGROUND, corner_radius=0)
        self.user = user
        self.action_master = action_master
        self.service = service or AttendanceService(user.id)
        self.loader = AsyncLoader(self)
        self.capabilities = {"permissions": []}
        self.ministries, self.ministry_map, self.create_ministries = [], {}, []
        self.current_session = None
        self.ready_flag, self.pending_session = False, None
        self.mode, self.session_offset, self.roster_offset = "sessions", 0, 0
        self.session_total, self.roster_total = 0, 0
        self.search_timer = None
        self.pending_marks = set()
        self.rendered_rows, self.row_data = {}, {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.build_header()
        self.notice = label(self, "Loading attendance...", 12, muted=True, anchor="w")
        self.notice.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 6))
        self.workspace = ctk.CTkFrame(self, fg_color="transparent")
        self.workspace.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 16))
        self.workspace.grid_columnconfigure(0, weight=1)
        self.bootstrap()

    def build_header(self):
        if self.action_master is not None:
            self.create_button = ActionButton(self.action_master, "Create Attendance", self.create_attendance,
                                              "primary", width=165)
            self.create_button.pack(side="left", padx=8)
            self.create_button.configure(state="disabled")
            return
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 10))
        header.grid_columnconfigure(0, weight=1)
        label(header, "Attendance", 28, True).grid(row=0, column=0, sticky="w")
        label(header, "Manage church services, meetings and ministry attendance", 12, muted=True).grid(row=1, column=0, sticky="w")
        self.create_button = ActionButton(header, "Create Attendance", self.create_attendance, "primary", width=165)
        self.create_button.grid(row=0, column=1, rowspan=2, padx=(14, 0))
        self.create_button.configure(state="disabled")

    def bootstrap(self):
        def fetch():
            return self.service.capabilities(), self.service.list_ministries(), self.service.list_ministries("create")
        self.loader.submit("bootstrap", fetch, self.ready, self.failed)

    def ready(self, result):
        self.capabilities, self.ministries, self.create_ministries = result
        self.central = self.capabilities.get("church_wide", "ATTENDANCE_VIEW_ALL" in self.capabilities["permissions"])
        all_label = "All Members" if self.central else "My ministries"
        self.ministry_map = {all_label: None, **{m["name"]: m["id"] for m in self.ministries}}
        self.context = "Church-wide sessions" if self.central else ", ".join(m["name"] for m in self.ministries)
        self.ready_flag = True
        self.create_button.configure(state="normal" if self.capabilities["can_create"] else "disabled")
        self.notice.configure(text="", text_color=theme.TEXT_MUTED)
        self.notice.grid_remove()
        if self.capabilities["can_view"]:
            if self.pending_session:
                self.open_session(self.pending_session)
                self.pending_session = None
            else:
                self.show_sessions()
        else:
            self.clear_workspace()
            EmptyState(self.workspace, "Attendance access is not assigned", "Ask an authorized administrator to assign a role and ministry scope.").grid(sticky="nsew")

    def failed(self, error):
        self.notice.configure(text=str(error), text_color=theme.DANGER)
        self.notice.grid()

    def clear_workspace(self):
        if self.search_timer:
            self.after_cancel(self.search_timer)
            self.search_timer = None
        self.rendered_rows, self.row_data = {}, {}
        for child in self.workspace.winfo_children():
            child.destroy()
        for row in range(5):
            self.workspace.grid_rowconfigure(row, weight=0)

    def show_sessions(self):
        self.mode = 'sessions'
        self.clear_workspace()
        self.workspace.grid_rowconfigure(2, weight=1)
        metrics = ctk.CTkFrame(self.workspace, fg_color='transparent')
        metrics.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        self.landing_cards = {}
        for index, (key, title) in enumerate([('today', "Today's sessions"), ('open', 'Open sessions'),
                                             ('completed', 'Completed sessions'), ('rate', 'Meeting attendance rate')]):
            metrics.grid_columnconfigure(index, weight=1, uniform='kpi')
            card = StatCard(metrics, title)
            card.set('—')
            card.grid(row=0, column=index, sticky='ew', padx=(0 if index == 0 else 4, 4))
            self.landing_cards[key] = card
        toolbar = AppCard(self.workspace)
        toolbar.grid(row=1, column=0, sticky='ew', pady=(0, 10))
        top = ctk.CTkFrame(toolbar, fg_color='transparent')
        top.pack(fill='x', padx=12, pady=(8, 4))
        label(top, self.context, 14, True).pack(side='left')
        ActionButton(top, 'Refresh', self.refresh_sessions, width=75).pack(side='right')
        if self.capabilities.get('can_manage_access'):
            ActionButton(top, 'Manage access', self.manage_access, width=110).pack(side='right', padx=8)
        self.section = ctk.StringVar(master=self, value='All')
        if not self.central:
            tabs = ctk.CTkSegmentedButton(toolbar, values=['All', 'Upcoming', 'Draft', 'Open', 'Recent', 'Sunday'],
                variable=self.section, command=lambda _v: self.refresh_sessions(reset=True), font=font(12),
                fg_color=theme.SURFACE_ALT, corner_radius=8,
                selected_color=("#DDECF7", "#245477"), selected_hover_color=("#C8E0F2", "#2C638E"),
                unselected_color=theme.SURFACE_ALT, unselected_hover_color=theme.BORDER, text_color=theme.TEXT)
            tabs.pack(fill='x', padx=12, pady=(0, 8))
        filters = ctk.CTkFrame(toolbar, fg_color='transparent')
        filters.pack(fill='x', padx=12, pady=(0, 10))
        filters.grid_columnconfigure(0, weight=1)
        self.session_search = ModernEntry(filters, placeholder_text='Search session title')
        self.session_search.grid(row=0, column=0, sticky='ew', padx=(0, 8))
        self.session_search.bind('<KeyRelease>', self.debounce_sessions)
        self.state_filter = ModernComboBox(filters, ['All', 'Draft', 'Open', 'Closed', 'Locked'],
            command=lambda _v: self.refresh_sessions(reset=True), width=110)
        self.state_filter.grid(row=0, column=1, padx=(0, 8))
        self.type_filter = ModernComboBox(filters, ['All types', 'Sunday Service', 'Ministry Meeting', 'Leadership Meeting',
            'Prayer Meeting', 'Church Meeting', 'Special Event', 'Sunday School', 'Other'],
            command=lambda _v: self.refresh_sessions(reset=True), width=165)
        self.type_filter.grid(row=0, column=2)
        dates = ctk.CTkFrame(toolbar, fg_color='transparent')
        dates.pack(fill='x', padx=12, pady=(0, 10))
        self.session_ministry = None
        if self.central or len(self.ministries) > 1:
            values = {'All ministries' if self.central else 'My ministries': None, **{m['name']: m['id'] for m in self.ministries}}
            self.session_ministry_map = values
            self.session_ministry = ModernComboBox(dates, list(values), width=185,
                command=lambda _v: self.refresh_sessions(reset=True))
            self.session_ministry.pack(side='left', padx=(0, 10))
        label(dates, 'From', 11, muted=True).pack(side='left', padx=(0, 5))
        self.date_from = DatePicker(dates, compact=True)
        self.date_from.pack(side='left', padx=(0, 10))
        label(dates, 'To', 11, muted=True).pack(side='left', padx=(0, 5))
        self.date_to = DatePicker(dates, compact=True)
        self.date_to.pack(side='left')
        for control in (self.date_from, self.date_to):
            control.variable.trace_add('write', lambda *_: self.debounce_sessions())
        ActionButton(dates, 'Clear', self.clear_session_filters, width=58).pack(side='right')
        self.session_rows = ctk.CTkScrollableFrame(self.workspace, fg_color='transparent', corner_radius=0)
        self.session_rows.grid(row=2, column=0, sticky='nsew')
        self.session_rows.grid_columnconfigure(0, weight=1)
        footer = ctk.CTkFrame(self.workspace, fg_color='transparent')
        footer.grid(row=3, column=0, sticky='ew', pady=(8, 0))
        self.session_page_label = label(footer, '', 12, muted=True)
        self.session_page_label.pack(side='left')
        ActionButton(footer, 'Trend', self.show_trend, width=75).pack(side='left', padx=12)
        self.session_previous = ActionButton(footer, 'Previous', lambda: self.session_page(-1), width=90)
        self.session_previous.pack(side='right', padx=6)
        self.session_next = ActionButton(footer, 'Next', lambda: self.session_page(1), width=75)
        self.session_next.pack(side='right')
        self.refresh_sessions()
        self.loader.submit('overview', self.service.overview, self.render_overview, self.failed)

    def render_overview(self, data):
        if self.mode != 'sessions':
            return
        self.overview_data = data
        for key, card in self.landing_cards.items():
            value = data[key]
            card.set('—' if value is None else f'{value:g}%' if key == 'rate' else value)

    def show_trend(self):
        dialog = FixedFooterDialog(self, 'Meeting attendance trend', self.context, width=650, height=540)
        dialog.cancel_button.configure(text='Close')
        rows = getattr(self, 'overview_data', {}).get('trend', [])
        if not rows:
            EmptyState(dialog.content, 'No completed meetings yet', 'Complete a ministry meeting to see attendance trends.').pack(fill='x')
        for row in rows:
            card = AppCard(dialog.content)
            card.pack(fill='x', padx=12, pady=8)
            label(card, row['title'], 14, True, anchor='w', wraplength=490).pack(fill='x', padx=16, pady=(12,4))
            label(card, display_date(row['date'])+f" · {row['rate']:g}% attendance", 12, muted=True).pack(anchor='w', padx=16)
            progress = ctk.CTkProgressBar(card, fg_color=theme.SURFACE_ALT, progress_color=theme.SECONDARY)
            progress.pack(fill='x', padx=16, pady=(8,16))
            progress.set(row['rate']/100)

    def debounce_sessions(self, _event=None):
        if self.search_timer:
            self.after_cancel(self.search_timer)
        self.search_timer = self.after(350, lambda: self.refresh_sessions(reset=True))

    def clear_session_filters(self):
        self.session_search.delete(0, 'end')
        self.state_filter.set('All')
        self.type_filter.set('All types')
        self.date_from.variable.set('')
        self.date_to.variable.set('')
        self.section.set('All')
        if self.session_ministry:
            self.session_ministry.set(next(iter(self.session_ministry_map)))
        self.refresh_sessions(reset=True)

    def session_page(self, direction):
        self.session_offset = max(0, self.session_offset + direction*25)
        self.refresh_sessions()

    def refresh_sessions(self, reset=False):
        self.search_timer = None
        if self.mode != 'sessions':
            return
        if reset:
            self.session_offset = 0
        try:
            params = dict(state=self.state_filter.get().upper(), search=self.session_search.get(), offset=self.session_offset,
                ministry_id=self.session_ministry_map[self.session_ministry.get()] if self.session_ministry else None,
                session_type=None if self.type_filter.get() == 'All types' else self.type_filter.get().upper().replace(' ', '_'),
                date_from=self.date_from.get_date() if self.date_from.variable.get().strip() else None,
                date_to=self.date_to.get_date() if self.date_to.variable.get().strip() else None)
            section = self.section.get()
            if section in {'Draft', 'Open'}:
                params['state'] = section.upper()
            elif section != 'All':
                params['section'] = section.upper()
        except ValueError as exc:
            self.failed(exc)
            return
        self.loader.submit('sessions', lambda: self.service.list_sessions(**params), self.render_sessions, self.failed)

    def render_sessions(self, data):
        if self.mode != 'sessions':
            return
        self.session_total = data['total']
        for child in self.session_rows.winfo_children():
            child.destroy()
        self.session_page_label.configure(text=f"{self.session_total} sessions · Page {self.session_offset//25+1}")
        self.session_previous.configure(state='normal' if self.session_offset else 'disabled')
        self.session_next.configure(state='normal' if self.session_offset+25 < self.session_total else 'disabled')
        if not data['rows']:
            EmptyState(self.session_rows, 'No sessions in this view', 'Create attendance or adjust the filters.').grid(sticky='ew')
        for index, session in enumerate(data['rows']):
            SessionRow(self.session_rows, session, self.open_session).grid(row=index, column=0, sticky='ew', padx=2, pady=4)
        self.notice.grid_remove()

    def create_attendance(self):
        CreateAttendanceDialog(self, self.service, self.create_ministries, self.capabilities,
                               lambda session: self.open_session(session["id"]))

    def manage_access(self):
        dialog = MinistryAccessDialog(self, self.service)
        dialog.bind("<Destroy>", lambda event: self.bootstrap() if event.widget == dialog and self.winfo_exists() else None, add="+")

    def open_session(self, session_id):
        if not self.ready_flag:
            self.pending_session = session_id
            return
        self.loader.submit("open_session", lambda: self.service.get_session(session_id), self.build_roster, self.failed)

    def build_roster(self, session):
        self.mode = "roster"
        self.current_session, self.roster_offset = session, 0
        self.clear_workspace()
        self.workspace.grid_rowconfigure(3, weight=1)
        summary = AppCard(self.workspace)
        summary.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        summary.grid_columnconfigure(0, weight=1)
        label(summary, session["title"], 21, True, anchor="w").grid(row=0, column=0, sticky="ew", padx=16, pady=(10, 0))
        detail = f"{display_date(session['session_date'])} · {session['session_type'].replace('_', ' ').title()} · {session['ministry_name']}"
        if session["start_time"]:
            detail += " · " + session["start_time"].strftime("%H:%M")
        if session["end_time"]:
            detail += "–" + session["end_time"].strftime("%H:%M")
        label(summary, detail, 12, muted=True, anchor="w").grid(row=1, column=0, sticky="ew", padx=16)
        StatusBadge(summary, session["state"]).grid(row=0, column=1, rowspan=2, padx=16)
        if session["description"]:
            label(summary, session["description"], 12, muted=True, anchor="w", wraplength=800).grid(row=2, column=0, columnspan=2, sticky="ew", padx=16)
        actions = ctk.CTkFrame(summary, fg_color="transparent")
        actions.grid(row=3, column=0, columnspan=2, sticky="ew", padx=16, pady=(8, 12))
        ActionButton(actions, "All sessions", self.show_sessions, width=105).pack(side="left", padx=(0, 7))
        for action, available in session["actions"].items():
            if available:
                title = {"open": "Open session", "close": "Close session", "reopen": "Reopen", "unlock": "Unlock / reopen", "lock": "Lock"}[action]
                ActionButton(actions, title, lambda a=action: self.change_state(a), width=105).pack(side="left", padx=3)
        if "ATTENDANCE_EXPORT" in self.capabilities["permissions"]:
            ActionButton(actions, "Export CSV", self.export, width=105).pack(side="right", padx=3)
        if "ATTENDANCE_VIEW_AUDIT" in self.capabilities["permissions"]:
            ActionButton(actions, "History", self.show_audit, width=80).pack(side="right", padx=3)
        stats_bar = ctk.CTkFrame(self.workspace, fg_color="transparent")
        stats_bar.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.stat_cards = {}
        for index, (key, title) in enumerate((('eligible','Eligible'),('PRESENT','Present'),('LATE','Late'),
                                             ('EXCUSED','Excused'),('ABSENT','Absent'),('rate','Attendance rate'))):
            stats_bar.grid_columnconfigure(index, weight=1, uniform="stat")
            card = StatCard(stats_bar, title)
            card.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 4, 0 if index == 5 else 4))
            self.stat_cards[key] = card
        filters = AppCard(self.workspace)
        filters.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        filters.grid_columnconfigure(0, weight=1)
        self.search = ModernEntry(filters, placeholder_text="Name, membership number or phone")
        self.search.grid(row=0, column=0, sticky="ew", padx=(12, 5), pady=8)
        self.search.bind("<KeyRelease>", self.debounce_search)
        choices = self.ministry_map if not session["ministry_id"] else {session["ministry_name"]: session["ministry_id"]}
        if not self.central and len(self.ministries) == 1 and not session['ministry_id']:
            choices = {self.ministries[0]['name']: self.ministries[0]['id']}
        self.roster_ministry_map = choices
        self.ministry_filter = None
        if len(choices) > 1:
            self.ministry_filter = ModernComboBox(filters, list(choices), command=lambda _v: self.refresh_roster(reset=True), width=180)
            self.ministry_filter.grid(row=0, column=1, padx=5)
        self.status_filter = ModernComboBox(filters, ["All", "Unmarked", "Present", "Late", "Excused", "Absent"],
                                           command=lambda _v: self.refresh_roster(reset=True), width=128)
        self.status_filter.grid(row=0, column=2, padx=5)
        ActionButton(filters, "Refresh", self.refresh_roster, width=78).grid(row=0, column=3, padx=(5, 12))
        self.roster_rows = ctk.CTkScrollableFrame(self.workspace, fg_color="transparent", corner_radius=0)
        self.roster_rows.grid(row=3, column=0, sticky="nsew")
        self.roster_rows.grid_columnconfigure(0, weight=1)
        footer = ctk.CTkFrame(self.workspace, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self.roster_page_label = label(footer, "", 12, muted=True)
        self.roster_page_label.pack(side="left")
        self.roster_previous = ActionButton(footer, "Previous", lambda: self.roster_page(-1), width=100)
        self.roster_previous.pack(side="right", padx=6)
        self.roster_next = ActionButton(footer, "Next", lambda: self.roster_page(1), width=85)
        self.roster_next.pack(side="right")
        self.refresh_roster()

    def debounce_search(self, _event=None):
        if self.search_timer:
            self.after_cancel(self.search_timer)
        self.search_timer = self.after(280, lambda: self.refresh_roster(reset=True))

    def roster_page(self, direction):
        self.roster_offset = max(0, self.roster_offset + direction*self.PAGE_SIZE)
        self.refresh_roster()

    def refresh_roster(self, reset=False):
        self.search_timer = None
        if self.mode != "roster":
            return
        if reset:
            self.roster_offset = 0
        sid = self.current_session["id"]
        search, ministry, status = self.search.get(), self.roster_ministry_id(), self.status_filter.get().upper()
        offset = self.roster_offset
        self.loader.submit("roster", lambda: (self.service.get_session(sid),
            self.service.roster(sid, search, ministry, status, self.PAGE_SIZE, offset)), self.render_roster, self.failed)

    def render_roster(self, result):
        session, data = result
        if self.mode != "roster" or session["id"] != self.current_session["id"]:
            return
        if session["state"] != self.current_session["state"]:
            self.build_roster(session)
            return
        ids = [member['id'] for member in data['rows']]
        if ids != list(self.rendered_rows):
            for child in self.roster_rows.winfo_children():
                child.destroy()
            self.rendered_rows, self.row_data = {}, {}
        self.roster_total = data["total"]
        for key, card in self.stat_cards.items():
            value = data["stats"][key]
            card.set(f"{value:g}%" if key == "rate" else value)
        self.roster_page_label.configure(text=f"{self.roster_total} matching members · Page {self.roster_offset//self.PAGE_SIZE+1} · {data['stats']['unmarked']} unmarked")
        self.roster_previous.configure(state="normal" if self.roster_offset else "disabled")
        self.roster_next.configure(state="normal" if self.roster_offset+self.PAGE_SIZE < self.roster_total else "disabled")
        if not data["rows"]:
            EmptyState(self.roster_rows, "No members in this view", "Adjust your filters or review the saved session roster.").grid(sticky="ew")
        for index, member in enumerate(data["rows"]):
            if self.row_data.get(member['id']) != member:
                old = self.rendered_rows.get(member['id'])
                if old:
                    old.destroy()
                self.rendered_rows[member['id']] = self.member_row(index, member)
                self.row_data[member['id']] = dict(member)
        self.notice.configure(text="", text_color=theme.TEXT_MUTED)
        self.notice.grid_remove()

    def member_row(self, index, member):
        card = AppCard(self.roster_rows)
        card.grid(row=index, column=0, sticky="ew", padx=2, pady=4)
        card.grid_columnconfigure(1, weight=3)
        card.grid_columnconfigure(2, weight=1)
        Avatar(card, member["full_name"], member["photo_path"]).grid(row=0, column=0, padx=(12, 10), pady=12)
        person = ctk.CTkFrame(card, fg_color="transparent")
        person.grid(row=0, column=1, sticky="ew", pady=10)
        label(person, member["full_name"], 14, True, anchor="w").pack(fill="x")
        label(person, f"{member['member_no']} · {member['phone'] or 'No phone'}", 11, muted=True, anchor="w").pack(fill="x")
        label(card, ", ".join(member["ministries"]) or "No ministry", 11, muted=True,
              wraplength=140, anchor="w", justify="left").grid(row=0, column=2, sticky="ew", padx=10)
        StatusBadge(card, member["attendance_status"]).grid(row=0, column=3, padx=10)
        marker = ctk.CTkFrame(card, fg_color="transparent")
        marker.grid(row=0, column=4, padx=12)
        label(marker, member["marked_by"] or "Not marked", 11, muted=True, wraplength=135).pack()
        if member["marked_at"]:
            label(marker, member["marked_at"].astimezone().strftime("%H:%M"), 11, muted=True).pack()
        actions = ctk.CTkFrame(card, fg_color="transparent")
        if member["attendance_status"]:
            actions.grid(row=0, column=5, sticky="e", padx=(0, 10), pady=8)
            if member["can_correct"]:
                ActionButton(actions, "Change", lambda: self.correct(member), width=65).pack(side="left", padx=3)
        elif member["can_record"]:
            actions.grid(row=1, column=1, columnspan=4, sticky="e", padx=12, pady=(0, 10))
            for status in ("PRESENT", "LATE", "EXCUSED", "ABSENT"):
                button = ActionButton(actions, status.title(), lambda s=status: self.mark(member, s),
                                      "primary" if status == "PRESENT" else "secondary", width=80)
                button.pack(side="left", padx=3)
                if member["id"] in self.pending_marks:
                    button.configure(state="disabled")
        if member["attendance_status"] and "ATTENDANCE_VIEW_AUDIT" in self.capabilities["permissions"]:
            ActionButton(actions, "History", lambda: self.show_audit(member["id"]), width=65).pack(side="left", padx=3)
        card.action_buttons = actions.winfo_children()
        return card

    def roster_ministry_id(self):
        if self.ministry_filter:
            return self.roster_ministry_map[self.ministry_filter.get()]
        return next(iter(self.roster_ministry_map.values()))

    def mark(self, member, status):
        if member["id"] in self.pending_marks:
            return
        self.pending_marks.add(member["id"])
        row = self.rendered_rows.get(member['id'])
        if row:
            for button in row.action_buttons:
                button.configure(state='disabled')
        sid = self.current_session["id"]
        def completed(error=None):
            self.pending_marks.discard(member["id"])
            if error:
                if row and row.winfo_exists():
                    for button in row.action_buttons:
                        button.configure(state='normal')
                self.failed(error)
            else:
                self.refresh_roster()
        self.loader.submit("mark:"+member["id"], lambda: self.service.mark(sid, member["id"], status),
                           lambda _result: completed(), completed)

    def correct(self, member):
        CorrectAttendanceDialog(self, self.service, self.current_session["id"], member, self.refresh_roster)

    def show_audit(self, member_id=None):
        AttendanceAuditDialog(self, self.service, self.current_session["id"], member_id)

    def change_state(self, action):
        sid = self.current_session["id"]
        detail = "Only unmarked members on this session's saved roster will become absent." if action == "close" else "This change will be recorded in the session history."
        def confirm(reason, dialog):
            dialog.confirm_button.configure(state="disabled")
            def success(_result):
                dialog.destroy()
                self.open_session(sid)
            def failed(error):
                dialog.error_var.set(str(error))
                dialog.confirm_button.configure(state="normal")
            dialog_loader = AsyncLoader(dialog)
            dialog_loader.submit("transition", lambda: self.service.transition(sid, action, reason=reason), success, failed)
        ConfirmationDialog(self, action.replace("_", " ").title()+" session", detail, confirm,
                           require_reason=action in {"reopen", "unlock", "lock"})

    @staticmethod
    def csv_cell(value):
        text = str(value or "")
        return "'"+text if text.lstrip().startswith(("=", "+", "-", "@")) else text

    def export(self):
        path = filedialog.asksaveasfilename(parent=self.winfo_toplevel(), defaultextension=".csv",
            initialfile="attendance_"+self.current_session["session_date"].isoformat()+".csv",
            filetypes=[("CSV report", "*.csv")])
        if not path:
            return
        sid, search, ministry, status = self.current_session["id"], self.search.get(), self.roster_ministry_id(), self.status_filter.get().upper()
        def write():
            rows, offset = [], 0
            while True:
                page = self.service.roster(sid, search, ministry, status, 200, offset, report=True)
                rows.extend(page["rows"])
                offset += 200
                if offset >= page["total"]:
                    break
            with Path(path).open("w", encoding="utf-8-sig", newline="") as output:
                writer = csv.writer(output)
                writer.writerow(["Member number", "Name", "Phone", "Ministries", "Status", "Originally marked by", "Original mark time"])
                for row in rows:
                    writer.writerow([self.csv_cell(row["member_no"]), self.csv_cell(row["full_name"]), self.csv_cell(row["phone"]),
                        self.csv_cell(", ".join(row["ministries"])), row["attendance_status"] or "UNMARKED",
                        self.csv_cell(row["marked_by"]), row["marked_at"].astimezone().strftime("%d/%m/%Y %H:%M:%S") if row["marked_at"] else ""])
            return len(rows)
        def exported(count):
            self.notice.configure(text=f"Exported {count} permitted members.", text_color=theme.SUCCESS)
            self.notice.grid()
        self.loader.submit("export", write, exported, self.failed)

    def destroy(self):
        if self.search_timer:
            self.after_cancel(self.search_timer)
        self.loader.close()
        if self.action_master is not None and self.create_button.winfo_exists():
            self.create_button.destroy()
        super().destroy()
