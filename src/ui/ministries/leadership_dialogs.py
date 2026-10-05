"""Fixed-footer position and appointment forms with explicit exceptional workflows."""
from datetime import date
import customtkinter as ctk
from src.services.ministry_leadership_service import MembershipRequiredError, PositionConflictError
from src.ui import theme
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.date_picker import DatePicker, display_date
from src.ui.components.modern import ActionButton, AppCard, Avatar, ConfirmationDialog, FixedFooterDialog, ModernEntry, StatusBadge, font, label
from src.ui.components.modern_select import ModernSelect
from src.ui.components.search_field import SearchField
from src.ui.ministries.dialogs import suggest_code


def heading(parent, text):
    label(parent, text, 12, True, anchor='w').pack(fill='x', padx=16, pady=(16, 6))


def textbox(parent, initial=''):
    widget = ctk.CTkTextbox(parent, height=100, corner_radius=11, border_width=1,
        fg_color=theme.INPUT, text_color=theme.TEXT, border_color=theme.BORDER, font=font())
    widget.pack(fill='x', padx=16, pady=(0, 10))
    widget.insert('1.0', initial or '')
    return widget


class LeadershipDialog(FixedFooterDialog):
    def __init__(self, master, title, subtitle='', **kwargs):
        super().__init__(master, title, subtitle, **kwargs)
        self.loader = AsyncLoader(self)

    def run(self, operation):
        if self.save_button.cget('state') == 'disabled':
            return
        self.error_var.set('')
        self.save_button.configure(state='disabled')
        self.loader.submit('save', operation, self.saved, self.failed)

    def saved(self, _result):
        self.on_saved()
        self.destroy()

    def failed(self, error):
        self.error_var.set(str(error))
        self.save_button.configure(state='normal')

    def destroy(self):
        parent = self.master.winfo_toplevel()
        super().destroy()
        if parent.winfo_exists() and isinstance(parent, ctk.CTkToplevel):
            parent.grab_set()


class PositionFormDialog(LeadershipDialog):
    def __init__(self, master, service, ministry, on_saved, position=None, capabilities=None):
        super().__init__(master, 'Edit position' if position else 'Add ministry position', ministry['name'], width=710, height=750)
        self.service, self.ministry, self.on_saved, self.position = service, ministry, on_saved, position
        self.capabilities = capabilities or {}
        heading(self.content, 'Position name *')
        self.name = ModernEntry(self.content, height=46)
        self.name.pack(fill='x', padx=16)
        self.name.insert(0, position['name'] if position else '')
        heading(self.content, 'Code *')
        self.code = ModernEntry(self.content, height=46)
        self.code.pack(fill='x', padx=16)
        self.code.insert(0, position['code'] if position else '')
        if position and position['in_use']:
            self.code.configure(state='disabled', fg_color=theme.DISABLED_INPUT, text_color=theme.TEXT_MUTED)
            label(self.content, 'Code is locked because appointment history exists.', 11, muted=True).pack(anchor='w', padx=16, pady=6)
        else:
            ActionButton(self.content, 'Suggest code from name', self.suggest).pack(anchor='w', padx=16, pady=6)
        heading(self.content, 'Description')
        self.description = textbox(self.content, position['description'] if position else '')
        heading(self.content, 'Leadership position')
        self.leadership = ModernSelect(self.content, ['Yes', 'No'])
        self.leadership.set('No' if position and not position['is_leadership'] else 'Yes')
        self.leadership.pack(fill='x', padx=16)
        heading(self.content, 'Display order')
        self.order = ModernEntry(self.content, height=46)
        self.order.pack(fill='x', padx=16)
        self.order.insert(0, str(position['sort_order'] if position else 0))
        heading(self.content, 'Maximum current holders')
        self.maximum = ModernEntry(self.content, placeholder_text='Positive number, or leave blank for Unlimited', height=46)
        self.maximum.pack(fill='x', padx=16)
        maximum = position['max_current_holders'] if position else 1
        if maximum is not None:
            self.maximum.insert(0, str(maximum))
        heading(self.content, 'Status')
        self.status = ModernSelect(self.content, ['Active', 'Inactive'])
        self.status.set('Inactive' if position and not position['is_active'] else 'Active')
        if position and not self.capabilities.get('position_archive'):
            self.status.configure(state='disabled')
        self.status.pack(fill='x', padx=16, pady=(0, 18))
        self.save_button = ActionButton(self.footer, 'Save position', self.save, 'primary', width=160)
        self.save_button.pack(side='right', padx=18, pady=14)

    def suggest(self):
        self.code.delete(0, 'end')
        self.code.insert(0, suggest_code(self.name.get()))

    def save(self):
        data = dict(name=self.name.get(), code=self.code.get(), description=self.description.get('1.0','end-1c'),
            sort_order=self.order.get(), max_current_holders=self.maximum.get(), is_leadership=self.leadership.get() == 'Yes', is_active=self.status.get() == 'Active')
        try:
            self.service._position_values(data)
        except Exception as error:
            self.error_var.set(str(error))
            return
        def operation():
            if self.position:
                return self.service.update_position(self.position['id'], data, self.position['updated_at'])
            return self.service.create_position(self.ministry['id'], data)
        if self.position and self.position['is_active'] and not data['is_active']:
            return self.confirm_change('Deactivate position', 'Current appointments must be ended first. All past appointments will remain available.', lambda:self.run(operation))
        self.run(operation)

    def confirm_change(self, title, detail, operation):
        def confirmed(_reason, dialog):
            dialog.destroy()
            self.grab_set()
            operation()
        dialog = ConfirmationDialog(self, title, detail, confirmed)
        dialog.confirm_button.configure(text=title, width=170)
        return dialog


