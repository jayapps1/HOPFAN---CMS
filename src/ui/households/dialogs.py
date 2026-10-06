"""Household forms reuse normal member creation and explicit confirmations."""
from datetime import date
import customtkinter as ctk
from src.services.household_service import HouseholdMoveRequired, HouseholdHeadConflict
from src.security.household_permissions import RELATIONSHIPS
from src.ui import theme
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.date_picker import DatePicker
from src.ui.components.modern import ActionButton, AppCard, Avatar, ConfirmationDialog, FixedFooterDialog, ModernEntry, font, label
from src.ui.components.modern_select import ModernSelect
from src.ui.components.search_field import SearchField
from src.ui.members.member_form_dialog import MemberFormDialog


def heading(parent, text):
    label(parent, text, 12, True, anchor='w').pack(fill='x', padx=16, pady=(14, 5))


def entry(parent, title, initial=''):
    heading(parent, title)
    widget = ModernEntry(parent, height=42)
    widget.pack(fill='x', padx=16)
    widget.insert(0, initial or '')
    return widget


def notes(parent, initial=''):
    heading(parent, 'Notes (optional)')
    widget = ctk.CTkTextbox(parent, height=90, corner_radius=10, fg_color=theme.INPUT,
        text_color=theme.TEXT, border_color=theme.BORDER, border_width=1, font=font())
    widget.pack(fill='x', padx=16, pady=(0, 12))
    widget.insert('1.0', initial or '')
    return widget


class HouseholdDialog(FixedFooterDialog):
    def __init__(self, master, title, subtitle='', **kwargs):
        super().__init__(master, title, subtitle, **kwargs)
        self.loader = AsyncLoader(self)

    def run(self, operation):
        if self.save_button.cget('state') == 'disabled': return
        self.error_var.set('')
        self.save_button.configure(state='disabled')
        self.loader.submit('save', operation, self.saved, self.failed)

    def saved(self, _result):
        self.on_saved()
        self.destroy()

    def failed(self, error):
        self.error_var.set(str(error))
        self.save_button.configure(state='normal')

    def confirm(self, title, detail, operation):
        def confirmed(_reason, dialog):
            dialog.destroy()
            self.grab_set()
            operation()
        dialog = ConfirmationDialog(self, title, detail, confirmed)
        dialog.confirm_button.configure(text='Confirm', width=130)
        return dialog

    def destroy(self):
        if not self.winfo_exists(): return
        parent = self.master.winfo_toplevel()
        super().destroy()
        if parent.winfo_exists() and isinstance(parent, ctk.CTkToplevel): parent.grab_set()


class HouseholdMemberPicker(HouseholdDialog):
    PAGE_SIZE = 20
    def __init__(self, master, service, on_selected, *, unassigned_only=False):
        super().__init__(master, 'Members without household' if unassigned_only else 'Choose existing member',
            'Search by member name, membership number, phone or email.', width=760, height=700)
        self.service, self.on_selected, self.unassigned_only = service, on_selected, unassigned_only
        self.offset, self.total = 0, 0
        self.cancel_button.configure(text='Close')
        self.search = SearchField(self.header, lambda:self.refresh(True), 'Name, member number, phone or email')
        self.search.pack(fill='x', padx=16, pady=10)
        self.notice = label(self.footer, 'Loading members…', 11, muted=True)
        self.notice.pack(side='left')
        self.previous = ActionButton(self.footer, 'Previous', lambda:self.page(-1), width=80)
        self.previous.pack(side='right', padx=6)
        self.next_button = ActionButton(self.footer, 'Next', lambda:self.page(1), width=70)
        self.next_button.pack(side='right', padx=14)
        self.refresh()

    def page(self, direction):
        self.offset = max(0, self.offset+direction*self.PAGE_SIZE)
        self.refresh()

    def refresh(self, reset=False):
        if reset: self.offset = 0
        params = dict(search=self.search.get(), unassigned_only=self.unassigned_only, limit=self.PAGE_SIZE, offset=self.offset)
        self.loader.submit('members', lambda:self.service.candidate_members(**params), self.render, lambda error:self.error_var.set(str(error)))

    def render(self, page):
        self.total = page['total']
        for child in self.content.winfo_children(): child.destroy()
        self.notice.configure(text=f'{self.total} members · Page {self.offset//self.PAGE_SIZE+1}')
        self.previous.configure(state='normal' if self.offset else 'disabled')
        self.next_button.configure(state='normal' if self.offset+len(page['rows'])<self.total else 'disabled')
        if not page['rows']: label(self.content, 'No matching members.', 15, muted=True).pack(pady=25)
        for member in page['rows']:
            row = AppCard(self.content); row.member = member
            row.pack(fill='x', padx=12, pady=4)
            row.grid_columnconfigure(1, weight=1)
            Avatar(row, member['full_name'], member.get('photo_path', '')).grid(row=0, column=0, rowspan=3, padx=12, pady=12)
            label(row, member['full_name'], 14, True, anchor='w', width=1, wraplength=340).grid(row=0, column=1, sticky='ew', pady=(10,0))
            label(row, member['member_no']+' · '+(member['phone'] or 'No phone'), 11, anchor='w', muted=True).grid(row=1, column=1, sticky='ew')
            label(row, member.get('household_name') or 'No household', 11, muted=True, anchor='w').grid(row=2, column=1, sticky='ew', pady=(0,10))
            row.select_button = ActionButton(row, 'Select', lambda person=member:self.selected(person), width=75)
            row.select_button.grid(row=0, column=2, rowspan=3, padx=12)

    def selected(self, member):
        callback = self.on_selected
        self.destroy()
        callback(member)


