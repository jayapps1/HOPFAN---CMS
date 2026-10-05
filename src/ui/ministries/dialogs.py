"""Fixed-footer ministry forms and explicit lifecycle confirmations."""
import re
import unicodedata
import customtkinter as ctk
from src.services.ministry_service import CATEGORIES, MinistryServiceError
from src.ui import theme
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.modern import ActionButton, FixedFooterDialog, ModernEntry, label, font
from src.ui.components.modern_select import ModernSelect


def suggest_code(name):
    text=unicodedata.normalize('NFKD',name).encode('ascii','ignore').decode().upper()
    text=re.sub(r'\s+(MINISTRY|FELLOWSHIP|DEPARTMENT|UNIT)$','',text.strip())
    return re.sub(r'[^A-Z0-9]+','_',text).strip('_')[:60]


class MinistryFormDialog(FixedFooterDialog):
    def __init__(self,master,service,on_saved,ministry=None,capabilities=None):
        super().__init__(master,'Edit ministry' if ministry else 'Add ministry',
            'A stable code keeps church records connected when the display name changes.',width=720,height=720)
        self.service,self.on_saved,self.ministry=service,on_saved,ministry
        self.capabilities=capabilities or {}
        self.loader=AsyncLoader(self)
        self.name_var=ctk.StringVar(master=self,value=ministry['name'] if ministry else '')
        self.code_var=ctk.StringVar(master=self,value=ministry['code'] if ministry else '')
        label(self.content,'Ministry name *',12,True).pack(anchor='w',padx=16,pady=(16,6))
        self.name_entry=ModernEntry(self.content,textvariable=self.name_var,height=46,corner_radius=11)
        self.name_entry.pack(fill='x',padx=16)
        label(self.content,'Code *',12,True).pack(anchor='w',padx=16,pady=(16,6))
        self.code_entry=ModernEntry(self.content,textvariable=self.code_var,height=46,corner_radius=11)
        self.code_entry.pack(fill='x',padx=16)
        self.code_locked=bool(ministry and ministry.get('in_use'))
        if self.code_locked:
            self.code_entry.configure(state='disabled',fg_color=theme.DISABLED_INPUT,text_color=theme.TEXT_MUTED)
            label(self.content,'Code is locked because this ministry has related church records.',11,muted=True,
                wraplength=570,anchor='w').pack(fill='x',padx=16,pady=(6,0))
        else:
            self.suggestion=ActionButton(self.content,'Use suggested code',lambda:self.code_var.set(suggest_code(self.name_var.get())),width=200)
            self.suggestion.pack(anchor='w',padx=16,pady=(6,0))
            self.name_trace=self.name_var.trace_add('write',self.update_suggestion)
            self.update_suggestion()
        label(self.content,'Category *',12,True).pack(anchor='w',padx=16,pady=(16,6))
        self.category=ModernSelect(self.content,[value.title() for value in CATEGORIES])
        self.category.set(ministry['category'].title() if ministry else 'Ministry')
        self.category.pack(fill='x',padx=16)
        label(self.content,'Description',12,True).pack(anchor='w',padx=16,pady=(16,6))
        self.description=ctk.CTkTextbox(self.content,height=110,corner_radius=11,border_width=1,
            fg_color=theme.INPUT,border_color=theme.BORDER,text_color=theme.TEXT,font=font())
        self.description.pack(fill='x',padx=16)
        if ministry:
            self.description.insert('1.0',ministry.get('description') or '')
        label(self.content,'Status',12,True).pack(anchor='w',padx=16,pady=(16,6))
        options=['Archived'] if ministry and ministry['status']=='ARCHIVED' else ['Active','Inactive']
        self.status=ModernSelect(self.content,options)
        self.status.set(ministry['status'].title() if ministry else 'Active')
        if ministry and (ministry['status']=='ARCHIVED' or not self.capabilities.get('deactivate')):
            self.status.configure(state='disabled')
        self.status.pack(fill='x',padx=16,pady=(0,18))
        self.save_button=ActionButton(self.footer,'Save ministry',self.save,'primary',width=150)
        self.save_button.pack(side='right',padx=18,pady=14)

    def update_suggestion(self,*_args):
        code=suggest_code(self.name_var.get())
        self.suggestion.configure(text='Use '+code if code else 'Use suggested code',state='normal' if code else 'disabled')

    def save(self):
        if self.save_button.cget('state')=='disabled':
            return
        data=dict(name=self.name_var.get(),code=self.code_var.get(),category=self.category.get().upper(),
            description=self.description.get('1.0','end-1c'),status=self.status.get().upper())
        try:
            self.service._validate(data)
        except MinistryServiceError as exc:
            self.error_var.set(str(exc))
            return
        if self.ministry and data['status']!=self.ministry['status']:
            action='deactivate' if data['status']=='INACTIVE' else 'activate'
            def confirmed(_reason,dialog):
                dialog.destroy()
                self.write(data)
            confirm=LifecycleConfirmation(self,action,self.ministry,confirmed)
            return confirm
        self.write(data)

    def write(self,data):
        self.error_var.set('')
        self.save_button.configure(state='disabled',text='Saving…')
        def operation():
            if self.ministry:
                return self.service.update_ministry(self.ministry['id'],data,expected_updated_at=self.ministry['updated_at'])
            return self.service.create_ministry(data)
        self.loader.submit('save',operation,self.saved,self.failed)

    def saved(self,_result):
        self.on_saved(_result)
        self.destroy()

    def failed(self,error):
        self.error_var.set(str(error))
        self.save_button.configure(state='normal',text='Save ministry')

    def destroy(self):
        if hasattr(self,'name_trace'):
            self.name_var.trace_remove('write',self.name_trace)
        super().destroy()


