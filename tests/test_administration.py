"""Account/RBAC integration tests in a disposable PostgreSQL schema."""
import json
import unittest
import uuid
from datetime import date
from sqlalchemy import event, select
from argon2 import PasswordHasher
import pyotp
from tests import test_attendance as fixtures
from src.models import (User, UserStatus, Role, Permission, UserMinistryScope, SecurityAuditLog,
    MinistryPosition, MinistryLeadershipAssignment, MemberMinistry)
from src.services.user_service import UserService
from src.services.role_service import RoleService
from src.services.auth_service import AuthService, AuthenticationError, PasswordRecoveryError
from src.services.authorization_service import AuthorizationService, AuthorizationDenied
from src.services.administration_base import AdministrationError
from src.services.member_service import MemberService
from src.services.attendance_service import AttendanceService
from src.models import AttendanceRecord
from src.security.administration_permissions import PERMISSIONS
from importlib import import_module


class AdministrationTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.AttendanceTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.AttendanceTests.tearDownClass.__func__)
    tearDown=fixtures.AttendanceTests.tearDown

    def setUp(self):
        fixtures.AttendanceTests.setUp(self)
        permissions={p.code:p for p in self.db.scalars(select(Permission))}
        for code,name in PERMISSIONS.items():
            if code not in permissions:
                permissions[code]=Permission(code=code,name=name,module='Administration',is_active=True)
                self.db.add(permissions[code])
        admin=self.db.scalar(select(Role).where(Role.code=='TEST_ADMIN'))
        admin.permissions=list(permissions.values())
        self.db.commit()
        self.service=UserService(self.users['Admin'].id,self.factory)
        self.roles=RoleService(self.users['Admin'].id,self.factory)
        self.auth=AuthService(self.factory)
        self.password='Original-Test!123'
        self.next_password='Changed-Test!456'
        self.officer=self.db.scalar(select(Role).where(Role.code=='TEST_LEADER'))

    def create(self,scopes=('Youth',),**data):
        suffix=uuid.uuid4().hex[:10]
        values=dict(username='staff'+suffix,email='staff'+suffix+'@example.invalid',phone='0500000000',
            member_id=str(self.members['Ama'].id),password=self.password,confirm_password=self.password,
            status='ACTIVE',require_password_change=False)
        values.update(data)
        return self.service.create_user(values,[str(self.officer.id)],[str(self.ministries[name].id) for name in scopes])

    def test_create_link_roles_scopes_and_duplicate_member(self):
        uid=self.create()
        user=self.service.get_user(uid)
        self.assertEqual(user['member']['id'],str(self.members['Ama'].id))
        self.assertEqual(user['roles'][0]['id'],str(self.officer.id))
        self.assertEqual(user['scopes'][0]['id'],str(self.ministries['Youth'].id))
        self.assertFalse(user['scopes'][0]['legacy_attendance_limits'])
        with self.assertRaisesRegex(AdministrationError,'This member already has a HOPFAN user account'):
            self.create()
        with self.assertRaisesRegex(AdministrationError,'username is already used'):
            self.create(member_id=None,username=user['username'].upper())
        with self.assertRaisesRegex(AdministrationError,'email address is already used'):
            self.create(member_id=None,email=user['email'].upper())
        logged=self.auth.authenticate_password(user['username'],self.password)
        self.assertEqual(str(logged.id),uid)
        self.assertIsNotNone(logged.last_login_at)
        self.assertNotIn('password_hash',user)
        self.assertNotIn('totp_secret',user)

    def test_own_multiple_scope_global_and_service_denial(self):
        uid=self.create()
        authz=AuthorizationService(uid,self.factory)
        self.assertTrue(authz.can_access_ministry(uid,self.ministries['Youth'].id,'MEMBERS_VIEW_OWN_MINISTRY'))
        for name in ('Women','Men'):
            with self.assertRaises(AuthorizationDenied):
                authz.require_ministry_permission(uid,self.ministries[name].id,'MEMBERS_VIEW_OWN_MINISTRY')
        reopen=self.db.scalar(select(Permission).where(Permission.code=='ATTENDANCE_REOPEN_SESSION'))
        self.officer.permissions.append(reopen);self.db.commit()
        self.assertTrue(authz.can_access_ministry(uid,self.ministries['Youth'].id,'ATTENDANCE_REOPEN_SESSION'))
        for code in ('ATTENDANCE_REOPEN_SESSION','ATTENDANCE_VIEW_AUDIT'):
            with self.assertRaises(AuthorizationDenied): authz.require_ministry_permission(uid,self.ministries['Women'].id,code)
        directory=MemberService(uid,self.factory).list_members()
        self.assertEqual({m['first_name'] for m in directory},{'Ama','Yaw'})
        self.service.update_access(uid,ministry_ids=[str(self.ministries['Youth'].id),str(self.ministries['Choir'].id)])
        self.assertTrue(authz.has_ministry_scope(uid,self.ministries['Choir'].id))
        self.assertFalse(authz.can_access_ministry(uid,self.ministries['Men'].id,'MEMBERS_VIEW_OWN_MINISTRY'))
        global_access=AuthorizationService(self.users['Admin'].id,self.factory)
        self.assertFalse(global_access.get_ministry_scopes())
        self.assertTrue(global_access.can_access_ministry(self.users['Admin'].id,self.ministries['Women'].id,'MEMBERS_VIEW_OWN_MINISTRY'))
        for code in ('MINISTRY_POSITION_VIEW','ATTENDANCE_CLOSE_SESSION','ATTENDANCE_EXPORT'):
            self.assertTrue(global_access.can_access_ministry(self.users['Admin'].id,self.ministries['Women'].id,code))
        with self.assertRaises(AuthorizationDenied): MemberService(uid,self.factory).get_member(self.members['Esi'].id)

    def test_legacy_restrictions_preserved_until_explicit_conversion(self):
        uid=self.create()
        scope=self.db.scalar(select(UserMinistryScope).where(UserMinistryScope.user_id==uuid.UUID(uid)))
        scope.legacy_attendance_limits=True
        scope.can_view_attendance=True
        scope.can_record_attendance=False
        self.db.commit()
        a=AuthorizationService(uid,self.factory).context()
        self.assertTrue(a.ministries('view'))
        self.assertFalse(a.ministries('record'))
        self.service.update_access(uid,ministry_ids=[str(self.ministries['Youth'].id)])
        self.assertFalse(AuthorizationService(uid,self.factory).context().ministries('record'))
        self.service.update_access(uid,ministry_ids=[str(self.ministries['Youth'].id)],normalize_existing=True)
        self.assertTrue(AuthorizationService(uid,self.factory).context().ministries('record'))

    def test_deactivation_keeps_history_and_rejects_authentication(self):
        uid=self.create()
        user=self.service.get_user(uid)
        session=self.services['Admin'].create_session(title='Historical attendance',session_type='SUNDAY_SERVICE',scope_type='GLOBAL',session_date=date.today())
        AttendanceService(uid,self.factory).mark(session['id'],self.members['Ama'].id,'PRESENT')
        self.service.set_status(uid,'INACTIVE')
        marked=self.db.scalar(select(AttendanceRecord).where(AttendanceRecord.session_id==uuid.UUID(session['id']),AttendanceRecord.member_id==self.members['Ama'].id))
        self.assertEqual(marked.marked_by_user_id,uuid.UUID(uid))
        with self.assertRaises(AuthenticationError): self.auth.authenticate_password(user['email'],self.password)
        with self.assertRaises(AuthorizationDenied): AuthorizationService(uid,self.factory).context()
        self.db.expire_all()
        self.assertIsNotNone(self.db.get(User,uuid.UUID(uid)))
        self.assertEqual(len(self.db.get(User,uuid.UUID(uid)).roles),1)
        self.assertEqual(self.db.scalar(select(MemberMinistry.id).where(MemberMinistry.member_id==self.members['Ama'].id)) is not None,True)
        self.assertTrue(self.service.audit_events(user_id=uid)['rows'])

    def test_failed_login_locks_and_authorized_unlock_is_audited(self):
        uid=self.create(); user=self.service.get_user(uid)
        for _ in range(5):
            with self.assertRaises(AuthenticationError): self.auth.authenticate_password(user['email'],'Wrong-Password!')
        locked=self.service.get_user(uid)
        self.assertEqual(locked['status'],'LOCKED')
        self.assertEqual(locked['failed_login_attempts'],5)
        with self.assertRaises(AuthenticationError): self.auth.authenticate_password(user['email'],self.password)
        self.service.unlock(uid)
        self.assertEqual(self.service.get_user(uid)['status'],'ACTIVE')
        self.assertEqual(self.auth.authenticate_password(user['email'],self.password).id,uuid.UUID(uid))
        actions={e['action'] for e in self.service.audit_events(user_id=uid)['rows']}
        self.assertTrue({'USER_UNLOCKED','ACCOUNT_LOCKED','LOGIN_FAILED','LOGIN_SUCCESS'}.issubset(actions))
        self.service.set_status(uid,'LOCKED')
        with self.assertRaises(AuthenticationError): self.auth.authenticate_password(user['email'],self.password)

    def test_argon2_reset_requires_proof_bound_password_change_without_secrets(self):
        uid=self.create(); user=self.service.get_user(uid)
        self.service.reset_password(uid,self.next_password,self.next_password)
        with self.assertRaises(AuthenticationError): self.auth.authenticate_password(user['email'],self.password)
        pending=self.auth.authenticate_password(user['email'],self.next_password)
        self.assertTrue(pending.require_password_change)
        self.assertTrue(pending.password_hash.startswith('$argon2'))
        with self.assertRaises(AuthorizationDenied): AuthorizationService(uid,self.factory).context()
        with self.assertRaises(AuthenticationError): self.auth.change_initial_password(pending.id,'Final-Password!789','Final-Password!789','invalid-ticket')
        with self.assertRaises(PasswordRecoveryError): self.auth.change_initial_password(pending.id,self.next_password,self.next_password,pending._authentication_ticket)
        done=self.auth.change_initial_password(pending.id,'Final-Password!789','Final-Password!789',pending._authentication_ticket)
        self.assertFalse(done.require_password_change)
        self.assertTrue(self.auth.session_valid(done.id,done.auth_revision))
        serialized=json.dumps(self.service.audit_events(user_id=uid),default=str)
        for secret in (self.password,self.next_password,'Final-Password!789',done.password_hash): self.assertNotIn(secret,serialized)

    def test_totp_reset_old_codes_denied_and_self_enrollment_only(self):
        uid=self.create(); user=self.service.get_user(uid)
        signed=self.auth.authenticate_password(user['email'],self.password)
        with self.assertRaises(AuthenticationError): self.auth.create_totp_enrollment(signed.id)
        secret,uri=self.auth.create_totp_enrollment(signed.id,signed._authentication_ticket)
        enrolled=self.auth.confirm_totp_enrollment(signed.id,secret,pyotp.TOTP(secret).now(),signed._authentication_ticket)
        self.assertTrue(enrolled.totp_enabled)
        self.assertNotEqual(secret,enrolled.totp_secret)
        self.assertEqual(self.auth.authenticate_totp_only(user['username'],pyotp.TOTP(secret).now()).id,signed.id)
        self.service.reset_totp(uid)
        with self.assertRaises(AuthenticationError): self.auth.authenticate_totp_only(user['email'],pyotp.TOTP(secret).now())
        with self.assertRaises(AuthenticationError): self.auth.create_totp_enrollment(signed.id,enrolled._authentication_ticket)
        after=self.service.get_user(uid)
        self.assertFalse(after['totp_enabled'])
        self.db.expire_all()
        self.assertIsNone(self.db.get(User,signed.id).totp_secret)
        audit_text=json.dumps(self.service.audit_events(user_id=uid),default=str)
        for private in (secret,uri,enrolled.totp_secret): self.assertNotIn(private,audit_text)
        resigned=self.auth.authenticate_password(user['email'],self.password)
        new_secret,_=self.auth.create_totp_enrollment(resigned.id,resigned._authentication_ticket)
        self.assertNotEqual(secret,new_secret)

    def test_software_role_removal_preserves_church_office(self):
        uid=self.create()
        position=MinistryPosition(ministry_id=self.ministries['Youth'].id,code='SECRETARY',name='Secretary',is_leadership=True,is_active=True)
        self.db.add(position);self.db.flush()
        assignment=MinistryLeadershipAssignment(ministry_id=self.ministries['Youth'].id,member_id=self.members['Ama'].id,
            position_id=position.id,position_name='Secretary',position_code='SECRETARY',start_date=date.today(),is_current=True)
        self.db.add(assignment);self.db.commit()
        self.service.update_access(uid,role_ids=[])
        self.assertFalse(AuthorizationService(uid,self.factory).get_effective_permissions())
        self.assertTrue(self.db.get(MinistryLeadershipAssignment,assignment.id).is_current)

    def test_last_administrator_and_technical_escalation_blocked(self):
        admin_id=self.users['Admin'].id
        with self.assertRaises(AdministrationError): self.service.set_status(admin_id,'INACTIVE')
        with self.assertRaises(AdministrationError): self.service.update_access(admin_id,role_ids=[])
        administrator=self.db.scalar(select(Role).where(Role.code=='TEST_ADMIN'))
        with self.assertRaises(AdministrationError): self.roles.update_role(administrator.id,dict(name=administrator.name,code=administrator.code,description=''),[])
        permissions={p.code:p for p in self.db.scalars(select(Permission))}
        technical=Role(code='TECH_TEST',name='Technical test role',is_active=True,permissions=[permissions[c] for c in PERMISSIONS])
        tech_user=User(username='tech-test',email='tech-test@example.invalid',password_hash='unused',status=UserStatus.ACTIVE,roles=[technical])
        self.db.add_all([technical,tech_user]);self.db.commit()
        tech_service=UserService(tech_user.id,self.factory)
        self.assertNotIn('FINANCE_VIEW',AuthorizationService(tech_user.id,self.factory).get_effective_permissions())
        uid=self.create(member_id=None)
        administrator=self.db.scalar(select(Role).where(Role.code=='TEST_ADMIN'))
        with self.assertRaises(AuthorizationDenied): tech_service.update_access(uid,role_ids=[str(administrator.id)])
        with self.assertRaises(AuthorizationDenied): RoleService(tech_user.id,self.factory).update_role(administrator.id,
            dict(name=administrator.name,code=administrator.code,description=''),[str(p.id) for p in administrator.permissions])

    def test_role_lifecycle_assignment_retention_and_seed_idempotence(self):
        catalogue=self.roles.permission_catalogue()
        ids=[p['id'] for p in catalogue if p['code']=='MEMBERS_VIEW_OWN_MINISTRY']
        rid=self.roles.create_role(dict(code='CUSTOM_SECRETARY',name='Custom secretary',description='Scoped'),ids)
        role=self.roles.get_role(rid)
        self.assertFalse(role['is_system'])
        uid=self.create()
        self.service.update_access(uid,role_ids=[rid])
        self.roles.set_active(rid,False)
        self.assertFalse(AuthorizationService(uid,self.factory).get_effective_permissions())
        self.assertEqual(self.roles.get_role(rid)['user_count'],1)
        self.roles.set_active(rid,True)
        self.assertTrue(AuthorizationService(uid,self.factory).get_effective_permissions())
        module=import_module('migrations.versions.a91c73d5f204_user_administration')
        module.seed_missing(self.db.connection());self.db.commit()
        role=self.db.scalar(select(Role).where(Role.code=='SYSTEM_ADMIN'))
        role.permissions=[];role.is_active=False;self.db.commit()
        module.seed_missing(self.db.connection());self.db.commit()
        self.db.expire_all()
        self.assertFalse(self.db.get(Role,role.id).is_active)
        self.assertFalse(self.db.get(Role,role.id).permissions)
        with self.assertRaises(AdministrationError): self.roles.set_active(role.id,False)

    def test_pagination_filters_and_fixed_query_count(self):
        uid=self.create()
        measured=[]
        def count(*args): measured.append(1)
        event.listen(self.test_engine,'before_cursor_execute',count)
        try:
            self.service.list_users(limit=1)
            small=len(measured);measured.clear()
            self.service.list_users(limit=100)
            large=len(measured)
        finally: event.remove(self.test_engine,'before_cursor_execute',count)
        self.assertLessEqual(large,small+1)
        self.assertLessEqual(large,12)
        page=self.service.list_users(search='Ama',role_id=str(self.officer.id),ministry_id=str(self.ministries['Youth'].id))
        self.assertEqual([r['id'] for r in page['rows']],[uid])
        self.assertEqual(self.service.list_users(limit=1,offset=1)['rows'].__len__(),1)

    def test_self_service_recovery_cannot_reset_without_verified_totp_or_reactivate(self):
        uid=self.create(); user=self.service.get_user(uid)
        with self.assertRaises(PasswordRecoveryError): self.auth.reset_password(uuid.UUID(uid),self.next_password)
        signed=self.auth.authenticate_password(user['email'],self.password)
        secret,_=self.auth.create_totp_enrollment(signed.id,signed._authentication_ticket)
        self.auth.confirm_totp_enrollment(signed.id,secret,pyotp.TOTP(secret).now(),signed._authentication_ticket)
        self.auth.verify_recovery_totp(signed.id,pyotp.TOTP(secret).now())
        self.service.set_status(uid,'INACTIVE')
        with self.assertRaises(PasswordRecoveryError): self.auth.reset_password(signed.id,self.next_password)
        self.assertEqual(self.service.get_user(uid)['status'],'INACTIVE')


if __name__=='__main__': unittest.main()
