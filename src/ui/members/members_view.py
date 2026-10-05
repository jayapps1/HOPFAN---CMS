"""Paginated member directory and scoped profile, using the shared desktop UI."""
import customtkinter as ctk
from src.services.member_service import MemberService
from src.ui import theme
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.app_shell import PageHeader
from src.ui.components.modern import ActionButton, AppCard, Avatar, EmptyState, FixedFooterDialog, ModernComboBox, ModernEntry, StatCard, StatusBadge, label
from src.ui.components.date_picker import display_date
from src.ui.members.member_form_dialog import MemberFormDialog


class MembersView(ctk.CTkFrame):
    PAGE_SIZE = 40

    def __init__(self, master, user, service=None, permissions=(), action_master=None):
        super().__init__(master, fg_color=theme.BACKGROUND, corner_radius=0)
        self.service = service or MemberService(user.id)
        self.permissions = set(permissions)
        self.loader = AsyncLoader(self)
        self.offset, self.search_timer = 0, None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self.add_button = None
        if action_master is None:
            header = PageHeader(self, 'Members', 'Find and view members in your assigned directory.')
            header.grid(row=0, column=0, sticky='ew', padx=22, pady=16)
            action_master = header.actions
        if 'MEMBERS_CREATE' in self.permissions:
            self.add_button = ActionButton(action_master, 'Add member', self.add_member, 'primary')
            self.add_button.pack(side='left')
        bar = ctk.CTkFrame(self, fg_color='transparent')
        bar.grid(row=1, column=0, sticky='ew', padx=22, pady=(0, 12))
        self.cards = {}
        for index, (key, title) in enumerate([('total','Members'), ('active','Active'), ('inactive','Inactive'), ('baptized','Baptized')]):
            bar.grid_columnconfigure(index, weight=1, uniform='stats')
            card = StatCard(bar, title)
            card.set('—')
            card.grid(row=0, column=index, sticky='ew', padx=(0 if not index else 4, 4))
            self.cards[key] = card
        filters = AppCard(self)
        filters.grid(row=2, column=0, sticky='ew', padx=22, pady=(0, 10))
        filters.grid_columnconfigure(0, weight=1)
        self.search = ModernEntry(filters, placeholder_text='Name, membership number, phone or email')
        self.search.grid(row=0, column=0, sticky='ew', padx=12, pady=10)
        self.search.bind('<KeyRelease>', self.debounce)
        self.status = ModernComboBox(filters, ['All', 'Active', 'Inactive', 'Transferred', 'Deceased'], width=130,
                                     command=lambda _v: self.refresh(reset=True))
        self.status.grid(row=0, column=1, padx=8)
        ActionButton(filters, 'Refresh', self.refresh, width=80).grid(row=0, column=2, padx=12)
        self.rows = ctk.CTkScrollableFrame(self, fg_color='transparent', corner_radius=0)
        self.rows.grid(row=3, column=0, sticky='nsew', padx=20)
        self.rows.grid_columnconfigure(0, weight=1)
        footer = ctk.CTkFrame(self, fg_color='transparent')
        footer.grid(row=4, column=0, sticky='ew', padx=22, pady=12)
        self.notice = label(footer, '', 12, muted=True)
        self.notice.pack(side='left')
        self.next_button = ActionButton(footer, 'Next', lambda: self.page(1), width=80)
        self.next_button.pack(side='right')
        self.previous = ActionButton(footer, 'Previous', lambda: self.page(-1), width=90)
        self.previous.pack(side='right', padx=8)
        self.refresh()

    def debounce(self, _event=None):
        if self.search_timer:
            self.after_cancel(self.search_timer)
        self.search_timer = self.after(300, lambda: self.refresh(reset=True))

    def page(self, direction):
        self.offset = max(0, self.offset+direction*self.PAGE_SIZE)
        self.refresh()

    def refresh(self, reset=False):
        self.search_timer = None
        if reset:
            self.offset = 0
        params = dict(search=self.search.get(), status=self.status.get().upper(), limit=self.PAGE_SIZE+1, offset=self.offset)
        self.loader.submit('directory', lambda: (self.service.stats(), self.service.list_members(**params)), self.render, self.failed)

    def render(self, result):
        stats, rows = result
        for key, card in self.cards.items():
            card.set(stats[key])
        for child in self.rows.winfo_children():
            child.destroy()
        self.next_button.configure(state='normal' if len(rows) > self.PAGE_SIZE else 'disabled')
        self.previous.configure(state='normal' if self.offset else 'disabled')
        self.notice.configure(text=f'Page {self.offset//self.PAGE_SIZE+1} · {min(len(rows), self.PAGE_SIZE)} members shown', text_color=theme.TEXT_MUTED)
        if not rows:
            EmptyState(self.rows, 'No members in this view', 'Adjust the search or membership status.').grid(sticky='ew')
        for index, member in enumerate(rows[:self.PAGE_SIZE]):
            card = AppCard(self.rows)
            card.grid(row=index, column=0, sticky='ew', padx=2, pady=4)
            card.grid_columnconfigure(1, weight=1)
            Avatar(card, member['full_name'], member['photo_path']).grid(row=0, column=0, rowspan=3, padx=12, pady=12)
            label(card, member['full_name'], 15, True, anchor='w').grid(row=0, column=1, sticky='ew', pady=(10,0))
            label(card, member['member_no']+' · '+(member['phone'] or 'No phone'), 12, muted=True, anchor='w').grid(row=1,column=1,sticky='ew')
            label(card, ', '.join(member['ministries']) or 'No ministry', 11, muted=True, anchor='w', wraplength=420).grid(row=2,column=1,sticky='ew',pady=(0,10))
            StatusBadge(card, member['status']).grid(row=0,column=2,rowspan=3,padx=12)
            ActionButton(card, 'View profile', lambda mid=member['id']: self.view_member(mid), width=100).grid(row=0,column=3,rowspan=3,padx=(0,12))

    def failed(self, error):
        self.notice.configure(text=str(error), text_color=theme.DANGER)

    def add_member(self):
        MemberFormDialog(self, self.service, lambda: self.refresh(reset=True))

    def view_member(self, member_id):
        return MemberProfileDialog(self, self.service, member_id, self.refresh, can_edit='MEMBERS_EDIT' in self.permissions)

    def destroy(self):
        if self.search_timer:
            self.after_cancel(self.search_timer)
        self.loader.close()
        if self.add_button and self.add_button.winfo_exists():
            self.add_button.destroy()
        super().destroy()


