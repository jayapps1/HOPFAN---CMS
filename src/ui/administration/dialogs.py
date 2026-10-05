"""Account dialogs using paged member selection and fixed modal actions."""
import secrets
import string
import customtkinter as ctk
from src.ui import theme
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.modern import (ActionButton, AppCard, Avatar, ConfirmationDialog, FixedFooterDialog,
    ModernEntry, StatusBadge, label, font)
from src.ui.components.modern_select import ModernSelect
from src.ui.components.multi_select_dropdown import MultiSelectDropdown
from src.ui.components.search_field import SearchField
from src.services.administration_base import AdministrationError
from src.services.authorization_service import AuthorizationDenied
from src.services.auth_service import AuthenticationError, PasswordRecoveryError


def timestamp(value):
    return value.astimezone().strftime('%d/%m/%Y %H:%M') if value else 'Never / not set'


def heading(parent,text):
    label(parent,text,12,True,anchor='w').pack(fill='x',padx=16,pady=(14,5))


def details(parent,text,**kwargs):
    widget=label(parent,text,12,muted=True,anchor='w',justify='left',wraplength=440,**kwargs)
    widget.pack(fill='x',padx=16,pady=(4,8))
    return widget


class AdminDialog(FixedFooterDialog):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.loader=AsyncLoader(self)
        self.busy=False

    def request(self,operation,success,button=None):
        if self.busy:
            return
        self.busy=True
        self.error_var.set('')
        if button: button.configure(state='disabled')
        def done(result):
            self.busy=False
            if button: button.configure(state='normal')
            success(result)
        def failed(error):
            self.busy=False
            if button: button.configure(state='normal')
            self.error_var.set(str(error) if isinstance(error,(AdministrationError,AuthorizationDenied,AuthenticationError,PasswordRecoveryError)) else 'Unable to complete this operation. Refresh and retry.')
        self.loader.submit('operation',operation,done,failed)

    def entry(self,title,value='',secret=False):
        heading(self.content,title)
        entry=ModernEntry(self.content,show='•' if secret else '')
        entry.pack(fill='x',padx=16,pady=(0,4))
        entry.insert(0,value or '')
        return entry


class MemberLinkPicker(AdminDialog):
    PAGE_SIZE=12
    def __init__(self,master,service,on_selected):
        super().__init__(master,'Link an existing member','Search by name, member number, email or phone.',width=720,height=640)
        self.service,self.on_selected=service,on_selected
        self.offset,self.total=0,0
        self.search=SearchField(self.header,lambda:self.refresh(True),'Search members')
        self.search.pack(fill='x',padx=16,pady=(0,14))
        self.notice=label(self.footer,'',11,muted=True)
        self.notice.pack(side='left',padx=8)
        self.previous=ActionButton(self.footer,'Previous',lambda:self.page(-1),width=82)
        self.previous.pack(side='right',padx=8,pady=14)
        self.next_button=ActionButton(self.footer,'Next',lambda:self.page(1),width=70)
        self.next_button.pack(side='right',padx=8,pady=14)
        self.refresh()

    def page(self,direction):
        self.offset=max(0,self.offset+direction*self.PAGE_SIZE)
        self.refresh()

    def refresh(self,reset=False):
        if reset: self.offset=0
        params=dict(search=self.search.get(),limit=self.PAGE_SIZE,offset=self.offset)
        self.loader.submit('members',lambda:self.service.search_members(**params),self.render,lambda e:self.error_var.set(str(e)))

    def render(self,page):
        self.total=page['total']
        for w in self.content.winfo_children(): w.destroy()
        self.content.grid_columnconfigure(0,weight=1)
        self.previous.configure(state='normal' if self.offset else 'disabled')
        self.next_button.configure(state='normal' if self.offset+len(page['rows'])<self.total else 'disabled')
        self.notice.configure(text=f'{self.total} members')
        for index,person in enumerate(page['rows']):
            row=AppCard(self.content)
            row.grid(row=index,column=0,sticky='ew',padx=12,pady=4)
            row.grid_columnconfigure(1,weight=1)
            Avatar(row,person['full_name'],person.get('photo_path')).grid(row=0,column=0,rowspan=3,padx=12,pady=12)
            label(row,person['full_name'],14,True,width=1,anchor='w').grid(row=0,column=1,sticky='ew',pady=(10,0))
            label(row,person['member_no']+' · '+(person.get('phone') or 'No phone'),11,muted=True,anchor='w').grid(row=1,column=1,sticky='ew')
            label(row,', '.join(person.get('ministries',[])) or 'No ministry membership',11,muted=True,anchor='w',wraplength=350).grid(row=2,column=1,sticky='ew',pady=(0,10))
            button=ActionButton(row,'Already linked' if person.get('user_id') else 'Select',lambda p=person:self.select(p),width=95)
            button.grid(row=0,column=2,rowspan=3,padx=12)
            if person.get('user_id'): button.configure(state='disabled')
        if not page['rows']: details(self.content,'No members match this search.')

    def select(self,person):
        self.on_selected(person)
        self.destroy()


