"""Permission-driven ministry configuration, lifecycle and immutable audit history."""
from contextlib import contextmanager
from datetime import datetime, timezone
import logging
import re
import uuid
from sqlalchemy import case, func, inspect, or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from src.config.database import SessionLocal
from src.models import (Ministry, MinistryAuditLog, Member, MemberMinistry, MemberStatus,
    AttendanceSession, UserMinistryScope, AuthorizationAuditLog, User,
    MinistryPosition, MinistryLeadershipAssignment, MinistryLeadershipAuditLog)
from src.security.attendance_permissions import load_access, AttendancePermissionError

CATEGORIES = ('MINISTRY','FELLOWSHIP','DEPARTMENT','UNIT','OTHER')
STATUSES = ('ACTIVE','INACTIVE','ARCHIVED')
DELETE_MESSAGE = 'This ministry cannot be permanently deleted because it has related church records. Archive it instead.'


class MinistryServiceError(Exception):
    pass


class MinistryAuthorizationError(MinistryServiceError, AttendancePermissionError):
    pass


def ministry_uuid(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise MinistryServiceError('Invalid ministry identifier.') from exc


class MinistryService:
    def __init__(self,user_id=None,session_factory=SessionLocal):
        self.user_id,self.session_factory = user_id,session_factory

    @contextmanager
    def _db(self):
        with self.session_factory() as db:
            try:
                yield db,load_access(db,self.user_id)
            except MinistryAuthorizationError:
                raise
            except AttendancePermissionError as exc:
                db.rollback()
                raise MinistryAuthorizationError(str(exc)) from exc
            except IntegrityError as exc:
                db.rollback()
                raise MinistryServiceError('The name/code is already used, or related records changed. Refresh and retry.') from exc
            except SQLAlchemyError as exc:
                db.rollback()
                logging.getLogger(__name__).error('Ministry operation failed: %s',type(exc).__name__)
                raise MinistryServiceError('The ministry operation could not be completed. Refresh and retry.') from exc

    @staticmethod
    def _require(access,action):
        if not (access.has('MINISTRIES_VIEW_ALL') and access.has('MINISTRIES_'+action)):
            raise MinistryAuthorizationError('You do not have permission to manage this ministry.')

    @staticmethod
    def _visible(db,access,stmt):
        if access.has('MINISTRIES_VIEW_ALL'):
            return stmt
        if not access.has('MINISTRIES_VIEW_OWN'):
            raise MinistryAuthorizationError('Ministry access is not assigned.')
        # Retain assigned historical workspace access when a ministry is archived.
        return stmt.where(Ministry.id.in_(access.ministry_ids('MINISTRIES_VIEW_OWN', include_inactive=True)))

    def capabilities(self):
        with self._db() as (db,access):
            self._visible(db,access,select(Ministry.id))
            return dict(view_all=access.has('MINISTRIES_VIEW_ALL'),
                **{action.lower():access.has('MINISTRIES_VIEW_ALL') and access.has('MINISTRIES_'+action)
                   for action in ('CREATE','EDIT','DEACTIVATE','ARCHIVE','RESTORE','DELETE_UNUSED')})

    @staticmethod
    def _status_expression():
        return case((Ministry.archived_at.is_not(None),'ARCHIVED'),(Ministry.is_active.is_(True),'ACTIVE'),else_='INACTIVE')

    @staticmethod
    def _counts():
        return select(MemberMinistry.ministry_id,
            func.count(MemberMinistry.member_id).label('members'),
            func.count(MemberMinistry.member_id).filter(Member.status==MemberStatus.ACTIVE).label('active_members'))\
            .join(Member).where(MemberMinistry.is_active.is_(True)).group_by(MemberMinistry.ministry_id).subquery()

    @staticmethod
    def _known_dependencies():
        return or_(*(select(model.id).where(model.ministry_id==Ministry.id).exists()
            for model in (MemberMinistry,AttendanceSession,UserMinistryScope,AuthorizationAuditLog,
                          MinistryPosition,MinistryLeadershipAssignment,MinistryLeadershipAuditLog)))

    @staticmethod
    def _dto(ministry,members=0,active_members=0,in_use=False):
        return dict(id=str(ministry.id),code=ministry.code,name=ministry.name,description=ministry.description or '',
            category=ministry.category,status=ministry.status,is_active=ministry.is_active,
            created_at=ministry.created_at,updated_at=ministry.updated_at,archived_at=ministry.archived_at,
            member_count=members,active_member_count=active_members,in_use=bool(in_use))

    def list_ministries(self,search='',status='ALL',category='ALL',limit=25,offset=0):
        with self._db() as (db,access):
            counts = self._counts()
            stmt = self._visible(db,access,select(Ministry,
                func.coalesce(counts.c.members,0),func.coalesce(counts.c.active_members,0),self._known_dependencies())
                .outerjoin(counts,counts.c.ministry_id==Ministry.id))
            if search.strip():
                pattern = '%'+search.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
                stmt = stmt.where(or_(Ministry.name.ilike(pattern,escape='\\'),Ministry.code.ilike(pattern,escape='\\')))
            if status!='ALL':
                if status not in STATUSES:
                    raise MinistryServiceError('Choose a valid ministry status.')
                stmt = stmt.where(self._status_expression()==status)
            if category!='ALL':
                if category not in CATEGORIES:
                    raise MinistryServiceError('Choose a valid category.')
                stmt = stmt.where(Ministry.category==category)
            total = db.scalar(select(func.count()).select_from(stmt.subquery()))
            rows = db.execute(stmt.order_by(func.lower(Ministry.name),Ministry.id)
                .limit(min(100,max(1,limit))).offset(max(0,offset)))
            return dict(total=total,rows=[self._dto(*row) for row in rows])

    def get_ministry_stats(self):
        with self._db() as (db,access):
            lifecycle = self._status_expression()
            rows = db.execute(self._visible(db,access,select(lifecycle,func.count(Ministry.id)))
                .group_by(lifecycle)).all()
            result = dict(total=0,active=0,inactive=0,archived=0)
            for status,count in rows:
                result[status.lower()]=count
                result['total']+=count
            return result

    def get_member_counts(self):
        with self._db() as (db,access):
            counts=self._counts()
            rows=db.execute(self._visible(db,access,select(Ministry.id,func.coalesce(counts.c.members,0))
                .outerjoin(counts,counts.c.ministry_id==Ministry.id)))
            return {str(mid):count for mid,count in rows}

    def _get(self,db,access,ministry_id,lock=False):
        stmt=self._visible(db,access,select(Ministry)).where(Ministry.id==ministry_uuid(ministry_id))
        row=db.scalar(stmt.with_for_update() if lock else stmt)
        if row is None:
            raise MinistryServiceError('Ministry unavailable or outside your assigned scope.')
        return row

    @staticmethod
    def _dependencies(db,ministry_id):
        # Reflect actual database references, including future module tables.
        connection=db.connection()
        schema=connection.get_execution_options().get('schema_translate_map',{}).get(None)
        inspector=inspect(connection)
        schema=schema or inspector.default_schema_name
        quote=connection.dialect.identifier_preparer.quote
        dependencies=[]
        references=db.execute(text("""SELECT n.nspname,c.relname,a.attname
            FROM pg_constraint f JOIN pg_class c ON c.oid=f.conrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=f.conkey[1]
            WHERE f.contype='f' AND f.confrelid=to_regclass(:target)
            AND cardinality(f.conkey)=1 AND cardinality(f.confkey)=1"""),
            dict(target=quote(schema)+'.'+quote('ministries'))).all()
        for reference_schema,table,column in references:
            exists=db.scalar(text(f'SELECT EXISTS (SELECT 1 FROM {quote(reference_schema)}.{quote(table)} WHERE {quote(column)}=:mid)'),dict(mid=ministry_id))
            if exists:
                dependencies.append(table)
        return sorted(set(dependencies))

    def get_ministry(self,ministry_id):
        with self._db() as (db,access):
            row=self._get(db,access,ministry_id)
            counts=self._counts()
            total,active=db.execute(select(func.coalesce(counts.c.members,0),func.coalesce(counts.c.active_members,0))
                .select_from(Ministry).outerjoin(counts,counts.c.ministry_id==Ministry.id).where(Ministry.id==row.id)).one()
            dependencies=self._dependencies(db,row.id)
            return dict(self._dto(row,total,active,bool(dependencies)),dependencies=dependencies)

    @staticmethod
    def _snapshot(row):
        return dict(code=row.code,name=row.name,category=row.category,description=row.description,
            status=row.status,archived_at=row.archived_at.isoformat() if row.archived_at else None)

    def _audit(self,db,access,row,action,old=None):
        db.add(MinistryAuditLog(ministry_id=row.id,actor_user_id=access.user_id,action=action,
            old_values=old,new_values=None if action=='DELETED_UNUSED' else self._snapshot(row)))

    @staticmethod
    def _validate(data):
        name=str(data.get('name','')).strip()
        code=str(data.get('code','')).strip().upper()
        description=str(data.get('description','') or '').strip()
        category=str(data.get('category','MINISTRY')).upper()
        if not name or len(name)>150:
            raise MinistryServiceError('Enter a ministry name of 1–150 characters.')
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,59}',code):
            raise MinistryServiceError('Code must start with a letter and contain only letters, digits or underscores (up to 60 characters).')
        if category not in CATEGORIES:
            raise MinistryServiceError('Choose a valid category.')
        if len(description)>10000:
            raise MinistryServiceError('Keep the description within 10,000 characters.')
        return dict(name=name,code=code,description=description or None,category=category)

    @staticmethod
    def _unique(db,values,excluding=None):
        stmt=select(Ministry.id).where(or_(func.upper(Ministry.code)==values['code'].upper(),func.lower(Ministry.name)==values['name'].lower()))
        if excluding:
            stmt=stmt.where(Ministry.id!=excluding)
        if db.scalar(stmt):
            raise MinistryServiceError('A ministry with that name or code already exists, including inactive or archived ministries.')

    def create_ministry(self,data):
        with self._db() as (db,access):
            self._require(access,'CREATE')
            values=self._validate(data)
            self._unique(db,values)
            status=data.get('status','ACTIVE')
            if status not in ('ACTIVE','INACTIVE'):
                raise MinistryServiceError('New ministries must start Active or Inactive.')
            row=Ministry(**values,is_active=status=='ACTIVE',created_by_user_id=access.user_id,updated_by_user_id=access.user_id)
            db.add(row)
            db.flush()
            self._audit(db,access,row,'CREATED')
            db.commit()
            return self._dto(row)

    @staticmethod
    def _check_version(row,expected_updated_at):
        if expected_updated_at is not None and row.updated_at!=expected_updated_at:
            raise MinistryServiceError('This ministry was changed by another user. Refresh before saving.')

    def update_ministry(self,ministry_id,data,expected_updated_at=None):
        with self._db() as (db,access):
            self._require(access,'EDIT')
            row=self._get(db,access,ministry_id,lock=True)
            self._check_version(row,expected_updated_at)
            values=self._validate(data)
            if str(data.get('code','')).strip()==row.code:
                values['code']=row.code
            if values['code']!=row.code and self._dependencies(db,row.id):
                raise MinistryServiceError('The code is locked because this ministry has related church records.')
            self._unique(db,values,row.id)
            old=self._snapshot(row)
            status=data.get('status',row.status)
            if status!=row.status:
                self._transition(db,access,row,status)
            for field,value in values.items():
                setattr(row,field,value)
            row.updated_by_user_id=access.user_id
            row.updated_at=datetime.now(timezone.utc)
            self._audit(db,access,row,'EDITED',old)
            db.commit()
            return self._dto(row)

    def _transition(self,db,access,row,target):
        old=self._snapshot(row)
        if target not in STATUSES:
            raise MinistryServiceError('Choose a valid ministry status.')
        if row.status==target:
            raise MinistryServiceError('The ministry already has this status. Refresh the list.')
        if row.status=='ARCHIVED':
            raise MinistryServiceError('Use Restore to change an archived ministry status.')
        action={'INACTIVE':'DEACTIVATE','ARCHIVED':'ARCHIVE','ACTIVE':'EDIT'}[target]
        self._require(access,action)
        row.is_active=target=='ACTIVE'
        if target=='ARCHIVED':
            row.archived_at=datetime.now(timezone.utc)
            row.archived_by_user_id=access.user_id
        row.updated_by_user_id=access.user_id
        row.updated_at=datetime.now(timezone.utc)
        self._audit(db,access,row,{'INACTIVE':'DEACTIVATED','ARCHIVED':'ARCHIVED','ACTIVE':'ACTIVATED'}[target],old)

    def _change(self,ministry_id,target,expected_updated_at=None):
        action={'INACTIVE':'DEACTIVATE','ARCHIVED':'ARCHIVE','ACTIVE':'EDIT'}[target]
        with self._db() as (db,access):
            self._require(access,action)
            row=self._get(db,access,ministry_id,lock=True)
            self._check_version(row,expected_updated_at)
            self._transition(db,access,row,target)
            db.commit()
            return self._dto(row)

    def activate_ministry(self,ministry_id,expected_updated_at=None):
        return self._change(ministry_id,'ACTIVE',expected_updated_at)

    def deactivate_ministry(self,ministry_id,expected_updated_at=None):
        return self._change(ministry_id,'INACTIVE',expected_updated_at)

    def archive_ministry(self,ministry_id,expected_updated_at=None):
        return self._change(ministry_id,'ARCHIVED',expected_updated_at)

    def restore_ministry(self,ministry_id,status='INACTIVE',expected_updated_at=None):
        with self._db() as (db,access):
            self._require(access,'RESTORE')
            row=self._get(db,access,ministry_id,lock=True)
            self._check_version(row,expected_updated_at)
            if row.status!='ARCHIVED' or status not in ('ACTIVE','INACTIVE'):
                raise MinistryServiceError('Restore an archived ministry to Active or Inactive.')
            old=self._snapshot(row)
            row.archived_at=row.archived_by_user_id=None
            row.is_active=status=='ACTIVE'
            row.updated_by_user_id=access.user_id
            row.updated_at=datetime.now(timezone.utc)
            self._audit(db,access,row,'RESTORED',old)
            db.commit()
            return self._dto(row)

    def delete_unused_ministry(self,ministry_id,*,confirmed=False,expected_updated_at=None):
        with self._db() as (db,access):
            self._require(access,'DELETE_UNUSED')
            if confirmed is not True:
                raise MinistryServiceError('Explicit confirmation is required for permanent deletion.')
            row=self._get(db,access,ministry_id,lock=True)
            self._check_version(row,expected_updated_at)
            if self._dependencies(db,row.id):
                raise MinistryServiceError(DELETE_MESSAGE)
            self._audit(db,access,row,'DELETED_UNUSED',self._snapshot(row))
            db.delete(row)
            db.commit()

    def audit_history(self,ministry_id,limit=50):
        with self._db() as (db,access):
            self._get(db,access,ministry_id)
            rows=db.execute(select(MinistryAuditLog,User.username).outerjoin(User,User.id==MinistryAuditLog.actor_user_id)
                .where(MinistryAuditLog.ministry_id==ministry_uuid(ministry_id))
                .order_by(MinistryAuditLog.occurred_at.desc(),MinistryAuditLog.id.desc()).limit(min(100,max(1,limit))))
            return [dict(action=row.action,actor=name or 'Unavailable account',occurred_at=row.occurred_at,
                old_values=row.old_values,new_values=row.new_values) for row,name in rows]
