"""Sunday School forms, paginated master-member search and confirmations."""
from datetime import date
import customtkinter as ctk
from src.ui import theme
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.date_picker import DatePicker,display_date
from src.ui.components.modern import ActionButton,AppCard,Avatar,ConfirmationDialog,FixedFooterDialog,ModernEntry,font,label
from src.ui.components.modern_select import ModernSelect
from src.ui.components.multi_select_dropdown import MultiSelectDropdown
from src.ui.components.search_field import SearchField
from src.ui.members.member_form_dialog import MemberFormDialog
from src.ui.ministries.dialogs import suggest_code
from src.security.sunday_school_permissions import TEACHER_ROLES,GUARDIAN_RELATIONSHIPS
from src.services.sunday_school_base import AgeRangeWarning,EnrollmentMoveRequired


def heading(parent,text): label(parent,text,12,True,anchor='w').pack(fill='x',padx=16,pady=(12,5))
def entry(parent,title,value=''):
    heading(parent,title); widget=ModernEntry(parent,height=40); widget.pack(fill='x',padx=16); widget.insert(0,'' if value is None else str(value)); return widget
def textbox(parent,title,value='',height=90):
    heading(parent,title); widget=ctk.CTkTextbox(parent,height=height,corner_radius=10,fg_color=theme.INPUT,text_color=theme.TEXT,border_color=theme.BORDER,border_width=1,font=font())
    widget.pack(fill='x',padx=16,pady=(0,8)); widget.insert('1.0',value or ''); return widget
def date_field(parent,title,value=None):
    heading(parent,title); widget=DatePicker(parent,initial_date=value,height=40); widget.pack(fill='x',padx=16); return widget


class SchoolDialog(FixedFooterDialog):
    def __init__(self,master,title,subtitle='',**kwargs):
        super().__init__(master,title,subtitle,**kwargs); self.loader=AsyncLoader(self)
    def run(self,operation):
        if self.save_button.cget('state')=='disabled': return
        self.error_var.set(''); self.save_button.configure(state='disabled')
        self.loader.submit('save',operation,self.saved,self.failed)
    def saved(self,result): self.on_saved(); self.destroy()
    def failed(self,error): self.error_var.set(str(error)); self.save_button.configure(state='normal')
    def confirm(self,title,detail,operation):
        def confirmed(_reason,dialog): dialog.destroy(); self.grab_set(); operation()
        return ConfirmationDialog(self,title,detail,confirmed)
    def destroy(self):
        if not self.winfo_exists(): return
        parent=self.master.winfo_toplevel(); super().destroy()
        if parent.winfo_exists() and isinstance(parent,ctk.CTkToplevel): parent.grab_set()


