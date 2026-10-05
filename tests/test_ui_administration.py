"""Administration layout and workflow validation with synthetic data only."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import unittest
import customtkinter as ctk
from PIL import ImageGrab
from src.ui import theme
from tests import test_ui_smoke as smoke
from tests.administration_preview import PreviewAdministrationService
from src.ui.administration.administration_view import AdministrationView
from src.ui.administration.dialogs import UserFormDialog,UserAccessDialog,UserProfileDialog,PasswordResetDialog
from src.ui.administration.role_dialogs import RoleFormDialog,RoleProfileDialog
from src.ui.login.account_security_dialogs import InitialPasswordDialog,AuthenticatorSetupDialog
from src.ui.dashboard.dashboard_view import DashboardView
from PIL import Image


class AdministrationUiTests(unittest.TestCase):
    setUpClass=classmethod(smoke.UiSmokeTests.setUpClass.__func__)
    tearDownClass=classmethod(smoke.UiSmokeTests.tearDownClass.__func__)
    setUp=smoke.UiSmokeTests.setUp
    tearDown=smoke.UiSmokeTests.tearDown
    pump=smoke.UiSmokeTests.pump
    wait_for=smoke.UiSmokeTests.wait_for
    assert_visible_in=smoke.UiSmokeTests.assert_visible_in

    def capture(self,name):
        path=Path('docs/screenshots/user_administration');path.mkdir(parents=True,exist_ok=True)
        self.pump()
        import ctypes
        from ctypes import wintypes
        get_parent=ctypes.windll.user32.GetParent
        get_parent.restype=wintypes.HWND
        get_parent.argtypes=[wintypes.HWND]
        target=self.root.grab_current() or self.root
        hwnd=get_parent(target.winfo_id())
        ImageGrab.grab(window=hwnd).save(path/(name+'.png'))

    def mount(self):
        service=PreviewAdministrationService()
        permissions=[p['code'] for p in service.permissions]
        shell=ctk.CTkFrame(self.root,fg_color=theme.BACKGROUND)
        shell.pack(fill='both',expand=True)
        sidebar=ctk.CTkFrame(shell,width=theme.SIDEBAR_WIDTH,fg_color=theme.SIDEBAR,corner_radius=0)
        sidebar.pack(side='left',fill='y');sidebar.pack_propagate(False)
        view=AdministrationView(shell,SimpleNamespace(id='preview'),permissions,user_service=service,role_service=service)
        view.pack(side='left',fill='both',expand=True)
        self.wait_for(lambda:len(view.body.records)==20,timeout=10)
        return shell,view,service,permissions

    def test_layouts_themes_directories_dialogs_and_groups(self):
        for width,height in ((1366,768),(1600,900),(1920,1080)):
            scale=self.root._get_window_scaling()
            self.root.geometry(f'{int((width-30)/scale)}x{int((height-70)/scale)}+0+0')
            for mode in ('light','dark'):
                ctk.set_appearance_mode(mode)
                shell,view,service,permissions=self.mount()
                self.pump()
                users=view.body
                for widget in (users.add_button,users.next_button,users.role,users.ministry): self.assert_visible_in(widget,self.root)
                row=users.rows.winfo_children()[0]
                self.assert_visible_in(row.view_button,users.rows._parent_canvas)
                self.capture(f'users_{width}_{mode}')
                form=users.create_user()
                self.wait_for(lambda:form.save_button.cget('state')=='normal',timeout=10)
                self.assert_visible_in(form.save_button,form)
                form.content._parent_canvas.yview_moveto(1);self.pump()
                self.capture(f'create_user_{width}_{mode}')
                form.scopes.open_popup();self.pump();self.assertIsNotNone(form.scopes.popup);form.scopes.close_popup()
                form.destroy()
                profile=UserProfileDialog(self.root,service,service.users[0],permissions,Mock())
                self.pump();self.assert_visible_in(profile.cancel_button,profile)
                self.capture(f'user_profile_{width}_{mode}');profile.destroy()
                view.selector.set('Roles');view.select('Roles')
                self.wait_for(lambda:len(view.body.records)==3,timeout=10);self.pump()
                self.capture(f'roles_{width}_{mode}')
                role_form=view.body.create_role()
                self.wait_for(lambda:role_form.save_button.cget('state')=='normal',timeout=15)
                self.assert_visible_in(role_form.save_button,role_form)
                role_form.content._parent_canvas.yview_moveto(.45);self.pump()
                self.capture(f'role_permissions_{width}_{mode}');role_form.destroy()
                view.selector.set('Permissions');view.select('Permissions')
                self.wait_for(lambda:len(view.body.permissions)>0,timeout=10)
                self.capture(f'permission_catalogue_{width}_{mode}')
                view.selector.set('Security audit');view.select('Security audit')
                self.wait_for(lambda:len(view.body.records)==1,timeout=10)
                self.assert_visible_in(view.body.next_button,self.root)
                self.capture(f'security_audit_{width}_{mode}')
                shell.destroy();self.pump()

    def test_create_member_link_filters_pagination_and_access(self):
        shell,view,service,permissions=self.mount()
        users=view.body
        users.page(1);self.wait_for(lambda:len(users.records)==5)
        users.status.set('Locked');users.refresh(True)
        self.wait_for(lambda:len(users.records)==6)
        form=users.create_user();self.wait_for(lambda:form.save_button.cget('state')=='normal',timeout=10)
        picker=form.pick_member();self.wait_for(lambda:picker.total==5)
        picker.search.insert(0,'Ama');picker.search.submit();self.wait_for(lambda:picker.total==1)
        picker.select(service.members[0]);self.pump()
        form.username.insert(0,'ama.mensah')
        form.password.insert(0,'Synthetic-Password!123');form.confirm.insert(0,'Synthetic-Password!123')
        form.roles.set_selected_ids([service.roles[1]['id']]);form.scopes.set_selected_ids([service.ministries[0]['id']])
        form.save();self.wait_for(lambda:not form.winfo_exists(),timeout=10)
        call=next(c for c in service.calls if c[0]=='create_user')
        self.assertEqual(call[1]['member_id'],service.members[0]['id'])
        self.assertTrue(call[1]['require_password_change'])
        self.assertEqual(call[3],[service.ministries[0]['id']])
        access=UserAccessDialog(self.root,service,service.users[0],Mock(),permissions)
        self.wait_for(lambda:access.save_button.cget('state')=='normal')
        access.scopes.set_selected_ids([service.ministries[1]['id']]);access.save()
        self.wait_for(lambda:not access.winfo_exists())
        self.assertEqual(next(c for c in service.calls if c[0]=='update_access')[2]['ministry_ids'],[service.ministries[1]['id']])
        shell.destroy()

    def test_role_and_security_actions_and_required_password_change(self):
        service=PreviewAdministrationService();permissions=[p['code'] for p in service.permissions]
        form=RoleFormDialog(self.root,service,Mock())
        self.wait_for(lambda:form.save_button.cget('state')=='normal',timeout=15)
        form.name.insert(0,'Scoped officer');form.code.insert(0,'SCOPED_OFFICER')
        next(iter(form.variables.values())).set(True)
        form.save();self.wait_for(lambda:not form.winfo_exists())
        self.assertEqual(len(next(c for c in service.calls if c[0]=='create_role')[2]),1)
        profile=UserProfileDialog(self.root,service,service.users[1],permissions,Mock())
        confirm=profile.confirm('Unlock account','Clear the lock.',lambda:service.unlock(service.users[1]['id']))
        self.pump();confirm.confirm();self.wait_for(lambda:not profile.winfo_exists())
        self.assertEqual(service.users[1]['status'],'ACTIVE')
        reset=PasswordResetDialog(self.root,service,service.users[0],Mock())
        reset.generate();self.assertEqual(reset.password.get(),reset.confirm.get())
        reset.save();self.wait_for(lambda:not reset.winfo_exists())
        self.assertTrue(service.users[0]['require_password_change'])
        fake_auth=Mock()
        fake_auth.change_initial_password.return_value=SimpleNamespace(id='preview',require_password_change=False)
        signed_in=Mock()
        initial=InitialPasswordDialog(self.root,fake_auth,SimpleNamespace(id='preview',_authentication_ticket='synthetic-ticket'),signed_in)
        self.pump();initial.password.insert(0,'Synthetic-New!123');initial.confirm.insert(0,'Synthetic-New!123')
        self.assert_visible_in(initial.save_button,initial)
        initial.save();self.wait_for(lambda:not initial.winfo_exists())
        signed_in.assert_called_once()
        fake_auth.change_initial_password.assert_called_once_with('preview','Synthetic-New!123','Synthetic-New!123','synthetic-ticket')

    def test_restricted_navigation_and_controls(self):
        service=PreviewAdministrationService()
        view=AdministrationView(self.root,SimpleNamespace(id='preview'),{'USER_VIEW'},user_service=service,role_service=service)
        view.pack(fill='both',expand=True)
        self.wait_for(lambda:len(view.body.records)==20)
        self.assertEqual(view.tabs,['Users'])
        self.assertIsNone(view.body.add_button)
        self.assertFalse(hasattr(view.body.rows.winfo_children()[0],'edit_button'))
        view.destroy()


    def test_technical_dashboard_has_account_metrics_without_business_data(self):
        service=PreviewAdministrationService()
        attendance=Mock()
        attendance.capabilities.return_value=dict(permissions=['USER_VIEW','ADMINISTRATION_VIEW'],can_view=False,
            can_create=False,can_manage_access=False,can_report=False,church_wide=False,scope_ids=[])
        with patch('src.ui.dashboard.dashboard_view.AttendanceService',return_value=attendance), \
             patch('src.ui.dashboard.dashboard_view.MemberService') as members, \
             patch('src.ui.dashboard.dashboard_view.MinistryService'), \
             patch('src.ui.dashboard.dashboard_view.UserService',return_value=service):
            view=DashboardView(self.root,self.user,Mock())
            self.pump(.5)
            self.assertEqual(set(view.allowed_pages),{'Dashboard','Administration'})
            self.assertEqual(view.context,'Account and access administration')
            self.assertIsNone(view.attendance_metric)
            members.return_value.stats.assert_not_called()
            attendance.overview.assert_not_called()
            self.assert_visible_in(view.authenticator_button,self.root)
            view.destroy()

    def test_user_owned_authenticator_enrollment(self):
        fake=Mock()
        user=SimpleNamespace(id='synthetic-user',email='synthetic@example.invalid',username='synthetic',_authentication_ticket='synthetic-ticket')
        fake.authenticate_password.return_value=user
        fake.create_totp_enrollment.return_value=('SYNTHETICSETUPKEY','synthetic-uri')
        fake.totp.qr_image.return_value=Image.new('RGB',(250,250),'white')
        fake.confirm_totp_enrollment.return_value=user
        enrolled=Mock()
        dialog=AuthenticatorSetupDialog(self.root,fake,user,enrolled)
        self.pump()
        dialog.password.insert(0,'Synthetic-Password!123')
        dialog.verify()
        self.wait_for(lambda:hasattr(dialog,'code'),timeout=10)
        fake.create_totp_enrollment.assert_called_once_with('synthetic-user','synthetic-ticket')
        dialog.confirm_enrollment('123456')
        self.wait_for(lambda:not dialog.winfo_exists())
        enrolled.assert_called_once_with(user)
        fake.confirm_totp_enrollment.assert_called_once_with('synthetic-user','SYNTHETICSETUPKEY','123456','synthetic-ticket')
        fake.cancel_totp_enrollment.assert_called_once_with('synthetic-user','synthetic-ticket')

if __name__=='__main__': unittest.main()