class MemberChoice:
    def build_member_choice(self, title='Member *'):
        heading(self.content, title)
        self.person = AppCard(self.content)
        self.person.pack(fill='x', padx=16)
        self.render_member()
        if self.capabilities.get('create_member'):
            self.new_member_button = ActionButton(self.content, 'Add new member', self.new_member, width=145)
            self.new_member_button.pack(anchor='w', padx=16, pady=8)

    def render_member(self):
        for child in self.person.winfo_children(): child.destroy()
        if self.member:
            Avatar(self.person, self.member['full_name'], self.member.get('photo_path', '')).pack(side='left', padx=12, pady=12)
            label(self.person, self.member['full_name']+'\n'+self.member['member_no'], 12, True, justify='left', wraplength=330).pack(side='left', pady=10)
        else:
            label(self.person, 'Choose an existing HOPFAN member.', 12, muted=True).pack(side='left', padx=12, pady=16)
        if self.capabilities.get('member_search'):
            self.choose_button = ActionButton(self.person, 'Search member', self.choose_member, width=125)
            self.choose_button.pack(side='right', padx=12, pady=12)

    def choose_member(self):
        return HouseholdMemberPicker(self, self.service, self.selected)

    def selected(self, member):
        self.member = member
        self.render_member()
        self.error_var.set('')

    def new_member(self):
        def created():
            if form.member: self.selected(form.member)
        form = MemberFormDialog(self, self.member_service, created)
        def closed(event):
            if event.widget == form and self.winfo_exists():
                self.grab_set()
                self.focus_set()
        form.bind('<Destroy>', closed, add='+')
        return form


class HouseholdFormDialog(MemberChoice, HouseholdDialog):
    def __init__(self, master, service, member_service, on_saved, capabilities, household=None):
        super().__init__(master, 'Edit household' if household else 'Create household',
            'Family relationships link existing members.', width=740, height=730)
        self.service, self.member_service, self.on_saved, self.capabilities, self.household = service, member_service, on_saved, capabilities, household
        self.member, self.move_from = None, None
        initial = household or {}
        self.name = entry(self.content, 'Household name *', initial.get('household_name'))
        if not household and capabilities.get('add_member'): self.build_member_choice('Household head (optional)')
        self.address = entry(self.content, 'Primary address (optional)', initial.get('primary_address'))
        self.phone = entry(self.content, 'Primary phone (optional)', initial.get('primary_phone'))
        self.notes = notes(self.content, initial.get('notes'))
        heading(self.content, 'Status')
        self.status = ModernSelect(self.content, ['Active', 'Inactive'])
        self.status.set(initial.get('status', 'ACTIVE').title())
        self.status.pack(fill='x', padx=16, pady=(0,16))
        self.save_button = ActionButton(self.footer, 'Save household' if household else 'Create household', self.save, 'primary', width=170)
        self.save_button.pack(side='right', padx=16, pady=14)

    def selected(self, member):
        self.move_from = None
        super().selected(member)

    def save(self):
        data = dict(household_name=self.name.get(), primary_address=self.address.get(), primary_phone=self.phone.get(),
            notes=self.notes.get('1.0','end-1c'), status=self.status.get().upper())
        if self.household:
            self.run(lambda:self.service.update_household(self.household['id'], data, self.household['updated_at']))
        else:
            move = dict(move_from_membership_id=self.move_from['id'], expected_source_updated_at=self.move_from['updated_at']) if self.move_from else {}
            member_id = self.member['id'] if self.member else None
            self.run(lambda:self.service.create_household(data, member_id, **move))

    def failed(self, error):
        super().failed(error)
        if isinstance(error, HouseholdMoveRequired) and self.capabilities.get('remove_member'):
            self.confirm('Create household and move head', str(error)+' The old membership will remain in history.',
                lambda:self.confirm_move(error.current))

    def confirm_move(self, current):
        self.move_from = current
        self.save()


