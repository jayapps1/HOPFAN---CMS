"""Synthetic administration data for desktop validation; no database connection."""
from copy import deepcopy
from datetime import datetime,timezone
import uuid
from src.security.administration_permissions import PERMISSIONS as ADMIN
from src.security.application_permissions import PERMISSIONS as APP
from src.security.attendance_permissions import PERMISSIONS as ATTENDANCE


class PreviewAdministrationService:
    def __init__(self):
        now=datetime.now(timezone.utc)
        self.permissions=[dict(id=str(uuid.uuid4()),code=code,name=name,module='Administration' if code in ADMIN else code.split('_')[0].title(),
            is_active=True,assignable=True,description='') for code,name in (ADMIN|APP|ATTENDANCE).items()]
        self.roles=[dict(id=str(uuid.uuid4()),name=name,code=name.upper().replace(' ','_'),description='Operational access within assigned ministry scopes.',
            is_system=i==0,is_active=True,user_count=7,permission_count=len(self.permissions),permission_ids=[p['id'] for p in self.permissions],
            permissions=deepcopy(self.permissions),updated_at=now) for i,name in enumerate(('Church Administrator','Ministry Secretary','Attendance Officer'))]
        self.ministries=[dict(id=str(uuid.uuid4()),name=name,is_active=True,legacy_attendance_limits=False) for name in ('Youth Ministry','Choir / Music Ministry','Women’s Fellowship','Men’s Fellowship')]
        self.members=[dict(id=str(uuid.uuid4()),full_name='Ama Mensah' if i==0 else f'Member {i+1} Mensah',member_no=f'HOPFAN-2026-{i+1:04d}',
            phone='050 000 0000',email=f'member{i+1}@example.invalid',photo_path='',ministries=['Youth Ministry','Choir / Music Ministry'],user_id=None) for i in range(5)]
        self.users=[]
        for i in range(25):
            member=deepcopy(self.members[i%5])
            user=dict(id=str(uuid.uuid4()),full_name=member['full_name'] if i==0 else f'Staff {i+1} Mensah',username=f'staff{i+1}',email=f'staff{i+1}@example.invalid',phone='050 000 0000',
                member=member,member_id=member['id'],photo_path='',roles=deepcopy(self.roles[1:2]),scopes=deepcopy(self.ministries[:2]),
                status=('ACTIVE','LOCKED','INACTIVE','SUSPENDED')[i%4],last_login_at=now,created_at=now,updated_at=now,
                failed_login_attempts=5 if i==1 else 0,locked_until=now if i==1 else None,totp_enabled=True,
                require_password_change=False,auth_revision=0,effective_permissions=[p['code'] for p in self.permissions],configured_permissions=[p['code'] for p in self.permissions])
            self.users.append(user)
        self.events=[dict(id=str(uuid.uuid4()),action='USER_ACCESS_CHANGED',actor='Church Administrator',target='Ama Mensah',created_at=now,
            old_values={'roles':['Attendance Officer']},new_values={'roles':['Ministry Secretary'],'scopes':['Youth Ministry','Choir / Music Ministry']})]
        self.calls=[]

    def access_options(self,user_id=None):
        return dict(roles=[dict(r,assignable=True) for r in self.roles],ministries=deepcopy(self.ministries))
    def stats(self):
        return dict(total=len(self.users),**{status.lower():sum(u['status']==status for u in self.users) for status in ('ACTIVE','LOCKED','INACTIVE','SUSPENDED')})
    def list_users(self,search='',status='ALL',role_id=None,ministry_id=None,limit=25,offset=0):
        rows=[u for u in self.users if (status=='ALL' or u['status']==status) and search.lower() in (u['full_name']+' '+u['username']+' '+u['email']).lower()
            and (not role_id or role_id in [r['id'] for r in u['roles']]) and (not ministry_id or ministry_id in [s['id'] for s in u['scopes']])]
        return dict(total=len(rows),rows=deepcopy(rows[offset:offset+limit]))
    def get_user(self,uid): return deepcopy(next(u for u in self.users if u['id']==uid))
    def search_members(self,search='',limit=15,offset=0):
        rows=[m for m in self.members if search.lower() in (m['full_name']+' '+m['member_no']+' '+m['email']).lower()]
        return dict(total=len(rows),rows=deepcopy(rows[offset:offset+limit]))
    def create_user(self,data,role_ids=(),ministry_ids=()):
        self.calls.append(('create_user',dict(data),list(role_ids),list(ministry_ids)))
        return str(uuid.uuid4())
    def update_profile(self,uid,data,expected=None): self.calls.append(('update_profile',uid,dict(data)))
    def update_access(self,uid,**kwargs): self.calls.append(('update_access',uid,kwargs))
    def reset_password(self,uid,password,confirm): self.calls.append(('reset_password',uid));self.modify(uid,require_password_change=True)
    def reset_totp(self,uid): self.calls.append(('reset_totp',uid));self.modify(uid,totp_enabled=False)
    def unlock(self,uid): self.calls.append(('unlock',uid));self.modify(uid,status='ACTIVE',failed_login_attempts=0,locked_until=None)
    def set_status(self,uid,status): self.calls.append(('set_status',uid,status));self.modify(uid,status=status)
    def modify(self,uid,**data): next(u for u in self.users if u['id']==uid).update(data)
    def list_roles(self,search='',status='ALL',limit=25,offset=0):
        rows=[r for r in self.roles if search.lower() in r['name'].lower() and (status=='ALL' or r['is_active']==(status=='ACTIVE'))]
        return dict(total=len(rows),rows=deepcopy(rows[offset:offset+limit]))
    def get_role(self,rid): return deepcopy(next(r for r in self.roles if r['id']==rid))
    def permission_catalogue(self): return deepcopy(self.permissions)
    def create_role(self,data,permission_ids=()): self.calls.append(('create_role',data,permission_ids));return str(uuid.uuid4())
    def update_role(self,rid,data,permission_ids,expected=None): self.calls.append(('update_role',rid,data,permission_ids))
    def set_active(self,rid,active): self.calls.append(('set_active',rid,active))
    def audit_events(self,**kwargs): return dict(total=len(self.events),rows=deepcopy(self.events))