class UserFormDialog(AdminDialog):
    def __init__(self,master,service,on_saved,user=None,member=None):
        super().__init__(master,'Edit account profile' if user else 'Create user','A member link is optional. Software access is assigned separately from church positions.',width=740,height=750)
        self.service,self.on_saved,self.user=service,on_saved,user
        self.member=member or (user.get('member') if user else None)
        heading(self.content,'Linked member')
        self.person=AppCard(self.content)
        self.person.pack(fill='x',padx=16)
        self.render_member()
        self.username=self.entry('Username *',user.get('username') if user else '')
        self.email=self.entry('Email *',user.get('email') if user else (member or {}).get('email',''))
        self.phone=self.entry('Phone',user.get('phone') if user else (member or {}).get('phone',''))
        if not user:
            self.password=self.entry('Initial password *',secret=True)
            self.confirm=self.entry('Confirm password *',secret=True)
            details(self.content,'Use 10+ characters with uppercase, lowercase, a number and a special character.')
            heading(self.content,'Status')
            self.status=ModernSelect(self.content,['Active','Inactive'])
            self.status.pack(fill='x',padx=16)
            heading(self.content,'Software roles')
            self.roles=MultiSelectDropdown(self.content,placeholder='Select software roles',search_label='roles')
            self.roles.pack(fill='x',padx=16)
            heading(self.content,'Ministry scopes')
            self.scopes=MultiSelectDropdown(self.content,placeholder='Select ministries')
            self.scopes.pack(fill='x',padx=16)
            self.require_change=ctk.BooleanVar(master=self,value=True)
            ctk.CTkCheckBox(self.content,text='Require password change at first login',variable=self.require_change,font=font(),text_color=theme.TEXT).pack(anchor='w',padx=16,pady=18)
            details(self.content,'Global permissions apply church-wide. Own-ministry permissions apply only within selected scopes. Authenticator setup is completed by the user later.')
        self.save_button=ActionButton(self.footer,'Save profile' if user else 'Create user',self.save,'primary',width=140)
        self.save_button.pack(side='right',padx=18,pady=14)
        if not user:
            self.save_button.configure(state='disabled')
            self.loader.submit('options',service.access_options,self.options_ready,lambda e:self.error_var.set(str(e)))

    def options_ready(self,options):
        self.roles.set_options([r for r in options['roles'] if r['assignable']])
        self.scopes.set_options([m for m in options['ministries'] if m['is_active']])
        self.save_button.configure(state='normal')

    def render_member(self):
        for w in self.person.winfo_children(): w.destroy()
        details(self.person,(self.member['full_name']+' · '+self.member['member_no']) if self.member else 'No member linked')
        actions=ctk.CTkFrame(self.person,fg_color='transparent')
        actions.pack(anchor='w',padx=12,pady=(0,10))
        ActionButton(actions,'Search member',self.pick_member,width=125).pack(side='left',padx=4)
        if self.member: ActionButton(actions,'Remove link',lambda:self.selected_member(None),width=115).pack(side='left',padx=4)

    def pick_member(self):
        return MemberLinkPicker(self,self.service,self.selected_member)

    def selected_member(self,person):
        self.member=person
        self.render_member()
        if person and not self.user:
            for entry,key in ((self.email,'email'),(self.phone,'phone')):
                if not entry.get() and person.get(key): entry.insert(0,person[key])

    def save(self):
        data=dict(username=self.username.get(),email=self.email.get(),phone=self.phone.get(),member_id=self.member['id'] if self.member else None)
        if self.user:
            operation=lambda:self.service.update_profile(self.user['id'],data,self.user['updated_at'])
        else:
            data.update(password=self.password.get(),confirm_password=self.confirm.get(),status=self.status.get().upper(),require_password_change=self.require_change.get())
            role_ids,scope_ids=self.roles.get_selected_ids(),self.scopes.get_selected_ids()
            operation=lambda:self.service.create_user(data,role_ids,scope_ids)
        def saved(result):
            if not self.user:
                self.password.delete(0,'end'); self.confirm.delete(0,'end')
            self.on_saved(result)
            self.destroy()
        self.request(operation,saved,self.save_button)