class MemberProfileDialog(FixedFooterDialog):
    def __init__(self, master, service, member_id, on_saved, can_edit=False):
        super().__init__(master, 'Member profile', 'Membership, contact information and ministry participation.', width=800, height=660)
        self.service, self.member_id, self.on_saved = service, member_id, on_saved
        self.loader = AsyncLoader(self)
        self.member = None
        self.cancel_button.configure(text='Close')
        if can_edit:
            ActionButton(self.footer, 'Edit member', self.edit_member, 'primary').pack(side='right', padx=18, pady=14)
        self.loader.submit('profile', lambda: service.get_member(member_id), self.render, lambda error: self.error_var.set(str(error)))

    def render(self, member):
        self.member = member
        for child in self.content.winfo_children():
            child.destroy()
        person = ctk.CTkFrame(self.content, fg_color='transparent')
        person.pack(fill='x', padx=16, pady=16)
        Avatar(person, member['full_name'], member['photo_path'], size=64).pack(side='left', padx=(0,16))
        details = ctk.CTkFrame(person, fg_color='transparent')
        details.pack(side='left', fill='x', expand=True)
        label(details, member['full_name'], 23, True).pack(anchor='w')
        label(details, member['member_no'], muted=True).pack(anchor='w')
        StatusBadge(person, member['status']).pack(side='right')
        fields = [('Phone', member['phone']), ('Alternate phone', member['alternate_phone']), ('Email', member['email']),
                  ('Address', member['address']), ('Gender', member['gender'].title()), ('Date of birth', display_date(member['date_of_birth'])),
                  ('Marital status', member['marital_status'].title()), ('Occupation', member['occupation']),
                  ('Joined church', display_date(member['date_joined'])), ('Baptized', 'Yes' if member['baptized'] else 'No'),
                  ('Baptism date', display_date(member['baptism_date'])), ('Ministries', ', '.join(member['ministries']))]
        for title, value in fields:
            row = AppCard(self.content)
            row.pack(fill='x', padx=16, pady=4)
            row.grid_columnconfigure(1, weight=1)
            label(row, title, 12, muted=True, width=150, anchor='w').grid(row=0,column=0,padx=12,pady=10)
            label(row, value or '—', 13, anchor='w', wraplength=430, justify='left').grid(row=0,column=1,sticky='ew',padx=12,pady=10)

    def edit_member(self):
        if self.member:
            MemberFormDialog(self, self.service, self.after_edit, member=self.member)

    def after_edit(self):
        self.on_saved()
        self.loader.submit('profile', lambda: self.service.get_member(self.member_id), self.render, lambda error: self.error_var.set(str(error)))