class SchoolMemberPicker(SchoolDialog):
    PAGE_SIZE=20
    def __init__(self,master,service,on_selected,kind='student',student_member_id=None):
        super().__init__(master,'Choose existing member','Search name, member number or guardian phone.',width=760,height=700)
        self.service,self.on_selected,self.kind,self.student_member_id=service,on_selected,kind,student_member_id
        self.offset,self.total=0,0; self.cancel_button.configure(text='Close')
        self.search=SearchField(self.header,lambda:self.refresh(True),'Name, member number or contact phone'); self.search.pack(fill='x',padx=16,pady=10)
        self.notice=label(self.footer,'Loading members…',11,muted=True); self.notice.pack(side='left')
        self.next_button=ActionButton(self.footer,'Next',lambda:self.page(1),width=70); self.next_button.pack(side='right',padx=12)
        self.previous=ActionButton(self.footer,'Previous',lambda:self.page(-1),width=80); self.previous.pack(side='right',padx=6)
        self.refresh()
    def page(self,direction): self.offset=max(0,self.offset+direction*self.PAGE_SIZE); self.refresh()
    def refresh(self,reset=False):
        if reset:self.offset=0
        params=dict(search=self.search.get(),limit=self.PAGE_SIZE,offset=self.offset)
        operation=(lambda:self.service.guardian_candidates(self.student_member_id,**params)) if self.kind=='guardian' else \
            (lambda:self.service.candidate_teachers(**params)) if self.kind=='teacher' else (lambda:self.service.candidate_members(**params))
        self.loader.submit('members',operation,self.render,lambda error:self.error_var.set(str(error)))
    def render(self,page):
        self.total=page['total']
        for child in self.content.winfo_children(): child.destroy()
        self.notice.configure(text=f'{self.total} members · Page {self.offset//self.PAGE_SIZE+1}')
        self.previous.configure(state='normal' if self.offset else 'disabled'); self.next_button.configure(state='normal' if self.offset+len(page['rows'])<self.total else 'disabled')
        if not page['rows']: label(self.content,'No matching active members.',15,muted=True).pack(pady=25)
        for member in page['rows']:
            card=AppCard(self.content); card.member=member; card.pack(fill='x',padx=12,pady=4); card.grid_columnconfigure(1,weight=1)
            Avatar(card,member['full_name'],member['photo_path']).grid(row=0,column=0,rowspan=3,padx=12,pady=12)
            label(card,member['full_name'],14,True,anchor='w',width=1,wraplength=350).grid(row=0,column=1,sticky='ew',pady=(10,0))
            age=f"Age {member['age']}" if member.get('age') is not None else 'Age unavailable'
            label(card,member['member_no']+' · '+age,11,muted=True,anchor='w').grid(row=1,column=1,sticky='ew')
            household=(member.get('household') or {}).get('household_name')
            detail='Household contact' if member.get('same_household') else household or display_date(member.get('date_of_birth')) or 'No household recorded'
            label(card,detail,11,muted=True,anchor='w').grid(row=2,column=1,sticky='ew',pady=(0,10))
            card.select_button=ActionButton(card,'Select',lambda person=member:self.select(person),width=75); card.select_button.grid(row=0,column=2,rowspan=3,padx=12)
    def select(self,member): callback=self.on_selected; self.destroy(); callback(member)


class ClassFormDialog(SchoolDialog):
    def __init__(self,master,service,on_saved,school_class=None,capabilities=None):
        super().__init__(master,'Edit Sunday School class' if school_class else 'Add Sunday School class',width=730,height=740)
        self.service,self.on_saved,self.school_class,self.capabilities=service,on_saved,school_class,capabilities or {}
        data=school_class or {}; self.fields={}
        for key,title in (('name','Class name *'),('code','Code *')): self.fields[key]=entry(self.content,title,data.get(key,''))
        ActionButton(self.content,'Suggest code',self.suggest,width=125).pack(anchor='w',padx=16,pady=6)
        for key,title in (('minimum_age','Recommended minimum age'),('maximum_age','Recommended maximum age'),('room_location','Room / location'),
            ('capacity','Student capacity (blank for unlimited)'),('teacher_capacity','Teacher capacity (blank for unlimited)'),('sort_order','Display order')):
            self.fields[key]=entry(self.content,title,data.get(key,0 if key=='sort_order' else ''))
        self.description=textbox(self.content,'Description',data.get('description',''))
        heading(self.content,'Status'); self.status=ModernSelect(self.content,['Active','Inactive']); self.status.set(data.get('status','ACTIVE').title()); self.status.pack(fill='x',padx=16,pady=(0,14))
        if school_class and not self.capabilities.get('class_archive'): self.status.configure(state='disabled')
        self.save_button=ActionButton(self.footer,'Save class',self.save,'primary',width=150); self.save_button.pack(side='right',padx=16,pady=14)
    def suggest(self): self.fields['code'].delete(0,'end'); self.fields['code'].insert(0,suggest_code(self.fields['name'].get()))
    def save(self):
        data={key:widget.get() for key,widget in self.fields.items()}; data.update(description=self.description.get('1.0','end-1c'),status=self.status.get().upper())
        if self.school_class: self.run(lambda:self.service.update_class(self.school_class['id'],data,self.school_class['updated_at']))
        else: self.run(lambda:self.service.create_class(data))