class AddFamilyMemberDialog(MemberChoice, HouseholdDialog):
    def __init__(self, master, service, member_service, household, capabilities, on_saved, member=None):
        super().__init__(master, 'Add family member', household['household_name'], width=740, height=730)
        self.service, self.member_service, self.household, self.capabilities, self.on_saved = service, member_service, household, capabilities, on_saved
        self.member, self.move_from, self.replace_head = member, None, None
        self.build_member_choice()
        heading(self.content, 'Relationship *')
        self.relationship = ModernSelect(self.content, list(RELATIONSHIPS.values()), command=self.relationship_changed)
        self.relationship.set('Spouse')
        self.relationship.pack(fill='x', padx=16)
        heading(self.content, 'Household head')
        self.head = ModernSelect(self.content, ['No','Yes'], command=self.head_changed)
        self.head.pack(fill='x', padx=16)
        heading(self.content, 'Joined date (optional)')
        self.joined = DatePicker(self.content, initial_date=date.today(), height=42)
        self.joined.pack(fill='x', padx=16)
        self.notes = notes(self.content)
        self.save_button = ActionButton(self.footer, 'Add member', self.save, 'primary', width=150)
        self.save_button.pack(side='right', padx=16, pady=14)

    def selected(self, member):
        self.move_from, self.replace_head = None, None
        super().selected(member)

    def relationship_changed(self, value):
        self.head.set('Yes' if value == RELATIONSHIPS['HEAD'] else 'No')
        self.replace_head = None

    def head_changed(self, value):
        if value == 'Yes': self.relationship.set(RELATIONSHIPS['HEAD'])
        elif self.relationship.get() == RELATIONSHIPS['HEAD']: self.relationship.set('Relative')
        self.replace_head = None

    def save(self):
        try:
            if not self.member: raise ValueError('Choose a member.')
            relationship = next(code for code, text in RELATIONSHIPS.items() if text == self.relationship.get())
            data = dict(is_household_head=self.head.get()=='Yes', joined_at=self.joined.get_date() if self.joined.variable.get().strip() else None, notes=self.notes.get('1.0','end-1c'))
            if self.move_from:
                data.update(move_from_membership_id=self.move_from['id'], expected_source_updated_at=self.move_from['updated_at'])
            if self.replace_head:
                data.update(replace_head_id=self.replace_head['id'], expected_head_updated_at=self.replace_head['updated_at'])
        except Exception as error:
            self.error_var.set(str(error)); return
        member_id = self.member['id']
        self.run(lambda:self.service.add_member(self.household['id'], member_id, relationship, **data))

    def failed(self, error):
        super().failed(error)
        if isinstance(error, HouseholdMoveRequired) and self.capabilities.get('remove_member'):
            return self.confirm('Move member to this household', str(error)+' The joined date will close the old membership and start the new one in a single transaction.',
                lambda:self.confirm_move(error.current))
        if isinstance(error, HouseholdHeadConflict) and self.capabilities.get('edit'):
            return self.confirm('Change household head', str(error)+' The previous head will remain a current family member with relationship Relative.',
                lambda:self.confirm_head(error.current))

    def confirm_move(self, current):
        self.move_from = current
        self.save()

    def confirm_head(self, current):
        self.replace_head = current
        self.save()


class RelationshipDialog(HouseholdDialog):
    def __init__(self, master, service, member, on_saved):
        super().__init__(master, 'Edit family relationship', member['full_name'], width=670, height=560)
        self.service, self.member, self.on_saved = service, member, on_saved
        heading(self.content, 'Relationship')
        values = [RELATIONSHIPS['HEAD']] if member['is_household_head'] else [text for code,text in RELATIONSHIPS.items() if code!='HEAD']
        self.relationship = ModernSelect(self.content, values)
        self.relationship.set(member['relationship_label'])
        self.relationship.pack(fill='x', padx=16)
        self.notes = notes(self.content, member['notes'])
        self.save_button = ActionButton(self.footer, 'Save relationship', self.save, 'primary', width=170)
        self.save_button.pack(side='right', padx=16, pady=14)

    def save(self):
        code = next(code for code,text in RELATIONSHIPS.items() if text==self.relationship.get())
        value = self.notes.get('1.0','end-1c')
        self.run(lambda:self.service.update_relationship(self.member['id'], code, value, self.member['updated_at']))


