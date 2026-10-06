"""Paged household directory, family profiles, history and authorized actions."""
import json
import customtkinter as ctk
from src.ui import theme
from src.ui.components.app_shell import PageHeader
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.action_menu import ActionMenu
from src.ui.components.date_picker import display_date
from src.ui.components.modern import ActionButton, AppCard, Avatar, EmptyState, StatCard, StatusBadge, label
from src.ui.components.modern_select import ModernSelect
from src.ui.components.search_field import SearchField
from src.ui.households.dialogs import (HouseholdDialog, HouseholdFormDialog, AddFamilyMemberDialog,
    HouseholdMemberPicker, RemoveFamilyMemberDialog, ChangeHouseholdHeadDialog, RelationshipDialog, HouseholdLifecycleDialog)


class HouseholdsView(ctk.CTkFrame):
    PAGE_SIZE = 25
    def __init__(self, master, service, member_service, on_members=None, action_master=None):
        super().__init__(master, fg_color=theme.BACKGROUND, corner_radius=0)
        self.service, self.member_service, self.on_members = service, member_service, on_members
        self.loader = AsyncLoader(self)
        self.offset, self.total, self.capabilities = 0, 0, {}
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(3, weight=1)
        if action_master is None:
            header = PageHeader(self, 'Households', 'Manage HOPFAN families and household relationships')
            header.grid(row=0, column=0, sticky='ew', padx=20, pady=12)
            action_master = header.actions
        self.create_button = ActionButton(action_master, 'Create household', self.create, 'primary', width=155)
        self.back_button = None
        if on_members:
            self.back_button = ActionButton(action_master, 'Members', on_members, width=90)
            self.back_button.pack(side='left', padx=(0,8))
        summary = ctk.CTkFrame(self, fg_color='transparent')
        summary.grid(row=1, column=0, sticky='ew', padx=20, pady=(0,12))
        self.cards = {}
        for index,(key,title) in enumerate((('total','Total households'),('active','Active households'),('members','Members in households'),('without','Members without household'))):
            summary.grid_columnconfigure(index, weight=1, uniform='summary')
            card = StatCard(summary, title); card.set('—')
            card.grid(row=0, column=index, sticky='ew', padx=4)
            self.cards[key] = card
        for widget in (self.cards['without'], self.cards['without'].value):
            widget.bind('<Button-1>', lambda _event:self.without_household(), add='+')
        filters = AppCard(self)
        filters.grid(row=2, column=0, sticky='ew', padx=20, pady=(0,10))
        filters.grid_columnconfigure(0, weight=1)
        self.search = SearchField(filters, lambda:self.refresh(True), 'Household name, member, code or phone')
        self.search.grid(row=0, column=0, sticky='ew', padx=10, pady=10)
        self.status = ModernSelect(filters, ['Active','Inactive','Archived','All'], width=130, command=lambda _value:self.refresh(True))
        self.status.grid(row=0, column=1, padx=6)
        ActionButton(filters, 'Refresh', self.refresh, width=85).grid(row=0, column=2, padx=10)
        self.rows = ctk.CTkScrollableFrame(self, fg_color='transparent')
        self.rows.grid(row=3, column=0, sticky='nsew', padx=16); self.rows.grid_columnconfigure(0, weight=1)
        footer = ctk.CTkFrame(self, fg_color='transparent')
        footer.grid(row=4, column=0, sticky='ew', padx=20, pady=10)
        self.notice = label(footer, 'Loading households…', 12, muted=True); self.notice.pack(side='left')
        self.next_button = ActionButton(footer, 'Next', lambda:self.page(1), width=70); self.next_button.pack(side='right')
        self.previous = ActionButton(footer, 'Previous', lambda:self.page(-1), width=85); self.previous.pack(side='right', padx=8)
        self.refresh()

    def page(self, direction):
        self.offset = max(0, self.offset+direction*self.PAGE_SIZE); self.refresh()

    def refresh(self, reset=False):
        if reset: self.offset = 0
        params = dict(search=self.search.get(), status=self.status.get(), limit=self.PAGE_SIZE, offset=self.offset)
        self.loader.submit('households', lambda:(self.service.capabilities(), self.service.get_household_stats(), self.service.list_households(**params)), self.render, self.failed)

    def failed(self, error):
        self.notice.configure(text=str(error), text_color=theme.DANGER)
        self.create_button.pack_forget()

    def render(self, result):
        self.capabilities, stats, page = result
        self.total = page['total']
        if self.offset and not page['rows'] and self.total:
            self.offset = ((self.total-1)//self.PAGE_SIZE)*self.PAGE_SIZE; self.refresh(); return
        self.create_button.pack_forget()
        if self.capabilities.get('create'): self.create_button.pack(side='left')
        for key, card in self.cards.items(): card.set(stats[key] if stats[key] is not None else '—')
        for child in self.rows.winfo_children(): child.destroy()
        self.notice.configure(text=f'{self.total} households · Page {self.offset//self.PAGE_SIZE+1}', text_color=theme.TEXT_MUTED)
        self.previous.configure(state='normal' if self.offset else 'disabled')
        self.next_button.configure(state='normal' if self.offset+len(page['rows'])<self.total else 'disabled')
        if not page['rows']:
            EmptyState(self.rows, 'No households yet' if not stats['total'] else 'No matching households',
                'Group related HOPFAN members into family households.' if not stats['total'] else 'Adjust the search or status filter.').grid(row=0, column=0, sticky='ew')
            return
        for index, household in enumerate(page['rows']):
            row = AppCard(self.rows); row.household = household
            row.grid(row=index, column=0, sticky='ew', padx=4, pady=4)
            row.grid_columnconfigure(0, weight=2); row.grid_columnconfigure(1, weight=1)
            label(row, household['household_name'], 15, True, anchor='w', width=1, wraplength=250).grid(row=0, column=0, sticky='ew', padx=12, pady=(12,2))
            label(row, household['household_code'], 11, muted=True, anchor='w').grid(row=1, column=0, sticky='ew', padx=12, pady=(0,12))
            label(row, household['head_name'] or 'No household head', 12, anchor='w', width=1, wraplength=160).grid(row=0, column=1, sticky='ew', padx=8)
            label(row, f"{household['member_count']} current members", 11, muted=True, anchor='w').grid(row=1, column=1, sticky='ew', padx=8)
            label(row, household['primary_phone'] or 'No phone', 12, width=100).grid(row=0, column=2, padx=6)
            label(row, 'Updated '+display_date(household['updated_at']), 10, muted=True).grid(row=1, column=2, padx=6)
            StatusBadge(row, household['status']).grid(row=0, column=3, rowspan=2, padx=8)
            actions = ctk.CTkFrame(row, fg_color='transparent'); actions.grid(row=0, column=4, rowspan=2, padx=12)
            row.view_button = ActionButton(actions, 'View', lambda item=household:self.view(item['id']), width=60)
            row.view_button.pack(side='left', padx=2)
            if self.capabilities.get('edit') and household['status']!='ARCHIVED':
                row.edit_button = ActionButton(actions, 'Edit', lambda item=household:self.edit(item), width=55)
                row.edit_button.pack(side='left', padx=2)

    def create(self):
        return HouseholdFormDialog(self, self.service, self.member_service, lambda:self.refresh(True), self.capabilities)

    def edit(self, household):
        return HouseholdFormDialog(self, self.service, self.member_service, self.refresh, self.capabilities, household)

    def view(self, household_id):
        return HouseholdProfileDialog(self, self.service, self.member_service, household_id, self.refresh)

    def without_household(self):
        if not self.capabilities.get('member_search'): return
        def selected(member):
            from src.ui.members.members_view import MemberProfileDialog
            MemberProfileDialog(self, self.member_service, member['id'], self.refresh)
        return HouseholdMemberPicker(self, self.service, selected, unassigned_only=True)

    def destroy(self):
        for widget in (self.create_button, self.back_button):
            if widget and widget.winfo_exists(): widget.destroy()
        super().destroy()


class HouseholdProfileDialog(HouseholdDialog):
    PAGE_SIZE = 20
    def __init__(self, master, service, member_service, household_id, on_saved):
        super().__init__(master, 'Household profile', 'Current family members and retained relationship history.', width=860, height=760)
        self.service, self.member_service, self.household_id, self.on_saved = service, member_service, household_id, on_saved
        self.household, self.capabilities, self.offset = None, {}, 0
        self.cancel_button.configure(text='Close')
        self.header.winfo_children()[1].pack_configure(pady=(2,6))
        toolbar = ctk.CTkFrame(self.header, fg_color='transparent'); toolbar.pack(fill='x', padx=16, pady=4)
        self.mode = ModernSelect(toolbar, ['Current members'], width=160, height=36, command=lambda _value:self.refresh(True))
        self.mode.pack(side='left')
        self.next_button = ActionButton(toolbar, 'Next', lambda:self.page(1), width=65); self.next_button.pack(side='right')
        self.previous = ActionButton(toolbar, 'Previous', lambda:self.page(-1), width=80); self.previous.pack(side='right', padx=6)
        self.notice = label(toolbar, 'Loading…', 11, muted=True); self.notice.pack(side='right', padx=12)
        self.edit_button = ActionButton(self.footer, 'Edit household', self.edit, width=130)
        self.add_button = ActionButton(self.footer, 'Add family member', self.add_member, 'primary', width=165)
        self.action_menu = None
        self.refresh()

    def page(self, direction):
        self.offset = max(0, self.offset+direction*self.PAGE_SIZE); self.refresh()

    def refresh(self, reset=False):
        if reset: self.offset = 0
        mode, offset = self.mode.get(), self.offset
        def fetch():
            capabilities, household = self.service.capabilities(), self.service.get_household(self.household_id)
            page = self.service.audit_events(self.household_id, limit=self.PAGE_SIZE, offset=offset) if mode=='Audit history' else self.service.get_household_members(
                self.household_id, history=mode=='Past memberships', limit=self.PAGE_SIZE, offset=offset)
            return capabilities, household, page, mode
        self.loader.submit('profile', fetch, self.render, lambda error:self.error_var.set(str(error)))

    def render(self, result):
        self.capabilities, self.household, page, mode = result
        household = self.household
        self.header.winfo_children()[0].configure(text=household['household_name'])
        self.header.winfo_children()[1].configure(text=household['household_code']+' · '+household['status'].title())
        self.error_var.set('')
        self.mode.configure(values=['Current members','Past memberships','Audit history'] if self.capabilities.get('view_all') else ['Current members'])
        unknown = household['stats'].get('unknown_age', 0)
        self.notice.configure(text=f"{page['total']} records"+(f' · {unknown} age unknown' if unknown else ''))
        self.previous.configure(state='normal' if self.offset else 'disabled')
        self.next_button.configure(state='normal' if self.offset+len(page['rows'])<page['total'] else 'disabled')
        self.edit_button.pack_forget(); self.add_button.pack_forget()
        if self.action_menu: self.action_menu.destroy(); self.action_menu = None
        actions = []
        if self.capabilities.get('archive'):
            action = 'restore' if household['status']=='ARCHIVED' else 'archive'
            actions.append(('Restore household' if action=='restore' else 'Archive household', lambda choice=action:self.lifecycle(choice)))
        if self.capabilities.get('delete') and not household['has_history']:
            actions.append(('Delete unused household', lambda:self.lifecycle('delete')))
        if actions:
            self.action_menu = ActionMenu(self.footer, actions); self.action_menu.pack(side='right', padx=12)
        if self.capabilities.get('add_member') and household['status']=='ACTIVE': self.add_button.pack(side='right', padx=6, pady=14)
        if self.capabilities.get('edit') and household['status']!='ARCHIVED': self.edit_button.pack(side='right', padx=6, pady=14)
        for child in self.content.winfo_children(): child.destroy()
        overview = AppCard(self.content); overview.pack(fill='x', padx=12, pady=6)
        overview.grid_columnconfigure(0, weight=1)
        detail = 'Head: '+(household['head_name'] or 'Not assigned')+' · Phone: '+(household['primary_phone'] or 'Not specified')
        label(overview, detail, 12, anchor='w', justify='left', width=1, wraplength=640).grid(row=0, column=0, sticky='ew', padx=12, pady=(8,2))
        label(overview, 'Address: '+(household['primary_address'] or 'Not specified'), 12, anchor='w', justify='left', width=1,
            wraplength=640).grid(row=1, column=0, sticky='ew', padx=12, pady=(2,8))
        if household['notes']: label(overview, household['notes'], 11, muted=True, anchor='w', justify='left', wraplength=640).grid(row=2, column=0, sticky='ew', padx=12, pady=8)
        summary = ctk.CTkFrame(self.content, fg_color='transparent'); summary.pack(fill='x', padx=12, pady=6)
        self.cards = {}
        for index,(key,title) in enumerate((('total','Total members'),('adults','Adults'),('children','Children'),('dependants','Dependants'))):
            summary.grid_columnconfigure(index, weight=1, uniform='family')
            card = StatCard(summary, title, compact=True); card.set(household['stats'][key]); card.grid(row=0, column=index, sticky='ew', padx=3)
            self.cards[key] = card
        self.member_rows = ctk.CTkFrame(self.content, fg_color='transparent'); self.member_rows.pack(fill='x', padx=10)
        if not page['rows']:
            EmptyState(self.member_rows, 'No family members have been added.' if mode=='Current members' else 'No records in this view',
                'Use Add family member to select an existing HOPFAN member.' if self.capabilities.get('add_member') and mode=='Current members' else '').pack(fill='x')
        for row in page['rows']:
            if mode=='Audit history': self.audit_row(row)
            else: self.family_row(row)

    def family_row(self, member):
        row = AppCard(self.member_rows); row.member = member; row.pack(fill='x', pady=4)
        row.grid_columnconfigure(1, weight=1)
        Avatar(row, member['full_name'], member['photo_path']).grid(row=0, column=0, rowspan=4, padx=12, pady=12)
        label(row, member['full_name']+' · '+member['member_no'], 13, True, anchor='w', width=1, wraplength=390).grid(row=0, column=1, sticky='ew', pady=(10,2))
        label(row, member['relationship_label'], 12, anchor='w').grid(row=1, column=1, sticky='ew')
        age = f"Age {member['age']}" if member['age'] is not None else 'Age unknown'
        detail = age+' · '+(display_date(member['date_of_birth']) or 'DOB not recorded')+' · '+(member['phone'] or 'No phone')
        label(row, detail, 11, muted=True, anchor='w', width=1, wraplength=390).grid(row=2, column=1, sticky='ew')
        period = (display_date(member['joined_at']) or 'Joined date unknown')+' – '+(display_date(member['left_at']) if member['left_at'] else 'Present')
        label(row, period, 11, muted=True, anchor='w').grid(row=3, column=1, sticky='ew', pady=(2,10))
        if member.get('sunday_school'):
            label(row,'Sunday School: '+(member['sunday_school'].get('class_name') or 'Not placed'),11,muted=True,anchor='w').grid(row=4,column=1,sticky='ew',pady=(0,8))
        StatusBadge(row, member['member_status']).grid(row=0, column=2, rowspan=2, padx=10)
        actions = []
        if member['is_active'] and self.household['status']!='ARCHIVED':
            if self.capabilities.get('edit'):
                actions.append(('Edit relationship', lambda person=member:self.edit_relationship(person)))
                if not member['is_household_head'] and self.household['status']=='ACTIVE':
                    actions.append(('Make household head', lambda person=member:self.change_head(person)))
            if self.capabilities.get('remove_member'): actions.append(('Remove from household', lambda person=member:self.remove_member(person)))
        if actions:
            row.action_menu = ActionMenu(row, actions); row.action_menu.grid(row=2, column=2, rowspan=2, padx=10)

    def audit_row(self, event):
        row = AppCard(self.member_rows); row.pack(fill='x', pady=4)
        label(row, event['action'].replace('_',' ').title(), 13, True, anchor='w').pack(fill='x', padx=12, pady=(10,2))
        label(row, event['actor']+' · '+display_date(event['occurred_at']), 11, muted=True).pack(anchor='w', padx=12)
        label(row, json.dumps({'before':event['old_values'], 'after':event['new_values']}, ensure_ascii=False), 11,
            wraplength=670, justify='left', anchor='w').pack(fill='x', padx=12, pady=8)

    def changed(self):
        self.on_saved(); self.refresh(True)

    def edit(self): return HouseholdFormDialog(self, self.service, self.member_service, self.changed, self.capabilities, self.household)
    def add_member(self): return AddFamilyMemberDialog(self, self.service, self.member_service, self.household, self.capabilities, self.changed)
    def edit_relationship(self, member): return RelationshipDialog(self, self.service, member, self.changed)
    def remove_member(self, member): return RemoveFamilyMemberDialog(self, self.service, member, self.changed)
    def change_head(self, member): return ChangeHouseholdHeadDialog(self, self.service, self.household, member, self.changed)
    def lifecycle(self, action):
        def saved():
            self.on_saved()
            if action=='delete': self.destroy()
            else: self.refresh(True)
        return HouseholdLifecycleDialog(self, self.service, self.household, action, saved)
