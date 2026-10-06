"""Classes, admission, class history, teachers and explicit guardian preferences."""
import re
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import aliased
from src.models import (Member, MemberStatus, HouseholdMember, Household,
    SundaySchoolClass as SchoolClass, SundaySchoolStudent as Student, SundaySchoolEnrollment as Enrollment,
    SundaySchoolTeacherAssignment as Teacher, SundaySchoolGuardian as Guardian,
    SundaySchoolLessonClass as LessonClass, SundaySchoolAttendanceSession as Session,
    SundaySchoolUserClassScope as ClassScope, SundaySchoolRosterMember as Roster,
    SundaySchoolAttendanceRecord as Record)
from src.security.sunday_school_permissions import TEACHER_ROLES, GUARDIAN_RELATIONSHIPS
from src.services.sunday_school_base import (SundaySchoolBase, SundaySchoolError, SundaySchoolDenied,
    EnrollmentMoveRequired, AgeRangeWarning, identifier, school_date, text_value, version,
    today, age_on, search_pattern, page_bounds)


class SundaySchoolService(SundaySchoolBase):
    @staticmethod
    def class_values(data):
        name, code = text_value(data.get('name'),150), str(data.get('code') or '').strip().upper()
        if not name: raise SundaySchoolError('Enter a class name.')
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,59}',code): raise SundaySchoolError('Use a class code starting with a letter, followed by letters, digits or underscores.')
        status = str(data.get('status','ACTIVE')).upper()
        if status not in ('ACTIVE','INACTIVE'): raise SundaySchoolError('Choose an active or inactive class status.')
        values = dict(name=name, code=code, status=status, description=text_value(data.get('description')),
            room_location=text_value(data.get('room_location'),150))
        for field in ('minimum_age','maximum_age','capacity','teacher_capacity','sort_order'):
            raw = data.get(field,0 if field=='sort_order' else None)
            try: value = None if raw in (None,'') else int(str(raw))
            except (ValueError,TypeError) as exc: raise SundaySchoolError('Enter whole numbers for ages, capacity and display order.') from exc
            if field=='sort_order' and (value is None or not 0<=value<=2147483647): raise SundaySchoolError('Display order must be a non-negative number.')
            if field in ('minimum_age','maximum_age') and value is not None and not 0<=value<=125: raise SundaySchoolError('Recommended ages must be between 0 and 125.')
            if field in ('capacity','teacher_capacity') and value is not None and not 1<=value<=2147483647: raise SundaySchoolError('Capacity must be positive or blank for unlimited.')
            values[field] = value
        if values['minimum_age'] is not None and values['maximum_age'] is not None and values['minimum_age']>values['maximum_age']:
            raise SundaySchoolError('Maximum age must be at least the minimum age.')
        return values

    @staticmethod
    def _class_query():
        students = select(Enrollment.class_id,func.count().label('students')).where(Enrollment.is_current.is_(True)).group_by(Enrollment.class_id).subquery()
        teachers = select(Teacher.class_id,func.count().label('teachers')).where(Teacher.is_current.is_(True)).group_by(Teacher.class_id).subquery()
        return select(SchoolClass,func.coalesce(students.c.students,0),func.coalesce(teachers.c.teachers,0))\
            .outerjoin(students,students.c.class_id==SchoolClass.id).outerjoin(teachers,teachers.c.class_id==SchoolClass.id)

    @staticmethod
    def class_dto(row, students=0, teachers=0):
        return dict(id=str(row.id),name=row.name,code=row.code,description=row.description or '',minimum_age=row.minimum_age,
            maximum_age=row.maximum_age,room_location=row.room_location or '',capacity=row.capacity,teacher_capacity=row.teacher_capacity,
            status=row.status,sort_order=row.sort_order,students=students,teachers=teachers,updated_at=row.updated_at,created_at=row.created_at)

    def capabilities(self):
        with self._db() as (db,access):
            return dict(permissions=sorted(access.permissions),view_all=access.global_access,class_ids=[str(cid) for cid in access.class_ids],
                member_search=access.has('MEMBERS_VIEW_ALL'),register_member=access.has('MEMBERS_VIEW_ALL') and access.has('MEMBERS_CREATE'),
                **{key:access.has('SUNDAY_SCHOOL_'+code) for key,code in (
                    ('class_view','CLASS_VIEW'),('class_create','CLASS_CREATE'),('class_edit','CLASS_EDIT'),('class_archive','CLASS_ARCHIVE'),
                    ('class_delete','CLASS_DELETE_UNUSED'),('student_view','STUDENT_VIEW'),('student_enroll','STUDENT_ENROLL'),('student_move','STUDENT_MOVE'),
                    ('student_end','STUDENT_END'),('student_edit','STUDENT_EDIT'),('guardian_view','GUARDIAN_VIEW'),('guardian_manage','GUARDIAN_MANAGE'),
                    ('teacher_view','TEACHER_VIEW'),('teacher_assign','TEACHER_ASSIGN'),('teacher_end','TEACHER_END'),
                    ('lesson_view','LESSON_VIEW'),('lesson_create','LESSON_CREATE'),('lesson_edit','LESSON_EDIT'),
                    ('attendance_view','ATTENDANCE_VIEW'),('attendance_create','ATTENDANCE_CREATE'),('attendance_record','ATTENDANCE_RECORD'),
                    ('attendance_correct','ATTENDANCE_CORRECT'),('attendance_close','ATTENDANCE_CLOSE'),('attendance_reopen','ATTENDANCE_REOPEN'),
                    ('report_view','REPORT_VIEW'),('report_export','REPORT_EXPORT'))})

    def list_classes(self, search='',status='ALL',limit=100,offset=0,*,class_id=None):
        with self._db('SUNDAY_SCHOOL_CLASS_VIEW') as (db,access):
            stmt = access.restrict(self._class_query(),SchoolClass.id)
            if class_id:
                self._class(db,access,class_id)
                stmt=stmt.where(SchoolClass.id==identifier(class_id))
            if status.upper()!='ALL': stmt=stmt.where(SchoolClass.status==status.upper())
            if search.strip():
                pattern=search_pattern(search); stmt=stmt.where(or_(SchoolClass.name.ilike(pattern),SchoolClass.code.ilike(pattern),SchoolClass.room_location.ilike(pattern)))
            total=db.scalar(select(func.count()).select_from(stmt.subquery())); limit,offset=page_bounds(limit,offset)
            rows=db.execute(stmt.order_by(SchoolClass.sort_order,func.lower(SchoolClass.name),SchoolClass.id).limit(limit).offset(offset))
            return dict(total=total,rows=[self.class_dto(*row) for row in rows])

    def get_class(self,class_id):
        with self._db('SUNDAY_SCHOOL_CLASS_VIEW') as (db,access):
            row=self._class(db,access,class_id)
            return self.class_dto(*db.execute(self._class_query().where(SchoolClass.id==row.id)).one())

    def class_options(self,limit=100,offset=0):
        with self._db() as (db,access):
            if not any(access.has('SUNDAY_SCHOOL_'+suffix) for suffix in ('CLASS_VIEW','STUDENT_VIEW','STUDENT_ENROLL','TEACHER_VIEW','TEACHER_ASSIGN','LESSON_VIEW','LESSON_CREATE','ATTENDANCE_VIEW','ATTENDANCE_CREATE','REPORT_VIEW')):
                return dict(total=0,rows=[])
            stmt=access.restrict(select(SchoolClass),SchoolClass.id)
            total=db.scalar(select(func.count()).select_from(stmt.subquery()));limit,offset=page_bounds(limit,offset)
            return dict(total=total,rows=[dict(id=str(row.id),name=row.name,code=row.code,status=row.status) for row in db.scalars(stmt.order_by(SchoolClass.sort_order,SchoolClass.name,SchoolClass.id).limit(limit).offset(offset))])

    def create_class(self,data):
        values=self.class_values(data)
        with self._db('SUNDAY_SCHOOL_CLASS_CREATE',True) as (db,access):
            if not access.global_access: raise SundaySchoolDenied('Class creation requires Sunday School-wide access.')
            row=SchoolClass(**values,created_by_user_id=access.user_id,updated_by_user_id=access.user_id)
            db.add(row); db.flush()
            self.audit(db,access,'CLASS_CREATED',class_id=row.id,new=dict(name=row.name,code=row.code,status=row.status))
            db.commit(); return self.class_dto(row)

    def update_class(self,class_id,data,expected_updated_at=None):
        values=self.class_values(data)
        with self._db('SUNDAY_SCHOOL_CLASS_EDIT',True) as (db,access):
            row=self._class(db,access,class_id); version(row,expected_updated_at)
            students=db.scalar(select(func.count()).select_from(Enrollment).where(Enrollment.class_id==row.id,Enrollment.is_current.is_(True)))
            teachers=db.scalar(select(func.count()).select_from(Teacher).where(Teacher.class_id==row.id,Teacher.is_current.is_(True)))
            if values['capacity'] is not None and students>values['capacity']: raise SundaySchoolError('Move or end enrollments before reducing student capacity.')
            if values['teacher_capacity'] is not None and teachers>values['teacher_capacity']: raise SundaySchoolError('End teacher assignments before reducing teacher capacity.')
            if values['code']!=row.code and (db.scalar(select(Enrollment.id).where(Enrollment.class_id==row.id).limit(1)) or db.scalar(select(Session.id).where(Session.class_id==row.id).limit(1))):
                raise SundaySchoolError('The class code is locked because class history exists.')
            if values['status']!=row.status: access.require('SUNDAY_SCHOOL_CLASS_ARCHIVE')
            old=dict(name=row.name,code=row.code,status=row.status)
            changed=[field for field,value in values.items() if getattr(row,field)!=value]
            for field,value in values.items(): setattr(row,field,value)
            row.updated_at=datetime.now(timezone.utc); row.updated_by_user_id=access.user_id
            self.audit(db,access,'CLASS_UPDATED',class_id=row.id,old=old,new=dict(name=row.name,code=row.code,status=row.status,changed_fields=changed))
            db.commit(); return self.class_dto(row,students,teachers)

    def set_class_status(self,class_id,status,expected_updated_at=None):
        status=str(status).upper()
        if status not in ('ACTIVE','INACTIVE'): raise SundaySchoolError('Choose an active or inactive class status.')
        with self._db('SUNDAY_SCHOOL_CLASS_ARCHIVE',True) as (db,access):
            row=self._class(db,access,class_id); version(row,expected_updated_at)
            old=row.status; row.status=status; row.updated_at=datetime.now(timezone.utc); row.updated_by_user_id=access.user_id
            self.audit(db,access,'CLASS_UPDATED',class_id=row.id,old={'status':old},new={'status':status})
            db.commit()

    def delete_unused_class(self,class_id,confirmed=False,expected_updated_at=None):
        with self._db('SUNDAY_SCHOOL_CLASS_DELETE_UNUSED',True) as (db,access):
            row=self._class(db,access,class_id); version(row,expected_updated_at)
            if confirmed is not True: raise SundaySchoolError('Confirm permanent deletion of this unused class.')
            if any(db.scalar(select(model.class_id).where(model.class_id==row.id).limit(1)) for model in (Enrollment,Teacher,Session,LessonClass,ClassScope)):
                raise SundaySchoolError('This class has history or dependencies. Deactivate it instead.')
            self.audit(db,access,'CLASS_DELETED_UNUSED',class_id=row.id,old={'name':row.name,'code':row.code})
            db.delete(row); db.commit()

    @staticmethod
    def _student_query():
        current=aliased(Enrollment)
        return select(Student,Member,current,SchoolClass).join(Member,Member.id==Student.member_id).outerjoin(
            current,(current.member_id==Student.member_id)&current.is_current.is_(True)).outerjoin(SchoolClass,SchoolClass.id==current.class_id)

    @staticmethod
    def _guardian_search(pattern,member_column=Member.id):
        guardian=aliased(Member)
        explicit=select(Guardian.id).join(Student,Student.id==Guardian.student_id).join(guardian,guardian.id==Guardian.guardian_member_id).where(
            Student.member_id==member_column,Guardian.is_active.is_(True),or_(guardian.phone.ilike(pattern),guardian.alternate_phone.ilike(pattern),
                func.concat_ws(' ',guardian.first_name,guardian.middle_name,guardian.last_name).ilike(pattern))).correlate(Member).exists()
        return explicit

    def list_students(self,search='',class_id=None,status='ACTIVE',minimum_age=None,maximum_age=None,gender=None,without_class=False,limit=25,offset=0):
        with self._db('SUNDAY_SCHOOL_STUDENT_VIEW') as (db,access):
            stmt=self._student_query().where(self.member_clause(access))
            if status.upper()!='ALL': stmt=stmt.where(Student.status==status.upper())
            if class_id: self._class(db,access,class_id); stmt=stmt.where(SchoolClass.id==identifier(class_id))
            if without_class:
                if not access.global_access: raise SundaySchoolDenied('Unassigned students require Sunday School-wide access.')
                stmt=stmt.where(SchoolClass.id.is_(None))
            if gender:
                if not access.global_access: raise SundaySchoolDenied('Gender filtering requires Sunday School-wide access.')
                if gender.upper() not in ('MALE','FEMALE'): raise SundaySchoolError('Choose a valid gender filter.')
                stmt=stmt.where(Member.gender==gender.upper())
            age_expr=func.extract('year',func.age(today(),Member.date_of_birth))
            if minimum_age not in (None,''): stmt=stmt.where(age_expr>=int(minimum_age))
            if maximum_age not in (None,''): stmt=stmt.where(age_expr<=int(maximum_age))
            if search.strip():
                pattern=search_pattern(search)
                filters=[func.concat_ws(' ',Member.first_name,Member.middle_name,Member.last_name).ilike(pattern),Member.member_no.ilike(pattern)]
                if access.has('SUNDAY_SCHOOL_GUARDIAN_VIEW'): filters.append(self._guardian_search(pattern))
                stmt=stmt.where(or_(*filters))
            total=db.scalar(select(func.count()).select_from(stmt.subquery())); limit,offset=page_bounds(limit,offset)
            rows=db.execute(stmt.order_by(Member.last_name,Member.first_name,Student.id).limit(limit).offset(offset)).all()
            ids=[member.id for _student,member,_enrollment,_class in rows]
            households,guardians=self.household_map(db,ids),self.guardian_map(db,access,ids)
            return dict(total=total,rows=[dict(self.member_dto(member),student_id=str(student.id),status=student.status,admission_date=student.admission_date,
                class_id=str(school_class.id) if school_class else None,class_name=school_class.name if school_class else '',
                enrollment_id=str(enrollment.id) if enrollment else None,start_date=enrollment.start_date if enrollment else None,
                **self.contact_fields(member.id,households,guardians)) for student,member,enrollment,school_class in rows])

    def candidate_members(self,search='',limit=20,offset=0):
        with self._db('SUNDAY_SCHOOL_STUDENT_ENROLL') as (db,access):
            access.require('MEMBERS_VIEW_ALL')
            stmt=select(Member).where(Member.status==MemberStatus.ACTIVE)
            if search.strip():
                pattern=search_pattern(search)
                family=aliased(HouseholdMember); contact=aliased(Member)
                child_family=aliased(HouseholdMember)
                family_contact=select(child_family.id).join(family,family.household_id==child_family.household_id).join(contact,contact.id==family.member_id).where(
                    child_family.member_id==Member.id,child_family.is_active.is_(True),family.is_active.is_(True),
                    or_(contact.phone.ilike(pattern),contact.alternate_phone.ilike(pattern))).correlate(Member).exists()
                stmt=stmt.where(or_(func.concat_ws(' ',Member.first_name,Member.middle_name,Member.last_name).ilike(pattern),Member.member_no.ilike(pattern),
                    Member.phone.ilike(pattern),self._guardian_search(pattern),family_contact))
            total=db.scalar(select(func.count()).select_from(stmt.subquery())); limit,offset=page_bounds(limit,offset)
            members=db.scalars(stmt.order_by(Member.last_name,Member.first_name,Member.id).limit(limit).offset(offset)).all()
            households=self.household_map(db,[member.id for member in members])
            return dict(total=total,rows=[dict(self.member_dto(member),household=households.get(member.id)) for member in members])

    def candidate_teachers(self,search='',limit=20,offset=0):
        with self._db('SUNDAY_SCHOOL_TEACHER_ASSIGN') as (db,access):
            access.require('MEMBERS_VIEW_ALL')
            stmt=select(Member).where(Member.status==MemberStatus.ACTIVE)
            if search:
                pattern=search_pattern(search); stmt=stmt.where(or_(func.concat_ws(' ',Member.first_name,Member.middle_name,Member.last_name).ilike(pattern),Member.member_no.ilike(pattern),Member.phone.ilike(pattern)))
            total=db.scalar(select(func.count()).select_from(stmt.subquery())); limit,offset=page_bounds(limit,offset)
            return dict(total=total,rows=[self.member_dto(member) for member in db.scalars(stmt.order_by(Member.last_name,Member.id).limit(limit).offset(offset))])

    def _register(self,db,access,member_id,admission_date=None,notes=None,existing_only=False):
        if not existing_only: access.require('MEMBERS_VIEW_ALL')
        member=db.get(Member,identifier(member_id))
        if not member or member.status!=MemberStatus.ACTIVE: raise SundaySchoolError('Choose an existing active Member.')
        student=db.scalar(select(Student).where(Student.member_id==member.id))
        if not student:
            if existing_only: raise SundaySchoolError('The existing student admission changed. Refresh before moving.')
            student=Student(member_id=member.id,admission_date=admission_date or today(),special_notes=notes)
            db.add(student); db.flush(); self.audit(db,access,'STUDENT_REGISTERED',member_id=member.id,new={'student_id':str(student.id)})
        if student.status!='ACTIVE': raise SundaySchoolError('Reactivate the Sunday School student before enrolling.')
        return student,member

    def register_student(self,member_id,admission_date=None,special_notes=''):
        with self._db('SUNDAY_SCHOOL_STUDENT_ENROLL',True) as (db,access):
            if not access.global_access: raise SundaySchoolDenied('Unassigned admission requires Sunday School-wide access.')
            student,member=self._register(db,access,member_id,school_date(admission_date or today()),text_value(special_notes))
            db.commit(); return dict(self.member_dto(member),student_id=str(student.id),status=student.status)

    def _enroll(self,db,access,class_id,member_id,start_date,notes,allow_age_override,existing_only=False):
        school_class=self._class(db,access,class_id,active=True)
        student,member=self._register(db,access,member_id,start_date,existing_only=existing_only)
        current=db.scalar(select(Enrollment).where(Enrollment.member_id==member.id,Enrollment.is_current.is_(True)))
        if current:
            if current.class_id==school_class.id: raise SundaySchoolError('This student is already enrolled in this class.')
            if not access.contains(current.class_id): raise SundaySchoolDenied('The existing class is outside your assigned access.')
            raise EnrollmentMoveRequired(dict(id=str(current.id),class_id=str(current.class_id),class_name=current.class_name,updated_at=current.updated_at))
        count=db.scalar(select(func.count()).select_from(Enrollment).where(Enrollment.class_id==school_class.id,Enrollment.is_current.is_(True)))
        if school_class.capacity is not None and count>=school_class.capacity: raise SundaySchoolError('This class has reached its student capacity.')
        last_end=db.scalar(select(func.max(Enrollment.end_date)).where(Enrollment.member_id==member.id))
        if last_end and start_date<last_end: raise SundaySchoolError('Enrollment cannot start before the previous class exit.')
        age=age_on(member.date_of_birth,start_date)
        outside=age is not None and ((school_class.minimum_age is not None and age<school_class.minimum_age) or (school_class.maximum_age is not None and age>school_class.maximum_age))
        if not isinstance(allow_age_override,bool): raise SundaySchoolError('Confirm an explicit age-range choice.')
        if outside and not allow_age_override: raise AgeRangeWarning(member.full_name,school_class.name,age)
        row=Enrollment(class_id=school_class.id,member_id=member.id,class_name=school_class.name,class_code=school_class.code,start_date=start_date,notes=notes)
        db.add(row); db.flush()
        self.audit(db,access,'STUDENT_ENROLLED',class_id=school_class.id,member_id=member.id,new={'enrollment_id':str(row.id),'start_date':start_date.isoformat(),'age_override':outside})
        return dict(id=str(row.id),class_id=str(school_class.id),class_name=school_class.name,member_id=str(member.id),updated_at=row.updated_at)

    def enroll_student(self,class_id,member_id,start_date=None,notes='',allow_age_override=False):
        start=school_date(start_date or today())
        with self._db('SUNDAY_SCHOOL_STUDENT_ENROLL',True) as (db,access):
            result=self._enroll(db,access,class_id,member_id,start,text_value(notes),allow_age_override); db.commit(); return result

    @classmethod
    def _end_enrollment(cls,db,access,row,effective,reason=''):
        if not row.is_current: raise SundaySchoolError('This enrollment is already historical.')
        if effective<row.start_date: raise SundaySchoolError('End date cannot precede enrollment.')
        row.is_current=False; row.end_date=effective; row.status='ENDED'; row.updated_at=datetime.now(timezone.utc)
        cls.audit(db,access,'STUDENT_ENROLLMENT_ENDED',class_id=row.class_id,member_id=row.member_id,new={'enrollment_id':str(row.id),'end_date':effective.isoformat()})
        if reason: row.notes=text_value(((row.notes or '')+'\n'+reason).strip())
        db.flush()

    def end_enrollment(self,enrollment_id,effective_date,reason='',expected_updated_at=None):
        effective=school_date(effective_date)
        with self._db('SUNDAY_SCHOOL_STUDENT_END',True) as (db,access):
            row=db.get(Enrollment,identifier(enrollment_id))
            if not row: raise SundaySchoolError('Enrollment not found.')
            self._class(db,access,row.class_id); version(row,expected_updated_at)
            self._end_enrollment(db,access,row,effective,text_value(reason)); db.commit()

    def move_student(self,enrollment_id,target_class_id,effective_date,notes='',allow_age_override=False,expected_updated_at=None):
        effective=school_date(effective_date)
        with self._db('SUNDAY_SCHOOL_STUDENT_MOVE',True) as (db,access):
            row=db.get(Enrollment,identifier(enrollment_id))
            if not row: raise SundaySchoolError('Enrollment not found.')
            self._class(db,access,row.class_id); self._class(db,access,target_class_id,active=True); version(row,expected_updated_at)
            if row.class_id==identifier(target_class_id): raise SundaySchoolError('Choose a different class.')
            source=row.class_id; self._end_enrollment(db,access,row,effective)
            result=self._enroll(db,access,target_class_id,row.member_id,effective,text_value(notes),allow_age_override,existing_only=True)
            self.audit(db,access,'STUDENT_MOVED',class_id=identifier(target_class_id),member_id=row.member_id,old={'class_id':str(source),'enrollment_id':str(row.id)},new={'class_id':str(target_class_id),'enrollment_id':result['id'],'effective_date':effective.isoformat()})
            db.commit(); return result

    def get_student(self,member_id):
        with self._db('SUNDAY_SCHOOL_STUDENT_VIEW') as (db,access):
            student=self._student(db,access,member_id); member=db.get(Member,student.member_id)
            current=db.scalar(select(Enrollment).where(Enrollment.member_id==member.id,Enrollment.is_current.is_(True)))
            cls=db.get(SchoolClass,current.class_id) if current else None
            result=dict(self.member_dto(member),student_id=str(student.id),status=student.status,admission_date=student.admission_date,
                special_notes=student.special_notes or '' if access.global_access and access.has('SUNDAY_SCHOOL_STUDENT_EDIT') else '',
                class_id=str(cls.id) if cls else None,class_name=cls.name if cls else '',enrollment_id=str(current.id) if current else None,
                enrollment_updated_at=current.updated_at if current else None,start_date=current.start_date if current else None,updated_at=student.updated_at)
            result.update(self.contact_fields(member.id,self.household_map(db,[member.id]),self.guardian_map(db,access,[member.id])))
            history=access.restrict(select(Enrollment).where(Enrollment.member_id==member.id),Enrollment.class_id)
            result['history']=[dict(id=str(row.id),class_id=str(row.class_id),class_name=row.class_name,start_date=row.start_date,end_date=row.end_date,is_current=row.is_current) for row in db.scalars(history.order_by(Enrollment.start_date.desc(),Enrollment.id).limit(100))]
            result['teachers']=self._teachers(db,access,current.class_id) if current and access.has('SUNDAY_SCHOOL_TEACHER_VIEW') else []
            result['attendance_rate']=None
            if access.has('SUNDAY_SCHOOL_ATTENDANCE_VIEW'):
                stmt=select(func.count(),func.count().filter(Record.status.in_(['PRESENT','LATE'])),func.count().filter(Record.status=='EXCUSED')).select_from(Roster).join(Session,Session.id==Roster.session_id)\
                    .outerjoin(Record,(Record.session_id==Roster.session_id)&(Record.member_id==Roster.member_id)).where(Roster.member_id==member.id,Session.state=='CLOSED')
                count,present,excused=db.execute(access.restrict(stmt,Session.class_id)).one()
                result['attendance_rate']=round(100*present/(count-excused),1) if count>excused else None
            return result

    def update_student(self,member_id,status='ACTIVE',special_notes='',expected_updated_at=None):
        if status.upper() not in ('ACTIVE','INACTIVE'): raise SundaySchoolError('Choose Active or Inactive.')
        with self._db('SUNDAY_SCHOOL_STUDENT_EDIT',True) as (db,access):
            student=self._student(db,access,member_id); version(student,expected_updated_at)
            if not access.global_access: raise SundaySchoolDenied('Admission notes and status require Sunday School-wide access.')
            if status.upper()=='INACTIVE':
                current=db.scalar(select(Enrollment).where(Enrollment.member_id==student.member_id,Enrollment.is_current.is_(True)))
                if current: access.require('SUNDAY_SCHOOL_STUDENT_END'); self._end_enrollment(db,access,current,today())
            old=student.status; student.status=status.upper(); student.special_notes=text_value(special_notes); student.updated_at=datetime.now(timezone.utc)
            self.audit(db,access,'STUDENT_UPDATED',member_id=student.member_id,old={'status':old},new={'status':student.status})
            db.commit()

    def set_guardian(self,member_id,guardian_member_id,relationship='GUARDIAN',is_primary=False,can_receive_sms=False,is_active=True):
        if relationship not in GUARDIAN_RELATIONSHIPS: raise SundaySchoolError('Choose a guardian relationship.')
        if any(not isinstance(flag,bool) for flag in (is_primary,can_receive_sms,is_active)): raise SundaySchoolError('Choose explicit guardian and contact consent flags.')
        with self._db('SUNDAY_SCHOOL_GUARDIAN_MANAGE',True) as (db,access):
            access.require('MEMBERS_VIEW_ALL'); student=self._student(db,access,member_id)
            gid=identifier(guardian_member_id)
            if gid==student.member_id: raise SundaySchoolError('A student cannot be their own guardian.')
            if not db.get(Member,gid): raise SundaySchoolError('Choose an existing Member as guardian.')
            link=db.scalar(select(Guardian).where(Guardian.student_id==student.id,Guardian.guardian_member_id==gid))
            if is_primary:
                db.execute(update(Guardian).where(Guardian.student_id==student.id).values(is_primary=False)); db.flush()
            if not link: link=Guardian(student_id=student.id,guardian_member_id=gid); db.add(link)
            link.relationship=relationship; link.is_primary=is_primary if is_active else False; link.can_receive_sms=can_receive_sms; link.is_active=is_active
            link.updated_at=datetime.now(timezone.utc); db.flush()
            self.audit(db,access,'GUARDIAN_UPDATED',member_id=student.member_id,new={'guardian_member_id':str(gid),'relationship':relationship,'is_primary':link.is_primary,'can_receive_sms':can_receive_sms,'is_active':is_active})
            db.commit()

    def guardian_candidates(self,member_id,search='',limit=20,offset=0):
        with self._db('SUNDAY_SCHOOL_GUARDIAN_MANAGE') as (db,access):
            access.require('MEMBERS_VIEW_ALL'); student=self._student(db,access,member_id)
            stmt=select(Member).where(Member.id!=student.member_id)
            if search:
                pattern=search_pattern(search); stmt=stmt.where(or_(func.concat_ws(' ',Member.first_name,Member.middle_name,Member.last_name).ilike(pattern),Member.member_no.ilike(pattern),Member.phone.ilike(pattern)))
            total=db.scalar(select(func.count()).select_from(stmt.subquery())); limit,offset=page_bounds(limit,offset)
            own=db.scalar(select(HouseholdMember.household_id).where(HouseholdMember.member_id==student.member_id,HouseholdMember.is_active.is_(True)))
            in_family=select(HouseholdMember.id).where(HouseholdMember.member_id==Member.id,HouseholdMember.household_id==own,HouseholdMember.is_active.is_(True)).correlate(Member).exists()
            rows=db.execute(select(Member,in_family).where(Member.id.in_(select(stmt.subquery().c.id))).order_by(in_family.desc(),Member.last_name,Member.id).limit(limit).offset(offset))
            return dict(total=total,rows=[dict(self.member_dto(member),same_household=related,phone=member.phone or '') for member,related in rows])

    @classmethod
    def _teachers(cls,db,access,class_id=None,history=False):
        stmt=select(Teacher,Member,SchoolClass).join(Member,Member.id==Teacher.member_id).join(SchoolClass,SchoolClass.id==Teacher.class_id).where(Teacher.is_current.is_(not history))
        if class_id: stmt=stmt.where(Teacher.class_id==identifier(class_id))
        stmt=access.restrict(stmt,Teacher.class_id)
        return [dict(cls.member_dto(member),id=str(row.id),member_id=str(member.id),class_id=str(school_class.id),class_name=school_class.name,
            role=row.role,role_label=TEACHER_ROLES[row.role],start_date=row.start_date,end_date=row.end_date,is_current=row.is_current,
            updated_at=row.updated_at,phone=member.phone or '') for row,member,school_class in db.execute(stmt.order_by(SchoolClass.sort_order,Member.last_name,Teacher.id))]

    def list_teachers(self,class_id=None,history=False,search='',limit=25,offset=0):
        with self._db('SUNDAY_SCHOOL_TEACHER_VIEW') as (db,access):
            if class_id: self._class(db,access,class_id)
            stmt=access.restrict(select(Teacher,Member,SchoolClass).join(Member,Member.id==Teacher.member_id)
                .join(SchoolClass,SchoolClass.id==Teacher.class_id).where(Teacher.is_current.is_(not history)),Teacher.class_id)
            if class_id:stmt=stmt.where(Teacher.class_id==identifier(class_id))
            if search:
                pattern=search_pattern(search)
                stmt=stmt.where(or_(func.concat_ws(' ',Member.first_name,Member.middle_name,Member.last_name).ilike(pattern),Member.member_no.ilike(pattern),SchoolClass.name.ilike(pattern)))
            total=db.scalar(select(func.count()).select_from(stmt.subquery()));limit,offset=page_bounds(limit,offset)
            rows=db.execute(stmt.order_by(SchoolClass.sort_order,Member.last_name,Teacher.id).limit(limit).offset(offset))
            return dict(total=total,rows=[dict(self.member_dto(member),id=str(row.id),member_id=str(member.id),class_id=str(school_class.id),class_name=school_class.name,
                role=row.role,role_label=TEACHER_ROLES[row.role],start_date=row.start_date,end_date=row.end_date,is_current=row.is_current,
                updated_at=row.updated_at,phone=member.phone or '') for row,member,school_class in rows])

    def assign_teacher(self,class_id,member_id,role='TEACHER',start_date=None):
        if role not in TEACHER_ROLES: raise SundaySchoolError('Choose a teaching role.')
        start=school_date(start_date or today())
        with self._db('SUNDAY_SCHOOL_TEACHER_ASSIGN',True) as (db,access):
            access.require('MEMBERS_VIEW_ALL'); school_class=self._class(db,access,class_id,active=True)
            member=db.get(Member,identifier(member_id))
            if not member or member.status!=MemberStatus.ACTIVE: raise SundaySchoolError('Choose an existing active Member as teacher.')
            count=db.scalar(select(func.count()).select_from(Teacher).where(Teacher.class_id==school_class.id,Teacher.is_current.is_(True)))
            if school_class.teacher_capacity is not None and count>=school_class.teacher_capacity: raise SundaySchoolError('This class has reached its teacher capacity.')
            row=Teacher(class_id=school_class.id,member_id=member.id,role=role,start_date=start)
            db.add(row); db.flush(); self.audit(db,access,'TEACHER_ASSIGNED',class_id=school_class.id,member_id=member.id,new={'assignment_id':str(row.id),'role':role})
            db.commit(); return dict(id=str(row.id),updated_at=row.updated_at)

    def end_teacher_assignment(self,assignment_id,end_date,expected_updated_at=None):
        effective=school_date(end_date)
        with self._db('SUNDAY_SCHOOL_TEACHER_END',True) as (db,access):
            row=db.get(Teacher,identifier(assignment_id))
            if not row: raise SundaySchoolError('Teacher assignment not found.')
            self._class(db,access,row.class_id); version(row,expected_updated_at)
            if not row.is_current or effective<row.start_date: raise SundaySchoolError('Choose a current assignment and valid end date.')
            row.is_current=False; row.end_date=effective; row.updated_at=datetime.now(timezone.utc)
            self.audit(db,access,'TEACHER_ASSIGNMENT_ENDED',class_id=row.class_id,member_id=row.member_id,new={'assignment_id':str(row.id),'end_date':effective.isoformat()})
            db.commit()

    @classmethod
    def member_summaries(cls,db,auth,member_ids):
        if not auth.has_any({'SUNDAY_SCHOOL_STUDENT_VIEW','SUNDAY_SCHOOL_TEACHER_VIEW'}): return {}
        access=cls.access(db,auth.user_id,auth); result={}
        if access.has('SUNDAY_SCHOOL_STUDENT_VIEW'):
            stmt=select(Student,Enrollment,SchoolClass).outerjoin(Enrollment,(Enrollment.member_id==Student.member_id)&Enrollment.is_current.is_(True))\
                .outerjoin(SchoolClass,SchoolClass.id==Enrollment.class_id).where(Student.member_id.in_(member_ids),cls.member_clause(access))
            for student,enrollment,school_class in db.execute(stmt):
                result[student.member_id]=dict(student=True,class_id=str(school_class.id) if school_class else None,class_name=school_class.name if school_class else '',
                    start_date=enrollment.start_date if enrollment else None,status=student.status,teachers=[])
        class_ids={identifier(value['class_id']) for value in result.values() if value.get('class_id')}
        if class_ids and access.has('SUNDAY_SCHOOL_TEACHER_VIEW'):
            mapping={cid:[] for cid in class_ids}
            for cid,teacher in db.execute(select(Teacher.class_id,Member).join(Member,Member.id==Teacher.member_id).where(Teacher.class_id.in_(class_ids),Teacher.is_current.is_(True))):mapping[cid].append(teacher.full_name)
            for value in result.values():value['class_teachers']=mapping.get(identifier(value['class_id']),[]) if value.get('class_id') else []
        if result and access.has('SUNDAY_SCHOOL_ATTENDANCE_VIEW'):
            stmt=select(Roster.member_id,func.count(),func.count().filter(Record.status.in_(['PRESENT','LATE'])),func.count().filter(Record.status=='EXCUSED')).join(Session,Session.id==Roster.session_id)\
                .outerjoin(Record,(Record.session_id==Roster.session_id)&(Record.member_id==Roster.member_id)).where(Roster.member_id.in_(list(result)),Session.state=='CLOSED').group_by(Roster.member_id)
            for mid,count,present,excused in db.execute(access.restrict(stmt,Session.class_id)):result[mid]['attendance_rate']=round(100*present/(count-excused),1) if count>excused else None
        if access.has('SUNDAY_SCHOOL_TEACHER_VIEW'):
            stmt=access.restrict(select(Teacher,SchoolClass).join(SchoolClass).where(Teacher.member_id.in_(member_ids),Teacher.is_current.is_(True)),Teacher.class_id)
            for assignment,school_class in db.execute(stmt):
                result.setdefault(assignment.member_id,dict(student=False,teachers=[]))['teachers'].append(dict(class_name=school_class.name,role_label=TEACHER_ROLES[assignment.role]))
        return result

    def resolve_recipients(self,class_id=None,absent_session_id=None):
        with self._db('SUNDAY_SCHOOL_REPORT_EXPORT') as (db,access):
            access.require('SUNDAY_SCHOOL_GUARDIAN_VIEW')
            stmt=select(Student.member_id).join(Enrollment,Enrollment.member_id==Student.member_id).where(Enrollment.is_current.is_(True),Student.status=='ACTIVE')
            stmt=access.restrict(stmt,Enrollment.class_id)
            if class_id: self._class(db,access,class_id); stmt=stmt.where(Enrollment.class_id==identifier(class_id))
            if absent_session_id:
                session=db.get(Session,identifier(absent_session_id))
                if not session: raise SundaySchoolError('Attendance session not found.')
                self._class(db,access,session.class_id)
                absent=select(Record.member_id).where(Record.session_id==session.id,Record.status=='ABSENT')
                stmt=stmt.where(Student.member_id.in_(absent))
            ids=list(db.scalars(stmt)); contacts=self.guardian_map(db,access,ids); recipients={}
            for mid,guardians in contacts.items():
                for guardian in guardians:
                    if guardian['can_receive_sms'] and guardian['phone'] and guardian['member_status']!='DECEASED':
                        target=recipients.setdefault(guardian['guardian_member_id'],dict(member_id=guardian['guardian_member_id'],full_name=guardian['full_name'],phone=guardian['phone'],student_member_ids=[]))
                        target['student_member_ids'].append(str(mid))
            return list(recipients.values())