class EnrollStudentDialog(SchoolDialog):
    def __init__(self,master,service,member_service,classes,capabilities,on_saved,student=None):
        super().__init__(master,'Move student' if student and student.get('enrollment_id') else 'Enroll Sunday School student',
            'Use an existing Member; class history is retained.',width=740,height=730)
        self.service,self.member_service,self.classes,self.capabilities,self.on_saved,self.student=service,member_service,classes,capabilities,on_saved,student
        self.member=student; self.age_override=False; self.person=AppCard(self.content); self.person.pack(fill='x',padx=16,pady=12); self.render_member()
        if not student and capabilities.get('register_member'):
            ActionButton(self.content,'Register new member',self.new_member,width=180).pack(anchor='w',padx=16,pady=6)
        heading(self.content,'Class'+(' *' if student and student.get('enrollment_id') else ' (optional during admission)'))
        self.class_map={row['name']:row['id'] for row in classes if row['status']=='ACTIVE'}
        values=list(self.class_map) if student and student.get('enrollment_id') else ['No class yet']+list(self.class_map)
        self.class_select=ModernSelect(self.content,values,placeholder='Configure an active class first'); self.class_select.pack(fill='x',padx=16)
        self.start=date_field(self.content,'Effective enrollment date *',date.today()); self.notes=textbox(self.content,'Enrollment notes')
        label(self.content,'Age ranges guide placement. An explicit override is required for an out-of-range student.',11,muted=True,wraplength=590,justify='left').pack(fill='x',padx=16,pady=8)
        self.save_button=ActionButton(self.footer,'Move student' if student and student.get('enrollment_id') else 'Enroll student',self.save,'primary',width=160)
        self.save_button.pack(side='right',padx=16,pady=14)
    def render_member(self):
        for child in self.person.winfo_children(): child.destroy()
        if self.member:
            Avatar(self.person,self.member['full_name'],self.member.get('photo_path','')).pack(side='left',padx=12,pady=12)
            label(self.person,self.member['full_name']+'\n'+self.member['member_no'],13,True,justify='left',wraplength=330).pack(side='left',pady=12)
        else: label(self.person,'Choose an existing Member.',12,muted=True).pack(side='left',padx=12,pady=16)
        if not self.student:
            ActionButton(self.person,'Search member',lambda:SchoolMemberPicker(self,self.service,self.selected),width=130).pack(side='right',padx=12,pady=12)
    def selected(self,member): self.member=member; self.age_override=False; self.render_member()
    def new_member(self):
        def created():
            if form.member:self.selected(form.member)
        form=MemberFormDialog(self,self.member_service,created)
        form.bind('<Destroy>',lambda event:self.grab_set() if event.widget==form and self.winfo_exists() else None,add='+'); return form
    def save(self):
        try:
            if not self.member: raise ValueError('Choose an existing Member.')
            selected=self.class_map.get(self.class_select.get()); start=self.start.get_date(); notes=self.notes.get('1.0','end-1c'); mid=self.member.get('member_id',self.member['id'])
            if self.student and self.student.get('enrollment_id'):
                if not selected: raise ValueError('Choose the destination class.')
                operation=lambda:self.service.move_student(self.student['enrollment_id'],selected,start,notes,self.age_override,self.student['enrollment_updated_at'])
            elif selected: operation=lambda:self.service.enroll_student(selected,mid,start,notes,self.age_override)
            else: operation=lambda:self.service.register_student(mid,start,notes)
        except Exception as error: self.error_var.set(str(error)); return
        self.run(operation)
    def failed(self,error):
        super().failed(error)
        if isinstance(error,AgeRangeWarning): return self.confirm('Override recommended age range',str(error),self.override_age)
        if isinstance(error,EnrollmentMoveRequired) and self.capabilities.get('student_move'):
            self.confirm('Move current enrollment',str(error)+' The old enrollment will remain historical.',lambda:self.confirm_move(error.current))
    def override_age(self): self.age_override=True; self.save()
    def confirm_move(self,current):
        self.student=dict(self.member,enrollment_id=current['id'],enrollment_updated_at=current['updated_at']); self.save()


