from datetime import date
import customtkinter as ctk
from src.models import AttendanceSessionType
from src.ui import theme
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.date_picker import DatePicker, display_date
from src.ui.components.modern import ActionButton, AppCard, FixedFooterDialog, ModernComboBox, ModernEntry, StatusBadge, font, label


def field(parent, text, row, column=0):
    shell = ctk.CTkFrame(parent, fg_color='transparent')
    shell.grid(row=row, column=column, sticky='ew', padx=12, pady=8)
    label(shell, text, 12, True).pack(anchor='w', pady=(0, 4))
    return shell


class CreateAttendanceDialog(FixedFooterDialog):
    def __init__(self, master, service, ministries, capabilities, on_saved):
        super().__init__(master, 'Create Attendance', 'Prepare a service or meeting for your chosen date.', height=660)
        self.service, self.on_saved = service, on_saved
        self.loader = AsyncLoader(self)
        self.selected_members = set()
        self.ministry_map = {m['name']: m['id'] for m in ministries}
        self.central = 'ATTENDANCE_CREATE_GLOBAL' in capabilities['permissions']
        self.advanced = False
        self.content.grid_columnconfigure((0, 1), weight=1, uniform='fields')
        shell = field(self.content, 'Attendance title *', 0)
        shell.grid(columnspan=2)
        self.title_entry = ModernEntry(shell, placeholder_text='For example, Youth Weekly Meeting')
        self.title_entry.pack(fill='x')
        self.type_map = {item.value.replace('_', ' ').title(): item.value for item in AttendanceSessionType}
        types = list(self.type_map) if self.central else [name for name in self.type_map if name != 'Sunday Service']
        self.type_box = ModernComboBox(field(self.content, 'Attendance type *', 1), types, command=self.type_changed)
        self.type_box.set('Sunday Service' if self.central else 'Ministry Meeting')
        self.type_box.pack(fill='x')
        self.scope_shell = field(self.content, 'Scope *', 1, 1)
        self.scope_box = ModernComboBox(self.scope_shell, ['Whole Church', 'Ministry'], command=self.scope_changed)
        self.scope_box.set('Whole Church' if self.central else 'Ministry')
        self.scope_box.pack(fill='x')
        self.ministry_shell = field(self.content, 'Ministry', 2)
        self.ministry_box = ModernComboBox(self.ministry_shell, list(self.ministry_map) or ['No assigned ministry'], command=self.ministry_changed)
        if self.central or len(ministries) > 1:
            self.ministry_box.pack(fill='x')
        else:
            label(self.ministry_shell, next(iter(self.ministry_map), 'No assigned ministry'), 14, True).pack(anchor='w', pady=6)
        self.date_picker = DatePicker(field(self.content, 'Date *', 2, 1), initial_date=date.today())
        self.date_picker.pack(fill='x')
        self.start = ModernEntry(field(self.content, 'Start time (HH:MM)', 3), placeholder_text='Optional, e.g. 09:00')
        self.start.pack(fill='x')
        self.end = ModernEntry(field(self.content, 'End time (HH:MM)', 3, 1), placeholder_text='Optional, e.g. 11:30')
        self.end.pack(fill='x')
        self.roster_info = label(field(self.content, 'Members included', 4), '', 12, muted=True, wraplength=280, justify='left')
        self.roster_info.pack(anchor='w')
        self.state_box = ModernComboBox(field(self.content, 'Initial state', 4, 1), ['Open', 'Draft'])
        self.state_box.pack(fill='x')
        shell = field(self.content, 'Description', 5)
        shell.grid(columnspan=2)
        self.description = ctk.CTkTextbox(shell, height=64, fg_color=theme.INPUT, text_color=theme.TEXT,
                                         border_width=1, border_color=theme.BORDER, font=font())
        self.description.pack(fill='x')
        self.advanced_button = ActionButton(self.content, 'Advanced roster options', self.toggle_advanced)
        self.advanced_button.grid(row=6, column=0, columnspan=2, sticky='w', padx=12, pady=8)
        self.roster_shell = field(self.content, 'Roster strategy', 7)
        self.roster_shell.grid(columnspan=2)
        self.roster_box = ModernComboBox(self.roster_shell, ['Whole Church'], command=self.roster_changed)
        self.roster_box.pack(fill='x')
        self.selected_shell = field(self.content, 'Selected members', 8)
        self.selected_shell.grid(columnspan=2)
        self.select_button = ActionButton(self.selected_shell, 'Choose members', self.choose_members)
        self.select_button.pack(anchor='w')
        self.selection_label = label(self.selected_shell, '', 12, muted=True)
        self.selection_label.pack(anchor='w')
        self.save_button = ActionButton(self.footer, 'Create Attendance', self.save, 'primary', width=170)
        self.save_button.pack(side='right', padx=18, pady=14)
        self.type_changed(self.type_box.get())
        self.bind('<Control-Return>', lambda _event: self.save())

    def type_changed(self, value):
        if self.type_map[value] == 'SUNDAY_SERVICE':
            self.scope_box.set('Whole Church')
        elif self.type_map[value] == 'LEADERSHIP_MEETING' and self.ministry_map:
            self.scope_box.set('Ministry')
        self.scope_changed(self.scope_box.get())

    def scope_changed(self, scope):
        self.selected_members.clear()
        sunday = self.type_map[self.type_box.get()] == 'SUNDAY_SERVICE'
        self.type_box.master.grid(columnspan=1 if self.central and not sunday else 2)
        if self.central and not sunday:
            self.scope_shell.grid()
        else:
            self.scope_shell.grid_remove()
        if scope == 'Ministry':
            self.date_picker.master.grid(column=1, columnspan=1)
            self.ministry_shell.grid()
            options = ['All Ministry Members', 'Ministry Leadership', 'Selected Members']
            default = 'Ministry Leadership' if self.type_map[self.type_box.get()] == 'LEADERSHIP_MEETING' else options[0]
        else:
            self.date_picker.master.grid(column=0, columnspan=2)
            self.ministry_shell.grid_remove()
            options, default = ['Whole Church', 'Selected Members'], 'Whole Church'
        self.roster_box.configure(values=options)
        self.roster_box.set(default)
        self.advanced = False
        if sunday:
            self.advanced_button.grid_remove()
        else:
            self.advanced_button.grid()
        self.roster_changed(default)

    def toggle_advanced(self):
        self.advanced = not self.advanced
        if not self.advanced:
            default = 'Whole Church' if self.scope_box.get() == 'Whole Church' else (
                'Ministry Leadership' if self.type_map[self.type_box.get()] == 'LEADERSHIP_MEETING' else 'All Ministry Members')
            self.roster_box.set(default)
            self.selected_members.clear()
        self.roster_changed(self.roster_box.get())

    def ministry_changed(self, _value):
        self.selected_members.clear()
        self.roster_changed(self.roster_box.get())

    def roster_changed(self, value):
        if self.advanced:
            self.roster_shell.grid()
        else:
            self.roster_shell.grid_remove()
        if self.advanced and value == 'Selected Members':
            self.selected_shell.grid()
        else:
            self.selected_shell.grid_remove()
        self.selection_label.configure(text=f'{len(self.selected_members)} members selected')
        self.roster_info.configure(text={'Whole Church': 'All active church members are included automatically.',
            'All Ministry Members': 'All active members of this ministry are included automatically.',
            'Ministry Leadership': 'Active ministry members with an assigned position are included automatically.',
            'Selected Members': f'{len(self.selected_members)} selected members.'}[value])
        self.advanced_button.configure(text='Use automatic roster' if self.advanced else 'Advanced roster options')

    def ministry_id(self):
        return self.ministry_map.get(self.ministry_box.get()) if self.scope_box.get() == 'Ministry' else None

    def choose_members(self):
        MemberSelectionDialog(self, self.service, self.ministry_id(), self.selected_members, self.selection_saved)

    def selection_saved(self, selected):
        self.selected_members = selected
        self.roster_changed('Selected Members')

    def save(self):
        if self.save_button.cget('state') == 'disabled':
            return
        try:
            payload = dict(title=self.title_entry.get(), session_type=self.type_map[self.type_box.get()],
                scope_type='GLOBAL' if self.scope_box.get() == 'Whole Church' else 'MINISTRY', session_date=self.date_picker.get_date(),
                ministry_id=self.ministry_id(), roster_type=self.roster_box.get().upper().replace(' ', '_'),
                selected_member_ids=list(self.selected_members), description=self.description.get('1.0', 'end').strip(),
                start_time=self.start.get(), end_time=self.end.get(), state=self.state_box.get().upper())
        except ValueError as exc:
            self.error_var.set(str(exc)); return
        self.save_button.configure(state='disabled', text='Creating...')
        self.loader.submit('save', lambda: self.service.create_session(**payload), self.saved, self.failed)

    def saved(self, session):
        self.on_saved(session)
        self.destroy()

    def failed(self, error):
        self.error_var.set(str(error))
        self.save_button.configure(state='normal', text='Create Attendance')