class LeadershipMemberPicker(LeadershipDialog):
    PAGE_SIZE = 20
    def __init__(self, master, service, ministry, on_selected):
        super().__init__(master, 'Choose member', 'Search by name, membership number or phone.', width=760, height=720)
        self.service, self.ministry, self.on_selected = service, ministry, on_selected
        self.offset, self.total = 0, 0
        self.cancel_button.configure(text='Close')
        self.search = SearchField(self.header, lambda:self.refresh(True), 'Name, member number or phone')
        self.search.pack(fill='x', padx=18, pady=(0, 14))
        self.notice = label(self.footer, 'Loading members…', 11, muted=True)
        self.notice.pack(side='left', padx=4)
        self.previous = ActionButton(self.footer, 'Previous', lambda:self.page(-1), width=85)
        self.previous.pack(side='right', padx=4, pady=14)
        self.next_button = ActionButton(self.footer, 'Next', lambda:self.page(1), width=70)
        self.next_button.pack(side='right', padx=8, pady=14)
        self.refresh()

    def page(self, direction):
        self.offset = max(0, min(self.offset+direction*self.PAGE_SIZE, (max(0, self.total-1)//self.PAGE_SIZE)*self.PAGE_SIZE))
        self.refresh()

    def refresh(self, reset=False):
        if reset:
            self.offset = 0
        params = dict(search=self.search.get(), offset=self.offset, limit=self.PAGE_SIZE)
        self.loader.submit('members', lambda:self.service.candidate_members(self.ministry['id'], **params), self.render, lambda error:self.error_var.set(str(error)))

    def render(self, result):
        self.total = result['total']
        for widget in self.content.winfo_children(): widget.destroy()
        self.content.grid_columnconfigure(0, weight=1)
        self.notice.configure(text=f'{self.total} members · Page {self.offset//self.PAGE_SIZE+1}')
        self.previous.configure(state='normal' if self.offset else 'disabled')
        self.next_button.configure(state='normal' if self.offset+len(result['rows']) < self.total else 'disabled')
        if not result['rows']:
            label(self.content, 'No matching active members.', 14, muted=True).grid(pady=30)
        for index, member in enumerate(result['rows']):
            row = AppCard(self.content)
            row.member = member
            row.grid(row=index, column=0, sticky='ew', padx=12, pady=4)
            row.grid_columnconfigure(1, weight=1)
            Avatar(row, member['full_name'], member['photo_path']).grid(row=0, column=0, rowspan=3, padx=12, pady=12)
            label(row, member['full_name'], 14, True, anchor='w', width=1, wraplength=350).grid(row=0, column=1, sticky='ew', pady=(10,0))
            label(row, member['member_no']+' · '+(member['phone'] or 'No phone'), 11, muted=True, anchor='w').grid(row=1, column=1, sticky='ew')
            label(row, 'Current ministry member' if member['in_ministry'] else 'Ministry membership required', 11, muted=True, anchor='w').grid(row=2, column=1, sticky='ew', pady=(0,10))
            row.select_button = ActionButton(row, 'Select', lambda person=member:self.select(person), width=70)
            row.select_button.grid(row=0, column=2, rowspan=3, padx=12)

    def select(self, member):
        self.on_selected(member)
        self.destroy()


class AssignmentFormDialog(LeadershipDialog):
    def __init__(self, master, service, ministry, on_saved, capabilities, assignment=None, position_id=None):
        super().__init__(master, 'Edit assignment' if assignment else 'Assign ministry position', ministry['name'], width=760, height=760)
        self.service, self.ministry, self.on_saved, self.capabilities, self.assignment = service, ministry, on_saved, capabilities, assignment
        self.member = dict(id=assignment['member_id'], full_name=assignment['full_name'], member_no=assignment['member_no'], phone=assignment['phone'], photo_path=assignment['photo_path']) if assignment else None
        self.positions, self.request = {}, None
        heading(self.content, 'Member *')
        self.person = AppCard(self.content)
        self.person.pack(fill='x', padx=16)
        self.render_member()
        heading(self.content, 'Position *')
        self.position = ModernSelect(self.content, [], placeholder='Loading ministry positions…')
        self.position.pack(fill='x', padx=16)
        heading(self.content, 'Start date *')
        self.start = DatePicker(self.content, initial_date=assignment['start_date'] if assignment else date.today(), height=46)
        self.start.pack(fill='x', padx=16)
        heading(self.content, 'End date'+(' *' if assignment and not assignment['is_current'] else ' (optional)'))
        self.end = DatePicker(self.content, initial_date=assignment['end_date'] if assignment else None, height=46)
        self.end.pack(fill='x', padx=16)
        if assignment and assignment['is_current']:
            self.end.set_enabled(False)
            label(self.content, 'Use End assignment to close a current appointment.', 11, muted=True).pack(anchor='w', padx=16, pady=6)
        heading(self.content, 'Notes')
        self.notes = textbox(self.content, assignment['notes'] if assignment else '')
        self.membership_button = ActionButton(self.content, 'Add to ministry and continue', self.enroll)
        self.save_button = ActionButton(self.footer, 'Save assignment' if assignment else 'Assign position', self.save, 'primary', width=170)
        self.save_button.pack(side='right', padx=18, pady=14)
        self.save_button.configure(state='disabled')
        self.loader.submit('positions', lambda:service.list_positions(ministry['id'], active_only=not bool(assignment)),
            lambda rows:self.loaded_positions(rows, position_id), lambda error:self.error_var.set(str(error)))

    def render_member(self):
        for widget in self.person.winfo_children(): widget.destroy()
        if self.member:
            Avatar(self.person, self.member['full_name'], self.member.get('photo_path','')).pack(side='left', padx=12, pady=12)
            label(self.person, self.member['full_name']+'\n'+self.member['member_no'], 13, True, justify='left', wraplength=330).pack(side='left', padx=4, pady=12)
        else:
            label(self.person, 'Choose an active church member.', 12, muted=True).pack(side='left', padx=12, pady=16)
        if not self.assignment:
            self.choose_button = ActionButton(self.person, 'Choose member', self.choose, width=120)
            self.choose_button.pack(side='right', padx=12, pady=12)

    def choose(self):
        return LeadershipMemberPicker(self, self.service, self.ministry, self.selected)

    def selected(self, member):
        self.member = member
        self.membership_button.pack_forget()
        self.render_member()
        self.error_var.set('')

    def loaded_positions(self, rows, position_id):
        self.positions = {row['name']+' · '+row['code']:row for row in rows}
        self.position.configure(values=list(self.positions))
        selected_id = self.assignment['position_id'] if self.assignment else position_id
        chosen = next((key for key, row in self.positions.items() if row['id'] == selected_id), next(iter(self.positions), ''))
        self.position.set(chosen)
        if self.assignment:
            self.position.configure(state='disabled')
        if rows:
            self.save_button.configure(state='normal')
        else:
            self.error_var.set('Define an active ministry position before appointing a member.')

    def save(self):
        if self.save_button.cget('state') == 'disabled': return
        try:
            if not self.member or self.position.get() not in self.positions:
                raise ValueError('Choose a member and ministry position.')
            data = dict(start_date=self.start.get_date(), end_date=self.end.get_date() if self.end.variable.get().strip() else None,
                        notes=self.notes.get('1.0','end-1c'))
            self.service._dates(data['start_date'], data['end_date'])
        except Exception as error:
            self.error_var.set(str(error))
            return
        if self.assignment:
            self.run(lambda:self.service.update_assignment(self.assignment['id'], data, self.assignment['updated_at']))
        else:
            self.request = dict(ministry_id=self.ministry['id'], member_id=self.member['id'], position_id=self.positions[self.position.get()]['id'], **data)
            self.membership_button.pack_forget()
            self.run(lambda:self.service.assign_member(**self.request))

    def failed(self, error):
        super().failed(error)
        if isinstance(error, MembershipRequiredError) and self.capabilities.get('add_membership'):
            self.membership_button.configure(text='Add to '+self.ministry['name']+' and continue')
            self.membership_button.pack(fill='x', padx=16, pady=(0,16))
        elif isinstance(error, PositionConflictError) and error.position['max_current_holders'] == 1 and len(error.holders) == 1 and self.capabilities.get('end') and self.request.get('end_date') is None:
            holder = error.holders[0]
            data = dict(self.request, replace_assignment_id=holder['id'], expected_replaced_updated_at=holder['updated_at'])
            detail = f"{holder['full_name']} currently holds {error.position['name']}. End that appointment and appoint {self.member['full_name']} effective {display_date(data['start_date'])}? Both changes will be saved together."
            return self.confirm('Replace position holder', detail, 'End and appoint', lambda:self.run(lambda:self.service.assign_member(**data)))

    def confirm(self, title, detail, button, operation):
        def confirmed(_reason, dialog):
            dialog.destroy()
            self.grab_set()
            operation()
        dialog = ConfirmationDialog(self, title, detail, confirmed)
        dialog.confirm_button.configure(text=button, width=180)
        return dialog

    def enroll(self):
        if not self.request: return
        data = dict(self.request, add_membership=True)
        detail = f"Add {self.member['full_name']} to {self.ministry['name']} and save this appointment? Membership and appointment will be committed together. Software access stays separately assigned."
        return self.confirm('Add ministry membership', detail, 'Add and continue', lambda:self.enrolled_write(data))

    def enrolled_write(self, data):
        self.request = data
        self.membership_button.pack_forget()
        self.run(lambda:self.service.assign_member(**data))


class EndAssignmentDialog(LeadershipDialog):
    def __init__(self, master, service, assignment, on_saved):
        super().__init__(master, 'End position assignment', assignment['ministry_name'], width=640, height=580)
        self.on_saved, self.service, self.assignment = on_saved, service, assignment
        label(self.content, assignment['full_name']+'\n'+assignment['position_name'], 19, True, wraplength=520, justify='left').pack(anchor='w', padx=16, pady=16)
        label(self.content, 'The appointment will remain in leadership history.', 12, muted=True).pack(anchor='w', padx=16)
        heading(self.content, 'End date *')
        self.end = DatePicker(self.content, initial_date=date.today(), height=46)
        self.end.pack(fill='x', padx=16)
        heading(self.content, 'Reason / Notes')
        self.notes = textbox(self.content)
        self.save_button = ActionButton(self.footer, 'End assignment', self.save, 'primary', width=165)
        self.save_button.pack(side='right', padx=18, pady=14)

    def save(self):
        try:
            end, notes = self.end.get_date(), self.notes.get('1.0','end-1c')
        except ValueError as error:
            self.error_var.set(str(error))
            return
        self.run(lambda:self.service.end_assignment(self.assignment['id'], end, notes, self.assignment['updated_at']))


class AssignmentProfileDialog(LeadershipDialog):
    def __init__(self, master, service, assignment_id):
        super().__init__(master, 'Position assignment', 'Appointment details and recorded changes.', width=740, height=700)
        self.cancel_button.configure(text='Close')
        self.assignment = None
        def load():
            row = service.get_assignment(assignment_id)
            return row, service.leadership_audit(row['ministry_id'], row['id'])
        self.loader.submit('profile', load, self.render, lambda error:self.error_var.set(str(error)))

    def render(self, result):
        row, audit = result
        self.assignment = row
        Avatar(self.content, row['full_name'], row['photo_path'], size=56).pack(anchor='w', padx=16, pady=16)
        label(self.content, row['full_name'], 20, True, wraplength=580, anchor='w').pack(fill='x', padx=16)
        label(self.content, row['member_no'], 12, muted=True).pack(anchor='w', padx=16)
        for title, value in (('Ministry',row['ministry_name']),('Position',row['position_name']),
            ('Status','Current' if row['is_current'] else 'Historical'), ('Start',display_date(row['start_date'])),
            ('End',display_date(row['end_date']) or 'Present'), ('Notes',row['notes'] or 'No notes.')):
            heading(self.content, title)
            label(self.content, value, 13, wraplength=580, justify='left', anchor='w').pack(fill='x', padx=16)
        heading(self.content, 'Appointment history')
        for item in audit:
            card = AppCard(self.content)
            card.pack(fill='x', padx=16, pady=4)
            label(card, item['action'].replace('_',' ').title(), 13, True).pack(anchor='w', padx=12, pady=(10,2))
            when = item['occurred_at'].astimezone().strftime('%d/%m/%Y %H:%M')
            label(card, item['actor']+' · '+when, 11, muted=True).pack(anchor='w', padx=12, pady=(0,10))
