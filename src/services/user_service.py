"""Account administration. No password hashes or authenticator secrets in DTOs."""
from datetime import datetime, timezone
import re
from argon2 import PasswordHasher
from sqlalchemy import func, or_, select, literal, false
from sqlalchemy.orm import selectinload
from src.models import User, UserStatus, Role, Ministry, Member, MemberMinistry, UserMinistryScope, Permission, SundaySchoolClass, SundaySchoolUserClassScope
from src.models.associations import user_roles
from src.services.administration_base import AdministrationService, AdministrationError, identifier, page_bounds, search_pattern, audit
from src.services.auth_service import AuthService, PasswordRecoveryError
from src.services.authorization_service import AuthorizationDenied


class UserService(AdministrationService):
    @staticmethod
    def _account_snapshot(user):
        return dict(username=user.username, email=user.email, phone=user.phone, member_id=str(user.member_id) if user.member_id else None,
            status=user.status.value, require_password_change=user.require_password_change)

    @staticmethod
    def _scope_snapshot(scopes):
        return [dict(ministry_id=str(s.ministry_id), is_active=s.is_active, legacy_attendance_limits=s.legacy_attendance_limits)
                for s in sorted(scopes, key=lambda s:str(s.ministry_id))]

    @classmethod
    def _dto(cls, user, scopes):
        member = user.member
        return dict(id=str(user.id), **cls._account_snapshot(user),
            full_name=member.full_name if member else user.username, photo_path=member.photo_path if member else None,
            member=dict(id=str(member.id), full_name=member.full_name, member_no=member.member_no) if member else None,
            roles=[dict(id=str(r.id), code=r.code, name=r.name, is_active=r.is_active) for r in sorted(user.roles, key=lambda r:r.name)],
            scopes=scopes, last_login_at=user.last_login_at, created_at=user.created_at, updated_at=user.updated_at,
            failed_login_attempts=user.failed_login_attempts, locked_until=user.locked_until,
            totp_enabled=user.totp_enabled, auth_revision=user.auth_revision,
            effective_permissions=sorted(cls._permissions(user.roles)) if user.status == UserStatus.ACTIVE and not user.require_password_change else [],
            configured_permissions=sorted(cls._permissions(user.roles)))

    @staticmethod
    def _scopes(db, ids):
        result = {uid:[] for uid in ids}
        if not ids:
            return result
        for scope, ministry in db.execute(select(UserMinistryScope, Ministry).join(Ministry).where(
                UserMinistryScope.user_id.in_(ids), UserMinistryScope.is_active.is_(True)).order_by(Ministry.name)):
            result[scope.user_id].append(dict(id=str(ministry.id), name=ministry.name, is_active=ministry.is_active,
                legacy_attendance_limits=scope.legacy_attendance_limits,
                legacy_limits={action:getattr(scope,field) for action,field in {
                    'view':'can_view_attendance','create':'can_create_attendance','record':'can_record_attendance',
                    'correct':'can_correct_attendance','close':'can_close_attendance','reports':'can_view_reports'}.items()} if scope.legacy_attendance_limits else None))
        return result

    @staticmethod
    def _school_ready(db):
        return db.scalar(select(Permission.id).where(Permission.code=='SUNDAY_SCHOOL_CLASS_VIEW')) is not None

    @classmethod
    def _school_scopes(cls,db,ids):
        result={uid:[] for uid in ids}
        if not ids or not cls._school_ready(db): return result
        stmt=select(SundaySchoolUserClassScope,SundaySchoolClass).join(SundaySchoolClass).where(
            SundaySchoolUserClassScope.user_id.in_(ids),SundaySchoolUserClassScope.is_active.is_(True)).order_by(SundaySchoolClass.name)
        for scope,school_class in db.execute(stmt):
            result[scope.user_id].append(dict(id=str(school_class.id),name=school_class.name,is_active=school_class.status=='ACTIVE'))
        return result

    @staticmethod
    def _set_school_scopes(db,access,user,class_ids):
        access.require_permission('USER_SCOPE_MANAGE')
        ids=set(identifier(cid) for cid in class_ids)
        existing=db.scalars(select(SundaySchoolUserClassScope).where(SundaySchoolUserClassScope.user_id==user.id)).all()
        retained={row.class_id for row in existing if row.is_active}
        rows=db.scalars(select(SundaySchoolClass).where(SundaySchoolClass.id.in_(ids))).all()
        if {row.id for row in rows}!=ids or any(row.status!='ACTIVE' and row.id not in retained for row in rows):
            raise AdministrationError('Select active Sunday School classes or retain existing historical scopes.')
        found={row.class_id:row for row in existing}
        for row in existing: row.is_active=row.class_id in ids
        for cid in ids-set(found): db.add(SundaySchoolUserClassScope(user_id=user.id,class_id=cid,created_by_user_id=access.user_id))

    @staticmethod
    def _directory_locations(db,ids,school_ready):
        ministries={uid:[] for uid in ids};schools={uid:[] for uid in ids}
        if not ids:return ministries,schools
        flags=('can_view_attendance','can_create_attendance','can_record_attendance','can_correct_attendance','can_close_attendance','can_view_reports')
        stmt=select(UserMinistryScope.user_id,Ministry.id,Ministry.name,Ministry.is_active,
            UserMinistryScope.legacy_attendance_limits,*(getattr(UserMinistryScope,key) for key in flags),literal('ministry')).join(Ministry).where(UserMinistryScope.user_id.in_(ids),UserMinistryScope.is_active.is_(True))
        if school_ready:
            stmt=stmt.union_all(select(SundaySchoolUserClassScope.user_id,SundaySchoolClass.id,SundaySchoolClass.name,
                SundaySchoolClass.status=='ACTIVE',false(),*(false() for _key in flags),literal('school')).join(SundaySchoolClass)
                .where(SundaySchoolUserClassScope.user_id.in_(ids),SundaySchoolUserClassScope.is_active.is_(True)))
        for row in db.execute(stmt):
            uid,cid,name,active,legacy,*rest=row
            if rest[-1]=='school':schools[uid].append(dict(id=str(cid),name=name,is_active=active))
            else:ministries[uid].append(dict(id=str(cid),name=name,is_active=active,legacy_attendance_limits=legacy,
                legacy_limits=dict(zip(('view','create','record','correct','close','reports'),rest[:-1]))))
        for mapping in (ministries,schools):
            for rows in mapping.values():rows.sort(key=lambda row:row['name'].casefold())
        return ministries,schools

    def list_users(self, search='', status='ALL', role_id=None, ministry_id=None, limit=25, offset=0):
        with self._db('USER_VIEW') as (db, access):
            stmt = select(User).outerjoin(Member, Member.id == User.member_id)
            if search.strip():
                pattern = search_pattern(search)
                fields = (User.username, User.email, User.phone, Member.member_no, Member.phone, Member.email,
                          func.concat_ws(' ', Member.first_name, Member.middle_name, Member.last_name))
                stmt = stmt.where(or_(*(f.ilike(pattern, escape='\\') for f in fields)))
            if status != 'ALL':
                try:
                    stmt = stmt.where(User.status == UserStatus(status))
                except ValueError as exc:
                    raise AdministrationError('Choose a valid account status.') from exc
            if role_id:
                stmt = stmt.where(select(user_roles.c.user_id).where(user_roles.c.user_id == User.id,
                    user_roles.c.role_id == identifier(role_id)).exists())
            if ministry_id:
                stmt = stmt.where(select(UserMinistryScope.id).where(UserMinistryScope.user_id == User.id,
                    UserMinistryScope.ministry_id == identifier(ministry_id), UserMinistryScope.is_active.is_(True)).exists())
            ready=select(Permission.id).where(Permission.code=='SUNDAY_SCHOOL_CLASS_VIEW').exists()
            total,school_ready = db.execute(select(func.count(),ready).select_from(stmt.subquery())).one()
            limit, offset = page_bounds(limit, offset)
            users = db.scalars(stmt.options(selectinload(User.member), selectinload(User.roles).selectinload(Role.permissions))
                .order_by(func.lower(User.username), User.id).limit(limit).offset(offset)).all()
            scopes,school_scopes=self._directory_locations(db,[u.id for u in users],school_ready)
            return dict(total=total, rows=[dict(self._dto(u, scopes[u.id]),school_scopes=school_scopes[u.id]) for u in users])

    def stats(self):
        with self._db('USER_VIEW') as (db, access):
            result = dict(total=0, active=0, locked=0, inactive=0, suspended=0)
            for status,count in db.execute(select(User.status, func.count()).group_by(User.status)):
                result[status.value.lower()] = count
                result['total'] += count
            return result

    def get_user(self, user_id):
        with self._db('USER_VIEW') as (db, access):
            user = self._user(db, user_id)
            return dict(self._dto(user, self._scopes(db, [user.id])[user.id]),school_scopes=self._school_scopes(db,[user.id])[user.id])

    def access_options(self, user_id=None):
        with self.session_factory() as db:
            from src.services.authorization_service import AuthorizationService
            access = AuthorizationService.load(db, self.user_id)
            if not access.has_any({'USER_VIEW','USER_CREATE','USER_EDIT','ROLE_ASSIGN','USER_SCOPE_MANAGE'}):
                raise AuthorizationDenied('Account administration access is not assigned.')
            roles = db.scalars(select(Role).options(selectinload(Role.permissions)).order_by(Role.name)).all()
            ministries = db.scalars(select(Ministry).order_by(Ministry.name)).all()
            retained = set()
            if user_id:
                retained = set(db.scalars(select(UserMinistryScope.ministry_id).where(
                    UserMinistryScope.user_id == identifier(user_id), UserMinistryScope.is_active.is_(True))))
            options=dict(roles=[dict(id=str(r.id),name=r.name+(' (inactive)' if not r.is_active else ''),
                is_active=r.is_active, assignable=self._can_delegate(access,r)) for r in roles],
                ministries=[dict(id=str(m.id),name=m.name+(' (inactive / archived)' if not m.is_active else ''),is_active=m.is_active)
                    for m in ministries if m.is_active or m.id in retained or (not user_id and access.has('USER_VIEW'))])
            if self._school_ready(db):
                retained_school={identifier(scope['id']) for scope in self._school_scopes(db,[identifier(user_id)]).get(identifier(user_id),[])} if user_id else set()
                options['school_classes']=[dict(id=str(row.id),name=row.name+(' (inactive)' if row.status!='ACTIVE' else ''),is_active=row.status=='ACTIVE')
                    for row in db.scalars(select(SundaySchoolClass).order_by(SundaySchoolClass.name)) if row.status=='ACTIVE' or row.id in retained_school]
            return options

    def search_members(self, search='', limit=15, offset=0):
        with self.session_factory() as db:
            from src.services.authorization_service import AuthorizationService
            access = AuthorizationService.load(db, self.user_id)
            if not access.has_any({'USER_CREATE','USER_EDIT'}):
                raise AuthorizationDenied('You do not have permission to link member accounts.')
            stmt = select(Member)
            if search.strip():
                pattern=search_pattern(search)
                stmt=stmt.where(or_(*(field.ilike(pattern,escape='\\') for field in
                    (func.concat_ws(' ',Member.first_name,Member.middle_name,Member.last_name),Member.member_no,Member.phone,Member.email))))
            total=db.scalar(select(func.count()).select_from(stmt.subquery()))
            limit,offset=page_bounds(limit,offset)
            members=db.scalars(stmt.order_by(Member.first_name,Member.last_name,Member.id).limit(limit).offset(offset)).all()
            mids=[m.id for m in members]
            ministry_names={mid:[] for mid in mids}
            if mids:
                for mid,name in db.execute(select(MemberMinistry.member_id,Ministry.name).join(Ministry)
                    .where(MemberMinistry.member_id.in_(mids),MemberMinistry.is_active.is_(True)).order_by(Ministry.name)):
                    ministry_names[mid].append(name)
            linked = dict(db.execute(select(User.member_id,User.id).where(User.member_id.in_(mids))).all()) if mids else {}
            return dict(total=total,rows=[dict(id=str(m.id),full_name=m.full_name,member_no=m.member_no,phone=m.phone or '',
                email=m.email or '',photo_path=m.photo_path,ministries=ministry_names[m.id],user_id=str(linked[m.id]) if m.id in linked else None) for m in members])

    def member_link(self, member_id):
        with self._db('USER_CREATE') as (db, access):
            m=db.get(Member,identifier(member_id))
            if not m:
                raise AdministrationError('Member not found.')
            return dict(id=str(m.id),full_name=m.full_name,member_no=m.member_no,phone=m.phone or '',email=m.email or '',photo_path=m.photo_path)

    @staticmethod
    def _profile(db, user, data):
        username=str(data.get('username','')).strip()
        email=str(data.get('email','')).strip().lower()
        phone=str(data.get('phone','')).strip()
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{2,79}',username):
            raise AdministrationError('Username must be 3–80 letters, numbers, dots, underscores or hyphens.')
        if len(email)>255 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):
            raise AdministrationError('Enter a valid email address.')
        if len(phone)>30:
            raise AdministrationError('Phone must be 30 characters or fewer.')
        for field,value,message in ((User.username,username,'This username is already used.'),(User.email,email,'This email address is already used.')):
            if db.scalar(select(User.id).where(func.lower(field)==value.lower(),User.id!=user.id)):
                raise AdministrationError(message)
        member_id=identifier(data['member_id']) if data.get('member_id') else None
        if member_id:
            if not db.get(Member,member_id):
                raise AdministrationError('Select an existing member.')
            if db.scalar(select(User.id).where(User.member_id==member_id,User.id!=user.id)):
                raise AdministrationError('This member already has a HOPFAN user account.')
        user.username,user.email,user.phone,user.member_id=username,email,phone or None,member_id

    def _set_roles(self, db, access, user, role_ids):
        ids=set(identifier(value) for value in role_ids)
        roles=db.scalars(select(Role).where(Role.id.in_(ids)).options(selectinload(Role.permissions))).all()
        if len(roles)!=len(ids):
            raise AdministrationError('Select valid software roles.')
        previous=set(r.id for r in user.roles)
        if ids != previous:
            access.require_permission('ROLE_ASSIGN')
        for r in roles:
            if r.id not in previous and not self._can_delegate(access,r):
                raise AuthorizationDenied('You may assign only active roles whose permissions you hold. Ask a business administrator for additional access.')
        user.roles=roles

    def _set_scopes(self, db, access, user, ministry_ids, normalize_existing=False):
        ids=set(identifier(value) for value in ministry_ids)
        scopes=db.scalars(select(UserMinistryScope).where(UserMinistryScope.user_id==user.id)).all()
        previous={s.ministry_id for s in scopes if s.is_active}
        if ids != previous or normalize_existing:
            access.require_permission('USER_SCOPE_MANAGE')
        valid=set(db.scalars(select(Ministry.id).where(Ministry.id.in_(ids),Ministry.is_active.is_(True)).with_for_update(read=True)))
        if not ids.issubset(valid | previous):
            raise AdministrationError('Select active ministries. Existing archived scopes can be retained or removed.')
        existing={s.ministry_id:s for s in scopes}
        for s in scopes:
            s.is_active=s.ministry_id in ids
            if s.is_active and (normalize_existing or s.ministry_id not in previous):
                s.legacy_attendance_limits=False
        for mid in ids-existing.keys():
            db.add(UserMinistryScope(user_id=user.id,ministry_id=mid,is_active=True,
                legacy_attendance_limits=False,created_by_user_id=access.user_id))

    def create_user(self, data, role_ids=(), ministry_ids=()):
        password=str(data.get('password',''))
        try:
            AuthService.validate_new_password(password)
        except PasswordRecoveryError as exc:
            raise AdministrationError(str(exc)) from exc
        if password!=data.get('confirm_password'):
            raise AdministrationError('The passwords do not match.')
        status=data.get('status','ACTIVE')
        if status not in ('ACTIVE','INACTIVE'):
            raise AdministrationError('New accounts must be active or inactive.')
        if type(data.get('require_password_change',True)) is not bool:
            raise AdministrationError('Choose whether a password change is required.')
        hashed=PasswordHasher().hash(password)
        with self._db('USER_CREATE',write=True) as (db,access):
            user=User(id=__import__('uuid').uuid4(),status=UserStatus(status),password_hash=hashed,
                require_password_change=data.get('require_password_change',True),auth_revision=0,roles=[])
            self._profile(db,user,data)
            db.add(user)
            db.flush()
            self._set_roles(db,access,user,role_ids)
            self._set_scopes(db,access,user,ministry_ids)
            audit(db,access.user_id,'USER_CREATED',user_id=user.id,new=dict(self._account_snapshot(user),role_ids=sorted(str(r.id) for r in user.roles),ministry_ids=sorted(str(identifier(m)) for m in ministry_ids)))
            db.commit()
            return str(user.id)

    @staticmethod
    def _version(user,expected):
        if expected is not None and user.updated_at!=expected:
            raise AdministrationError('This account changed. Refresh before saving.')

    def update_profile(self,user_id,data,expected_updated_at=None):
        with self._db('USER_EDIT',write=True) as (db,access):
            user=self._user(db,user_id,True)
            self._version(user,expected_updated_at)
            old=self._account_snapshot(user)
            self._profile(db,user,data)
            audit(db,access.user_id,'USER_PROFILE_EDITED',user_id=user.id,old=old,new=self._account_snapshot(user))
            db.commit()

    def update_access(self,user_id,*,role_ids=None,ministry_ids=None,class_ids=None,normalize_existing=False,expected_updated_at=None):
        if type(normalize_existing) is not bool:
            raise AdministrationError('Choose whether to replace legacy attendance limits.')
        permission='ROLE_ASSIGN' if role_ids is not None else 'USER_SCOPE_MANAGE'
        with self._db(permission,write=True) as (db,access):
            user=self._user(db,user_id,True)
            self._version(user,expected_updated_at)
            scopes=db.scalars(select(UserMinistryScope).where(UserMinistryScope.user_id==user.id)).all()
            old=dict(role_ids=sorted(str(r.id) for r in user.roles),scopes=self._scope_snapshot(scopes))
            if class_ids is not None: old['school_class_ids']=[scope['id'] for scope in self._school_scopes(db,[user.id])[user.id]]
            if role_ids is not None:
                self._set_roles(db,access,user,role_ids)
            if ministry_ids is not None:
                self._set_scopes(db,access,user,ministry_ids,normalize_existing)
            if class_ids is not None: self._set_school_scopes(db,access,user,class_ids)
            user.updated_at=datetime.now(timezone.utc)
            user.auth_revision+=1
            self._protect_recovery(db)
            scopes=db.scalars(select(UserMinistryScope).where(UserMinistryScope.user_id==user.id)).all()
            new=dict(role_ids=sorted(str(r.id) for r in user.roles),scopes=self._scope_snapshot(scopes))
            if class_ids is not None:
                db.flush(); new['school_class_ids']=[scope['id'] for scope in self._school_scopes(db,[user.id])[user.id]]
            audit(db,access.user_id,'USER_ACCESS_CHANGED',user_id=user.id,old=old,new=new)
            db.commit()

    def set_status(self,user_id,status):
        if status not in ('ACTIVE','INACTIVE','SUSPENDED','LOCKED'):
            raise AdministrationError('Choose a valid account status.')
        permission='USER_EDIT' if status=='ACTIVE' else ('USER_LOCK' if status=='LOCKED' else 'USER_DEACTIVATE')
        with self._db(permission,write=True) as (db,access):
            user=self._user(db,user_id,True)
            if user.status==UserStatus.LOCKED and status=='ACTIVE':
                access.require_permission('USER_UNLOCK')
            old=dict(status=user.status.value)
            user.status=UserStatus(status)
            user.locked_until=None
            if status=='ACTIVE':
                user.failed_login_attempts=0
            user.auth_revision+=1
            self._protect_recovery(db)
            audit(db,access.user_id,'USER_STATUS_CHANGED',user_id=user.id,old=old,new=dict(status=status))
            db.commit()

    def unlock(self,user_id):
        with self._db('USER_UNLOCK',write=True) as (db,access):
            user=self._user(db,user_id,True)
            if user.status in (UserStatus.INACTIVE,UserStatus.SUSPENDED):
                raise AdministrationError('Activate this account separately before unlocking it.')
            old=dict(status=user.status.value,failed_login_attempts=user.failed_login_attempts)
            user.status=UserStatus.ACTIVE
            user.failed_login_attempts=0
            user.locked_until=None
            user.auth_revision+=1
            audit(db,access.user_id,'USER_UNLOCKED',user_id=user.id,old=old,new=dict(status='ACTIVE',failed_login_attempts=0))
            db.commit()

    def reset_password(self,user_id,password,confirm_password):
        if password!=confirm_password:
            raise AdministrationError('The passwords do not match.')
        try:
            AuthService.validate_new_password(password)
        except PasswordRecoveryError as exc:
            raise AdministrationError(str(exc)) from exc
        hashed=PasswordHasher().hash(password)
        with self._db('USER_RESET_PASSWORD',write=True) as (db,access):
            user=self._user(db,user_id,True)
            user.password_hash=hashed
            user.require_password_change=True
            user.auth_revision+=1
            audit(db,access.user_id,'PASSWORD_RESET',user_id=user.id,new=dict(require_password_change=True))
            db.commit()

    def reset_totp(self,user_id):
        with self._db('USER_RESET_TOTP',write=True) as (db,access):
            user=self._user(db,user_id,True)
            old=dict(totp_enabled=user.totp_enabled)
            user.totp_enabled=False
            user.totp_secret=None
            user.totp_confirmed_at=None
            user.auth_revision+=1
            audit(db,access.user_id,'TOTP_RESET',user_id=user.id,old=old,new=dict(totp_enabled=False,reenrollment_required=True))
            db.commit()
