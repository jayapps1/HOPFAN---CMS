"""Scoped appointments, vacancies and configurable positions in the ministry profile."""
import customtkinter as ctk
from src.ui import theme
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.modern import ActionButton, AppCard, Avatar, EmptyState, StatCard, StatusBadge, ConfirmationDialog, label, font
from src.ui.components.modern_select import ModernSelect
from src.ui.components.search_field import SearchField
from src.ui.components.action_menu import ActionMenu
from src.ui.components.date_picker import display_date
from src.ui.ministries.leadership_dialogs import (LeadershipDialog, PositionFormDialog, AssignmentFormDialog,
    EndAssignmentDialog, AssignmentProfileDialog)


class MinistryLeadershipView(ctk.CTkFrame):
    PAGE_SIZE = 20
    def __init__(self, master, service, ministry):
        super().__init__(master, fg_color=theme.BACKGROUND, corner_radius=0)
        self.service, self.ministry = service, ministry
        self.loader = AsyncLoader(self)
        self.capabilities, self.offset, self.total = {}, 0, 0
        self.action_master=getattr(master,'tabs',None)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.grid(row=0, column=0, sticky='ew', pady=(2, 10))
        header.grid_columnconfigure(0, weight=1)
        label(header, 'Ministry leadership', 17, True, anchor='w').grid(row=0, column=0, sticky='ew')
        self.assign_button = ActionButton(self.action_master or header, 'Assign position', self.assign, 'primary', width=135)
        self.manage_button = ActionButton(self.action_master or header, 'Manage positions', self.manage, width=145)
        self.header = header
        if self.action_master:
            header.grid_remove()
            subtitles=[widget for widget in master.header.winfo_children() if isinstance(widget,ctk.CTkLabel)]
            self.profile_title=subtitles[0] if subtitles else None
            self.profile_subtitle=subtitles[1] if len(subtitles)>1 else None
            if self.profile_title:
                self.profile_title.configure(text=ministry['name']+' leadership',anchor='w',justify='left',wraplength=680)
            if self.profile_subtitle: self.profile_subtitle.pack_forget()
        stats = ctk.CTkFrame(self, fg_color='transparent')
        stats.grid(row=1, column=0, sticky='ew', pady=(0, 10))
        self.cards = {}
        for index, (key, title) in enumerate((('current','Current appointments'),('members','Members holding positions'),('vacant','Vacant leadership positions'))):
            stats.grid_columnconfigure(index, weight=1, uniform='stats')
            card = StatCard(stats, title)
            # Keep the shared card palette/type while giving the list room at 768px height.
            card.value.pack_forget()
            card_header=card.winfo_children()[0]
            card_header.pack_configure(pady=8)
            card.value.configure(font=font(18,True),height=22)
            card.value.pack(in_=card_header,side='right',padx=(8,0))
            card.set('—')
            card.grid(row=0, column=index, sticky='ew', padx=(0 if index == 0 else 4, 4))
            self.cards[key] = card
        filters = AppCard(self)
        filters.grid(row=2, column=0, sticky='ew', pady=(0, 8))
        filters.grid_columnconfigure(0, weight=1)
        self.search = SearchField(filters, lambda:self.refresh(True), 'Position, member name or number')
        self.search.grid(row=0, column=0, sticky='ew', padx=10, pady=10)
        self.status = ModernSelect(filters, ['Current', 'Historical', 'Vacant'], width=125, command=lambda _v:self.refresh(True))
        self.status.grid(row=0, column=1, padx=(0, 10))
        self.rows = ctk.CTkScrollableFrame(self, fg_color='transparent', corner_radius=0)
        self.rows.grid(row=3, column=0, sticky='nsew')
        self.rows.grid_columnconfigure(0, weight=1)
        footer = ctk.CTkFrame(self, fg_color='transparent')
        footer.grid(row=4, column=0, sticky='ew', pady=(8, 2))
        self.notice = label(footer, 'Loading leadership…', 11, muted=True, anchor='w', wraplength=350)
        self.notice.pack(side='left')
        self.next_button = ActionButton(footer, 'Next', lambda:self.page(1), width=65)
        self.next_button.pack(side='right')
        self.previous = ActionButton(footer, 'Previous', lambda:self.page(-1), width=85)
        self.previous.pack(side='right', padx=6)
        self.refresh()

    def page(self, direction):
        self.offset = max(0, self.offset+direction*self.PAGE_SIZE)
        self.refresh()

    def refresh(self, reset=False):
        if reset: self.offset = 0
        params = dict(status={'Current':'CURRENT','Historical':'HISTORY','Vacant':'VACANT'}[self.status.get()], search=self.search.get(), offset=self.offset, limit=self.PAGE_SIZE)
        self.loader.submit('workspace', lambda:(self.service.capabilities(self.ministry['id']), self.service.leadership_stats(self.ministry['id']),
            self.service.list_leadership(self.ministry['id'], **params)), self.render, self.failed)

    def render(self, result):
        caps, stats, page = result
        self.capabilities, self.total = caps, page['total']
        for key, card in self.cards.items(): card.set(stats[key])
        self.hide_actions()
        if caps.get('assign') and self.ministry['is_active']:
            if self.action_master: self.assign_button.pack(side='left',padx=(12,4))
            else: self.assign_button.grid(row=0, column=1, padx=4)
        if caps.get('positions_view'):
            if self.action_master: self.manage_button.pack(side='left',padx=4)
            else: self.manage_button.grid(row=0, column=2, padx=(4, 0))
        if self.offset and not page['rows'] and self.total:
            self.offset = ((self.total-1)//self.PAGE_SIZE)*self.PAGE_SIZE
            self.refresh()
            return
        self.next_button.configure(state='normal' if self.offset+len(page['rows']) < self.total else 'disabled')
        self.previous.configure(state='normal' if self.offset else 'disabled')
        self.notice.configure(text=f"{self.total} {self.status.get().lower()} results · Page {self.offset//self.PAGE_SIZE+1}", text_color=theme.TEXT_MUTED)
        for widget in self.rows.winfo_children(): widget.destroy()
        if not page['rows']:
            title = 'No vacant leadership positions' if self.status.get() == 'Vacant' else 'No '+self.status.get().lower()+' appointments'
            detail = 'Configure positions and appoint ministry members.' if stats['positions'] == 0 else 'Adjust the search or choose another view.'
            EmptyState(self.rows, title, detail).grid(row=0, column=0, sticky='ew')
        for index, appointment in enumerate(page['rows']):
            if self.status.get() == 'Vacant': self.vacancy(index, appointment)
            else: self.appointment(index, appointment)

    def appointment(self, index, row):
        card = AppCard(self.rows)
        card.appointment = row
        card.grid(row=index, column=0, sticky='ew', pady=4, padx=2)
        card.grid_columnconfigure(1, weight=1)
        Avatar(card, row['full_name'], row['photo_path'], size=36).grid(row=0, column=0, rowspan=3, padx=10, pady=12)
        label(card, row['position_name'], 14, True, anchor='w', width=1, wraplength=360).grid(row=0, column=1, sticky='ew', pady=(10,0))
        label(card, row['full_name']+' · '+row['member_no'], 12, anchor='w', width=1, wraplength=350).grid(row=1, column=1, sticky='ew')
        period = ('No system account ? ' if row.get('has_system_account') is False else '') + display_date(row['start_date'])+' – '+(display_date(row['end_date']) if row['end_date'] else 'Present')
        label(card, period, 11, muted=True, anchor='w').grid(row=2, column=1, sticky='ew', pady=(0,10))
        StatusBadge(card, 'CURRENT' if row['is_current'] else 'HISTORICAL').grid(row=0, column=2, rowspan=3, padx=8)
        actions = ctk.CTkFrame(card, fg_color='transparent')
        actions.grid(row=0, column=3, rowspan=3, padx=(0,10), pady=8)
        card.view_button = ActionButton(actions, 'View', lambda:self.view(row['id']), width=55)
        card.view_button.pack(side='left', padx=2)
        choices=[]
        if self.capabilities.get('edit'): choices.append(('Edit assignment',lambda:self.edit(row)))
        if row['is_current'] and self.capabilities.get('end'): choices.append(('End assignment',lambda:self.end(row)))
        if self.capabilities.get('grant_system_access') and not row.get('has_system_account', True):
            choices.append(('Grant system access',lambda:self.grant_access(row)))
        if choices:
            card.action_menu=ActionMenu(actions, choices)
            card.action_menu.pack(side='left', padx=4)

    def grant_access(self, row):
        from src.services.user_service import UserService
        from src.ui.administration.dialogs import UserFormDialog
        service=UserService(self.service.user_id, self.service.session_factory)
        self.loader.submit('member-link',lambda:service.member_link(row['member_id']),
            lambda member:UserFormDialog(self,service,lambda _:self.refresh(),member=member),
            lambda error:self.notice.configure(text=str(error)))

    def vacancy(self, index, position):
        card=AppCard(self.rows)
        card.position=position
        card.grid(row=index, column=0, sticky='ew', pady=4, padx=2)
        card.grid_columnconfigure(0, weight=1)
        label(card, position['name'], 15, True, anchor='w').grid(row=0, column=0, sticky='ew', padx=12, pady=(12,2))
        maximum=position['max_current_holders']
        detail = f"{position['current_holders']} of {maximum} holders" if maximum else 'No current holder · Multiple holders allowed'
        label(card, detail, 11, muted=True, anchor='w').grid(row=1,column=0,sticky='ew',padx=12,pady=(0,12))
        StatusBadge(card,'VACANT').grid(row=0,column=1,rowspan=2,padx=8)
        if self.capabilities.get('assign') and self.ministry['is_active']:
            card.assign_button=ActionButton(card,'Assign',lambda:self.assign(position['id']), 'primary', width=75)
            card.assign_button.grid(row=0,column=2,rowspan=2,padx=12)

    def assign(self, position_id=None):
        return AssignmentFormDialog(self,self.service,self.ministry,self.saved,self.capabilities,position_id=position_id)

    def edit(self,row):
        return AssignmentFormDialog(self,self.service,self.ministry,self.saved,self.capabilities,assignment=row)

    def end(self,row):
        return EndAssignmentDialog(self,self.service,row,self.saved)

    def view(self,assignment_id):
        return AssignmentProfileDialog(self,self.service,assignment_id)

    def manage(self):
        return PositionManagerDialog(self,self.service,self.ministry,self.refresh)

    def saved(self):
        self.refresh(True)

    def failed(self,error):
        self.notice.configure(text=str(error),text_color=theme.ERROR_TEXT)

    def hide_actions(self):
        for button in (self.assign_button,self.manage_button):
            if self.action_master: button.pack_forget()
            else: button.grid_forget()

    def destroy(self):
        for button in (self.assign_button,self.manage_button):
            if button.winfo_exists(): button.destroy()
        super().destroy()


class PositionManagerDialog(LeadershipDialog):
    def __init__(self,master,service,ministry,on_changed):
        super().__init__(master,'Manage positions',ministry['name'],width=820,height=740)
        self.service,self.ministry,self.on_changed=service,ministry,on_changed
        self.positions,self.capabilities=[],{}
        self.cancel_button.configure(text='Close')
        toolbar=ctk.CTkFrame(self.header,fg_color='transparent')
        toolbar.pack(fill='x',padx=18,pady=(0,14))
        self.status=ModernSelect(toolbar,['Active','Inactive','All'],width=135,command=lambda _v:self.render_rows())
        self.status.pack(side='left')
        self.add_button=ActionButton(toolbar,'Add position',self.add,'primary',width=130)
        self.refresh()

    def refresh(self):
        self.loader.submit('positions',lambda:(self.service.capabilities(self.ministry['id']),self.service.list_positions(self.ministry['id'])),
            self.render,lambda error:self.error_var.set(str(error)))

    def render(self,result):
        self.capabilities,self.positions=result
        self.add_button.pack_forget()
        if self.capabilities.get('position_create'): self.add_button.pack(side='right')
        self.render_rows()

    def render_rows(self):
        for widget in self.content.winfo_children(): widget.destroy()
        self.content.grid_columnconfigure(0,weight=1)
        rows=[row for row in self.positions if self.status.get()=='All' or row['is_active']==(self.status.get()=='Active')]
        if not rows:
            EmptyState(self.content,'No positions in this view','Define the offices used by this ministry.').grid(row=0,column=0,sticky='ew')
        for index,row in enumerate(rows):
            card=AppCard(self.content)
            card.position=row
            card.grid(row=index,column=0,sticky='ew',padx=12,pady=4)
            card.grid_columnconfigure(0,weight=1)
            label(card,row['name'],15,True,anchor='w',width=1,wraplength=350).grid(row=0,column=0,sticky='ew',padx=12,pady=(12,2))
            label(card,row['code']+' · '+('Leadership' if row['is_leadership'] else 'Other position')+f" · Order {row['sort_order']}",11,muted=True,anchor='w',width=1,wraplength=350).grid(row=1,column=0,sticky='ew',padx=12)
            capacity=str(row['max_current_holders']) if row['max_current_holders'] else 'Unlimited'
            label(card,f"Current holders: {row['current_holders']} · Limit: {capacity}",11,muted=True,anchor='w').grid(row=2,column=0,sticky='ew',padx=12,pady=(2,12))
            StatusBadge(card,'ACTIVE' if row['is_active'] else 'INACTIVE').grid(row=0,column=1,rowspan=3,padx=8)
            actions=ctk.CTkFrame(card,fg_color='transparent')
            actions.grid(row=0,column=2,rowspan=3,padx=12)
            if self.capabilities.get('position_edit'):
                card.edit_button=ActionButton(actions,'Edit',lambda position=row:self.edit(position),width=55)
                card.edit_button.pack(side='left',padx=2)
            choices=[]
            if row['is_active'] and self.capabilities.get('position_archive'):
                choices.append(('Deactivate position',lambda position=row:self.change(position,'deactivate')))
            if not row['in_use'] and self.capabilities.get('position_delete'):
                choices.append(('Delete unused position',lambda position=row:self.change(position,'delete')))
            if choices:
                card.action_menu=ActionMenu(actions,choices)
                card.action_menu.pack(side='left',padx=4)

    def add(self):
        return PositionFormDialog(self,self.service,self.ministry,self.changed,capabilities=self.capabilities)

    def edit(self,position):
        return PositionFormDialog(self,self.service,self.ministry,self.changed,position,self.capabilities)

    def changed(self):
        self.refresh()
        self.on_changed()

    def change(self,position,action):
        title='Deactivate position' if action=='deactivate' else 'Delete unused position'
        detail=position['name']+' will become inactive. Appointment history remains. End current appointments first.' if action=='deactivate' else 'Permanently delete '+position['name']+'? Deletion is allowed only when no appointment history exists.'
        def confirmed(_reason,dialog):
            dialog.confirm_button.configure(state='disabled')
            loader=AsyncLoader(dialog)
            def operation():
                if action=='deactivate': return self.service.deactivate_position(position['id'],position['updated_at'])
                return self.service.delete_unused_position(position['id'],confirmed=True,expected_updated_at=position['updated_at'])
            def complete(_result):
                dialog.destroy()
                self.grab_set()
                self.changed()
            def failed(error):
                dialog.error_var.set(str(error))
                dialog.confirm_button.configure(state='normal')
            loader.submit('change',operation,complete,failed)
        dialog=ConfirmationDialog(self,title,detail,confirmed)
        dialog.confirm_button.configure(text=title,width=180)
        return dialog
