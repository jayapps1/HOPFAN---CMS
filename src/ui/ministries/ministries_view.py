"""Paginated, permission-aware ministry management and assigned ministry directory."""
import customtkinter as ctk
from src.services.ministry_service import MinistryService, CATEGORIES
from src.ui import theme
from src.ui.components.app_shell import PageHeader
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.modern import ActionButton, AppCard, EmptyState, StatCard, StatusBadge, label
from src.ui.components.modern_select import ModernSelect
from src.ui.components.search_field import SearchField
from src.ui.components.action_menu import ActionMenu
from src.ui.components.date_picker import display_date
from src.ui.ministries.dialogs import MinistryFormDialog, LifecycleConfirmation
from src.ui.ministries.profile import MinistryProfileDialog


class MinistriesView(ctk.CTkFrame):
    PAGE_SIZE=20

    def __init__(self,master,user,service=None,action_master=None):
        super().__init__(master,fg_color=theme.BACKGROUND,corner_radius=0)
        self.service=service or MinistryService(user.id)
        self.loader=AsyncLoader(self)
        self.capabilities={}
        self.offset,self.total=0,0
        self.add_button=None
        self.action_master=action_master
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(4,weight=1)
        if action_master is None:
            header=PageHeader(self,'Ministries','Manage HOPFAN ministries, fellowships and departments')
            header.grid(row=0,column=0,sticky='ew',padx=22,pady=(16,12))
            self.action_master=header.actions
        self.summary=ctk.CTkFrame(self,fg_color='transparent')
        self.summary.grid(row=1,column=0,sticky='ew',padx=22,pady=(0,12))
        self.cards={}
        for index,(key,title) in enumerate((('total','Total ministries'),('active','Active'),('inactive','Inactive'),('archived','Archived'))):
            self.summary.grid_columnconfigure(index,weight=1,uniform='stats')
            card=StatCard(self.summary,title)
            card.set('—')
            card.grid(row=0,column=index,sticky='ew',padx=(0 if index==0 else 4,4))
            self.cards[key]=card
        filters=AppCard(self)
        filters.grid(row=2,column=0,sticky='ew',padx=22,pady=(0,10))
        filters.grid_columnconfigure(0,weight=1)
        label(filters,'Search',11,True).grid(row=0,column=0,sticky='w',padx=12,pady=(8,4))
        label(filters,'Category',11,True).grid(row=0,column=1,sticky='w',padx=6,pady=(8,4))
        label(filters,'Status',11,True).grid(row=0,column=2,sticky='w',padx=6,pady=(8,4))
        self.search=SearchField(filters,lambda:self.refresh(reset=True))
        self.search.grid(row=1,column=0,sticky='ew',padx=12,pady=(0,10))
        self.category=ModernSelect(filters,['All categories']+[value.title() for value in CATEGORIES],width=150,
            command=lambda _value:self.refresh(reset=True))
        self.category.grid(row=1,column=1,padx=6,pady=(0,10))
        self.status=ModernSelect(filters,['All','Active','Inactive','Archived'],width=120,
            command=lambda _value:self.refresh(reset=True))
        self.status.set('Active')
        self.status.grid(row=1,column=2,padx=6,pady=(0,10))
        self.refresh_button=ActionButton(filters,'Refresh',self.refresh,width=80)
        self.refresh_button.grid(row=1,column=3,padx=(6,12),pady=(0,10))
        self.table_header=ctk.CTkFrame(self,fg_color=theme.SURFACE_ALT,corner_radius=8)
        self.table_header.grid(row=3,column=0,sticky='ew',padx=24,pady=(0,4))
        self.columns(self.table_header)
        for index,(title,width) in enumerate((('Ministry',1),('Code',76),('Category',82),('Members',60),('Status',88),('Updated',82),('Actions',190))):
            label(self.table_header,title,11,True,width=width,anchor='w' if index==0 else 'center').grid(row=0,column=index,
                sticky='ew',padx=(12,0) if index==0 else (0,12) if index==6 else 0,pady=10)
        self.rows=ctk.CTkScrollableFrame(self,fg_color='transparent',corner_radius=0)
        self.rows.grid(row=4,column=0,sticky='nsew',padx=20)
        self.rows.grid_columnconfigure(0,weight=1)
        self.footer=ctk.CTkFrame(self,fg_color='transparent')
        self.footer.grid(row=5,column=0,sticky='ew',padx=22,pady=12)
        self.footer.grid_columnconfigure(0,weight=1)
        self.notice=label(self.footer,'Loading ministries…',12,muted=True,anchor='w',justify='left',wraplength=540,width=1)
        self.notice.grid(row=0,column=0,sticky='ew',padx=(0,12))
        self.previous=ActionButton(self.footer,'Previous',lambda:self.page(-1),width=86)
        self.previous.grid(row=0,column=1,padx=6)
        self.next_button=ActionButton(self.footer,'Next',lambda:self.page(1),width=75)
        self.next_button.grid(row=0,column=2)
        self.refresh()

    @staticmethod
    def columns(frame):
        frame.grid_columnconfigure(0,weight=1)
        for index,width in enumerate((76,82,60,88,82,190),1):
            frame.grid_columnconfigure(index,minsize=width)

    def refresh(self,reset=False):
        if reset:
            self.offset=0
        params=dict(search=self.search.get(),status=self.status.get().upper(),
            category='ALL' if self.category.get()=='All categories' else self.category.get().upper(),
            limit=self.PAGE_SIZE,offset=self.offset)
        self.notice.configure(text='Loading ministries…',text_color=theme.TEXT_MUTED)
        self.loader.submit('directory',lambda:(self.service.capabilities(),self.service.get_ministry_stats(),
            self.service.list_ministries(**params)),self.render,self.failed)

    def page(self,direction):
        self.offset=max(0,self.offset+direction*self.PAGE_SIZE)
        self.refresh()

    def render(self,result):
        self.capabilities,stats,page=result
        if self.capabilities.get('create') and self.add_button is None:
            self.add_button=ActionButton(self.action_master,'Add ministry',self.add_ministry,'primary',width=145)
            self.add_button.pack(side='left')
        elif not self.capabilities.get('create') and self.add_button:
            self.add_button.destroy()
            self.add_button=None
        for key,value in stats.items():
            self.cards[key].set(value)
        self.total=page['total']
        if self.offset and not page['rows'] and self.total:
            self.offset=max(0,((self.total-1)//self.PAGE_SIZE)*self.PAGE_SIZE)
            self.refresh()
            return
        for child in self.rows.winfo_children():
            child.destroy()
        self.previous.configure(state='normal' if self.offset else 'disabled')
        self.next_button.configure(state='normal' if self.offset+len(page['rows'])<self.total else 'disabled')
        self.notice.configure(text=f"{self.total} ministries found · Page {self.offset//self.PAGE_SIZE+1}",text_color=theme.TEXT_MUTED)
        if not page['rows']:
            empty=EmptyState(self.rows,'No ministries found',
                "Create HOPFAN's first ministry or fellowship." if stats['total']==0 and self.capabilities.get('create') else 'Adjust the search, category or status filter.')
            empty.grid(row=0,column=0,sticky='ew')
            if self.capabilities.get('create'):
                ActionButton(empty,'Add ministry',self.add_ministry,'primary').pack(pady=(0,24))
        for index,ministry in enumerate(page['rows']):
            self.render_row(index,ministry)

    def render_row(self,index,ministry):
        card=AppCard(self.rows)
        card.ministry=ministry
        card.grid(row=index,column=0,sticky='ew',padx=2,pady=4)
        self.columns(card)
        name=label(card,ministry['name'],13,True,anchor='w',justify='left',wraplength=180,width=1)
        name.grid(row=0,column=0,sticky='ew',padx=(12,6),pady=16)
        name.bind('<Configure>',lambda event:name.configure(wraplength=max(80,event.width/name._get_widget_scaling()-8)))
        for column,value,width in ((1,ministry['code'],76),(2,ministry['category'].title(),82),(3,str(ministry['member_count']),60),
            (5,display_date(ministry['updated_at']),82)):
            label(card,value,11,muted=column in (1,5),width=width,wraplength=width).grid(row=0,column=column,pady=12)
        StatusBadge(card,ministry['status']).grid(row=0,column=4,padx=2)
        actions=ctk.CTkFrame(card,fg_color='transparent')
        actions.grid(row=0,column=6,padx=(4,12),pady=12)
        card.view_button=ActionButton(actions,'View',lambda:self.view_ministry(ministry['id']),width=48)
        card.view_button.pack(side='left',padx=2)
        if self.capabilities.get('edit'):
            card.edit_button=ActionButton(actions,'Edit',lambda:self.edit_ministry(ministry['id']),width=48)
            card.edit_button.pack(side='left',padx=2)
        choices=[]
        if ministry['status']=='ARCHIVED':
            if self.capabilities.get('restore'):
                choices.append(('Restore',lambda:self.change('restore',ministry)))
        else:
            action='deactivate' if ministry['status']=='ACTIVE' else 'activate'
            if self.capabilities.get('deactivate' if action=='deactivate' else 'edit'):
                choices.append((action.title(),lambda a=action:self.change(a,ministry)))
            if self.capabilities.get('archive'):
                choices.append(('Archive',lambda:self.change('archive',ministry)))
        if self.capabilities.get('delete_unused') and not ministry.get('in_use'):
            choices.append(('Delete unused',lambda:self.change('delete_unused',ministry)))
        if choices:
            card.action_menu=ActionMenu(actions,choices)
            card.action_menu.pack(side='left',padx=(4,0))

    def add_ministry(self):
        return MinistryFormDialog(self,self.service,self.saved,capabilities=self.capabilities)

    def edit_ministry(self,ministry_id):
        self.loader.submit('edit-profile',lambda:self.service.get_ministry(ministry_id),
            lambda profile:MinistryFormDialog(self,self.service,self.saved,profile,self.capabilities),self.failed)

    def view_ministry(self,ministry_id):
        return MinistryProfileDialog(self,self.service,ministry_id)

    def saved(self,ministry=None):
        if ministry:
            self.search.delete(0,'end')
            self.category.set('All categories')
            self.status.set(ministry['status'].title())
        self.refresh(reset=bool(ministry))

    def change(self,action,ministry):
        def confirmed(_reason,dialog):
            kwargs=dict(expected_updated_at=ministry['updated_at'])
            if action=='restore':
                kwargs['status']=dialog.restore_status.get().upper()
            if action=='delete_unused':
                kwargs['confirmed']=True
            dialog.confirm_button.configure(state='disabled',text='Working…')
            loader=AsyncLoader(dialog)
            def operation():
                method=getattr(self.service,action+'_ministry')
                return method(ministry['id'],**kwargs)
            def completed(_result):
                dialog.destroy()
                self.saved()
            def failed(error):
                dialog.error_var.set(str(error))
                dialog.confirm_button.configure(state='normal',text='Retry')
            loader.submit('lifecycle',operation,completed,failed)
        return LifecycleConfirmation(self,action,ministry,confirmed)

    def failed(self,error):
        self.notice.configure(text=str(error),text_color=theme.ERROR_TEXT)

    def destroy(self):
        self.loader.close()
        if self.add_button and self.add_button.winfo_exists():
            self.add_button.destroy()
        super().destroy()
