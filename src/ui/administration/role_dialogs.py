"""Grouped permission selection for custom and established software roles."""
import customtkinter as ctk
from src.ui import theme
from src.ui.components.modern import ActionButton, AppCard, ConfirmationDialog, font, label
from src.ui.components.async_loader import AsyncLoader
from src.ui.administration.dialogs import AdminDialog, heading, details
from src.services.administration_base import AdministrationError
from src.services.authorization_service import AuthorizationDenied


class RoleFormDialog(AdminDialog):
    def __init__(self,master,service,on_saved,role=None):
        super().__init__(master,'Edit role' if role else 'Create role','Select the capabilities this software role grants.',width=800,height=740)
        self.service,self.role,self.on_saved=service,role,on_saved
        self.name=self.entry('Role name *',role['name'] if role else '')
        self.code=self.entry('Role code *',role['code'] if role else '')
        if role and role['is_system']: self.code.configure(state='disabled')
        heading(self.content,'Description')
        self.description=ctk.CTkTextbox(self.content,height=80,fg_color=theme.INPUT,text_color=theme.TEXT,font=font(),border_width=1,border_color=theme.BORDER)
        self.description.pack(fill='x',padx=16)
        self.description.insert('1.0',role['description'] if role else '')
        details(self.content,'You may grant only permissions you hold. Church positions are unaffected by software role changes.')
        self.groups=ctk.CTkFrame(self.content,fg_color='transparent')
        self.groups.pack(fill='x',padx=16,pady=10)
        self.variables={}
        self.save_button=ActionButton(self.footer,'Save role',self.save,'primary',width=130)
        self.save_button.pack(side='right',padx=18,pady=14)
        self.save_button.configure(state='disabled')
        self.loader.submit('permissions',service.permission_catalogue,self.render_permissions,lambda e:self.error_var.set(str(e)))

    def render_permissions(self,permissions):
        selected=set(self.role['permission_ids']) if self.role else set()
        modules={}
        for permission in permissions: modules.setdefault(permission['module'],[]).append(permission)
        for module,rows in modules.items():
            group=AppCard(self.groups)
            group.pack(fill='x',pady=5)
            heading(group,module)
            for p in rows:
                var=ctk.BooleanVar(master=self,value=p['id'] in selected)
                self.variables[p['id']]=var
                checkbox=ctk.CTkCheckBox(group,text=p['name']+(' (inactive)' if not p['is_active'] else ''),variable=var,
                    text_color=theme.TEXT,font=font(12),state='normal' if p['assignable'] and p['is_active'] else 'disabled')
                checkbox.pack(anchor='w',padx=16,pady=5)
            label(group,'',height=4).pack()
        self.save_button.configure(state='normal')

    def save(self):
        data=dict(name=self.name.get(),code=self.code.get(),description=self.description.get('1.0','end').strip())
        ids=[pid for pid,var in self.variables.items() if var.get()]
        operation=(lambda:self.service.update_role(self.role['id'],data,ids,self.role['updated_at'])) if self.role else (lambda:self.service.create_role(data,ids))
        def saved(result): self.on_saved(result); self.destroy()
        self.request(operation,saved,self.save_button)


class RoleProfileDialog(AdminDialog):
    def __init__(self,master,service,role,permissions,on_saved):
        super().__init__(master,'Role profile',role['name'],width=740,height=690)
        self.cancel_button.configure(text='Close')
        self.service,self.role,self.permissions,self.on_saved=service,role,set(permissions),on_saved
        for title,value in (('Role code',role['code']),('Description',role['description'] or 'No description'),
            ('Status','Active' if role['is_active'] else 'Inactive'),('System role','Yes' if role['is_system'] else 'No'),
            ('Assigned users',str(role['user_count']))): heading(self.content,title); details(self.content,value)
        modules={}
        for permission in role['permissions']: modules.setdefault(permission['module'],[]).append(permission['name']+(' (inactive)' if not permission['is_active'] else ''))
        for module,rows in modules.items(): heading(self.content,module+' permissions'); details(self.content,'\n'.join(rows))
        if not modules: details(self.content,'This role grants no permissions.')
        if 'ROLE_EDIT' in self.permissions:
            ActionButton(self.footer,'Edit role',lambda:RoleFormDialog(self,service,self.changed,role),'primary',width=120).pack(side='right',padx=18,pady=14)
        if 'ROLE_ARCHIVE' in self.permissions and not role['is_system']:
            ActionButton(self.content,'Deactivate role' if role['is_active'] else 'Activate role',self.change_status,width=160).pack(anchor='w',padx=16,pady=14)

    def changed(self,result): self.on_saved(result); self.destroy()

    def change_status(self):
        active=not self.role['is_active']
        def confirmed(_reason,dialog):
            loader=AsyncLoader(dialog)
            dialog.confirm_button.configure(state='disabled')
            def done(_): dialog.destroy(); self.changed(None)
            def fail(error):
                dialog.confirm_button.configure(state='normal'); dialog.error_var.set(str(error) if isinstance(error,(AdministrationError,AuthorizationDenied)) else 'Unable to change role status.')
            loader.submit('status',lambda:self.service.set_active(self.role['id'],active),done,fail)
        return ConfirmationDialog(self,'Activate role' if active else 'Deactivate role',
            'Assigned user accounts and historical records remain. Effective permissions follow the active roles.',confirmed)