class UserAccessDialog(AdminDialog):
    def __init__(self,master,service,user,on_saved,permissions):
        super().__init__(master,'Edit software access',user['full_name']+' · '+user['username'],width=720,height=610)
        self.service,self.user,self.on_saved,self.permissions=service,user,on_saved,set(permissions)
        self.role_ids=[r['id'] for r in user['roles']]
        self.scope_ids=[s['id'] for s in user['scopes']]
        heading(self.content,'Software roles')
        self.roles=MultiSelectDropdown(self.content,selected_ids=self.role_ids,placeholder='Select roles',search_label='roles')
        self.roles.pack(fill='x',padx=16)
        heading(self.content,'Ministry scopes')
        self.scopes=MultiSelectDropdown(self.content,selected_ids=self.scope_ids)
        self.scopes.pack(fill='x',padx=16)
        details(self.content,'Roles give capabilities. Scopes determine where own-ministry capabilities apply. Global permissions remain church-wide even when scopes are selected.')
        details(self.content,'Revoking a role or scope preserves church positions, participation and historical records.')
        self.normalize=ctk.BooleanVar(master=self,value=False)
        if any(s.get('legacy_attendance_limits') for s in user['scopes']) and 'USER_SCOPE_MANAGE' in self.permissions:
            ctk.CTkCheckBox(self.content,text='Replace legacy attendance limits with role capabilities',variable=self.normalize,
                font=font(),text_color=theme.TEXT).pack(anchor='w',padx=16,pady=14)
            details(self.content,'Existing attendance restrictions stay in force unless you explicitly select this option.')
        self.save_button=ActionButton(self.footer,'Save access',self.save,'primary',width=140)
        self.save_button.pack(side='right',padx=18,pady=14)
        self.save_button.configure(state='disabled')
        self.loader.submit('options',lambda:service.access_options(user['id']),self.options_ready,lambda e:self.error_var.set(str(e)))

    def options_ready(self,options):
        self.roles.set_options([r for r in options['roles'] if r['assignable'] or r['id'] in self.role_ids])
        self.scopes.set_options(options['ministries'])
        if 'ROLE_ASSIGN' not in self.permissions: self.roles.configure(state='disabled')
        if 'USER_SCOPE_MANAGE' not in self.permissions: self.scopes.configure(state='disabled')
        self.save_button.configure(state='normal')

    def save(self):
        params=dict(expected_updated_at=self.user['updated_at'])
        if 'ROLE_ASSIGN' in self.permissions: params['role_ids']=self.roles.get_selected_ids()
        if 'USER_SCOPE_MANAGE' in self.permissions: params.update(ministry_ids=self.scopes.get_selected_ids(),normalize_existing=self.normalize.get())
        operation=lambda:self.service.update_access(self.user['id'],**params)
        def saved(_):
            self.on_saved(None); self.destroy()
        if self.normalize.get():
            def confirm(_reason,dialog):
                dialog.destroy(); self.request(operation,saved,self.save_button)
            return ConfirmationDialog(self,'Change legacy scope behavior','Own-ministry role capabilities will apply to the selected scopes, replacing their previous per-attendance restrictions.',confirm)
        self.request(operation,saved,self.save_button)


