"""Modern member form with a scrolling body and persistent save/cancel footer."""
from pathlib import Path
from tkinter import filedialog
import customtkinter as ctk
from src.services.member_service import MemberServiceError
from src.ui import theme
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.date_picker import DatePicker, display_date, parse_date
from src.ui.components.multi_select_dropdown import MultiSelectDropdown
from src.ui.components.modern import ActionButton, Avatar, AppCard, FixedFooterDialog, ModernComboBox, ModernEntry, font, label


class MemberFormDialog(FixedFooterDialog):
    def __init__(self, master, service, on_saved, member=None):
        super().__init__(master, 'Edit member' if member else 'Add member',
            'Personal information, contact details, church records and ministries.', width=880, height=740)
        self.service, self.on_saved, self.member = service, on_saved, member
        self.loader = AsyncLoader(self)
        self.variables = {}
        self.selected_ministries = set(member.get('ministry_ids', []) if member else [])
        self.photo_source = None
        self.baptized_var = ctk.BooleanVar(master=self, value=bool(member.get('baptized', False) if member else False))
        self.content.grid_columnconfigure((0,1), weight=1, uniform='fields')
        self.section('Profile', 0)
        photo = AppCard(self.content)
        photo.grid(row=1,column=0,columnspan=2,sticky='ew',padx=12,pady=(4,12))
        name = member['full_name'] if member else 'New member'
        self.avatar = Avatar(photo, name, member.get('photo_path','') if member else '', size=56)
        self.avatar.pack(side='left', padx=16,pady=14)
        info = ctk.CTkFrame(photo,fg_color='transparent')
        self.photo_info = info
        info.pack(side='left',fill='x',expand=True)
        label(info, member['member_no'] if member else 'Member number assigned on save', 13, True).pack(anchor='w')
        self.photo_label = label(info, 'Profile photo is optional', 12, muted=True)
        self.photo_label.pack(anchor='w')
        ActionButton(photo,'Choose photo',self.choose_photo,width=110).pack(side='right',padx=16)
        self.section('Personal information', 2)
        self.entry('first_name','First name *',3,0)
        self.entry('last_name','Last name *',3,1)
        self.entry('middle_name','Middle name',4,0)
        self.combo('gender','Gender',4,1,['Unspecified','Male','Female'])
        self.date_field('date_of_birth','Date of birth',5,0)
        self.combo('marital_status','Marital status',5,1,['Unspecified','Single','Married','Divorced','Widowed'])
        self.entry('occupation','Occupation',6,0,span=2)
        self.section('Contact information', 7)
        self.entry('phone','Phone',8,0)
        self.entry('alternate_phone','Alternate phone',8,1)
        self.entry('email','Email',9,0,span=2)
        self.entry('address','Address',10,0,span=2)
        self.section('Church information', 11)
        self.date_field('date_joined','Joined church',12,0)
        self.combo('status','Membership status',12,1,['Active','Inactive','Transferred','Deceased'])
        baptized = self.shell('Baptism',13,0)
        self.baptism_switch = ctk.CTkSwitch(baptized,text='Not baptized',variable=self.baptized_var,
            font=font(), text_color=theme.TEXT, progress_color=theme.SECONDARY)
        self.baptism_switch.pack(anchor='w',pady=12)
        self.baptism_date = self.date_field('baptism_date','Baptism date',13,1)
        self.baptism_trace = self.baptized_var.trace_add('write', self.sync_baptism)
        self.sync_baptism()
        self.section('Ministry participation', 14)
        self.ministry_shell = ctk.CTkFrame(self.content, fg_color='transparent')
        self.ministry_shell.grid(row=15, column=0, columnspan=2, sticky='ew', padx=12, pady=(4,16))
        self.ministry_select = MultiSelectDropdown(self.ministry_shell, selected_ids=self.selected_ministries,
            command=self.ministries_changed, state='disabled')
        self.ministry_select.pack(fill='x')
        self.ministry_notice = label(self.ministry_shell,'Loading ministries…',12,muted=True,anchor='w',justify='left')
        self.ministry_notice.pack(anchor='w', fill='x', pady=(6,0))
        self.ministry_notice.bind('<Configure>', lambda event:self.ministry_notice.configure(wraplength=max(160,event.width-8)))
        self.save_button = ActionButton(self.footer,'Save member',self.save,'primary',width=140)
        self.save_button.pack(side='right',padx=18,pady=14)
        self.loader.submit('ministries',service.list_ministries,self.show_ministries,lambda error:self.error_var.set(str(error)))
        self.bind('<Control-s>',lambda _event:self.save())

    def section(self, title, row):
        label(self.content, title, 14, True).grid(row=row, column=0, columnspan=2,
            sticky='w', padx=12, pady=(16,4))

    def shell(self,title,row,column,span=1):
        frame=ctk.CTkFrame(self.content,fg_color='transparent')
        frame.grid(row=row,column=column,columnspan=span,sticky='ew',padx=12,pady=8)
        label(frame,title,12,True).pack(anchor='w',pady=(0,4))
        return frame

    def variable(self,key):
        self.variables[key]=ctk.StringVar(master=self,value=self.member.get(key,'') if self.member else '')
        return self.variables[key]

    def entry(self,key,title,row,column,span=1):
        ModernEntry(self.shell(title,row,column,span),textvariable=self.variable(key),height=46,corner_radius=11).pack(fill='x')

    def combo(self,key,title,row,column,options):
        variable=self.variable(key)
        variable.set(variable.get().replace('_',' ').title() or options[0])
        control=ModernComboBox(self.shell(title,row,column),options,variable=variable)
        control.set(self.member.get(key,'').replace('_',' ').title() if self.member and self.member.get(key) else options[0])
        control.pack(fill='x')

    def date_field(self,key,title,row,column):
        variable=self.variable(key)
        variable.set(display_date(variable.get()))
        control = DatePicker(self.shell(title,row,column),variable=variable,height=46)
        control.pack(fill='x')
        return control

    def sync_baptism(self, *_args):
        baptized = self.baptized_var.get()
        if not baptized:
            self.variables['baptism_date'].set('')
        self.baptism_date.set_enabled(baptized)
        self.baptism_switch.configure(text='Baptized' if baptized else 'Not baptized')

    @staticmethod
    def display_date(value):
        return display_date(value)

    @staticmethod
    def storage_date(value):
        if not str(value or '').strip():
            return ''
        try:
            return parse_date(value).isoformat()
        except ValueError as exc:
            raise MemberServiceError(str(exc)) from exc

    def show_ministries(self,ministries):
        self.ministry_select.set_options(ministries)
        self.ministry_select.configure(state='readonly' if ministries or self.selected_ministries else 'disabled')
        self.ministries_changed(self.ministry_select.get_selected_ids())

    def ministries_changed(self, ids):
        self.selected_ministries = set(ids)
        names = self.ministry_select.get_selected_names()
        unavailable = len(self.selected_ministries)-len(names)
        text = ', '.join(names)
        if unavailable:
            text += (' · ' if text else '')+f'{unavailable} existing inactive selection(s) retained'
        self.ministry_notice.configure(text=text or ('Choose all ministries this member participates in.'
            if self.ministry_select.options else 'No active ministries available.'))

    def choose_photo(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[('Member photo','*.jpg *.jpeg *.png *.webp')])
        if path:
            self.photo_source=path
            self.avatar.destroy()
            self.avatar = Avatar(self.photo_info.master, self.member['full_name'] if self.member else 'New member', path, size=56)
            self.avatar.pack(side='left', before=self.photo_info, padx=16, pady=14)
            self.photo_label.configure(text=Path(path).name)

    def save(self):
        if self.save_button.cget('state')=='disabled':
            return
        try:
            data={key:var.get().strip() for key,var in self.variables.items()}
            if not data['first_name'] or not data['last_name']:
                raise MemberServiceError('First and last names are required.')
            for key in ('date_of_birth','date_joined'):
                data[key]=self.storage_date(data[key])
            for key in ('gender','marital_status'):
                data[key]='' if data[key]=='Unspecified' else data[key].upper()
            data['status']=data['status'].upper()
            data['baptized']=self.baptized_var.get()
            data['baptism_date']=(self.storage_date(data['baptism_date']) or None) if data['baptized'] else None
            email=data['email']
            if email and ('@' not in email or '.' not in email.split('@')[-1]):
                raise MemberServiceError('Enter a valid email address.')
        except MemberServiceError as exc:
            self.error_var.set(str(exc));return
        # Keep the existing primary membership first when it remains selected.
        original=self.member.get('ministry_ids',[]) if self.member else []
        ids=[mid for mid in original if mid in self.selected_ministries]+sorted(self.selected_ministries-set(original))
        photo=self.photo_source
        def write():
            saved=self.service.update_member(self.member['id'],data,ids) if self.member else self.service.create_member(data,ids)
            if photo:
                try:
                    self.service.set_photo(saved['id'],photo)
                except Exception as exc:
                    # The profile transaction has committed; a retry must use this member.
                    return saved, str(exc) if isinstance(exc, MemberServiceError) else 'The photo could not be saved.'
            return saved, None
        self.save_button.configure(text='Saving…',state='disabled')
        self.loader.submit('save',write,self.saved,self.failed)

    def saved(self,result):
        saved, photo_error = result
        self.member = saved
        self.on_saved()
        if photo_error:
            self.error_var.set('Member saved. Photo: '+photo_error)
            self.save_button.configure(text='Retry save', state='normal')
            return
        self.destroy()

    def failed(self,error):
        self.error_var.set(str(error))
        self.save_button.configure(text='Save member',state='normal')

    def destroy(self):
        self.baptized_var.trace_remove('write', self.baptism_trace)
        super().destroy()
