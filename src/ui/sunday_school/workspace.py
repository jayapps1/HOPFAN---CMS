"""Complete Sunday School workspace backed only by authorized service methods."""
from datetime import date
from pathlib import Path
import tkinter.filedialog as filedialog
import customtkinter as ctk
from src.ui import theme
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.app_shell import PageHeader
from src.ui.components.action_menu import ActionMenu
from src.ui.components.date_picker import DatePicker,display_date
from src.ui.components.modern import ActionButton,AppCard,Avatar,EmptyState,StatCard,StatusBadge,font,label
from src.ui.components.modern_select import ModernSelect
from src.ui.components.search_field import SearchField
from src.services.sunday_school_service import SundaySchoolService
from src.services.sunday_school_attendance_service import SundaySchoolAttendanceService
from src.services.sunday_school_lesson_service import SundaySchoolLessonService
from src.services.sunday_school_report_service import SundaySchoolReportService
from src.services.member_service import MemberService
from src.ui.sunday_school.dialogs import (SchoolDialog,ClassFormDialog,EnrollStudentDialog,AssignTeacherDialog,GuardianDialog,
    LessonFormDialog,CreateSchoolAttendanceDialog,CorrectSchoolAttendanceDialog,EndEnrollmentDialog,textbox)


def wrap(parent,text,row,column,bold=False,width=240):
    widget=label(parent,text,12,bold,anchor='w',justify='left',width=1,wraplength=width)
    widget.grid(row=row,column=column,sticky='ew',padx=10,pady=6);return widget