class PasswordResetDialog(AdminDialog):
    def __init__(self,master,service,user,on_saved):
        super().__init__(master,'Reset password',user['full_name'],width=620,height=540)
        self.service,self.user,self.on_saved=service,user,on_saved
        details(self.content,'Set or generate a temporary password. The user must change it at the next sign-in. Account status and authenticator enrollment are managed separately.')
        self.password=self.entry('Temporary password *',secret=True)
        self.confirm=self.entry('Confirm temporary password *',secret=True)
        self.generated=ctk.StringVar(master=self,value='')
        ActionButton(self.content,'Generate temporary password',self.generate,width=235).pack(anchor='w',padx=16,pady=14)
        label(self.content,'',textvariable=self.generated,wraplength=500).pack(fill='x',padx=16)
        details(self.content,'Share the temporary password privately. It is displayed only during this reset and is never recorded in audit history.')
        self.save_button=ActionButton(self.footer,'Reset password',self.save,'primary',width=150)
        self.save_button.pack(side='right',padx=18,pady=14)

    def generate(self):
        chars=[secrets.choice(string.ascii_uppercase),secrets.choice(string.ascii_lowercase),secrets.choice(string.digits),secrets.choice('!@#$%&*')]
        chars += [secrets.choice(string.ascii_letters+string.digits+'!@#$%&*') for _ in range(12)]
        secrets.SystemRandom().shuffle(chars)
        password=''.join(chars)
        for entry in (self.password,self.confirm): entry.delete(0,'end'); entry.insert(0,password)
        self.generated.set('Temporary password: '+password)

    def save(self):
        password,confirm=self.password.get(),self.confirm.get()
        def saved(_):
            self.generated.set(''); self.password.delete(0,'end'); self.confirm.delete(0,'end')
            self.on_saved(None); self.destroy()
        self.request(lambda:self.service.reset_password(self.user['id'],password,confirm),saved,self.save_button)


