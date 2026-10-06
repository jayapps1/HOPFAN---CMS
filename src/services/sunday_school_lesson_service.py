"""One lesson plan can serve one, several or all classes."""
from datetime import datetime,timezone
from sqlalchemy import delete,or_,select,func
from src.models import SundaySchoolLesson as Lesson,SundaySchoolLessonClass as LessonClass,SundaySchoolClass as SchoolClass,SundaySchoolAttendanceSession as Session,User
from src.services.sunday_school_base import SundaySchoolBase,SundaySchoolError,SundaySchoolDenied,identifier,school_date,text_value,version,today,page_bounds,search_pattern


class SundaySchoolLessonService(SundaySchoolBase):
    @staticmethod
    def _visible(access,stmt):
        if access.global_access: return stmt
        if not access.class_ids:return stmt.where(False)
        applies=select(LessonClass.lesson_id).where(LessonClass.lesson_id==Lesson.id,LessonClass.class_id.in_(access.class_ids)).correlate(Lesson).exists()
        return stmt.where(or_(Lesson.applies_to_all.is_(True),applies),or_(Lesson.status=='PUBLISHED',Lesson.created_by_user_id==access.user_id))

    @staticmethod
    def values(data):
        title=text_value(data.get('title'),200)
        if not title: raise SundaySchoolError('Enter a lesson title.')
        status=str(data.get('status','DRAFT')).upper()
        if status not in ('DRAFT','PUBLISHED','ARCHIVED'): raise SundaySchoolError('Choose Draft, Published or Archived.')
        return dict(title=title,lesson_date=school_date(data.get('lesson_date'),future=True),status=status,
            **{key:text_value(data.get(key),200 if key in ('topic','scripture_reference') else 10000) for key in ('topic','scripture_reference','objective','lesson_summary','teacher_notes')})

    def _scope(self,db,access,class_ids,all_classes):
        if not isinstance(all_classes,bool): raise SundaySchoolError('Choose an explicit lesson scope.')
        ids=set(identifier(cid) for cid in class_ids)
        if all_classes:
            if not access.global_access: raise SundaySchoolDenied('All-school lessons require Sunday School-wide access.')
            if ids: raise SundaySchoolError('Choose either all classes or a specific class selection.')
        elif not ids: raise SundaySchoolError('Select at least one class for the lesson.')
        for cid in ids: self._class(db,access,cid,active=True)
        return ids

    def _dto(self,db,access,rows):
        ids=[row.id for row,_author in rows]; mapping={lid:[] for lid in ids}
        counts=dict(db.execute(select(LessonClass.lesson_id,func.count()).where(LessonClass.lesson_id.in_(ids)).group_by(LessonClass.lesson_id)).all()) if ids else {}
        if ids:
            stmt=select(LessonClass.lesson_id,SchoolClass).join(SchoolClass).where(LessonClass.lesson_id.in_(ids))
            for lid,cls in db.execute(access.restrict(stmt,SchoolClass.id).order_by(SchoolClass.sort_order,SchoolClass.name)):
                mapping[lid].append(dict(id=str(cls.id),name=cls.name))
        return [dict(id=str(row.id),title=row.title,lesson_date=row.lesson_date,topic=row.topic or '',scripture_reference=row.scripture_reference or '',
            objective=row.objective or '',lesson_summary=row.lesson_summary or '',teacher_notes=row.teacher_notes or '',status=row.status,
            applies_to_all=row.applies_to_all,classes=mapping[row.id],author=author or 'System',updated_at=row.updated_at,
            can_edit=access.has('SUNDAY_SCHOOL_LESSON_EDIT') and (access.global_access or
                not row.applies_to_all and len(mapping[row.id])==counts.get(row.id,0))) for row,author in rows]

    def list_lessons(self,class_id=None,search='',view='ALL',limit=25,offset=0):
        with self._db('SUNDAY_SCHOOL_LESSON_VIEW') as (db,access):
            stmt=self._visible(access,select(Lesson,User.username).outerjoin(User,User.id==Lesson.created_by_user_id))
            if class_id:
                self._class(db,access,class_id)
                applies=select(LessonClass.lesson_id).where(LessonClass.lesson_id==Lesson.id,LessonClass.class_id==identifier(class_id)).correlate(Lesson).exists()
                stmt=stmt.where(or_(Lesson.applies_to_all.is_(True),applies))
            if view.upper()=='UPCOMING': stmt=stmt.where(Lesson.lesson_date>=today(),Lesson.status=='PUBLISHED')
            elif view.upper()=='RECENT': stmt=stmt.where(Lesson.lesson_date<=today(),Lesson.status=='PUBLISHED')
            elif view.upper() in ('DRAFT','PUBLISHED','ARCHIVED'): stmt=stmt.where(Lesson.status==view.upper())
            if search: stmt=stmt.where(or_(Lesson.title.ilike(search_pattern(search)),Lesson.topic.ilike(search_pattern(search))))
            total=db.scalar(select(func.count()).select_from(stmt.subquery())); limit,offset=page_bounds(limit,offset)
            rows=db.execute(stmt.order_by(Lesson.lesson_date.desc(),Lesson.id).limit(limit).offset(offset)).all()
            return dict(total=total,rows=self._dto(db,access,rows))

    def get_lesson(self,lesson_id):
        with self._db('SUNDAY_SCHOOL_LESSON_VIEW') as (db,access):
            row=db.execute(self._visible(access,select(Lesson,User.username).outerjoin(User,User.id==Lesson.created_by_user_id)).where(Lesson.id==identifier(lesson_id))).first()
            if not row: raise SundaySchoolDenied('Lesson not found or outside your permitted classes.')
            return self._dto(db,access,[row])[0]

    def create_lesson(self,data,class_ids=(),all_classes=False):
        values=self.values(data)
        with self._db('SUNDAY_SCHOOL_LESSON_CREATE',True) as (db,access):
            ids=self._scope(db,access,class_ids,all_classes)
            row=Lesson(**values,applies_to_all=all_classes,created_by_user_id=access.user_id); db.add(row); db.flush()
            for cid in ids: db.add(LessonClass(lesson_id=row.id,class_id=cid))
            self.audit(db,access,'LESSON_CREATED',new={'lesson_id':str(row.id),'class_ids':sorted(str(cid) for cid in ids),'all_classes':all_classes,'status':row.status})
            db.commit(); return dict(id=str(row.id),updated_at=row.updated_at)

    def update_lesson(self,lesson_id,data,class_ids=(),all_classes=False,expected_updated_at=None):
        values=self.values(data)
        with self._db('SUNDAY_SCHOOL_LESSON_EDIT',True) as (db,access):
            row=db.scalar(self._visible(access,select(Lesson)).where(Lesson.id==identifier(lesson_id)))
            if not row: raise SundaySchoolDenied('Lesson not found or outside your permitted classes.')
            version(row,expected_updated_at)
            existing=set(db.scalars(select(LessonClass.class_id).where(LessonClass.lesson_id==row.id)))
            if row.applies_to_all and not access.global_access: raise SundaySchoolDenied('All-school lesson editing requires Sunday School-wide access.')
            if not access.global_access and not existing.issubset(access.class_ids): raise SundaySchoolDenied('Editing a shared lesson requires access to every selected class.')
            ids=self._scope(db,access,class_ids,all_classes)
            attached=db.scalars(select(Session).where(Session.lesson_id==row.id)).all()
            if any(session.session_date!=values['lesson_date'] or (not all_classes and session.class_id not in ids) for session in attached):
                raise SundaySchoolError('Existing attendance uses this lesson date/class scope. Preserve those links.')
            old={'title':row.title,'status':row.status,'lesson_date':row.lesson_date.isoformat()}
            for key,value in values.items(): setattr(row,key,value)
            row.applies_to_all=all_classes; row.updated_at=datetime.now(timezone.utc)
            db.execute(delete(LessonClass).where(LessonClass.lesson_id==row.id))
            for cid in ids: db.add(LessonClass(lesson_id=row.id,class_id=cid))
            self.audit(db,access,'LESSON_UPDATED',old=old,new={'lesson_id':str(row.id),'title':row.title,'status':row.status,'class_ids':sorted(str(cid) for cid in ids),'all_classes':all_classes})
            db.commit()
            # Return the authorized write result even if archiving removes the
            # lesson from a scoped reader's ordinary visible lesson list.
            return self._dto(db,access,[(row,None)])[0]
