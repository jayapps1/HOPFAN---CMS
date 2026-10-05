"""Modern member form with a scrolling body and persistent save/cancel footer."""
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog
import customtkinter as ctk
from src.services.member_service import MemberServiceError
from src.ui import theme
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.date_picker import DatePicker, DatePickerDialog, display_date, parse_date
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
        self.ministry_buttons = {}
        self.baptized_var = ctk.BooleanVar(master=self, value=bool(member.get('baptized', False) if member else False))
        self.content.grid_columnconfigure((0,1), weight=1, uniform='fields')
        photo = AppCard(self.content)
        photo.grid(row=0,column=0,columnspan=2,sticky='ew',padx=12,pady=12)
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
        self.entry('first_name','First name *',1,0)
        self.entry('last_name','Last name *',1,1)
        self.entry('middle_name','Middle name',2,0)
        self.combo('gender','Gender',2,1,['Unspecified','Male','Female'])
        self.date_field('date_of_birth','Date of birth',3,0)
        self.combo('marital_status','Marital status',3,1,['Unspecified','Single','Married','Divorced','Widowed'])
        self.entry('phone','Phone',4,0)
        self.entry('alternate_phone','Alternate phone',4,1)
        self.entry('email','Email',5,0)
        self.entry('occupation','Occupation',5,1)
        self.entry('address','Address',6,0,span=2)
        self.date_field('date_joined','Joined church',7,0)
        self.combo('status','Membership status',7,1,['Active','Inactive','Transferred','Deceased'])
        baptized = self.shell('Baptism',8,0)
        ctk.CTkSwitch(baptized,text='Baptized',variable=self.baptized_var, font=font(),text_color=theme.TEXT,
                      progress_color=theme.SECONDARY).pack(anchor='w',pady=8)
        self.date_field('baptism_date','Baptism date',8,1)
        self.ministry_shell = self.shell('Ministry participation',9,0,span=2)
        self.ministry_notice = label(self.ministry_shell,'Loading ministries…',12,muted=True)
        self.ministry_notice.pack(anchor='w')
        self.save_button = ActionButton(self.footer,'Save member',self.save,'primary',width=140)
        self.save_button.pack(side='right',padx=18,pady=14)
        self.loader.submit('ministries',service.list_ministries,self.show_ministries,lambda error:self.error_var.set(str(error)))
        self.bind('<Control-s>',lambda _event:self.save())

    def shell(self,title,row,column,span=1):
        frame=ctk.CTkFrame(self.content,fg_color='transparent')
        frame.grid(row=row,column=column,columnspan=span,sticky='ew',padx=12,pady=8)
        label(frame,title,12,True).pack(anchor='w',pady=(0,4))
        return frame

    def variable(self,key):
        self.variables[key]=ctk.StringVar(master=self,value=self.member.get(key,'') if self.member else '')
        return self.variables[key]

    def entry(self,key,title,row,column,span=1):
        ModernEntry(self.shell(title,row,column,span),textvariable=self.variable(key)).pack(fill='x')

    def combo(self,key,title,row,column,options):
        variable=self.variable(key)
        variable.set(variable.get().replace('_',' ').title() or options[0])
        control=ModernComboBox(self.shell(title,row,column),options,variable=variable)
        control.set(self.member.get(key,'').replace('_',' ').title() if self.member and self.member.get(key) else options[0])
        control.pack(fill='x')

    def date_field(self,key,title,row,column):
        variable=self.variable(key)
        variable.set(display_date(variable.get()))
        DatePicker(self.shell(title,row,column),variable=variable).pack(fill='x')

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
        self.ministry_notice.configure(text='Select the ministries this member participates in.' if ministries else 'No active ministries available.')
        for index,ministry in enumerate(ministries):
            button=ActionButton(self.ministry_shell,'',width=220)
            button.pack(anchor='w',pady=4)
            button.ministry=ministry
            button.configure(command=lambda b=button:self.toggle_ministry(b))
            self.ministry_buttons[ministry['id']]=button
            self.style_ministry(button)

    def style_ministry(self,button):
        selected=button.ministry['id'] in self.selected_ministries
        button.configure(text=('Selected · ' if selected else 'Select · ')+button.ministry['name'],
            fg_color=theme.SECONDARY if selected else theme.SURFACE_ALT,
            text_color='#FFFFFF' if selected else theme.TEXT,
            hover_color=theme.SECONDARY_HOVER if selected else theme.BORDER)

    def toggle_ministry(self,button):
        self.selected_ministries.symmetric_difference_update({button.ministry['id']})
        self.style_ministry(button)

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
            for key in ('date_of_birth','date_joined','baptism_date'):
                data[key]=self.storage_date(data[key])
            for key in ('gender','marital_status'):
                data[key]='' if data[key]=='Unspecified' else data[key].upper()
            data['status']=data['status'].upper()
            data['baptized']=self.baptized_var.get()
            if not data['baptized']:
                data['baptism_date']=''
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