class UserProfileDialog(AdminDialog):
    def __init__(self,master,service,user,permissions,on_saved):
        super().__init__(master,'User profile',user['full_name'],width=800,height=730)
        self.service,self.user,self.permissions,self.on_saved=service,user,set(permissions),on_saved
        Avatar(self.header,user['full_name'],user.get('photo_path'),48).pack(side='right',padx=16,pady=8)
        heading(self.content,'Account')
        details(self.content,f"{user['username']} · {user['email'] or 'No email'}\n{user.get('phone') or 'No phone'}\nCreated {timestamp(user['created_at'])}\nLast login {timestamp(user['last_login_at'])}")
        StatusBadge(self.content,user['status']).pack(anchor='w',padx=16)
        heading(self.content,'Member link')
        details(self.content,user['member']['full_name']+' · '+user['member']['member_no'] if user['member'] else 'No member linked')
        heading(self.content,'Software roles')
        details(self.content,', '.join(r['name']+(' (inactive)' if not r['is_active'] else '') for r in user['roles']) or 'No roles assigned')
        heading(self.content,'Ministry scopes')
        scope_lines=[]
        for scope in user['scopes']:
            text=scope['name']+(' · inactive ministry' if not scope['is_active'] else '')
            if scope.get('legacy_attendance_limits'):
                allowed=', '.join(name.title() for name,value in (scope.get('legacy_limits') or {}).items() if value) or 'None'
                text+='\nLegacy attendance capabilities allowed: '+allowed
            scope_lines.append(text)
        details(self.content,'\n'.join(scope_lines) or 'No ministry scopes. Global permissions do not require scopes.')
        details(self.content,'Global permissions apply church-wide; own-ministry permissions apply within the listed active scopes.')
        heading(self.content,'Authenticator and security')
        details(self.content,f"Authenticator: {'Enabled' if user['totp_enabled'] else 'Not configured'}\nFailed login attempts: {user['failed_login_attempts']}\nLocked until: {timestamp(user['locked_until'])}\nPassword change required: {'Yes' if user['require_password_change'] else 'No'}")
        actions=ctk.CTkFrame(self.content,fg_color='transparent')
        actions.pack(fill='x',padx=12,pady=10)
        actions.grid_columnconfigure((0,1),weight=1)
        choices=[]
        if 'USER_EDIT' in self.permissions: choices.append(('Edit profile',lambda:UserFormDialog(self,service,self.changed,user)))
        if self.permissions.intersection({'ROLE_ASSIGN','USER_SCOPE_MANAGE'}): choices.append(('Edit access',lambda:UserAccessDialog(self,service,user,self.changed,self.permissions)))
        if 'USER_RESET_PASSWORD' in self.permissions: choices.append(('Reset password',lambda:PasswordResetDialog(self,service,user,self.changed)))
        if 'USER_UNLOCK' in self.permissions and (user['status']=='LOCKED' or user['failed_login_attempts']): choices.append(('Unlock account',lambda:self.confirm('Unlock account','Clear the login lock and failed attempts.',lambda:service.unlock(user['id']))))
        if 'USER_RESET_TOTP' in self.permissions and user['totp_enabled']: choices.append(('Reset authenticator',lambda:self.confirm('Reset authenticator','Existing codes will stop working. The user must enroll a new authenticator after signing in with a password.',lambda:service.reset_totp(user['id']))))
        if 'USER_DEACTIVATE' in self.permissions and user['status'] not in ('INACTIVE','SUSPENDED'): choices.append(('Deactivate user',lambda:self.confirm('Deactivate user','Prevent future sign-in while retaining historical records and church positions.',lambda:service.set_status(user['id'],'INACTIVE'))))
        if 'USER_LOCK' in self.permissions and user['status']=='ACTIVE': choices.append(('Lock account',lambda:self.confirm('Lock account','Prevent sign-in until an authorized administrator unlocks the account.',lambda:service.set_status(user['id'],'LOCKED'))))
        if 'USER_EDIT' in self.permissions and user['status'] in ('INACTIVE','SUSPENDED'): choices.append(('Activate user',lambda:self.confirm('Activate user','Restore sign-in using the configured software roles and scopes.',lambda:service.set_status(user['id'],'ACTIVE'))))
        for index,(title,command) in enumerate(choices): ActionButton(actions,title,command,width=160).grid(row=index//2,column=index%2,sticky='ew',padx=4,pady=4)
        heading(self.content,'Effective permissions')
        details(self.content,'\n'.join(user['effective_permissions']) or 'No effective permissions. Account access is disabled, a password change is pending, or no active role grants are assigned.')
        if user['configured_permissions']!=user['effective_permissions']:
            heading(self.content,'Configured permissions after account recovery')
            details(self.content,'\n'.join(user['configured_permissions']) or 'None')
        self.cancel_button.configure(text='Close')

    def changed(self,result):
        self.on_saved(result)
        self.destroy()

    def confirm(self,title,text,operation):
        def confirmed(_reason,dialog):
            loader=AsyncLoader(dialog)
            dialog.confirm_button.configure(state='disabled')
            def saved(_): dialog.destroy(); self.changed(None)
            def failed(error):
                dialog.confirm_button.configure(state='normal'); dialog.error_var.set(str(error) if isinstance(error,(AdministrationError,AuthorizationDenied)) else 'Unable to complete this change.')
            loader.submit('security',operation,saved,failed)
        return ConfirmationDialog(self,title,text,confirmed)
