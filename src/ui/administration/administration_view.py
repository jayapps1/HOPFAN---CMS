"""Real Users, Roles, Permissions and Security Audit administration workspaces."""
import json
import customtkinter as ctk
from src.ui import theme
from src.ui.components.app_shell import PageHeader
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.modern import ActionButton, AppCard, Avatar, EmptyState, StatCard, StatusBadge, label, font
from src.ui.components.modern_select import ModernSelect
from src.ui.components.search_field import SearchField
from src.ui.administration.dialogs import UserFormDialog, UserProfileDialog, UserAccessDialog, AdminDialog, details, heading, timestamp
from src.ui.administration.role_dialogs import RoleFormDialog, RoleProfileDialog
from src.services.administration_base import AdministrationError
from src.services.authorization_service import AuthorizationDenied
from src.services.user_service import UserService
from src.services.role_service import RoleService


def wrapped(parent,text,row,column,bold=False,wraplength=280):
    w=label(parent,text,12,bold,anchor='w',justify='left',width=1,wraplength=wraplength)
    w.grid(row=row,column=column,sticky='ew',padx=10,pady=6)
    return w


class DirectoryView(ctk.CTkFrame):
    PAGE_SIZE=20
    def __init__(self,master,title,subtitle):
        super().__init__(master,fg_color=theme.BACKGROUND,corner_radius=0)
        self.loader=AsyncLoader(self)
        self.offset,self.total=0,0
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(4,weight=1)
        self.header=PageHeader(self,title,subtitle)
        self.header.grid(row=0,column=0,sticky='ew',padx=20,pady=(8,12))
        self.filters=AppCard(self)
        self.filters.grid(row=2,column=0,sticky='ew',padx=20,pady=(0,10))
        self.rows=ctk.CTkScrollableFrame(self,fg_color='transparent')
        self.rows.grid(row=4,column=0,sticky='nsew',padx=16)
        self.rows.grid_columnconfigure(0,weight=1)
        footer=ctk.CTkFrame(self,fg_color='transparent')
        footer.grid(row=5,column=0,sticky='ew',padx=20,pady=12)
        footer.grid_columnconfigure(0,weight=1)
        self.notice=label(footer,'Loading...',12,muted=True,anchor='w',width=1)
        self.notice.grid(row=0,column=0,sticky='ew')
        self.previous=ActionButton(footer,'Previous',lambda:self.page(-1),width=85)
        self.previous.grid(row=0,column=1,padx=5)
        self.next_button=ActionButton(footer,'Next',lambda:self.page(1),width=70)
        self.next_button.grid(row=0,column=2)
        self.records=[]

    def page(self,direction):
        self.offset=max(0,self.offset+direction*self.PAGE_SIZE)
        self.refresh()

    def failed(self,error):
        self.notice.configure(text=str(error) if isinstance(error,(AdministrationError,AuthorizationDenied)) else 'Unable to load this workspace.',text_color=theme.DANGER)
        for w in self.rows.winfo_children(): w.destroy()

    def directory(self,page):
        self.total,self.records=page['total'],page['rows']
        if self.offset and not self.records and self.total:
            self.offset=((self.total-1)//self.PAGE_SIZE)*self.PAGE_SIZE
            self.refresh(); return False
        for w in self.rows.winfo_children(): w.destroy()
        self.notice.configure(text=f'{self.total} records · Page {self.offset//self.PAGE_SIZE+1}',text_color=theme.TEXT_MUTED)
        self.previous.configure(state='normal' if self.offset else 'disabled')
        self.next_button.configure(state='normal' if self.offset+len(self.records)<self.total else 'disabled')
        if not self.records: EmptyState(self.rows,'No matching records','Adjust the search or filters.').grid(row=0,column=0,sticky='ew')
        return True


class UsersView(DirectoryView):
    def __init__(self,master,service,permissions):
        super().__init__(master,'Users','Manage HOPFAN system access, roles and account security.')
        self.service,self.permissions=service,set(permissions)
        self.add_button=None
        if 'USER_CREATE' in self.permissions:
            self.add_button=ActionButton(self.header.actions,'Create user',self.create_user,'primary',width=140)
            self.add_button.pack(side='left')
        summary=ctk.CTkFrame(self,fg_color='transparent')
        summary.grid(row=1,column=0,sticky='ew',padx=20,pady=(0,12))
        self.cards={}
        for i,(key,title) in enumerate((('total','Total users'),('active','Active'),('locked','Locked'),('inactive','Inactive'))):
            summary.grid_columnconfigure(i,weight=1,uniform='stats')
            card=StatCard(summary,title)
            card.grid(row=0,column=i,sticky='ew',padx=4)
            self.cards[key]=card
        self.search=SearchField(self.filters,lambda:self.refresh(True),'Search name, username, email or phone')
        self.search.grid(row=0,column=0,columnspan=4,sticky='ew',padx=12,pady=10)
        for i in range(3): self.filters.grid_columnconfigure(i,weight=1)
        self.status=ModernSelect(self.filters,['All statuses','Active','Locked','Inactive','Suspended'],width=120,command=lambda _:self.refresh(True))
        self.status.grid(row=1,column=0,sticky='ew',padx=(12,4),pady=(0,10))
        self.role=ModernSelect(self.filters,['All roles'],width=150,command=lambda _:self.refresh(True),search_label='roles')
        self.role.grid(row=1,column=1,sticky='ew',padx=4,pady=(0,10))
        self.ministry=ModernSelect(self.filters,['All ministries'],width=175,command=lambda _:self.refresh(True),search_label='ministries')
        self.ministry.grid(row=1,column=2,sticky='ew',padx=4,pady=(0,10))
        ActionButton(self.filters,'Refresh',self.refresh,width=78).grid(row=1,column=3,padx=(4,12),pady=(0,10))
        self.role_options,self.scope_options={},{}
        self.table_header=ctk.CTkFrame(self,fg_color=theme.SURFACE_ALT)
        self.table_header.grid(row=3,column=0,sticky='ew',padx=20,pady=(0,4))
        self.columns(self.table_header)
        for i,title in enumerate(('User / Member / Email','Roles / Ministry scopes','Status / Last login','Actions')): wrapped(self.table_header,title,0,i,True,110 if i==2 else 280)
        self.loader.submit('options',service.access_options,self.options_ready,self.failed)
        self.refresh()

    @staticmethod
    def columns(row):
        row.grid_columnconfigure(0,weight=3,minsize=155)
        row.grid_columnconfigure(1,weight=3,minsize=155)
        row.grid_columnconfigure(2,weight=1,minsize=118)
        row.grid_columnconfigure(3,minsize=115)

    def options_ready(self,options):
        self.role_options={r['name']:r['id'] for r in options['roles']}
        self.scope_options={m['name']:m['id'] for m in options['ministries']}
        self.role.configure(values=['All roles']+list(self.role_options))
        self.ministry.configure(values=['All ministries']+list(self.scope_options))

    def refresh(self,reset=False):
        if reset: self.offset=0
        params=dict(search=self.search.get(),status='ALL' if self.status.get()=='All statuses' else self.status.get().upper(),
            role_id=self.role_options.get(self.role.get()),ministry_id=self.scope_options.get(self.ministry.get()),limit=self.PAGE_SIZE,offset=self.offset)
        self.loader.submit('users',lambda:(self.service.stats(),self.service.list_users(**params)),self.render,self.failed)

    def render(self,result):
        stats,page=result
        for key,card in self.cards.items(): card.set(stats[key]+(stats.get('suspended',0) if key=='inactive' else 0))
        if not self.directory(page): return
        for i,user in enumerate(self.records):
            row=AppCard(self.rows)
            row.user=user
            row.grid(row=i,column=0,sticky='ew',padx=3,pady=4)
            self.columns(row)
            identity=ctk.CTkFrame(row,fg_color='transparent')
            identity.grid(row=0,column=0,sticky='ew',pady=8)
            identity.grid_columnconfigure(1,weight=1)
            Avatar(identity,user['full_name'],user.get('photo_path'),34).grid(row=0,column=0,rowspan=2,padx=(10,0))
            wrapped(identity,user['full_name'],0,1,True)
            number=user['member']['member_no'] if user['member'] else 'No member link'
            wrapped(identity,user['username']+' · '+number+'\n'+(user['email'] or 'No email'),1,1)
            wrapped(row,', '.join(r['name'] for r in user['roles']) or 'No roles',0,1,True)
            wrapped(row,', '.join(s['name'] for s in user['scopes']) or 'No ministry scopes',1,1)
            StatusBadge(row,user['status']).grid(row=0,column=2,padx=4,pady=(12,2))
            wrapped(row,timestamp(user['last_login_at']),1,2,wraplength=110)
            actions=ctk.CTkFrame(row,fg_color='transparent')
            actions.grid(row=0,column=3,rowspan=2,padx=8,pady=12)
            row.view_button=ActionButton(actions,'View',lambda u=user:self.view_user(u['id']),width=50)
            row.view_button.pack(side='left',padx=2)
            if 'USER_EDIT' in self.permissions:
                row.edit_button=ActionButton(actions,'Edit',lambda u=user:self.edit_user(u['id']),width=50)
                row.edit_button.pack(side='left',padx=2)

    def saved(self,_=None): self.refresh()
    def create_user(self,member=None): return UserFormDialog(self,self.service,self.saved,member=member)
    def view_user(self,user_id):
        self.loader.submit('profile',lambda:self.service.get_user(user_id),lambda u:UserProfileDialog(self,self.service,u,self.permissions,self.saved),self.failed)
    def edit_user(self,user_id):
        self.loader.submit('profile',lambda:self.service.get_user(user_id),lambda u:UserFormDialog(self,self.service,self.saved,u),self.failed)


class RolesView(DirectoryView):
    def __init__(self,master,service,permissions):
        super().__init__(master,'Roles','Define software capabilities independently of church positions.')
        self.service,self.permissions=service,set(permissions)
        self.add_button=None
        if 'ROLE_CREATE' in self.permissions:
            self.add_button=ActionButton(self.header.actions,'Create role',self.create_role,'primary',width=140)
            self.add_button.pack(side='left')
        self.filters.grid_columnconfigure(0,weight=1)
        self.search=SearchField(self.filters,lambda:self.refresh(True),'Search role name, code or description')
        self.search.grid(row=0,column=0,sticky='ew',padx=12,pady=12)
        self.status=ModernSelect(self.filters,['All','Active','Inactive'],width=120,command=lambda _:self.refresh(True))
        self.status.grid(row=0,column=1,padx=6)
        ActionButton(self.filters,'Refresh',self.refresh,width=80).grid(row=0,column=2,padx=(6,12))
        self.refresh()

    def refresh(self,reset=False):
        if reset: self.offset=0
        params=dict(search=self.search.get(),status=self.status.get().upper(),limit=self.PAGE_SIZE,offset=self.offset)
        self.loader.submit('roles',lambda:self.service.list_roles(**params),self.render,self.failed)

    def render(self,page):
        if not self.directory(page): return
        for i,role in enumerate(self.records):
            row=AppCard(self.rows)
            row.grid(row=i,column=0,sticky='ew',padx=3,pady=4)
            row.grid_columnconfigure(0,weight=1)
            wrapped(row,role['name']+' · '+role['code'],0,0,True)
            wrapped(row,role['description'],1,0)
            wrapped(row,f"{role['user_count']} users · {role['permission_count']} permissions · {'System role' if role['is_system'] else 'Custom role'}",2,0)
            StatusBadge(row,'ACTIVE' if role['is_active'] else 'INACTIVE').grid(row=0,column=1,rowspan=3,padx=6)
            actions=ctk.CTkFrame(row,fg_color='transparent')
            actions.grid(row=0,column=2,rowspan=3,padx=12)
            row.view_button=ActionButton(actions,'View',lambda r=role:self.view_role(r['id']),width=55)
            row.view_button.pack(side='left',padx=2)
            if 'ROLE_EDIT' in self.permissions: ActionButton(actions,'Edit',lambda r=role:self.edit_role(r['id']),width=55).pack(side='left',padx=2)

    def saved(self,_=None): self.refresh()
    def create_role(self): return RoleFormDialog(self,self.service,self.saved)
    def view_role(self,role_id): self.loader.submit('role',lambda:self.service.get_role(role_id),lambda r:RoleProfileDialog(self,self.service,r,self.permissions,self.saved),self.failed)
    def edit_role(self,role_id): self.loader.submit('role',lambda:self.service.get_role(role_id),lambda r:RoleFormDialog(self,self.service,self.saved,r),self.failed)


class PermissionsView(ctk.CTkFrame):
    def __init__(self,master,service):
        super().__init__(master,fg_color='transparent')
        self.loader=AsyncLoader(self)
        self.header=PageHeader(self,'Permissions','Capabilities granted through active software roles.')
        self.header.pack(fill='x',padx=20,pady=12)
        self.search=SearchField(self,lambda:self.render(self.permissions),'Search permission name, code or module')
        self.search.pack(fill='x',padx=20,pady=(0,12))
        self.rows=ctk.CTkScrollableFrame(self,fg_color='transparent')
        self.rows.pack(fill='both',expand=True,padx=16)
        self.permissions=[]
        self.loader.submit('catalogue',service.permission_catalogue,self.ready,lambda e:label(self.rows,str(e),wraplength=600).pack())

    def ready(self,permissions): self.permissions=permissions; self.render(permissions)
    def render(self,permissions):
        for w in self.rows.winfo_children(): w.destroy()
        term=self.search.get().casefold()
        groups={}
        for p in permissions:
            if term in (p['name']+' '+p['code']+' '+p['module']).casefold(): groups.setdefault(p['module'],[]).append(p)
        for module,rows in groups.items():
            card=AppCard(self.rows)
            card.pack(fill='x',padx=4,pady=6)
            heading(card,module+f' · {len(rows)} permissions')
            for p in rows: details(card,p['name']+'\n'+p['code']+(' · inactive' if not p['is_active'] else ''))


class AuditView(DirectoryView):
    def __init__(self,master,service):
        super().__init__(master,'Security audit','Account, role, sign-in and recovery history. Credentials are never recorded.')
        self.service=service
        self.filters.grid_columnconfigure(0,weight=1)
        ActionButton(self.filters,'Refresh',self.refresh,width=90).pack(anchor='e',padx=12,pady=12)
        self.refresh()

    def refresh(self): self.loader.submit('audit',lambda:self.service.audit_events(limit=self.PAGE_SIZE,offset=self.offset),self.render,self.failed)
    def render(self,page):
        if not self.directory(page): return
        for i,event in enumerate(self.records):
            row=AppCard(self.rows)
            row.grid(row=i,column=0,sticky='ew',padx=4,pady=4)
            row.grid_columnconfigure(0,weight=1)
            wrapped(row,event['action'].replace('_',' ').title()+' · '+event['target'],0,0,True)
            wrapped(row,'By '+event['actor']+' · '+timestamp(event['created_at']),1,0)
            ActionButton(row,'Details',lambda e=event:self.show_event(e),width=75).grid(row=0,column=1,rowspan=2,padx=12,pady=12)

    def show_event(self,event):
        dialog=AdminDialog(self,event['action'].replace('_',' ').title(),event['target'],width=700,height=620)
        dialog.cancel_button.configure(text='Close')
        details(dialog.content,'By '+event['actor']+' · '+timestamp(event['created_at']))
        for title,key in (('Before','old_values'),('After','new_values')):
            heading(dialog.content,title)
            details(dialog.content,json.dumps(event[key],indent=2,ensure_ascii=False) if event[key] else 'None')
        return dialog


class AdministrationView(ctk.CTkFrame):
    def __init__(self,master,user,permissions,user_service=None,role_service=None,on_ministries=None):
        super().__init__(master,fg_color=theme.BACKGROUND,corner_radius=0)
        self.permissions=set(permissions)
        self.user_service=user_service or UserService(user.id)
        self.role_service=role_service or RoleService(user.id)
        self.body=None
        toolbar=ctk.CTkFrame(self,fg_color='transparent')
        toolbar.pack(fill='x',padx=20,pady=(6,10))
        self.tabs=[]
        for title,code in (('Users','USER_VIEW'),('Roles','ROLE_VIEW'),('Permissions','PERMISSION_VIEW'),('Security audit','SECURITY_AUDIT_VIEW')):
            if code in self.permissions: self.tabs.append(title)
        self.selector=ctk.CTkSegmentedButton(toolbar,values=self.tabs,command=self.select,font=font(12,True),height=38,
            fg_color=theme.SURFACE_ALT,selected_color=theme.SECONDARY,selected_hover_color=theme.SECONDARY_HOVER,
            unselected_color=theme.SURFACE_ALT,unselected_hover_color=theme.BORDER,text_color=theme.TEXT)
        self.selector.pack(side='left')
        if on_ministries and self.permissions.intersection({'MINISTRIES_VIEW_ALL','MINISTRIES_VIEW_OWN'}):
            ActionButton(toolbar,'Ministries',on_ministries,width=100).pack(side='right')
        if self.tabs: self.selector.set(self.tabs[0]); self.select(self.tabs[0])
        else: EmptyState(self,'No administration capabilities assigned','Ask an authorized administrator for the specific account or role permissions needed.').pack(fill='both',expand=True)

    def select(self,name):
        if name not in self.tabs: return
        if self.body: self.body.destroy()
        routes={'Users':lambda:UsersView(self,self.user_service,self.permissions),
            'Roles':lambda:RolesView(self,self.role_service,self.permissions),'Permissions':lambda:PermissionsView(self,self.role_service),
            'Security audit':lambda:AuditView(self,self.user_service)}
        self.body=routes[name]()
        self.body.pack(fill='both',expand=True)