class AssignTeacherDialog(SchoolDialog):
    def __init__(self,master,service,classes,on_saved,teacher=None):
        super().__init__(master,'End teaching assignment' if teacher else 'Assign Sunday School teacher',width=730,height=650)
        self.service,self.on_saved,self.teacher,self.member=service,on_saved,teacher,None
        if teacher:
            label(self.content,teacher['full_name']+' · '+teacher['class_name'],15,True).pack(anchor='w',padx=16,pady=16)
            self.effective=date_field(self.content,'End date *',date.today())
            label(self.content,'This ends the teaching assignment. Review account roles and class scopes separately.',12,muted=True,wraplength=550,justify='left').pack(fill='x',padx=16,pady=16)
        else:
            self.person=AppCard(self.content); self.person.pack(fill='x',padx=16,pady=12); self.render_member()
            heading(self.content,'Class *'); self.class_map={row['name']:row['id'] for row in classes if row['status']=='ACTIVE'}
            self.class_select=ModernSelect(self.content,list(self.class_map),placeholder='Configure an active class first'); self.class_select.pack(fill='x',padx=16)
            heading(self.content,'Teaching role'); self.role=ModernSelect(self.content,list(TEACHER_ROLES.values())); self.role.pack(fill='x',padx=16)
            self.effective=date_field(self.content,'Start date *',date.today())
            label(self.content,'Assigning a teacher does not create an account or grant software access.',12,muted=True,wraplength=560,justify='left').pack(fill='x',padx=16,pady=16)
        self.save_button=ActionButton(self.footer,'End assignment' if teacher else 'Assign teacher',self.save,'primary',width=165); self.save_button.pack(side='right',padx=16,pady=14)
    def render_member(self):
        for child in self.person.winfo_children():child.destroy()
        label(self.person,self.member['full_name'] if self.member else 'Choose an existing Member.',13,True).pack(side='left',padx=12,pady=16)
        ActionButton(self.person,'Search member',lambda:SchoolMemberPicker(self,self.service,self.selected,'teacher'),width=135).pack(side='right',padx=12,pady=12)
    def selected(self,member):self.member=member; self.render_member()
    def save(self):
        try:
            effective=self.effective.get_date()
            if self.teacher: operation=lambda:self.service.end_teacher_assignment(self.teacher['id'],effective,self.teacher['updated_at'])
            else:
                if not self.member or self.class_select.get() not in self.class_map:raise ValueError('Choose a teacher and active class.')
                mid=self.member['member_id']; cid=self.class_map[self.class_select.get()]; role=next(code for code,name in TEACHER_ROLES.items() if name==self.role.get())
                operation=lambda:self.service.assign_teacher(cid,mid,role,effective)
        except Exception as error:self.error_var.set(str(error));return
        self.run(operation)


class GuardianDialog(SchoolDialog):
    def __init__(self,master,service,student,on_saved,guardian=None):
        super().__init__(master,'Edit guardian contact' if guardian else 'Add guardian contact',student['full_name'],width=700,height=610)
        self.service,self.student,self.on_saved,self.member=service,student,on_saved,guardian
        self.person=AppCard(self.content);self.person.pack(fill='x',padx=16,pady=12);self.render_member()
        heading(self.content,'Relationship');self.relationship=ModernSelect(self.content,list(GUARDIAN_RELATIONSHIPS.values()));self.relationship.set(GUARDIAN_RELATIONSHIPS[(guardian or {}).get('relationship','GUARDIAN')]);self.relationship.pack(fill='x',padx=16)
        self.primary=ctk.BooleanVar(master=self,value=bool((guardian or {}).get('is_primary',False)))
        self.sms=ctk.BooleanVar(master=self,value=bool((guardian or {}).get('can_receive_sms',False)))
        self.active=ctk.BooleanVar(master=self,value=True)
        for title,var in (('Primary guardian / contact',self.primary),('Consent recorded for future SMS contact',self.sms),('Active guardian relationship',self.active)):
            ctk.CTkCheckBox(self.content,text=title,variable=var,font=font(),text_color=theme.TEXT).pack(anchor='w',padx=16,pady=10)
        label(self.content,'Select the guardian explicitly. Household membership does not establish a biological relationship.',11,muted=True,wraplength=550,justify='left').pack(fill='x',padx=16,pady=12)
        self.save_button=ActionButton(self.footer,'Save guardian',self.save,'primary',width=150);self.save_button.pack(side='right',padx=16,pady=14)
    def render_member(self):
        for child in self.person.winfo_children():child.destroy()
        label(self.person,self.member['full_name'] if self.member else 'Choose a parent or guardian Member.',13,True,wraplength=330).pack(side='left',padx=12,pady=16)
        ActionButton(self.person,'Search guardian',lambda:SchoolMemberPicker(self,self.service,self.selected,'guardian',self.student['member_id']),width=145).pack(side='right',padx=12,pady=12)
    def selected(self,member):self.member=member;self.render_member()
    def save(self):
        if not self.member:self.error_var.set('Choose an existing guardian Member.');return
        gid=self.member.get('guardian_member_id',self.member.get('member_id',self.member.get('id')))
        relationship=next(code for code,name in GUARDIAN_RELATIONSHIPS.items() if name==self.relationship.get())
        primary,sms,active=self.primary.get(),self.sms.get(),self.active.get()
        self.run(lambda:self.service.set_guardian(self.student['member_id'],gid,relationship,primary,sms,active))


