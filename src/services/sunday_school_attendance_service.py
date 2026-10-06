"""Class-only saved rosters and auditable attendance, separate from church attendance."""
from datetime import datetime, timezone
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import aliased
from src.models import (Member, MemberStatus, User, SundaySchoolClass as SchoolClass,
    SundaySchoolStudent as Student, SundaySchoolEnrollment as Enrollment, SundaySchoolLesson as Lesson,
    SundaySchoolLessonClass as LessonClass, SundaySchoolAttendanceSession as Session,
    SundaySchoolRosterMember as Roster, SundaySchoolAttendanceRecord as Record)
from src.services.sunday_school_base import (SundaySchoolBase,SundaySchoolError,SundaySchoolDenied,
    identifier,school_date,text_value,version,today,page_bounds,search_pattern,SundaySchoolConflict,SundaySchoolNotFound)


class SundaySchoolAttendanceService(SundaySchoolBase):
    STATUSES = ('PRESENT','LATE','EXCUSED','ABSENT')

    def _session(self,db,access,session_id):
        row=db.get(Session,identifier(session_id))
        if not row: raise SundaySchoolNotFound('Sunday School attendance session not found.')
        self._class(db,access,row.class_id)
        return row

    def _open(self,db,access,row):
        self._class(db,access,row.class_id,active=True)
        if row.state!='DRAFT': raise SundaySchoolError('This attendance session has already been opened.')
        if row.session_date>today(): raise SundaySchoolError('Open class attendance on or after its scheduled date.')
        enrollments=db.scalars(select(Enrollment).join(Student,Student.member_id==Enrollment.member_id)
            .join(Member,Member.id==Enrollment.member_id).where(Enrollment.class_id==row.class_id,Enrollment.is_current.is_(True),
                Enrollment.start_date<=row.session_date,Student.status=='ACTIVE',Member.status==MemberStatus.ACTIVE)).all()
        for enrollment in enrollments: db.add(Roster(session_id=row.id,member_id=enrollment.member_id,enrollment_id=enrollment.id))
        row.state='OPEN'; row.opened_at=datetime.now(timezone.utc); row.closed_at=None; db.flush()
        self.audit(db,access,'ATTENDANCE_OPENED',class_id=row.class_id,session_id=row.id,new={'eligible':len(enrollments)})

    def create_session(self,class_id,session_date,title='',lesson_id=None,open_now=True):
        selected_date=school_date(session_date,future=True)
        if not isinstance(open_now,bool): raise SundaySchoolError('Choose whether to open attendance now.')
        with self._db('SUNDAY_SCHOOL_ATTENDANCE_CREATE',True) as (db,access):
            cls=self._class(db,access,class_id,active=True)
            if lesson_id:
                lesson=db.get(Lesson,identifier(lesson_id))
                applies=db.scalar(select(LessonClass.lesson_id).where(LessonClass.lesson_id==identifier(lesson_id),LessonClass.class_id==cls.id))
                if not lesson or lesson.status!='PUBLISHED' or not (lesson.applies_to_all or applies): raise SundaySchoolError('Choose a published lesson that applies to this class.')
                if lesson.lesson_date!=selected_date: raise SundaySchoolError('The lesson and attendance dates must match.')
            row=Session(class_id=cls.id,lesson_id=identifier(lesson_id) if lesson_id else None,session_date=selected_date,
                title=text_value(title,200) or cls.name+' Sunday School',created_by_user_id=access.user_id)
            db.add(row); db.flush()
            self.audit(db,access,'ATTENDANCE_CREATED',class_id=cls.id,session_id=row.id,new={'session_date':selected_date.isoformat(),'lesson_id':str(lesson_id) if lesson_id else None})
            if open_now: self._open(db,access,row)
            db.commit(); return dict(id=str(row.id),state=row.state,class_id=str(cls.id),session_date=row.session_date)

    def open_session(self,session_id,expected_updated_at=None):
        with self._db('SUNDAY_SCHOOL_ATTENDANCE_CREATE',True) as (db,access):
            row=self._session(db,access,session_id); version(row,expected_updated_at); self._open(db,access,row); db.commit()

    def list_sessions(self,class_id=None,search='',state='ALL',limit=25,offset=0,*,date_from=None,date_to=None):
        with self._db('SUNDAY_SCHOOL_ATTENDANCE_VIEW') as (db,access):
            counts=select(Roster.session_id,func.count().label('eligible')).group_by(Roster.session_id).subquery()
            stmt=access.restrict(select(Session,SchoolClass.name,Lesson.title,func.coalesce(counts.c.eligible,0)).join(SchoolClass)
                .outerjoin(Lesson,Lesson.id==Session.lesson_id).outerjoin(counts,counts.c.session_id==Session.id),Session.class_id)
            if class_id: self._class(db,access,class_id); stmt=stmt.where(Session.class_id==identifier(class_id))
            if date_from and date_to and date_from>date_to:raise SundaySchoolError('Attendance dates are invalid.')
            if date_from:stmt=stmt.where(Session.session_date>=date_from)
            if date_to:stmt=stmt.where(Session.session_date<=date_to)
            if state.upper()!='ALL': stmt=stmt.where(Session.state==state.upper())
            if search: stmt=stmt.where(or_(Session.title.ilike(search_pattern(search)),SchoolClass.name.ilike(search_pattern(search))))
            total=db.scalar(select(func.count()).select_from(stmt.subquery())); limit,offset=page_bounds(limit,offset)
            rows=db.execute(stmt.order_by(Session.session_date.desc(),Session.created_at.desc(),Session.id).limit(limit).offset(offset))
            return dict(total=total,rows=[dict(id=str(row.id),title=row.title,class_id=str(row.class_id),class_name=class_name,
                lesson_id=str(row.lesson_id) if row.lesson_id else None,lesson_title=lesson_title or '',session_date=row.session_date,state=row.state,eligible=eligible,
                opened_at=row.opened_at,closed_at=row.closed_at,updated_at=row.updated_at) for row,class_name,lesson_title,eligible in rows])

    @classmethod
    def _stats(cls,db,row):
        eligible=db.scalar(select(func.count()).select_from(Roster).where(Roster.session_id==row.id))
        values=dict(db.execute(select(Record.status,func.count()).where(Record.session_id==row.id).group_by(Record.status)).all())
        stats={status.lower():values.get(status,0) for status in cls.STATUSES}
        denominator=eligible-stats['excused']; stats.update(eligible=eligible,unmarked=eligible-sum(values.values()),
            rate=round(100*(stats['present']+stats['late'])/denominator,1) if denominator else None)
        return stats

    def get_session(self,session_id,*,include_teachers=True):
        with self._db('SUNDAY_SCHOOL_ATTENDANCE_VIEW') as (db,access):
            row=self._session(db,access,session_id); cls=db.get(SchoolClass,row.class_id)
            lesson=db.get(Lesson,row.lesson_id) if row.lesson_id else None
            from src.services.sunday_school_service import SundaySchoolService
            teachers=SundaySchoolService._teachers(db,access,row.class_id) if include_teachers and access.has('SUNDAY_SCHOOL_TEACHER_VIEW') else []
            return dict(id=str(row.id),class_id=str(cls.id),class_name=cls.name,title=row.title,session_date=row.session_date,state=row.state,
                lesson_title=lesson.title if lesson else '',teacher_names=', '.join(teacher['full_name'] for teacher in teachers),
                stats=self._stats(db,row),opened_at=row.opened_at,closed_at=row.closed_at,updated_at=row.updated_at,
                actions=dict(open=row.state=='DRAFT' and access.has('SUNDAY_SCHOOL_ATTENDANCE_CREATE'),
                    close=row.state=='OPEN' and access.has('SUNDAY_SCHOOL_ATTENDANCE_CLOSE'),
                    reopen=row.state=='CLOSED' and access.global_access and access.has('SUNDAY_SCHOOL_ATTENDANCE_REOPEN')))

    def get_roster(self,session_id,search='',status='ALL',limit=25,offset=0,*,member_id=None):
        with self._db('SUNDAY_SCHOOL_ATTENDANCE_VIEW') as (db,access):
            row=self._session(db,access,session_id)
            marker=aliased(User)
            stmt=select(Member,Record,marker.username).select_from(Roster).join(Member,Member.id==Roster.member_id)\
                .outerjoin(Record,(Record.session_id==Roster.session_id)&(Record.member_id==Roster.member_id))\
                .outerjoin(marker,marker.id==Record.marked_by_user_id).where(Roster.session_id==row.id)
            if member_id is not None:stmt=stmt.where(Member.id==identifier(member_id))
            if status.upper()=='UNMARKED': stmt=stmt.where(Record.id.is_(None))
            elif status.upper()!='ALL':
                if status.upper() not in self.STATUSES: raise SundaySchoolError('Choose a valid attendance status.')
                stmt=stmt.where(Record.status==status.upper())
            if search:
                pattern=search_pattern(search)
                filters=[func.concat_ws(' ',Member.first_name,Member.middle_name,Member.last_name).ilike(pattern),Member.member_no.ilike(pattern)]
                if access.has('SUNDAY_SCHOOL_GUARDIAN_VIEW'):
                    from src.services.sunday_school_service import SundaySchoolService
                    filters.append(SundaySchoolService._guardian_search(pattern))
                stmt=stmt.where(or_(*filters))
            total=db.scalar(select(func.count()).select_from(stmt.subquery())); limit,offset=page_bounds(limit,offset)
            rows=db.execute(stmt.order_by(Member.last_name,Member.first_name,Member.id).limit(limit).offset(offset)).all()
            ids=[member.id for member,_record,_marker in rows]; households=self.household_map(db,ids); guardians=self.guardian_map(db,access,ids)
            return dict(total=total,rows=[dict(self.member_dto(member),record_id=str(record.id) if record else None,status=record.status if record else None,
                marked_by=marked_by or '',marked_at=record.marked_at if record else None,updated_at=record.updated_at if record else None,
                can_mark=row.state=='OPEN' and not record and access.has('SUNDAY_SCHOOL_ATTENDANCE_RECORD'),
                can_correct=bool(record) and access.has('SUNDAY_SCHOOL_ATTENDANCE_CORRECT') and (row.state=='OPEN' or access.global_access),
                **self.contact_fields(member.id,households,guardians)) for member,record,marked_by in rows])

    def mark(self,session_id,member_id,status,notes=''):
        status=str(status).upper()
        if status not in self.STATUSES: raise SundaySchoolError('Choose Present, Late, Excused or Absent.')
        with self._db('SUNDAY_SCHOOL_ATTENDANCE_RECORD',True) as (db,access):
            session=self._session(db,access,session_id)
            if session.state!='OPEN': raise SundaySchoolError('Open the class attendance session before recording.')
            mid=identifier(member_id)
            if not db.get(Roster,(session.id,mid)): raise SundaySchoolDenied('This member is not in the saved class roster.')
            existing=db.scalar(select(Record).where(Record.session_id==session.id,Record.member_id==mid))
            if existing:
                if existing.status==status: return dict(id=str(existing.id),status=existing.status)
                raise SundaySchoolConflict('Attendance is already marked. Use Correct with a reason.')
            row=Record(session_id=session.id,member_id=mid,status=status,notes=text_value(notes),marked_by_user_id=access.user_id)
            db.add(row); db.flush(); self.audit(db,access,'ATTENDANCE_MARKED',class_id=session.class_id,session_id=session.id,
                member_id=mid,record_id=row.id,new={'status':status})
            db.commit(); return dict(id=str(row.id),status=row.status,session_id=str(session.id),member_id=str(row.member_id))

    def correct(self,record_id,status,reason,expected_updated_at=None):
        status=str(status).upper(); reason=text_value(reason,1000)
        if status not in self.STATUSES or not reason: raise SundaySchoolError('Choose a valid status and enter a correction reason.')
        with self._db('SUNDAY_SCHOOL_ATTENDANCE_CORRECT',True) as (db,access):
            row=db.get(Record,identifier(record_id))
            if not row: raise SundaySchoolNotFound('Attendance record not found.')
            session=self._session(db,access,row.session_id); version(row,expected_updated_at)
            if session.state!='OPEN' and not access.global_access: raise SundaySchoolDenied('Closed attendance correction requires Sunday School-wide access.')
            old=row.status; row.status=status; row.updated_at=datetime.now(timezone.utc)
            self.audit(db,access,'ATTENDANCE_CORRECTED',class_id=session.class_id,session_id=session.id,member_id=row.member_id,
                record_id=row.id,old={'status':old},new={'status':status},reason=reason)
            db.commit(); return dict(id=str(row.id),status=row.status,session_id=str(session.id),member_id=str(row.member_id))

    def close_session(self,session_id,expected_updated_at=None):
        with self._db('SUNDAY_SCHOOL_ATTENDANCE_CLOSE',True) as (db,access):
            row=self._session(db,access,session_id); version(row,expected_updated_at)
            if row.state!='OPEN': raise SundaySchoolError('Only open attendance can be closed.')
            marked=select(Record.member_id).where(Record.session_id==row.id)
            missing=list(db.scalars(select(Roster.member_id).where(Roster.session_id==row.id,Roster.member_id.not_in(marked))))
            for mid in missing: db.add(Record(session_id=row.id,member_id=mid,status='ABSENT',marked_by_user_id=access.user_id))
            row.state='CLOSED'; row.closed_at=datetime.now(timezone.utc); row.updated_at=datetime.now(timezone.utc)
            self.audit(db,access,'ATTENDANCE_CLOSED',class_id=row.class_id,session_id=row.id,new={'absent_added':len(missing)})
            db.commit()

    def reopen_session(self,session_id,reason,expected_updated_at=None):
        reason=text_value(reason,1000)
        if not reason: raise SundaySchoolError('Enter a reopening reason.')
        with self._db('SUNDAY_SCHOOL_ATTENDANCE_REOPEN',True) as (db,access):
            if not access.global_access: raise SundaySchoolDenied('Reopening attendance requires Sunday School-wide access.')
            row=self._session(db,access,session_id); version(row,expected_updated_at)
            if row.state!='CLOSED': raise SundaySchoolError('Choose a closed attendance session.')
            row.state='OPEN'; row.closed_at=None; row.updated_at=datetime.now(timezone.utc)
            self.audit(db,access,'ATTENDANCE_REOPENED',class_id=row.class_id,session_id=row.id,reason=reason)
            db.commit()
