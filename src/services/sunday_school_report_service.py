"""Scoped baseline reports and safe CSV exports, independent of desktop widgets."""
import csv
import io
from datetime import timedelta
from sqlalchemy import func,select
from src.models import (Member,SundaySchoolClass as SchoolClass,SundaySchoolStudent as Student,
    SundaySchoolEnrollment as Enrollment,SundaySchoolTeacherAssignment as Teacher,
    SundaySchoolAttendanceSession as Session,SundaySchoolRosterMember as Roster,
    SundaySchoolAttendanceRecord as Record,SundaySchoolLesson as Lesson)
from src.services.sunday_school_base import SundaySchoolBase,SundaySchoolError,SundaySchoolDenied,identifier,school_date,today,page_bounds,age_on
from src.services.sunday_school_service import SundaySchoolService


class SundaySchoolReportService(SundaySchoolBase):
    REPORTS = {'Enrollment by class':'enrollment','Class size':'class_size','Age distribution':'ages',
        'Attendance by date':'dates','Attendance by student':'students','Attendance trends':'trends',
        'Repeated absence':'absence','Teacher assignments':'teachers','Students without class':'unassigned','Lessons delivered':'lessons'}

    @staticmethod
    def _period(stmt,start,end):
        if start: stmt=stmt.where(Session.session_date>=school_date(start,future=True))
        if end: stmt=stmt.where(Session.session_date<=school_date(end,future=True))
        return stmt

    def report(self,kind='enrollment',class_id=None,start_date=None,end_date=None,absence_threshold=2,limit=100,offset=0):
        if kind not in self.REPORTS.values(): raise SundaySchoolError('Choose a Sunday School report.')
        if start_date and end_date and school_date(start_date,future=True)>school_date(end_date,future=True): raise SundaySchoolError('Report end date cannot precede its start date.')
        with self._db('SUNDAY_SCHOOL_REPORT_VIEW') as (db,access):
            if class_id: self._class(db,access,class_id)
            rows=[]
            if kind in ('enrollment','class_size'):
                stmt=access.restrict(SundaySchoolService._class_query(),SchoolClass.id)
                if class_id: stmt=stmt.where(SchoolClass.id==identifier(class_id))
                rows=[dict(class_name=cls.name,students=students,teachers=teachers,capacity=cls.capacity if cls.capacity is not None else 'Unlimited',
                    room=cls.room_location or '',status=cls.status) for cls,students,teachers in db.execute(stmt.order_by(SchoolClass.sort_order,SchoolClass.name))]
            elif kind=='ages':
                stmt=select(Member.date_of_birth).join(Student,Student.member_id==Member.id).where(Student.status=='ACTIVE',self.member_clause(access))
                if class_id: stmt=stmt.where(select(Enrollment.id).where(Enrollment.member_id==Member.id,Enrollment.class_id==identifier(class_id),Enrollment.is_current.is_(True)).correlate(Member).exists())
                buckets={'0–3':0,'4–6':0,'7–9':0,'10–12':0,'13–17':0,'18+':0,'Age unavailable':0}
                for dob in db.scalars(stmt):
                    age=age_on(dob,today())
                    key='Age unavailable' if age is None else '0–3' if age<=3 else '4–6' if age<=6 else '7–9' if age<=9 else '10–12' if age<=12 else '13–17' if age<=17 else '18+'
                    buckets[key]+=1
                rows=[dict(age_range=key,students=count) for key,count in buckets.items()]
            elif kind=='teachers':
                rows=[dict(teacher=row['full_name'],member_no=row['member_no'],class_name=row['class_name'],role=row['role_label'],start_date=row['start_date'],end_date=row['end_date'] or '')
                    for row in SundaySchoolService._teachers(db,access,class_id)]
            elif kind=='unassigned':
                if not access.global_access: raise SundaySchoolDenied('Unassigned-student reports require Sunday School-wide access.')
                current=select(Enrollment.id).where(Enrollment.member_id==Student.member_id,Enrollment.is_current.is_(True)).correlate(Student).exists()
                stmt=select(Student,Member).join(Member,Member.id==Student.member_id).where(Student.status=='ACTIVE',~current)
                rows=[dict(student=member.full_name,member_no=member.member_no,age=age_on(member.date_of_birth,today()),admission_date=student.admission_date) for student,member in db.execute(stmt.order_by(Member.last_name,Member.id))]
            elif kind=='lessons':
                stmt=select(Lesson.title,Lesson.lesson_date,func.count(Session.id)).join(Session,Session.lesson_id==Lesson.id).where(Session.state=='CLOSED')
                stmt=self._period(access.restrict(stmt,Session.class_id),start_date,end_date)
                if class_id: stmt=stmt.where(Session.class_id==identifier(class_id))
                rows=[dict(lesson=title,lesson_date=selected_date,class_sessions_delivered=count) for title,selected_date,count in db.execute(stmt.group_by(Lesson.id).order_by(Lesson.lesson_date.desc()))]
            else:
                stmt=select(Member.id,Member.first_name,Member.middle_name,Member.last_name,Member.member_no,
                    Session.session_date,SchoolClass.name,Record.status).select_from(Roster).join(Session,Session.id==Roster.session_id)\
                    .join(SchoolClass,SchoolClass.id==Session.class_id).join(Member,Member.id==Roster.member_id)\
                    .outerjoin(Record,(Record.session_id==Roster.session_id)&(Record.member_id==Roster.member_id)).where(Session.state=='CLOSED')
                stmt=self._period(access.restrict(stmt,Session.class_id),start_date,end_date)
                if class_id: stmt=stmt.where(Session.class_id==identifier(class_id))
                grouped={}
                for mid,first,middle,last,number,selected_date,classname,status in db.execute(stmt.order_by(Session.session_date)):
                    key=(mid,) if kind in ('students','absence') else (selected_date,classname) if kind=='dates' else (selected_date,)
                    group=grouped.setdefault(key,dict(student=' '.join(p for p in (first,middle,last) if p),member_no=number) if kind in ('students','absence') else
                        dict(date=selected_date,class_name=classname) if kind=='dates' else dict(date=selected_date))
                    group['eligible']=group.get('eligible',0)+1
                    for code in ('present','late','excused','absent'): group[code]=group.get(code,0)+int((status or 'ABSENT').lower()==code)
                for group in grouped.values():
                    denominator=group['eligible']-group['excused']
                    group['rate']=round(100*(group['present']+group['late'])/denominator,1) if denominator else None
                rows=list(grouped.values())
                if kind=='absence':
                    try: threshold=max(1,int(absence_threshold))
                    except (ValueError,TypeError) as exc: raise SundaySchoolError('Use a positive absence threshold.') from exc
                    rows=[row for row in rows if row['absent']>=threshold]
            columns=list(rows[0]) if rows else {'enrollment':['class_name','students','teachers','capacity','room','status'],
                'class_size':['class_name','students','teachers','capacity','room','status'],'ages':['age_range','students'],
                'teachers':['teacher','member_no','class_name','role','start_date','end_date'],
                'unassigned':['student','member_no','age','admission_date'],'lessons':['lesson','lesson_date','class_sessions_delivered']}.get(kind,
                ['student','member_no','eligible','present','late','excused','absent','rate'] if kind in ('students','absence') else ['date','eligible','present','late','excused','absent','rate'])
            limit,offset=page_bounds(limit,offset)
            return dict(total=len(rows),columns=columns,rows=rows[offset:offset+limit])

    def export_csv(self,kind='enrollment',**filters):
        with self._db('SUNDAY_SCHOOL_REPORT_EXPORT') as (db,access): access.require('SUNDAY_SCHOOL_REPORT_VIEW')
        output=io.StringIO(newline=''); writer=csv.writer(output); offset=0
        while True:
            page=self.report(kind,limit=100,offset=offset,**filters)
            if not offset: writer.writerow(page['columns'])
            for row in page['rows']:
                values=[]
                for column in page['columns']:
                    value='' if row[column] is None else str(row[column])
                    if value.lstrip().startswith(('=','+','-','@')): value="'"+value
                    values.append(value)
                writer.writerow(values)
            offset+=len(page['rows'])
            if offset>=page['total'] or not page['rows']: break
        return output.getvalue()

    def dashboard(self,class_id=None):
        with self._db('SUNDAY_SCHOOL_CLASS_VIEW') as (db,access):
            class_query=access.restrict(select(SchoolClass.id),SchoolClass.id)
            if class_id is not None:
                selected=self._class(db,access,class_id)
                class_query=class_query.where(SchoolClass.id == selected.id)
            classes=class_query.subquery()
            class_count=db.scalar(select(func.count()).select_from(classes))
            active_classes=db.scalar(select(func.count()).select_from(SchoolClass).where(SchoolClass.id.in_(select(classes.c.id)),SchoolClass.status=='ACTIVE'))
            student_scope=self.member_clause(access) if class_id is None else select(Enrollment.id).where(Enrollment.member_id==Student.member_id,Enrollment.is_current.is_(True),Enrollment.class_id.in_(select(classes.c.id))).correlate(Student).exists()
            students=db.scalar(select(func.count()).select_from(Student).where(Student.status=='ACTIVE',student_scope)) if access.has('SUNDAY_SCHOOL_STUDENT_VIEW') else None
            teachers=db.scalar(select(func.count(func.distinct(Teacher.member_id))).where(Teacher.is_current.is_(True),Teacher.class_id.in_(select(classes.c.id)))) if access.has('SUNDAY_SCHOOL_TEACHER_VIEW') else None
            unassigned=db.scalar(select(func.count()).select_from(Student).where(Student.status=='ACTIVE',~select(Enrollment.id).where(Enrollment.member_id==Student.member_id,Enrollment.is_current.is_(True)).correlate(Student).exists())) if class_id is None and access.global_access and access.has('SUNDAY_SCHOOL_STUDENT_VIEW') else None
            last_sunday=today()-timedelta(days=(today().weekday()+1)%7)
            present=db.scalar(select(func.count(func.distinct(Record.member_id))).join(Session,Session.id==Record.session_id).where(Session.class_id.in_(select(classes.c.id)),
                Session.state=='CLOSED',Session.session_date==last_sunday,Record.status.in_(['PRESENT','LATE']))) if access.has('SUNDAY_SCHOOL_ATTENDANCE_VIEW') else None
            absent=db.scalar(select(func.count(func.distinct(Record.member_id))).join(Session,Session.id==Record.session_id).where(Session.class_id.in_(select(classes.c.id)),
                Session.state=='CLOSED',Session.session_date==last_sunday,Record.status=='ABSENT')) if access.has('SUNDAY_SCHOOL_ATTENDANCE_VIEW') else None
            totals=db.execute(select(func.count(),func.count().filter(Record.status.in_(['PRESENT','LATE'])),func.count().filter(Record.status=='EXCUSED')).select_from(Roster)
                .join(Session,Session.id==Roster.session_id).outerjoin(Record,(Record.session_id==Roster.session_id)&(Record.member_id==Roster.member_id))
                .where(Session.state=='CLOSED',Session.class_id.in_(select(classes.c.id)),Session.session_date>=today()-timedelta(days=30))).one() if access.has('SUNDAY_SCHOOL_ATTENDANCE_VIEW') else (0,0,0)
            denominator=totals[0]-totals[2]
            rate=round(100*totals[1]/denominator,1) if denominator else None
            attendance=[]
            if access.has('SUNDAY_SCHOOL_ATTENDANCE_VIEW'):
                stmt=select(SchoolClass.name,Session.session_date,func.count(Roster.member_id),func.count().filter(Record.status.in_(['PRESENT','LATE'])))\
                    .join(Session,Session.class_id==SchoolClass.id).join(Roster,Roster.session_id==Session.id)\
                    .outerjoin(Record,(Record.session_id==Roster.session_id)&(Record.member_id==Roster.member_id)).where(Session.state=='CLOSED')
                stmt=stmt.where(SchoolClass.id.in_(select(classes.c.id))).group_by(SchoolClass.id,Session.id).order_by(Session.session_date.desc()).limit(5)
                attendance=[dict(class_name=name,date=selected_date,eligible=count,present=marked) for name,selected_date,count,marked in db.execute(stmt)]
            absences=[]
            if access.has('SUNDAY_SCHOOL_STUDENT_VIEW') and access.has('SUNDAY_SCHOOL_ATTENDANCE_VIEW'):
                stmt=access.restrict(select(Member,Session.session_date,SchoolClass.name).join(Record,Record.member_id==Member.id).join(Session,Session.id==Record.session_id)
                    .join(SchoolClass,SchoolClass.id==Session.class_id).where(Session.state=='CLOSED',Record.status=='ABSENT'),Session.class_id)
                stmt=stmt.where(Session.class_id.in_(select(classes.c.id)))
                absences=[dict(student=member.full_name,class_name=name,date=selected_date) for member,selected_date,name in db.execute(stmt.order_by(Session.session_date.desc()).limit(5))]
            return dict(students=students,classes=class_count,active_classes=active_classes,teachers=teachers,present_last_sunday=present,absent_last_sunday=absent,last_sunday=last_sunday,rate=rate,
                students_without_class=unassigned,class_attendance=attendance,recent_absences=absences)

    def online_attendance_report(self,kind='classes',class_id=None,start_date=None,end_date=None,limit=25,offset=0):
        """Bounded SQL aggregates for portal reports, using the existing scope."""
        if kind not in ('classes','dates','students'):raise SundaySchoolError('Choose a supported attendance report.')
        if start_date and end_date and start_date>end_date:raise SundaySchoolError('Report dates are invalid.')
        with self._db('SUNDAY_SCHOOL_REPORT_VIEW') as (db,access):
            access.require('SUNDAY_SCHOOL_ATTENDANCE_VIEW')
            if kind=='students':access.require('SUNDAY_SCHOOL_STUDENT_VIEW')
            else:access.require('SUNDAY_SCHOOL_CLASS_VIEW')
            if class_id:self._class(db,access,class_id)
            keys=[SchoolClass.id.label('id'),SchoolClass.name.label('label')] if kind=='classes' else [
                Session.session_date.label('date')] if kind=='dates' else [Member.id.label('id'),
                func.concat_ws(' ',Member.first_name,Member.middle_name,Member.last_name).label('label'),Member.member_no.label('member_no')]
            stmt=select(*keys,func.count().label('eligible'),
                func.count().filter(Record.status=='PRESENT').label('present'),
                func.count().filter(Record.status=='LATE').label('late'),
                func.count().filter(Record.status=='EXCUSED').label('excused'),
                func.count().filter(Record.status=='ABSENT').label('absent')).select_from(Roster)\
                .join(Session,Session.id==Roster.session_id).join(SchoolClass,SchoolClass.id==Session.class_id)\
                .join(Member,Member.id==Roster.member_id).outerjoin(Record,(Record.session_id==Roster.session_id)&(Record.member_id==Roster.member_id))\
                .where(Session.state=='CLOSED')
            stmt=self._period(access.restrict(stmt,Session.class_id),start_date,end_date)
            if class_id:stmt=stmt.where(Session.class_id==identifier(class_id))
            stmt=stmt.group_by(*keys)
            total=db.scalar(select(func.count()).select_from(stmt.subquery()))
            limit,offset=page_bounds(limit,offset)
            rows=[]
            for result in db.execute(stmt.order_by(*keys).limit(limit).offset(offset)).mappings():
                row=dict(result)
                if kind=='dates':row['label']=row['date'].isoformat();row.pop('date')
                row['id']=str(row.get('id') or row['label'])
                denominator=row['eligible']-row['excused']
                row['rate']=round(100*(row['present']+row['late'])/denominator,1) if denominator else None
                rows.append(row)
            return dict(total=total,rows=rows)


    def online_attendance_csv(self,kind='classes',**filters):
        with self._db('SUNDAY_SCHOOL_REPORT_EXPORT') as (db,access):
            access.require('SUNDAY_SCHOOL_REPORT_VIEW')
        columns=['label','member_no','eligible','present','late','excused','absent','rate']
        output=io.StringIO(newline='');writer=csv.writer(output);writer.writerow(columns);offset=0
        while True:
            page=self.online_attendance_report(kind,limit=100,offset=offset,**filters)
            for row in page['rows']:
                cells=[]
                for column in columns:
                    value='' if row.get(column) is None else str(row[column])
                    if value.lstrip().startswith(('=','+','-','@')):value="'"+value
                    cells.append(value)
                writer.writerow(cells)
            offset+=len(page['rows'])
            if not page['rows'] or offset>=page['total']:break
        return output.getvalue()