class LifecycleConfirmation(FixedFooterDialog):
    def __init__(self,master,action,ministry,on_confirm):
        titles={'deactivate':'Deactivate ministry','activate':'Activate ministry','archive':'Archive ministry',
            'restore':'Restore ministry','delete_unused':'Permanently delete ministry'}
        details={
            'deactivate':'It will leave active assignment and new-attendance selectors. Existing participation and church history will remain.',
            'activate':'It will become available for new member assignments and permitted attendance creation.',
            'archive':'It will leave normal active selectors. Historical church records and relationships will remain available.',
            'restore':'The same ministry and its church records will be restored. Choose its availability below.',
            'delete_unused':'This permanently removes an unused ministry. The service will reject deletion if any church records are linked. Archive is the preferred option.'}
        super().__init__(master,titles[action],ministry['name'],width=620,height=480)
        self.on_confirm=on_confirm
        self.action=action
        label(self.content,details[action],13,wraplength=510,justify='left',anchor='w').pack(fill='x',padx=16,pady=20)
        self.restore_status=None
        if action=='restore':
            label(self.content,'Restore as',12,True).pack(anchor='w',padx=16,pady=(0,6))
            self.restore_status=ModernSelect(self.content,['Inactive','Active'])
            self.restore_status.pack(fill='x',padx=16,pady=(0,16))
        if action=='delete_unused':
            label(self.content,'Type the ministry code to confirm permanent deletion:',12,True,
                wraplength=510,anchor='w').pack(fill='x',padx=16,pady=(0,6))
            self.code_confirm=ModernEntry(self.content,placeholder_text=ministry['code'],height=46,corner_radius=11)
            self.code_confirm.pack(fill='x',padx=16)
        self.code=ministry['code']
        self.confirm_button=ActionButton(self.footer,'Delete permanently' if action=='delete_unused' else titles[action],
            self.confirm,'danger' if action=='delete_unused' else 'primary',width=180)
        self.confirm_button.pack(side='right',padx=18,pady=14)

    def confirm(self):
        if self.confirm_button.cget('state')=='disabled':
            return
        if self.action=='delete_unused' and self.code_confirm.get().strip()!=self.code:
            self.error_var.set('Enter the exact ministry code to confirm.')
            return
        self.on_confirm('',self)

    def destroy(self):
        parent=self.master.winfo_toplevel()
        super().destroy()
        if parent.winfo_exists() and isinstance(parent,ctk.CTkToplevel):
            parent.grab_set()