class MemberSelectionDialog(FixedFooterDialog):
    def __init__(self, master, service, ministry_id, selected, on_saved):
        super().__init__(master, "Choose roster members", "Select from eligible active members.", height=600)
        self.service, self.ministry_id, self.on_saved = service, ministry_id, on_saved
        self.selected = set(selected)
        self.offset, self.total = 0, 0
        self.loader = AsyncLoader(self)
        self.search = ModernEntry(self.header, placeholder_text="Name, membership number or phone")
        self.search.pack(fill="x", padx=18, pady=(0, 12))
        self.search.bind("<Return>", lambda _e: self.refresh(reset=True))
        ActionButton(self.footer, "Previous", lambda: self.page(-1), width=80).pack(side="left", padx=4)
        ActionButton(self.footer, "Next", lambda: self.page(1), width=80).pack(side="left", padx=4)
        ActionButton(self.footer, "Use selection", self.save, "primary").pack(side="right", padx=18, pady=14)
        self.refresh()

    def page(self, direction):
        self.offset = max(0, min(self.offset+direction*50, max(0, (self.total-1)//50*50)))
        self.refresh()

    def refresh(self, reset=False):
        if reset:
            self.offset = 0
        search, offset = self.search.get(), self.offset
        self.loader.submit("members", lambda: self.service.candidate_members(self.ministry_id, search, offset),
                           self.render, lambda error: self.error_var.set(str(error)))

    def render(self, data):
        self.total = data["total"]
        for child in self.content.winfo_children():
            child.destroy()
        for member in data["rows"]:
            button = ActionButton(self.content, "", width=400)
            button.member = member
            button.configure(command=lambda b=button: self.toggle(b))
            button.pack(fill="x", padx=12, pady=4)
            self.style(button)
        self.error_var.set(f"{len(self.selected)} selected · {self.total} eligible members")

    def style(self, button):
        member = button.member
        selected = member["id"] in self.selected
        button.configure(text=f"{'Selected' if selected else 'Select'}  |  {member['full_name']}  |  {member['member_no']}",
            fg_color=theme.SECONDARY if selected else theme.SURFACE_ALT,
            text_color="#FFFFFF" if selected else theme.TEXT,
            hover_color=theme.SECONDARY_HOVER if selected else theme.BORDER)

    def toggle(self, button):
        mid = button.member["id"]
        self.selected.symmetric_difference_update({mid})
        self.style(button)
        self.error_var.set(f"{len(self.selected)} selected · {self.total} eligible members")

    def save(self):
        if not self.selected:
            self.error_var.set("Select at least one member.")
            return
        self.on_saved(set(self.selected))
        parent = self.master.winfo_toplevel()
        self.destroy()
        if parent.winfo_exists():
            parent.grab_set()


class CorrectAttendanceDialog(FixedFooterDialog):
    def __init__(self, master, service, session_id, member, on_saved):
        super().__init__(master, "Correct Attendance", member["full_name"] + " · " + member["member_no"], height=480)
        self.service, self.session_id, self.member, self.on_saved = service, session_id, member, on_saved
        self.loader = AsyncLoader(self)
        label(self.content, "Current status", 12, True).pack(anchor="w", padx=16, pady=(14, 4))
        StatusBadge(self.content, member["attendance_status"]).pack(anchor="w", padx=16)
        label(self.content, "New status *", 12, True).pack(anchor="w", padx=16, pady=(14, 4))
        self.status = ModernComboBox(self.content, ["Present", "Late", "Excused", "Absent"])
        self.status.set(member["attendance_status"].title())
        self.status.pack(fill="x", padx=16)
        label(self.content, "Reason for correction *", 12, True).pack(anchor="w", padx=16, pady=(14, 4))
        self.reason = ModernEntry(self.content, placeholder_text="For example, presence confirmed after roll verification")
        self.reason.pack(fill="x", padx=16, pady=(0, 16))
        self.save_button = ActionButton(self.footer, "Save Correction", self.save, "primary", width=160)
        self.save_button.pack(side="right", padx=18, pady=14)

    def save(self):
        reason, status = self.reason.get().strip(), self.status.get().upper()
        if not reason:
            self.error_var.set("A correction reason is required.")
            return
        if self.save_button.cget("state") == "disabled":
            return
        self.save_button.configure(state="disabled")
        self.loader.submit("save", lambda: self.service.mark(self.session_id, self.member["id"], status,
            reason=reason, expected_status=self.member["attendance_status"]), self.saved, self.failed)

    def saved(self, _result):
        self.on_saved()
        self.destroy()

    def failed(self, error):
        self.error_var.set(str(error))
        self.save_button.configure(state="normal")


class AttendanceAuditDialog(FixedFooterDialog):
    def __init__(self, master, service, session_id, member_id=None):
        super().__init__(master, "Attendance history", "Original marking, corrections and session changes.", width=820)
        self.service, self.session_id, self.member_id = service, session_id, member_id
        self.loader, self.offset = AsyncLoader(self), 0
        self.cancel_button.configure(text="Close")
        ActionButton(self.footer, "Previous", lambda: self.page(-1), width=100).pack(side="left", padx=4)
        self.next_button = ActionButton(self.footer, "Next", lambda: self.page(1), width=100)
        self.next_button.pack(side="right", padx=18, pady=14)
        self.refresh()

    def page(self, direction):
        self.offset = max(0, self.offset+direction*100)
        self.refresh()

    def refresh(self):
        offset = self.offset
        self.loader.submit("audit", lambda: self.service.audit_history(self.session_id, self.member_id, offset),
                           self.render, lambda error: self.error_var.set(str(error)))

    def render(self, rows):
        for child in self.content.winfo_children():
            child.destroy()
        self.next_button.configure(state="normal" if len(rows) == 100 else "disabled")
        if not rows:
            label(self.content, "No history entries on this page.", muted=True).pack(pady=32)
        for entry in rows:
            card = AppCard(self.content)
            card.pack(fill="x", padx=12, pady=5)
            stamp = entry["changed_at"].astimezone().strftime("%d/%m/%Y %H:%M:%S")
            label(card, f"{entry['action'].replace('_', ' ').title()} · {entry['member'] or 'Session'}", 13, True).pack(anchor="w", padx=12, pady=(8, 0))
            label(card, f"{entry['old_status'] or 'Unmarked'} to {entry['new_status'] or '—'} · {entry['changed_by']} · {stamp}", 12, muted=True).pack(anchor="w", padx=12)
            if entry["reason"]:
                label(card, entry["reason"], 12, wraplength=650, justify="left").pack(anchor="w", padx=12, pady=(0, 10))


class MinistryAccessDialog(FixedFooterDialog):
    FIELDS = {"can_view_attendance": "View attendance", "can_create_attendance": "Create ministry sessions",
              "can_record_attendance": "Mark members", "can_correct_attendance": "Correct open attendance",
              "can_close_attendance": "Close ministry sessions", "can_view_reports": "Export ministry reports",
              "is_active": "Scope enabled"}

    def __init__(self, master, service):
        super().__init__(master, "Ministry attendance access", "Grant access to an existing user for a specific ministry.", height=650)
        self.service, self.loader = service, AsyncLoader(self)
        self.variables = {field: ctk.BooleanVar(master=self, value=False) for field in self.FIELDS}
        self.assign_role = ctk.BooleanVar(master=self, value=False)
        self.save_button = ActionButton(self.footer, "Save access", self.save, "primary")
        self.save_button.pack(side="right", padx=18, pady=14)
        self.save_button.configure(state="disabled")
        self.loader.submit("config", self.service.access_configuration, self.build, lambda error: self.error_var.set(str(error)))

    def build(self, data):
        self.data = data
        self.user_map = {u["name"]: u["id"] for u in data["users"]}
        self.ministry_map = {m["name"]: m["id"] for m in data["ministries"]}
        label(self.content, "User", 12, True).pack(anchor="w", padx=16, pady=(12, 4))
        self.user_box = ModernComboBox(self.content, list(self.user_map) or ["No users"], command=self.load_scope)
        self.user_box.pack(fill="x", padx=16)
        label(self.content, "Ministry", 12, True).pack(anchor="w", padx=16, pady=(12, 4))
        self.ministry_box = ModernComboBox(self.content, list(self.ministry_map) or ["No ministries"], command=self.load_scope)
        self.ministry_box.pack(fill="x", padx=16, pady=(0, 10))
        ActionButton(self.content, "Use ministry leader permissions", self.leader_preset).pack(anchor="w", padx=16, pady=8)
        for key, title in self.FIELDS.items():
            ctk.CTkSwitch(self.content, text=title, variable=self.variables[key], font=font(),
                          text_color=theme.TEXT, progress_color=theme.SECONDARY).pack(anchor="w", padx=16, pady=5)
        ctk.CTkSwitch(self.content, text="Assign Ministry Attendance Leader role", variable=self.assign_role,
                      font=font(), text_color=theme.TEXT).pack(anchor="w", padx=16, pady=(14, 8))
        label(self.content, "Existing central permissions remain separate from ministry grants.", 12, muted=True).pack(anchor="w", padx=16, pady=8)
        self.save_button.configure(state="normal" if self.user_map and self.ministry_map else "disabled")
        self.load_scope()

    def load_scope(self, _value=None):
        uid, mid = self.user_map.get(self.user_box.get()), self.ministry_map.get(self.ministry_box.get())
        grant = next((s for s in self.data["scopes"] if s["user_id"] == uid and s["ministry_id"] == mid), {})
        for key, variable in self.variables.items():
            variable.set(grant.get(key, key == "is_active"))
        self.assign_role.set(False)

    def leader_preset(self):
        for variable in self.variables.values():
            variable.set(True)
        self.assign_role.set(True)

    def save(self):
        if self.save_button.cget("state") == "disabled":
            return
        uid, mid = self.user_map[self.user_box.get()], self.ministry_map[self.ministry_box.get()]
        grants = {key: variable.get() for key, variable in self.variables.items()}
        assign = self.assign_role.get()
        self.save_button.configure(state="disabled")
        self.loader.submit("save", lambda: self.service.set_ministry_scope(uid, mid, grants, assign_leader_role=assign),
                           lambda _result: self.destroy(), self.failed)

    def failed(self, error):
        self.error_var.set(str(error))
        self.save_button.configure(state="normal")
