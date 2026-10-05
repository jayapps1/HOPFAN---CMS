"""Software role lifecycle and permission catalogue; assignments are preserved."""
import re
from datetime import datetime, timezone
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import selectinload
from src.models import Role, Permission, User
from src.models.associations import user_roles, role_permissions
from src.services.administration_base import AdministrationService, AdministrationError, identifier, page_bounds, search_pattern, audit
from src.services.authorization_service import AuthorizationDenied


class RoleService(AdministrationService):
    @staticmethod
    def _dto(role, users=0):
        return dict(id=str(role.id),code=role.code,name=role.name,description=role.description or '',
            is_system=role.is_system,is_active=role.is_active,user_count=users,
            permission_count=len(role.permissions),permission_ids=[str(p.id) for p in role.permissions],
            permissions=[dict(id=str(p.id),code=p.code,name=p.name,module=p.module,is_active=p.is_active) for p in sorted(role.permissions,key=lambda p:(p.module,p.name))],
            updated_at=role.updated_at)

    def list_roles(self,search='',status='ALL',limit=25,offset=0):
        with self._db('ROLE_VIEW') as (db,access):
            counts=select(user_roles.c.role_id,func.count().label('users')).group_by(user_roles.c.role_id).subquery()
            stmt=select(Role,func.coalesce(counts.c.users,0)).outerjoin(counts,counts.c.role_id==Role.id)
            if search.strip():
                pattern=search_pattern(search)
                stmt=stmt.where(or_(Role.name.ilike(pattern,escape='\\'),Role.code.ilike(pattern,escape='\\'),Role.description.ilike(pattern,escape='\\')))
            if status!='ALL':
                if status not in ('ACTIVE','INACTIVE'):
                    raise AdministrationError('Choose a valid role status.')
                stmt=stmt.where(Role.is_active.is_(status=='ACTIVE'))
            total=db.scalar(select(func.count()).select_from(stmt.subquery()))
            limit,offset=page_bounds(limit,offset)
            rows=db.execute(stmt.options(selectinload(Role.permissions)).order_by(Role.name,Role.id).limit(limit).offset(offset))
            return dict(total=total,rows=[self._dto(r,count) for r,count in rows])

    def get_role(self,role_id):
        with self._db('ROLE_VIEW') as (db,access):
            role=self._role(db,role_id)
            count=db.scalar(select(func.count()).select_from(user_roles).where(user_roles.c.role_id==role.id))
            return self._dto(role,count)

    @staticmethod
    def _role(db,role_id,lock=False):
        stmt=select(Role).where(Role.id==identifier(role_id)).options(selectinload(Role.permissions))
        row=db.scalar(stmt.with_for_update() if lock else stmt)
        if not row:
            raise AdministrationError('Software role not found.')
        return row

    def permission_catalogue(self):
        with self._db('PERMISSION_VIEW') as (db,access):
            return [dict(id=str(p.id),code=p.code,name=p.name,module=p.module,description=p.description or '',
                is_active=p.is_active,assignable=access.has(p.code)) for p in db.scalars(select(Permission).order_by(Permission.module,Permission.name))]

    @staticmethod
    def _values(db,role,data):
        name=str(data.get('name','')).strip()
        code=str(data.get('code','')).strip().upper()
        description=str(data.get('description','')).strip()
        if not name or len(name)>120:
            raise AdministrationError('Enter a role name of 120 characters or fewer.')
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{1,79}',code):
            raise AdministrationError('Role code must use 2–80 uppercase letters, numbers or underscores.')
        if len(description)>3000:
            raise AdministrationError('Description must be 3,000 characters or fewer.')
        for field,value in ((Role.name,name),(Role.code,code)):
            if db.scalar(select(Role.id).where(func.lower(field)==value.lower(),Role.id!=role.id)):
                raise AdministrationError('This role name or code is already used.')
        if role.is_system and role.code!=code:
            raise AdministrationError('System role codes cannot be changed.')
        role.name,role.code,role.description=name,code,description or None

    def _set_permissions(self,db,access,role,permission_ids):
        ids=set(identifier(i) for i in permission_ids)
        permissions=db.scalars(select(Permission).where(Permission.id.in_(ids))).all()
        if len(permissions)!=len(ids):
            raise AdministrationError('Select valid permissions.')
        previous=set(p.id for p in role.permissions)
        # Editing grants on a role that exceeds the actor's authority would allow
        # indirect escalation through another account. Technical admins cannot.
        if any(p.is_active and not access.has(p.code) for p in role.permissions):
            raise AuthorizationDenied('A business administrator must edit this role because it grants permissions outside your authority.')
        for p in permissions:
            if p.id not in previous and (not p.is_active or not access.has(p.code)):
                raise AuthorizationDenied('You may grant only active permissions you hold.')
        role.permissions=permissions

    def create_role(self,data,permission_ids=()):
        import uuid
        with self._db('ROLE_CREATE',write=True) as (db,access):
            role=Role(id=uuid.uuid4(),is_active=True,is_system=False,permissions=[])
            self._values(db,role,data)
            self._set_permissions(db,access,role,permission_ids)
            db.add(role)
            db.flush()
            audit(db,access.user_id,'ROLE_CREATED',role_id=role.id,new=dict(code=role.code,name=role.name,permissions=sorted(p.code for p in role.permissions)))
            db.commit()
            return str(role.id)

    def update_role(self,role_id,data,permission_ids,expected_updated_at=None):
        with self._db('ROLE_EDIT',write=True) as (db,access):
            role=self._role(db,role_id,True)
            if expected_updated_at is not None and role.updated_at!=expected_updated_at:
                raise AdministrationError('This role changed. Refresh before saving.')
            old=dict(code=role.code,name=role.name,description=role.description,permissions=sorted(p.code for p in role.permissions))
            self._values(db,role,data)
            self._set_permissions(db,access,role,permission_ids)
            role.updated_at=datetime.now(timezone.utc)
            db.execute(update(User).where(User.id.in_(select(user_roles.c.user_id).where(user_roles.c.role_id==role.id)))
                .values(auth_revision=User.auth_revision+1))
            self._protect_recovery(db)
            audit(db,access.user_id,'ROLE_EDITED',role_id=role.id,old=old,
                new=dict(code=role.code,name=role.name,description=role.description,permissions=sorted(p.code for p in role.permissions)))
            db.commit()

    def set_active(self,role_id,is_active):
        if type(is_active) is not bool:
            raise AdministrationError('Choose a valid role status.')
        with self._db('ROLE_ARCHIVE',write=True) as (db,access):
            role=self._role(db,role_id,True)
            if role.is_system:
                raise AdministrationError('System roles cannot be deactivated. Edit their permissions deliberately instead.')
            if is_active and any(p.is_active and not access.has(p.code) for p in role.permissions):
                raise AuthorizationDenied('You cannot activate a role with permissions outside your authority.')
            old=dict(is_active=role.is_active)
            role.is_active=is_active
            role.updated_at=datetime.now(timezone.utc)
            db.execute(update(User).where(User.id.in_(select(user_roles.c.user_id).where(user_roles.c.role_id==role.id)))
                .values(auth_revision=User.auth_revision+1))
            self._protect_recovery(db)
            audit(db,access.user_id,'ROLE_STATUS_CHANGED',role_id=role.id,old=old,new=dict(is_active=is_active))
            db.commit()