class LessonFormDialog(SchoolDialog):
    def __init__(self,master,service,classes,capabilities,on_saved,lesson=None):
        super().__init__(master,'Edit Sunday School lesson' if lesson else 'Create Sunday School lesson',width=760,height=740)
        self.service,self.capabilities,self.on_saved,self.lesson=service,capabilities,on_saved,lesson
        data=lesson or {};self.title_entry=entry(self.content,'Lesson title *',data.get('title',''));self.selected_date=date_field(self.content,'Lesson date *',data.get('lesson_date',date.today()))
        self.topic=entry(self.content,'Topic',data.get('topic',''));self.scripture=entry(self.content,'Scripture reference',data.get('scripture_reference',''))
        heading(self.content,'Classes')
        self.classes=MultiSelectDropdown(self.content,selected_ids=[row['id'] for row in data.get('classes',[])],placeholder='Select classes',search_label='classes')
        self.classes.set_options([dict(id=row['id'],name=row['name']) for row in classes if row['status']=='ACTIVE']);self.classes.pack(fill='x',padx=16)
        self.all_classes=ctk.BooleanVar(master=self,value=data.get('applies_to_all',False))
        self.all_toggle=ctk.CTkCheckBox(self.content,text='All Sunday School classes',variable=self.all_classes,command=self.scope_changed,font=font(),text_color=theme.TEXT)
        if capabilities.get('view_all'):self.all_toggle.pack(anchor='w',padx=16,pady=10)
        self.objective=textbox(self.content,'Objective',data.get('objective',''));self.summary=textbox(self.content,'Lesson summary',data.get('lesson_summary',''));self.teacher_notes=textbox(self.content,'Teaching notes',data.get('teacher_notes',''))
        heading(self.content,'Status');self.status=ModernSelect(self.content,['Draft','Published','Archived']);self.status.set(data.get('status','DRAFT').title());self.status.pack(fill='x',padx=16,pady=(0,16))
        self.save_button=ActionButton(self.footer,'Save lesson',self.save,'primary',width=150);self.save_button.pack(side='right',padx=16,pady=14);self.scope_changed()
    def scope_changed(self):self.classes.configure(state='disabled' if self.all_classes.get() else 'readonly')
    def save(self):
        try:
            data=dict(title=self.title_entry.get(),lesson_date=self.selected_date.get_date(),topic=self.topic.get(),scripture_reference=self.scripture.get(),objective=self.objective.get('1.0','end-1c'),lesson_summary=self.summary.get('1.0','end-1c'),teacher_notes=self.teacher_notes.get('1.0','end-1c'),status=self.status.get().upper())
            all_classes=self.all_classes.get();ids=[] if all_classes else self.classes.get_selected_ids()
        except Exception as error:self.error_var.set(str(error));return
        if self.lesson:self.run(lambda:self.service.update_lesson(self.lesson['id'],data,ids,all_classes,self.lesson['updated_at']))
        else:self.run(lambda:self.service.create_lesson(data,ids,all_classes))