class SchoolDirectory(ctk.CTkFrame):
    PAGE_SIZE=25
    def __init__(self,master,title,subtitle):
        super().__init__(master,fg_color=theme.BACKGROUND,corner_radius=0)
        self.loader=AsyncLoader(self);self.offset,self.total,self.records=0,0,[]
        self.grid_columnconfigure(0,weight=1);self.grid_rowconfigure(3,weight=1)
        self.header=PageHeader(self,title,subtitle);self.header.grid(row=0,column=0,sticky='ew',padx=20,pady=(8,10))
        self.filters=AppCard(self);self.filters.grid(row=2,column=0,sticky='ew',padx=20,pady=(0,10));self.filters.grid_columnconfigure(0,weight=1)
        self.search=SearchField(self.filters,lambda:self.refresh(True),'Search');self.search.grid(row=0,column=0,sticky='ew',padx=10,pady=10)
        self.rows=ctk.CTkScrollableFrame(self,fg_color='transparent');self.rows.grid(row=3,column=0,sticky='nsew',padx=16);self.rows.grid_columnconfigure(0,weight=1)
        footer=ctk.CTkFrame(self,fg_color='transparent');footer.grid(row=4,column=0,sticky='ew',padx=20,pady=10)
        self.notice=label(footer,'Loading…',12,muted=True);self.notice.pack(side='left')
        self.next_button=ActionButton(footer,'Next',lambda:self.page(1),width=70);self.next_button.pack(side='right')
        self.previous=ActionButton(footer,'Previous',lambda:self.page(-1),width=85);self.previous.pack(side='right',padx=8)
    def page(self,direction):self.offset=max(0,self.offset+direction*self.PAGE_SIZE);self.refresh()
    def failed(self,error):self.notice.configure(text=str(error),text_color=theme.DANGER)
    def directory(self,page,title,detail):
        self.total,self.records=page['total'],page['rows']
        if self.offset and not self.records and self.total:self.offset=((self.total-1)//self.PAGE_SIZE)*self.PAGE_SIZE;self.refresh();return False
        for child in self.rows.winfo_children():child.destroy()
        self.notice.configure(text=f'{self.total} results · Page {self.offset//self.PAGE_SIZE+1}',text_color=theme.TEXT_MUTED)
        self.previous.configure(state='normal' if self.offset else 'disabled');self.next_button.configure(state='normal' if self.offset+len(self.records)<self.total else 'disabled')
        if not self.records:EmptyState(self.rows,title,detail).grid(row=0,column=0,sticky='ew')
        return True


class SundaySchoolWorkspace(ctk.CTkFrame):
    def __init__(self,master,user,service=None,attendance=None,lessons=None,reports=None,member_service=None):
        super().__init__(master,fg_color=theme.BACKGROUND,corner_radius=0)
        self.user=user;self.service=service or SundaySchoolService(user.id);self.attendance=attendance or SundaySchoolAttendanceService(user.id)
        self.lessons=lessons or SundaySchoolLessonService(user.id);self.reports=reports or SundaySchoolReportService(user.id)
        self.members=member_service or MemberService(user.id);self.loader=AsyncLoader(self);self.body=None;self.capabilities={};self.classes=[]
        self.grid_columnconfigure(0,weight=1);self.grid_rowconfigure(1,weight=1)
        self.nav=ctk.CTkSegmentedButton(self,values=['Overview'],command=self.select,font=font(12,True),height=38,
            fg_color=theme.SURFACE_ALT,selected_color=theme.SECONDARY,selected_hover_color=theme.SECONDARY_HOVER,
            unselected_color=theme.SURFACE_ALT,unselected_hover_color=theme.BORDER,text_color=theme.TEXT)
        self.nav.grid(row=0,column=0,sticky='ew',padx=20,pady=(8,10))
        self.notice=label(self,'Loading Sunday School…',14,muted=True);self.notice.grid(row=1,column=0,pady=30)
        self.loader.submit('setup',lambda:(self.service.capabilities(),self.service.class_options(limit=100)),self.ready,self.failed)
    def failed(self,error):self.notice.configure(text=str(error),text_color=theme.DANGER)
    def ready(self,result):
        self.capabilities,page=result;self.classes=page['rows'];self.notice.grid_remove()
        tabs=[name for name,key in (('Overview','class_view'),('Students','student_view'),('Classes','class_view'),('Attendance','attendance_view'),('Lessons','lesson_view'),('Teachers','teacher_view'),('Reports','report_view')) if self.capabilities.get(key)]
        if not tabs:self.notice.grid();self.notice.configure(text='No Sunday School operations are assigned to this account.');return
        self.nav.configure(values=tabs);self.nav.set(tabs[0]);self.select(tabs[0])
    def refresh_classes(self):
        self.loader.submit('class-options',lambda:self.service.class_options(limit=100),lambda page:setattr(self,'classes',page['rows']),self.failed)
    def select(self,name):
        self.nav.set(name)
        if self.body:self.body.destroy()
        types={'Overview':SchoolOverview,'Students':SchoolStudents,'Classes':SchoolClasses,'Attendance':SchoolAttendance,'Lessons':SchoolLessons,'Teachers':SchoolTeachers,'Reports':SchoolReports}
        self.body=types[name](self,self);self.body.grid(row=1,column=0,sticky='nsew')
    def student(self,member_id):return StudentProfileDialog(self,self,member_id)
    def enroll(self,student=None):return EnrollStudentDialog(self,self.service,self.members,self.classes,self.capabilities,self.changed,student)
    def assign_teacher(self,teacher=None):return AssignTeacherDialog(self,self.service,self.classes,self.changed,teacher)
    def lesson(self,lesson=None):return LessonFormDialog(self,self.lessons,self.classes,self.capabilities,self.changed,lesson)
    def create_attendance(self):return CreateSchoolAttendanceDialog(self,self.attendance,self.lessons,self.classes,self.changed)
    def open_attendance(self,session_id):return SchoolRosterDialog(self,self,session_id)
    def changed(self):
        self.refresh_classes()
        if self.body and hasattr(self.body,'refresh'):self.body.refresh(True)


class SchoolOverview(ctk.CTkScrollableFrame):
    def __init__(self,master,workspace):
        super().__init__(master,fg_color='transparent');self.workspace=workspace;self.loader=AsyncLoader(self);self.grid_columnconfigure(0,weight=1)
        bar=ctk.CTkFrame(self,fg_color='transparent');bar.grid(row=0,column=0,sticky='ew',padx=20,pady=(0,10));self.cards={}
        for index,(key,title) in enumerate((('students','Students'),('classes','Classes'),('teachers','Teachers'),('present_last_sunday','Present last Sunday'),('rate','Attendance rate'))):
            bar.grid_columnconfigure(index,weight=1,uniform='summary');card=StatCard(bar,title,compact=True);card.set('—');card.grid(row=0,column=index,sticky='ew',padx=3);self.cards[key]=card
        quick=AppCard(self);quick.grid(row=1,column=0,sticky='ew',padx=20,pady=8);label(quick,'Quick actions',16,True).pack(anchor='w',padx=16,pady=(10,6))
        buttons=ctk.CTkFrame(quick,fg_color='transparent');buttons.pack(fill='x',padx=12,pady=(0,12))
        for text,key,command in (('Take attendance','attendance_create',workspace.create_attendance),('Enroll student','student_enroll',workspace.enroll),('Create lesson','lesson_create',workspace.lesson),('View classes','class_view',lambda:workspace.select('Classes'))):
            if workspace.capabilities.get(key):ActionButton(buttons,text,command,width=145).pack(side='left',padx=4)
        self.sections={}
        for index,title in enumerate(('Class attendance','Upcoming lessons','Recent absences','Students without class'),start=2):
            card=AppCard(self);card.grid(row=index,column=0,sticky='ew',padx=20,pady=8);label(card,title,16,True).pack(anchor='w',padx=16,pady=(10,6))
            body=ctk.CTkFrame(card,fg_color='transparent');body.pack(fill='x',padx=16,pady=(0,12));self.sections[title]=body
        self.notice=label(self,'Loading overview…',12,muted=True);self.notice.grid(row=6,column=0,sticky='ew',padx=20,pady=8);self.refresh()
    def refresh(self,reset=False):
        self.loader.submit('overview',lambda:(self.workspace.reports.dashboard(),self.workspace.lessons.list_lessons(view='UPCOMING',limit=5) if self.workspace.capabilities.get('lesson_view') else dict(rows=[])),self.render,lambda error:self.notice.configure(text=str(error)))
    def render(self,result):
        stats,lessons=result;self.notice.configure(text='Attendance rate uses closed class sessions from the last 30 days. Last Sunday: '+display_date(stats['last_sunday']))
        for key,card in self.cards.items():card.set('—' if stats[key] is None else str(stats[key])+'%' if key=='rate' else stats[key])
        for body in self.sections.values():
            for child in body.winfo_children():child.destroy()
        for row in stats['class_attendance']:label(self.sections['Class attendance'],f"{row['class_name']} · {display_date(row['date'])} · {row['present']}/{row['eligible']} present or late",12,anchor='w').pack(fill='x',pady=3)
        if not stats['class_attendance']:label(self.sections['Class attendance'],'No closed class attendance yet.',12,muted=True).pack(anchor='w')
        for row in lessons['rows']:label(self.sections['Upcoming lessons'],display_date(row['lesson_date'])+' · '+row['title'],12,anchor='w').pack(fill='x',pady=3)
        if not lessons['rows']:label(self.sections['Upcoming lessons'],'No upcoming published lessons.',12,muted=True).pack(anchor='w')
        for row in stats['recent_absences']:label(self.sections['Recent absences'],row['student']+' · '+row['class_name']+' · '+display_date(row['date']),12,anchor='w').pack(fill='x',pady=3)
        if not stats['recent_absences']:label(self.sections['Recent absences'],'No absences in this view.',12,muted=True).pack(anchor='w')
        without=stats['students_without_class'];label(self.sections['Students without class'],str(without)+' admitted students need class placement.' if without is not None else 'Unassigned student information requires Sunday School-wide access.',12,muted=True).pack(anchor='w')
        if without and self.workspace.capabilities.get('student_view'):ActionButton(self.sections['Students without class'],'View students',lambda:self.workspace.select('Students'),width=140).pack(anchor='w',pady=8)


class SchoolClasses(SchoolDirectory):
    def __init__(self,master,workspace):
        super().__init__(master,'Classes','Manage Sunday School classes and enrollment');self.workspace=workspace
        self.status=ModernSelect(self.filters,['All','Active','Inactive'],width=125,command=lambda _v:self.refresh(True));self.status.grid(row=0,column=1,padx=10)
        self.add_button=None
        if workspace.capabilities.get('class_create') and workspace.capabilities.get('view_all'):
            self.add_button=ActionButton(self.header.actions,'Add class',self.add,'primary',width=130);self.add_button.pack(side='left')
        bar=ctk.CTkFrame(self,fg_color='transparent');bar.grid(row=1,column=0,sticky='ew',padx=20,pady=(0,10));self.cards={}
        for index,(key,title) in enumerate((('classes','Total classes'),('active_classes','Active classes'),('students','Students'),('teachers','Teachers'))):
            bar.grid_columnconfigure(index,weight=1,uniform='summary');card=StatCard(bar,title,compact=True);card.set('—');card.grid(row=0,column=index,sticky='ew',padx=3);self.cards[key]=card
        self.refresh()
    def refresh(self,reset=False):
        if reset:self.offset=0
        params=dict(search=self.search.get(),status=self.status.get(),limit=self.PAGE_SIZE,offset=self.offset)
        self.loader.submit('classes',lambda:(self.workspace.service.list_classes(**params),self.workspace.reports.dashboard()),self.render,self.failed)
    def render(self,page):
        page,stats=page
        for key,card in self.cards.items():card.set(stats[key] if stats[key] is not None else '—')
        if not self.directory(page,'No Sunday School classes have been configured.','Configure class names, age guidance, rooms and capacity.'):return
        for index,row in enumerate(page['rows']):
            card=AppCard(self.rows);card.item=row;card.grid(row=index,column=0,sticky='ew',padx=4,pady=4);card.grid_columnconfigure(0,weight=2)
            wrap(card,row['name']+'\n'+row['code'],0,0,True)
            age=('Any age' if row['minimum_age'] is None and row['maximum_age'] is None else str(row['minimum_age'] or 0)+'–'+(str(row['maximum_age']) if row['maximum_age'] is not None else 'Unlimited'))
            wrap(card,age,0,1,width=100);wrap(card,f"{row['students']} students\n{row['teachers']} teachers",0,2,width=120);wrap(card,row['room_location'] or 'Room not set',0,3,width=140)
            StatusBadge(card,row['status']).grid(row=0,column=4,padx=8)
            card.view_button=ActionButton(card,'View',lambda item=row:self.view(item),width=60);card.view_button.grid(row=0,column=5,padx=6)
            if self.workspace.capabilities.get('class_edit'):card.edit_button=ActionButton(card,'Edit',lambda item=row:self.edit(item),width=55);card.edit_button.grid(row=0,column=6,padx=6)
    def add(self):return ClassFormDialog(self,self.workspace.service,self.workspace.changed,capabilities=self.workspace.capabilities)
    def edit(self,row):return ClassFormDialog(self,self.workspace.service,self.workspace.changed,row,self.workspace.capabilities)
    def view(self,row):return ClassProfileDialog(self,self.workspace,row)


class ClassProfileDialog(SchoolDialog):
    def __init__(self,master,workspace,school_class):
        super().__init__(master,school_class['name'],'Class configuration, current students and teachers.',width=820,height=720)
        self.workspace,self.school_class=workspace,school_class;self.cancel_button.configure(text='Close')
        self.mode=ModernSelect(self.header,['Students','Teachers'],width=150,command=lambda _v:self.refresh());self.mode.pack(anchor='w',padx=16,pady=8)
        if workspace.capabilities.get('class_edit'):ActionButton(self.footer,'Edit class',lambda:ClassFormDialog(self,workspace.service,self.refresh,self.school_class,workspace.capabilities),width=130).pack(side='right',padx=10,pady=14)
        self.actions=None;choices=[]
        if workspace.capabilities.get('class_archive'):choices.append(('Deactivate class' if school_class['status']=='ACTIVE' else 'Activate class',self.status_change))
        if workspace.capabilities.get('class_delete'):choices.append(('Delete unused class',self.delete))
        if choices:self.actions=ActionMenu(self.footer,choices);self.actions.pack(side='right',padx=10)
        self.refresh()
    def refresh(self):
        mode=self.mode.get()
        def fetch():
            row=self.workspace.service.get_class(self.school_class['id'])
            page=self.workspace.service.list_students(class_id=row['id'],status='ALL',limit=100) if mode=='Students' and self.workspace.capabilities.get('student_view') else self.workspace.service.list_teachers(class_id=row['id'],limit=100) if mode=='Teachers' and self.workspace.capabilities.get('teacher_view') else dict(rows=[])
            return row,page
        self.loader.submit('class',fetch,self.render,lambda error:self.error_var.set(str(error)))
    def render(self,result):
        self.school_class,page=result
        for child in self.content.winfo_children():child.destroy()
        row=self.school_class
        label(self.content,f"{row['code']} · {row['status'].title()} · {row['students']} students · {row['teachers']} teachers",13,True).pack(anchor='w',padx=16,pady=14)
        label(self.content,'Room: '+(row['room_location'] or 'Not configured'),12,muted=True).pack(anchor='w',padx=16)
        if not page['rows']:EmptyState(self.content,'No records in this permitted view.').pack(fill='x')
        for item in page['rows']:
            card=AppCard(self.content);card.pack(fill='x',padx=12,pady=4)
            Avatar(card,item['full_name'],item['photo_path']).pack(side='left',padx=12,pady=12)
            label(card,item['full_name']+' · '+item['member_no'],13,True).pack(side='left',padx=8)
            if self.mode.get()=='Students':ActionButton(card,'View student',lambda value=item:self.workspace.student(value['member_id']),width=130).pack(side='right',padx=12)
            else:label(card,item['role_label'],12,muted=True).pack(side='right',padx=12)
    def status_change(self):
        new='INACTIVE' if self.school_class['status']=='ACTIVE' else 'ACTIVE'
        self.confirm('Change class status','Current enrollments and history remain. Inactive classes reject new enrollment and attendance opening.',lambda:self.lifecycle(lambda:self.workspace.service.set_class_status(self.school_class['id'],new,self.school_class['updated_at'])))
    def delete(self):self.confirm('Delete unused class','Classes with any teaching, student, lesson, attendance or account-scope history are protected.',lambda:self.lifecycle(lambda:self.workspace.service.delete_unused_class(self.school_class['id'],True,self.school_class['updated_at']),True))
    def lifecycle(self,operation,close=False):
        def saved(_result):self.workspace.changed();self.destroy() if close else self.refresh()
        self.loader.submit('lifecycle',operation,saved,lambda error:self.error_var.set(str(error)))


class SchoolStudents(SchoolDirectory):
    def __init__(self,master,workspace):
        super().__init__(master,'Sunday School students','Admission, class placement and operational guardian contacts');self.workspace=workspace
        self.class_map={'All classes':None,**{row['name']:row['id'] for row in workspace.classes}}
        self.class_select=ModernSelect(self.filters,list(self.class_map),width=165,command=lambda _v:self.refresh(True));self.class_select.grid(row=0,column=1,padx=6)
        self.status=ModernSelect(self.filters,['Active','Inactive','All'],width=120,command=lambda _v:self.refresh(True));self.status.grid(row=0,column=2,padx=6)
        self.placement=ModernSelect(self.filters,['All students','Without class'] if workspace.capabilities.get('view_all') else ['Assigned students'],width=150,command=lambda _v:self.refresh(True));self.placement.grid(row=0,column=3,padx=8)
        self.age_filter=ModernSelect(self.filters,['Any age','0–3','4–6','7–9','10–12','13–17','18+'],width=120,command=lambda _v:self.refresh(True));self.age_filter.grid(row=1,column=0,sticky='w',padx=10,pady=(0,10))
        self.gender=ModernSelect(self.filters,['Any gender','Male','Female'],width=120,command=lambda _v:self.refresh(True))
        if workspace.capabilities.get('view_all'):self.gender.grid(row=1,column=1,padx=6,pady=(0,10))
        self.add_button=None
        if workspace.capabilities.get('student_enroll'):
            self.add_button=ActionButton(self.header.actions,'Enroll student',workspace.enroll,'primary',width=145);self.add_button.pack(side='left')
        bar=ctk.CTkFrame(self,fg_color='transparent');bar.grid(row=1,column=0,sticky='ew',padx=20,pady=(0,10));self.cards={}
        for index,(key,title) in enumerate((('students','Total students'),('present_last_sunday','Present last Sunday'),('absent_last_sunday','Absent last Sunday'),('classes','Classes'),('students_without_class','Without class'))):
            bar.grid_columnconfigure(index,weight=1,uniform='summary');card=StatCard(bar,title,compact=True);card.set('—');card.grid(row=0,column=index,sticky='ew',padx=3);self.cards[key]=card
        self.refresh()
    def refresh(self,reset=False):
        if reset:self.offset=0
        selected=self.age_filter.get();low=high=None
        if '–' in selected:low,high=selected.split('–')
        elif selected=='18+':low=18
        params=dict(search=self.search.get(),class_id=self.class_map[self.class_select.get()],status=self.status.get(),without_class=self.placement.get()=='Without class',minimum_age=low,maximum_age=high,
            gender=None if self.gender.get()=='Any gender' else self.gender.get(),limit=self.PAGE_SIZE,offset=self.offset)
        self.loader.submit('students',lambda:(self.workspace.service.list_students(**params),self.workspace.reports.dashboard() if self.workspace.capabilities.get('class_view') else {}),self.render,self.failed)
    def render(self,page):
        page,stats=page
        for key,card in self.cards.items():card.set(stats.get(key) if stats.get(key) is not None else '—')
        if not self.directory(page,'No students are currently enrolled.','Enroll an existing HOPFAN Member or register admission before class placement.'):return
        for index,row in enumerate(page['rows']):
            card=AppCard(self.rows);card.item=row;card.grid(row=index,column=0,sticky='ew',padx=4,pady=4);card.grid_columnconfigure(1,weight=2);card.grid_columnconfigure(2,weight=1)
            Avatar(card,row['full_name'],row['photo_path']).grid(row=0,column=0,rowspan=2,padx=12,pady=12)
            wrap(card,row['full_name']+'\n'+row['member_no'],0,1,True,width=240)
            wrap(card,row['class_name'] or 'No current class',0,2,width=150)
            wrap(card,(str(row['age'])+' years') if row['age'] is not None else 'Age unavailable',0,3,width=100)
            wrap(card,row['guardian_name'] or 'Guardian not configured',1,1,width=240);wrap(card,row['guardian_phone'] or '',1,2,width=140)
            StatusBadge(card,row['status']).grid(row=0,column=4,rowspan=2,padx=8)
            card.view_button=ActionButton(card,'View',lambda item=row:self.workspace.student(item['member_id']),width=65);card.view_button.grid(row=0,column=5,rowspan=2,padx=12)


class StudentProfileDialog(SchoolDialog):
    def __init__(self,master,workspace,member_id):
        super().__init__(master,'Sunday School student','Member identity, guardian contacts and retained class history.',width=820,height=730)
        self.workspace,self.member_id,self.student=workspace,member_id,None;self.cancel_button.configure(text='Close');self.refresh()
    def refresh(self):self.loader.submit('student',lambda:self.workspace.service.get_student(self.member_id),self.render,lambda error:self.error_var.set(str(error)))
    def changed(self):self.refresh();self.workspace.changed()
    def render(self,student):
        self.student=student
        for child in self.content.winfo_children():child.destroy()
        for child in self.footer.winfo_children():
            if child!=self.cancel_button:child.destroy()
        person=AppCard(self.content);person.pack(fill='x',padx=12,pady=8)
        Avatar(person,student['full_name'],student['photo_path'],56).pack(side='left',padx=12,pady=12)
        label(person,student['full_name']+'\n'+student['member_no'],17,True,justify='left').pack(side='left',padx=8)
        StatusBadge(person,student['status']).pack(side='right',padx=12)
        age=str(student['age'])+' years' if student['age'] is not None else 'Age unavailable'
        label(self.content,age+' · DOB '+(display_date(student['date_of_birth']) or 'not recorded'),12,muted=True).pack(anchor='w',padx=16,pady=6)
        label(self.content,'Current class: '+(student['class_name'] or 'Not placed'),15,True).pack(anchor='w',padx=16,pady=6)
        label(self.content,'Household: '+((student.get('household') or {}).get('household_name') or 'Not recorded'),12,muted=True).pack(anchor='w',padx=16)
        teachers=', '.join(row['full_name'] for row in student['teachers']) or 'No current teachers configured'
        label(self.content,'Teachers: '+teachers,12,wraplength=650,justify='left').pack(anchor='w',padx=16,pady=6)
        label(self.content,'Parents / guardians',16,True).pack(anchor='w',padx=16,pady=(14,6))
        for guardian in student['guardians']:
            card=AppCard(self.content);card.pack(fill='x',padx=12,pady=4)
            label(card,guardian['full_name']+' · '+guardian['relationship'].title()+(' · Primary' if guardian['is_primary'] else ''),13,True).pack(anchor='w',padx=12,pady=(10,3))
            label(card,guardian['phone'] or 'Phone not recorded',12,muted=True).pack(anchor='w',padx=12,pady=(0,10))
            if self.workspace.capabilities.get('guardian_manage'):ActionButton(card,'Edit guardian',lambda contact=guardian:GuardianDialog(self,self.workspace.service,self.student,self.changed,contact),width=145).pack(anchor='e',padx=12,pady=8)
        if not student['guardians']:label(self.content,'No guardian has been explicitly configured.',12,muted=True).pack(anchor='w',padx=16,pady=8)
        if self.workspace.capabilities.get('guardian_manage'):ActionButton(self.content,'Add guardian',lambda:GuardianDialog(self,self.workspace.service,self.student,self.changed),width=145).pack(anchor='w',padx=16,pady=8)
        label(self.content,'Class history',16,True).pack(anchor='w',padx=16,pady=(14,6))
        for row in student['history']:label(self.content,row['class_name']+' · '+display_date(row['start_date'])+' – '+(display_date(row['end_date']) if row['end_date'] else 'Present'),12).pack(anchor='w',padx=16,pady=5)
        if student['special_notes']:label(self.content,student['special_notes'],12,wraplength=650,justify='left').pack(fill='x',padx=16,pady=10)
        if self.workspace.capabilities.get('student_move') and student['enrollment_id']:ActionButton(self.footer,'Move student',lambda:self.workspace.enroll(self.student),'primary',width=135).pack(side='right',padx=8,pady=14)
        elif self.workspace.capabilities.get('student_enroll'):ActionButton(self.footer,'Place in class',lambda:self.workspace.enroll(self.student),'primary',width=145).pack(side='right',padx=8,pady=14)
        choices=[]
        if self.workspace.capabilities.get('student_end') and student['enrollment_id']:choices.append(('End enrollment',lambda:EndEnrollmentDialog(self,self.workspace.service,self.student,self.changed)))
        if self.workspace.capabilities.get('student_edit') and self.workspace.capabilities.get('view_all'):choices.append(('Edit admission status / notes',lambda:StudentStatusDialog(self,self.workspace,self.student,self.changed)))
        if choices:self.actions=ActionMenu(self.footer,choices);self.actions.pack(side='right',padx=8)


class StudentStatusDialog(SchoolDialog):
    def __init__(self,master,workspace,student,on_saved):
        super().__init__(master,'Edit Sunday School admission',student['full_name'],width=680,height=590)
        self.workspace,self.student,self.on_saved=workspace,student,on_saved
        self.status=ModernSelect(self.content,['Active','Inactive']);self.status.set(student['status'].title());self.status.pack(fill='x',padx=16,pady=16)
        self.notes=textbox(self.content,'Restricted admission notes',student['special_notes'])
        label(self.content,'Deactivation ends a current class enrollment today. Reactivation does not restore old enrollment.',12,muted=True,wraplength=540,justify='left').pack(fill='x',padx=16,pady=16)
        self.save_button=ActionButton(self.footer,'Save admission',self.save,'primary',width=165);self.save_button.pack(side='right',padx=16,pady=14)
    def save(self):
        status,notes=self.status.get().upper(),self.notes.get('1.0','end-1c')
        self.run(lambda:self.workspace.service.update_student(self.student['member_id'],status,notes,self.student['updated_at']))


class SchoolTeachers(SchoolDirectory):
    def __init__(self,master,workspace):
        super().__init__(master,'Teachers','Teaching assignments are independent from account access');self.workspace=workspace
        self.status=ModernSelect(self.filters,['Current','Historical'],width=145,command=lambda _v:self.refresh(True));self.status.grid(row=0,column=1,padx=10)
        self.add_button=None
        if workspace.capabilities.get('teacher_assign'):self.add_button=ActionButton(self.header.actions,'Assign teacher',workspace.assign_teacher,'primary',width=150);self.add_button.pack(side='left')
        self.refresh()
    def refresh(self,reset=False):
        if reset:self.offset=0
        params=dict(search=self.search.get(),history=self.status.get()=='Historical',limit=self.PAGE_SIZE,offset=self.offset)
        self.loader.submit('teachers',lambda:self.workspace.service.list_teachers(**params),self.render,self.failed)
    def render(self,page):
        if not self.directory(page,'No teaching assignments in this view.','Assign existing Members as teachers, assistants or coordinators.'):return
        for index,row in enumerate(page['rows']):
            card=AppCard(self.rows);card.item=row;card.grid(row=index,column=0,sticky='ew',padx=4,pady=4);card.grid_columnconfigure(1,weight=1)
            Avatar(card,row['full_name'],row['photo_path']).grid(row=0,column=0,padx=12,pady=12);wrap(card,row['full_name']+'\n'+row['member_no'],0,1,True)
            wrap(card,row['class_name']+'\n'+row['role_label'],0,2,width=180);wrap(card,display_date(row['start_date'])+' – '+(display_date(row['end_date']) if row['end_date'] else 'Present'),0,3,width=160)
            if self.workspace.capabilities.get('teacher_end') and row['is_current']:card.end_button=ActionButton(card,'End',lambda item=row:self.workspace.assign_teacher(item),width=65);card.end_button.grid(row=0,column=4,padx=12)


class SchoolLessons(SchoolDirectory):
    def __init__(self,master,workspace):
        super().__init__(master,'Lessons','One lesson plan can serve one, several or all classes');self.workspace=workspace
        self.status=ModernSelect(self.filters,['Upcoming','Recent','Draft','Published','Archived','All'],width=140,command=lambda _v:self.refresh(True));self.status.grid(row=0,column=1,padx=10)
        self.add_button=None
        if workspace.capabilities.get('lesson_create'):self.add_button=ActionButton(self.header.actions,'Create lesson',workspace.lesson,'primary',width=145);self.add_button.pack(side='left')
        self.refresh()
    def refresh(self,reset=False):
        if reset:self.offset=0
        params=dict(search=self.search.get(),view=self.status.get(),limit=self.PAGE_SIZE,offset=self.offset)
        self.loader.submit('lessons',lambda:self.workspace.lessons.list_lessons(**params),self.render,self.failed)
    def render(self,page):
        if not self.directory(page,'No lessons have been created.','Create a lesson, select its class scope and publish it when ready.'):return
        for index,row in enumerate(page['rows']):
            card=AppCard(self.rows);card.item=row;card.grid(row=index,column=0,sticky='ew',padx=4,pady=4);card.grid_columnconfigure(1,weight=2)
            wrap(card,display_date(row['lesson_date']),0,0,width=100);wrap(card,row['title']+'\n'+(row['topic'] or 'Topic not set'),0,1,True)
            classes='All classes' if row['applies_to_all'] else ', '.join(value['name'] for value in row['classes']);wrap(card,classes,0,2,width=170)
            wrap(card,row['author']+'\n'+row['status'].title(),0,3,width=130)
            card.view_button=ActionButton(card,'View',lambda item=row:LessonProfileDialog(self,self.workspace,item),width=60);card.view_button.grid(row=0,column=4,padx=12)


class LessonProfileDialog(SchoolDialog):
    def __init__(self,master,workspace,lesson):
        super().__init__(master,lesson['title'],display_date(lesson['lesson_date']),width=780,height=690);self.cancel_button.configure(text='Close')
        for title,key in (('Topic','topic'),('Scripture','scripture_reference'),('Objective','objective'),('Lesson summary','lesson_summary'),('Teaching notes','teacher_notes')):
            label(self.content,title,14,True).pack(anchor='w',padx=16,pady=(12,4));label(self.content,lesson[key] or 'Not provided',12,wraplength=640,justify='left',anchor='w').pack(fill='x',padx=16)
        if workspace.capabilities.get('lesson_edit'):ActionButton(self.footer,'Edit lesson',lambda:workspace.lesson(lesson),width=145).pack(side='right',padx=16,pady=14)


class SchoolAttendance(SchoolDirectory):
    def __init__(self,master,workspace):
        super().__init__(master,'Sunday School attendance','Class sessions and saved student rosters');self.workspace=workspace
        self.status=ModernSelect(self.filters,['All','Draft','Open','Closed'],width=135,command=lambda _v:self.refresh(True));self.status.grid(row=0,column=1,padx=10)
        self.add_button=None
        if workspace.capabilities.get('attendance_create'):self.add_button=ActionButton(self.header.actions,'Create attendance',workspace.create_attendance,'primary',width=180);self.add_button.pack(side='left')
        self.refresh()
    def refresh(self,reset=False):
        if reset:self.offset=0
        params=dict(search=self.search.get(),state=self.status.get(),limit=self.PAGE_SIZE,offset=self.offset)
        self.loader.submit('sessions',lambda:self.workspace.attendance.list_sessions(**params),self.render,self.failed)
    def render(self,page):
        if not self.directory(page,'No class attendance sessions yet.','Create a session for an active class. Future sessions can be planned.'):return
        for index,row in enumerate(page['rows']):
            card=AppCard(self.rows);card.item=row;card.grid(row=index,column=0,sticky='ew',padx=4,pady=4);card.grid_columnconfigure(1,weight=2)
            wrap(card,display_date(row['session_date']),0,0,width=100);wrap(card,row['title']+'\n'+row['class_name'],0,1,True)
            wrap(card,row['lesson_title'] or 'No lesson',0,2,width=200);wrap(card,str(row['eligible'])+' eligible',0,3,width=110)
            StatusBadge(card,row['state']).grid(row=0,column=4,padx=8)
            card.view_button=ActionButton(card,'Open',lambda item=row:self.workspace.open_attendance(item['id']),width=75);card.view_button.grid(row=0,column=5,padx=12)


class SchoolRosterDialog(SchoolDialog):
    PAGE_SIZE=25
    def __init__(self,master,workspace,session_id):
        super().__init__(master,'Sunday School attendance','Class roster, guardian contacts and original markers.',width=1120,height=790)
        self.workspace,self.session_id,self.session,self.offset=workspace,session_id,None,0;self.cancel_button.configure(text='Close')
        self.summary=ctk.CTkFrame(self.header,fg_color='transparent');self.summary.pack(fill='x',padx=14,pady=6);self.cards={}
        for index,(key,title) in enumerate((('eligible','Eligible'),('present','Present'),('late','Late'),('excused','Excused'),('absent','Absent'))):
            self.summary.grid_columnconfigure(index,weight=1,uniform='stats');card=StatCard(self.summary,title,compact=True);card.set('—');card.grid(row=0,column=index,sticky='ew',padx=3);self.cards[key]=card
        bar=ctk.CTkFrame(self.header,fg_color='transparent');bar.pack(fill='x',padx=16,pady=6);bar.grid_columnconfigure(0,weight=1)
        self.search=SearchField(bar,lambda:self.refresh(True),'Student or guardian');self.search.grid(row=0,column=0,sticky='ew')
        self.status=ModernSelect(bar,['All','Unmarked','Present','Late','Excused','Absent'],width=125,height=36,command=lambda _v:self.refresh(True));self.status.grid(row=0,column=1,padx=8)
        self.previous=ActionButton(bar,'Previous',lambda:self.page(-1),width=80);self.previous.grid(row=0,column=2,padx=4)
        self.next_button=ActionButton(bar,'Next',lambda:self.page(1),width=65);self.next_button.grid(row=0,column=3,padx=4)
        self.notice=label(self.footer,'Loading…',11,muted=True);self.notice.pack(side='left',padx=8)
        self.lifecycle_button=ActionButton(self.footer,'Close attendance',self.lifecycle,'primary',width=165);self.refresh()
    def page(self,direction):self.offset=max(0,self.offset+direction*self.PAGE_SIZE);self.refresh()
    def refresh(self,reset=False):
        if reset:self.offset=0
        params=dict(search=self.search.get(),status=self.status.get(),limit=self.PAGE_SIZE,offset=self.offset)
        self.loader.submit('roster',lambda:(self.workspace.attendance.get_session(self.session_id),self.workspace.attendance.get_roster(self.session_id,**params)),self.render,lambda error:self.error_var.set(str(error)))
    def render(self,result):
        self.session,page=result;row=self.session
        self.header.winfo_children()[0].configure(text=row['class_name']+' · '+display_date(row['session_date']))
        self.header.winfo_children()[1].configure(text=(row['teacher_names'] or 'No teacher configured')+' · '+(row['lesson_title'] or 'No lesson'))
        for key,card in self.cards.items():card.set(row['stats'][key])
        self.notice.configure(text=f"{row['state'].title()} · {page['total']} students · {row['stats']['unmarked']} unmarked")
        self.previous.configure(state='normal' if self.offset else 'disabled');self.next_button.configure(state='normal' if self.offset+len(page['rows'])<page['total'] else 'disabled')
        self.lifecycle_button.pack_forget()
        for action,title in (('open','Open attendance'),('close','Close attendance'),('reopen','Reopen attendance')):
            if row['actions'][action]:self.lifecycle_button.configure(text=title);self.lifecycle_button.pack(side='right',padx=16,pady=14);break
        for child in self.content.winfo_children():child.destroy()
        if not page['rows']:EmptyState(self.content,'No eligible students in this view.','Only saved members of this class appear here.').pack(fill='x')
        for student in page['rows']:
            card=AppCard(self.content);card.student=student;card.pack(fill='x',padx=8,pady=4);card.grid_columnconfigure(1,weight=2);card.grid_columnconfigure(2,weight=1)
            Avatar(card,student['full_name'],student['photo_path']).grid(row=0,column=0,rowspan=2,padx=10,pady=12)
            wrap(card,student['full_name']+'\n'+student['member_no'],0,1,True,width=280)
            wrap(card,student['guardian_name'] or 'Guardian not configured',0,2,width=175)
            wrap(card,student['guardian_phone'] or '',1,2,width=140)
            age=str(student['age'])+' years' if student['age'] is not None else 'Age unavailable';wrap(card,age,1,1,width=240)
            wrap(card,student['marked_by'] or 'Unmarked',0,3,width=110)
            if student['can_mark']:
                card.status_select=ModernSelect(card,['Present','Late','Excused','Absent'],width=125,height=36);card.status_select.grid(row=0,column=4,padx=6)
                card.mark_button=ActionButton(card,'Mark',lambda person=student,select=card.status_select:self.mark(person,select.get().upper()),width=65);card.mark_button.grid(row=0,column=5,padx=10)
            else:
                StatusBadge(card,student['status'] or 'UNMARKED').grid(row=0,column=4,padx=6)
                if student['can_correct']:card.correct_button=ActionButton(card,'Change',lambda person=student:self.correct(person),width=80);card.correct_button.grid(row=0,column=5,padx=10)
    def mark(self,student,status):self.loader.submit('mark-'+student['member_id'],lambda:self.workspace.attendance.mark(self.session_id,student['member_id'],status),lambda _result:self.refresh(),lambda error:self.error_var.set(str(error)))
    def correct(self,student):return CorrectSchoolAttendanceDialog(self,self.workspace.attendance,student,student['status'],self.refresh)
    def lifecycle(self):
        if self.session['actions']['open']:operation=lambda:self.workspace.attendance.open_session(self.session_id);detail='Save the current eligible roster for this class and open attendance.'
        elif self.session['actions']['close']:operation=lambda:self.workspace.attendance.close_session(self.session_id,self.session['updated_at']);detail='Only unmarked members of this saved class roster will be marked absent.'
        else:
            return ReopenSchoolAttendanceDialog(self,self.workspace.attendance,self.session,self.refresh)
        def confirmed():self.loader.submit('lifecycle',operation,lambda _result:self.refresh(),lambda error:self.error_var.set(str(error)))
        return self.confirm(self.lifecycle_button.cget('text'),detail,confirmed)


class ReopenSchoolAttendanceDialog(SchoolDialog):
    def __init__(self,master,service,session,on_saved):
        super().__init__(master,'Reopen class attendance',session['class_name'],width=650,height=480);self.service,self.session,self.on_saved=service,session,on_saved
        self.reason=ModernSelect(self.content,['Data correction','Additional recording'],width=240);self.reason.pack(fill='x',padx=16,pady=16)
        self.save_button=ActionButton(self.footer,'Reopen attendance',self.save,'primary',width=180);self.save_button.pack(side='right',padx=16,pady=14)
    def save(self):
        reason=self.reason.get();self.run(lambda:self.service.reopen_session(self.session['id'],reason,self.session['updated_at']))


class SchoolReports(SchoolDirectory):
    def __init__(self,master,workspace):
        super().__init__(master,'Sunday School reports','Enrollment, attendance, staffing and lesson delivery');self.workspace=workspace
        self.search.grid_remove();self.kind=ModernSelect(self.filters,list(SundaySchoolReportService.REPORTS),width=220,command=lambda _v:self.refresh(True));self.kind.grid(row=0,column=0,sticky='w',padx=10,pady=10)
        self.class_map={'All permitted classes':None,**{row['name']:row['id'] for row in workspace.classes}}
        self.class_select=ModernSelect(self.filters,list(self.class_map),width=200,command=lambda _v:self.refresh(True));self.class_select.grid(row=0,column=1,padx=8)
        self.start=DatePicker(self.filters,height=36);self.start.grid(row=1,column=0,sticky='ew',padx=10,pady=(0,10))
        self.end=DatePicker(self.filters,height=36);self.end.grid(row=1,column=1,padx=8,pady=(0,10))
        ActionButton(self.filters,'Apply dates',lambda:self.refresh(True),width=115).grid(row=1,column=2,padx=10)
        self.export_button=None
        if workspace.capabilities.get('report_export'):self.export_button=ActionButton(self.header.actions,'Export CSV',self.export,'primary',width=125);self.export_button.pack(side='left')
        self.refresh()
    def filters_values(self):
        return dict(class_id=self.class_map[self.class_select.get()],start_date=self.start.get_date() if self.start.variable.get().strip() else None,end_date=self.end.get_date() if self.end.variable.get().strip() else None)
    def refresh(self,reset=False):
        if reset:self.offset=0
        try:params=self.filters_values();kind=SundaySchoolReportService.REPORTS[self.kind.get()]
        except Exception as error:self.failed(error);return
        self.loader.submit('report',lambda:self.workspace.reports.report(kind,limit=self.PAGE_SIZE,offset=self.offset,**params),self.render,self.failed)
    def render(self,page):
        if not self.directory(page,'No report records for these filters.','Choose another report, class or date range.'):return
        for index,row in enumerate(page['rows']):
            card=AppCard(self.rows);card.grid(row=index,column=0,sticky='ew',padx=4,pady=4)
            for column,key in enumerate(page['columns']):
                card.grid_columnconfigure(column,weight=1)
                value=display_date(row[key]) if isinstance(row[key],date) else '—' if row[key] is None else str(row[key])
                wrap(card,key.replace('_',' ').title()+'\n'+value,0,column,bold=column==0,width=160)
    def export(self):
        try:params=self.filters_values();kind=SundaySchoolReportService.REPORTS[self.kind.get()]
        except Exception as error:self.failed(error);return
        filename=filedialog.asksaveasfilename(parent=self.winfo_toplevel(),defaultextension='.csv',initialfile='sunday_school_'+kind+'.csv',filetypes=[('CSV files','*.csv')])
        if not filename:return
        def written(content):
            try:Path(filename).write_text(content,encoding='utf-8-sig');self.notice.configure(text='Report exported.')
            except OSError:self.notice.configure(text='Unable to save this report file.',text_color=theme.DANGER)
        self.loader.submit('export',lambda:self.workspace.reports.export_csv(kind,**params),written,self.failed)