class RemoveFamilyMemberDialog(HouseholdDialog):
    def __init__(self, master, service, member, on_saved):
        super().__init__(master, 'Remove from household', member['full_name'], width=670, height=570)
        self.service, self.member, self.on_saved = service, member, on_saved
        label(self.content, 'This membership will become historical. The member record remains available.', 13,
            wraplength=550, justify='left').pack(fill='x', padx=16, pady=16)
        heading(self.content, 'Effective date *')
        self.effective = DatePicker(self.content, initial_date=date.today(), height=42)
        self.effective.pack(fill='x', padx=16)
        self.reason = notes(self.content)
        self.save_button = ActionButton(self.footer, 'Remove member', self.save, 'danger', width=160)
        self.save_button.pack(side='right', padx=16, pady=14)

    def save(self):
        try: effective = self.effective.get_date()
        except Exception as error: self.error_var.set(str(error)); return
        reason = self.reason.get('1.0','end-1c')
        self.run(lambda:self.service.remove_member(self.member['id'], effective, reason, self.member['updated_at']))


class ChangeHouseholdHeadDialog(HouseholdDialog):
    def __init__(self, master, service, household, member, on_saved):
        super().__init__(master, 'Change household head', household['household_name'], width=680, height=540)
        self.service, self.household, self.member, self.on_saved = service, household, member, on_saved
        detail = f"Make {member['full_name']} the household head?"
        if household['head_name']: detail += f" {household['head_name']} will remain in this household."
        label(self.content, detail, 14, wraplength=550, justify='left').pack(fill='x', padx=16, pady=18)
        heading(self.content, 'Previous head’s new relationship')
        self.previous = ModernSelect(self.content, [text for code,text in RELATIONSHIPS.items() if code!='HEAD'])
        self.previous.set('Relative')
        self.previous.pack(fill='x', padx=16)
        if not household['head_name']: self.previous.configure(state='disabled')
        self.save_button = ActionButton(self.footer, 'Change head', self.save, 'primary', width=150)
        self.save_button.pack(side='right', padx=16, pady=14)

    def save(self):
        code = next(code for code,text in RELATIONSHIPS.items() if text==self.previous.get())
        self.run(lambda:self.service.change_household_head(self.household['id'], self.member['id'],
            current_head_id=self.household['head_membership_id'], expected_updated_at=self.member['updated_at'],
            expected_head_updated_at=self.household['head_updated_at'], previous_relationship=code))


class HouseholdLifecycleDialog(HouseholdDialog):
    def __init__(self, master, service, household, action, on_saved):
        titles = {'archive':'Archive household', 'restore':'Restore household', 'delete':'Delete unused household'}
        super().__init__(master, titles[action], household['household_name'], width=680, height=520)
        self.service, self.household, self.action, self.on_saved = service, household, action, on_saved
        detail = {'archive':'End current memberships on the effective date and archive this household. Family history and member records will be retained.',
            'restore':'Restore this household to Active. Add current memberships explicitly; historical links remain ended.',
            'delete':'Permanently delete this unused household. This is allowed only when no family relationship history exists.'}[action]
        label(self.content, detail, 14, wraplength=550, justify='left').pack(fill='x', padx=16, pady=18)
        if action=='archive':
            heading(self.content, 'Effective date *')
            self.effective = DatePicker(self.content, initial_date=date.today(), height=42)
            self.effective.pack(fill='x', padx=16)
        self.save_button = ActionButton(self.footer, titles[action], self.save, 'danger' if action!='restore' else 'primary', width=200)
        self.save_button.pack(side='right', padx=16, pady=14)

    def save(self):
        expected = self.household['updated_at']
        if self.action=='archive':
            try: effective = self.effective.get_date()
            except Exception as error: self.error_var.set(str(error)); return
            self.run(lambda:self.service.archive_household(self.household['id'], effective, expected))
        elif self.action=='restore': self.run(lambda:self.service.restore_household(self.household['id'], expected))
        else: self.run(lambda:self.service.delete_unused_household(self.household['id'], confirmed=True, expected_updated_at=expected))