class CreateSchoolAttendanceDialog(SchoolDialog):
    def __init__(self,master,service,lesson_service,classes,on_saved):
        super().__init__(master,'Create class attendance','Class rosters are saved when attendance is opened.',width=720,height=650)
        self.service,self.lesson_service,self.on_saved=service,lesson_service,on_saved
        self.class_map={row['name']:row['id'] for row in classes if row['status']=='ACTIVE'}
        heading(self.content,'Class *');self.class_select=ModernSelect(self.content,list(self.class_map),placeholder='Configure an active class first',command=lambda _v:self.load_lessons());self.class_select.pack(fill='x',padx=16)
        self.selected_date=date_field(self.content,'Attendance date *',date.today());self.title_entry=entry(self.content,'Title (optional)')
        heading(self.content,'Lesson (optional)');self.lesson_map={};self.lesson=ModernSelect(self.content,['No lesson']);self.lesson.pack(fill='x',padx=16)
        ActionButton(self.content,'Refresh lesson choices',self.load_lessons,width=190).pack(anchor='w',padx=16,pady=8)
        heading(self.content,'Create as');self.session_state_select=ModernSelect(self.content,['Open now','Planned']);self.session_state_select.pack(fill='x',padx=16,pady=(0,16))
        self.save_button=ActionButton(self.footer,'Create attendance',self.save,'primary',width=180);self.save_button.pack(side='right',padx=16,pady=14);self.load_lessons()
    def load_lessons(self):
        cid=self.class_map.get(self.class_select.get())
        if cid:self.loader.submit('lessons',lambda:self.lesson_service.list_lessons(class_id=cid,view='PUBLISHED',limit=100),self.lessons_loaded,lambda _error:None)
    def lessons_loaded(self,page):
        self.lesson_map={display_date(row['lesson_date'])+' · '+row['title']:row['id'] for row in page['rows']};self.lesson.configure(values=['No lesson']+list(self.lesson_map));self.lesson.set('No lesson')
    def save(self):
        try:
            cid=self.class_map.get(self.class_select.get())
            if not cid:raise ValueError('Choose an active class.')
            selected_date=self.selected_date.get_date();title=self.title_entry.get();lid=self.lesson_map.get(self.lesson.get());open_now=self.session_state_select.get()=='Open now'
        except Exception as error:self.error_var.set(str(error));return
        self.run(lambda:self.service.create_session(cid,selected_date,title,lid,open_now))


class CorrectSchoolAttendanceDialog(SchoolDialog):
    def __init__(self,master,service,record,status,on_saved):
        super().__init__(master,'Correct Sunday School attendance',record['full_name'],width=660,height=500)
        self.service,self.record,self.on_saved=service,record,on_saved
        heading(self.content,'New status');self.status=ModernSelect(self.content,['Present','Late','Excused','Absent']);self.status.set(status.title());self.status.pack(fill='x',padx=16)
        self.reason=entry(self.content,'Correction reason *')
        label(self.content,'The original marker and time remain recorded. This change adds correction history.',12,muted=True,wraplength=530,justify='left').pack(fill='x',padx=16,pady=16)
        self.save_button=ActionButton(self.footer,'Save correction',self.save,'primary',width=165);self.save_button.pack(side='right',padx=16,pady=14)
    def save(self):
        status,reason=self.status.get().upper(),self.reason.get()
        self.run(lambda:self.service.correct(self.record['record_id'],status,reason,self.record['updated_at']))


class EndEnrollmentDialog(SchoolDialog):
    def __init__(self,master,service,student,on_saved):
        super().__init__(master,'End class enrollment',student['full_name'],width=650,height=500)
        self.service,self.student,self.on_saved=service,student,on_saved
        self.effective=date_field(self.content,'Effective end date *',date.today());self.reason=entry(self.content,'Reason / notes (optional)')
        self.save_button=ActionButton(self.footer,'End enrollment',self.save,'primary',width=165);self.save_button.pack(side='right',padx=16,pady=14)
    def save(self):
        try:effective=self.effective.get_date();reason=self.reason.get()
        except Exception as error:self.error_var.set(str(error));return
        self.run(lambda:self.service.end_enrollment(self.student['enrollment_id'],effective,reason,self.student['enrollment_updated_at']))
