"""Desktop interaction checks using synthetic members and mocked authentication."""
from datetime import date
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import customtkinter as ctk

from src.services.auth_service import AuthenticationError
from src.services.member_service import MemberServiceError
from src.ui import theme
from src.ui.components.modern_select import ModernSelect
from src.ui.components.multi_select_dropdown import MultiSelectDropdown
from src.ui.login.login_view import LoginView
from src.ui.members.member_form_dialog import MemberFormDialog
from tests import test_ui_smoke as smoke


class UiRefinementTests(unittest.TestCase):
    setUpClass = classmethod(smoke.UiSmokeTests.setUpClass.__func__)
    tearDownClass = classmethod(smoke.UiSmokeTests.tearDownClass.__func__)
    setUp = smoke.UiSmokeTests.setUp
    tearDown = smoke.UiSmokeTests.tearDown
    pump = smoke.UiSmokeTests.pump
    wait_for = smoke.UiSmokeTests.wait_for
    assert_visible_in = smoke.UiSmokeTests.assert_visible_in
    capture = smoke.UiSmokeTests.capture

    def member_service(self):
        service = Mock()
        service.list_ministries.return_value = [dict(id=f'ministry-{index}', name=name) for index,name in enumerate(
            ['Youth Ministry','Choir / Music Ministry','ICT Ministry','Media Ministry','Prayer Ministry',
             "Women's Fellowship",'Counselling Ministry','Evangelism Ministry'])]
        # Hold the form open after submitting, so the payload can be examined.
        service.create_member.side_effect = MemberServiceError('Synthetic validation response')
        service.update_member.side_effect = MemberServiceError('Synthetic validation response')
        return service

    def test_baptism_toggle_calendar_and_null_submission(self):
        service = self.member_service()
        dialog = MemberFormDialog(self.root, service, lambda:None)
        self.wait_for(lambda:bool(dialog.ministry_select.options))
        self.assertEqual(dialog.baptism_date.entry.cget('state'),'disabled')
        self.assertEqual(dialog.baptism_date.calendar_button.cget('state'),'disabled')
        self.assertIsNone(dialog.baptism_date.open_calendar())
        dialog.variables['first_name'].set('Synthetic')
        dialog.variables['last_name'].set('Member')
        dialog.save()
        self.wait_for(lambda:dialog.save_button.cget('state')=='normal')
        submitted = service.create_member.call_args.args[0]
        self.assertFalse(submitted['baptized'])
        self.assertIsNone(submitted['baptism_date'])

        dialog.baptized_var.set(True)
        self.assertEqual(dialog.baptism_date.entry.cget('state'),'normal')
        self.assertEqual(dialog.baptism_date.calendar_button.cget('state'),'normal')
        dialog.content._parent_canvas.yview_moveto(1)
        self.pump()
        calendar = dialog.baptism_date.open_calendar()
        self.pump()
        calendar.select(date(2026,10,5))
        self.assertEqual(dialog.variables['baptism_date'].get(),'05/10/2026')
        dialog.save()
        self.wait_for(lambda:dialog.save_button.cget('state')=='normal')
        submitted = service.create_member.call_args.args[0]
        self.assertTrue(submitted['baptized'])
        self.assertEqual(submitted['baptism_date'],'2026-10-05')
        # Disable while the calendar is still opening; its delayed grab is cancelled.
        calendar = dialog.baptism_date.open_calendar()
        dialog.baptized_var.set(False)
        self.pump(.1)
        self.assertFalse(calendar.winfo_exists())
        self.assertEqual(dialog.grab_current(),dialog)
        self.assertEqual(dialog.variables['baptism_date'].get(),'')
        # Even an externally supplied stale/invalid value is not submitted while off.
        dialog.variables['baptism_date'].set('stale value')
        dialog.save()
        self.wait_for(lambda:dialog.save_button.cget('state')=='normal')
        self.assertIsNone(service.create_member.call_args.args[0]['baptism_date'])
        dialog.destroy()

    def test_edit_preselection_deselection_and_baptism_in_both_themes(self):
        for mode in ('light','dark'):
            ctk.set_appearance_mode(mode)
            for baptized in (False,True):
                member = dict(id='preview-member',full_name='Synthetic Member',member_no='PREVIEW-001',
                    first_name='Synthetic',last_name='Member',baptized=baptized,baptism_date='2026-10-05',
                    ministry_ids=['ministry-0','ministry-1'])
                service = self.member_service()
                dialog = MemberFormDialog(self.root,service,lambda:None,member=member)
                self.wait_for(lambda:bool(dialog.ministry_select.options))
                self.assertEqual(dialog.variables['baptism_date'].get(),'05/10/2026' if baptized else '')
                self.assertEqual(dialog.baptism_date.enabled,baptized)
                self.assertEqual(set(dialog.ministry_select.get()),set(member['ministry_ids']))
                dialog.ministry_select.pick('ministry-2')
                dialog.ministry_select.pick('ministry-1')
                dialog.ministry_select.pick('ministry-1')
                self.assertEqual(set(dialog.ministry_select.get()),{'ministry-0','ministry-1','ministry-2'})
                self.assertEqual(dialog.ministry_select.variable.get(),'3 ministries selected')
                dialog.content._parent_canvas.yview_moveto(1)
                self.pump()
                self.assert_visible_in(dialog.save_button,self.root)
                self.capture(f'refinement_member_{mode}_{"on" if baptized else "off"}')
                dialog.ministry_select.open_popup()
                self.pump()
                popup = dialog.ministry_select.popup
                self.assertIsNotNone(popup)
                self.assertEqual(popup.grab_current(),popup)
                self.assertTrue(popup.search_hint.winfo_ismapped())
                self.capture(f'refinement_ministries_{mode}')
                popup.search.insert(0,'ICT')
                popup.filter_changed()
                self.assertEqual(popup.keys,['ministry-2'])
                popup.pick_active()
                self.assertEqual(set(dialog.ministry_select.get()),{'ministry-0','ministry-1'})
                popup.event_generate('<Escape>')
                self.pump()
                self.assertIsNone(dialog.ministry_select.popup)
                self.assertEqual(dialog.grab_current(),dialog)
                dialog.save()
                self.wait_for(lambda:dialog.save_button.cget('state')=='normal')
                self.assertEqual(service.update_member.call_args.args[2],['ministry-0','ministry-1'])
                dialog.destroy()

    def test_select_keyboard_search_outside_click_bounds_and_lifecycle(self):
        for mode in ('light','dark'):
            ctk.set_appearance_mode(mode)
            variable = ctk.StringVar(master=self.root,value='Item 0')
            command = Mock()
            select = ModernSelect(self.root,[f'Item {index}' for index in range(24)],variable=variable,command=command,width=240)
            select.place(relx=1,rely=1,x=-16,y=-16,anchor='se')
            self.pump()
            select.set('Item 1')
            command.assert_not_called()
            self.assertEqual(variable.get(),'Item 1')
            select.focus_set()
            select._canvas.event_generate('<Down>')
            self.pump()
            popup = select.popup
            self.assertIsNotNone(popup)
            left,top,width,height = theme.desktop_work_area(self.root)
            self.assertGreaterEqual(popup.winfo_rootx(),left)
            self.assertGreaterEqual(popup.winfo_rooty(),top)
            self.assertLessEqual(popup.winfo_rootx()+popup.winfo_width(),left+width)
            self.assertLessEqual(popup.winfo_rooty()+popup.winfo_height(),top+height)
            self.assertLessEqual(abs(popup.winfo_width()-select.winfo_width()),2)
            self.capture('refinement_single_'+mode)
            popup.search.insert(0,'Item 2')
            popup.filter_changed()
            self.assertEqual(popup.keys,['Item 2','Item 20','Item 21','Item 22','Item 23'])
            popup.move(1)
            popup.pick_active()
            self.assertEqual(variable.get(),'Item 20')
            command.assert_called_once_with('Item 20')
            select.configure(state='disabled')
            select.open_popup()
            self.assertIsNone(select.popup)
            select.configure(state='readonly')
            for _index in range(8):
                select.open_popup()
                self.pump(.04)
                select.popup.outside_click(SimpleNamespace(x_root=0,y_root=0))
                self.pump(.04)
                self.assertIsNone(select.popup)
            select.open_popup()
            self.pump(.05)
            select.destroy()
            self.pump(.05)
            # Closing a parent with an open multi-select must not leave a grab or callback.
            dialog = MemberFormDialog(self.root,self.member_service(),lambda:None)
            self.wait_for(lambda:bool(dialog.ministry_select.options))
            dialog.content._parent_canvas.yview_moveto(1)
            self.pump()
            dialog.ministry_select.open_popup()
            self.pump(.1)
            dialog.destroy()
            self.pump(.1)
            self.assertIsNone(self.root.grab_current())

    def test_login_resolutions_themes_inline_errors_and_totp_keyboard(self):
        for width,height in ((1366,768),(1600,900),(1920,1080)):
            scale = self.root._get_window_scaling()
            self.root.geometry(f'{int((width-30)/scale)}x{int((height-70)/scale)}+0+0')
            for mode in ('light','dark'):
                ctk.set_appearance_mode(mode)
                view = LoginView(self.root,lambda _user:None,
                    lambda:ctk.set_appearance_mode('dark' if ctk.get_appearance_mode()=='Light' else 'light'))
                view.auth_service = Mock()
                self.pump()
                self.assert_visible_in(view.signin_button,self.root)
                self.assert_visible_in(view.email_field,self.root)
                self.assertTrue(view.email_field.placeholder.winfo_ismapped())
                self.capture(f'refinement_login_password_{width}_{mode}')
                view.toggle_password()
                self.assertEqual(view.password_entry.cget('show'),'')
                view.toggle_password()
                self.assertEqual(view.password_entry.cget('show'),'•')
                view.login_with_password()
                self.assertIn('Enter your email',view.status_var.get())
                view.email_var.set('synthetic@example.invalid')
                view.password_var.set('synthetic-password')
                view.auth_service.authenticate_password.side_effect = AuthenticationError('Account locked. Contact an administrator.')
                view.login_with_password()
                self.wait_for(lambda:not view.busy)
                self.assertIn('Account locked',view.status_var.get())
                self.assertEqual(view.password_var.get(),'')
                view.show_totp_form()
                self.pump()
                for field in view.totp_input.entries:
                    self.assert_visible_in(field,self.root)
                self.capture(f'refinement_login_totp_{width}_{mode}')
                view.auth_service.authenticate_totp_only.side_effect = AuthenticationError('Invalid authenticator code.')
                for index,digit in enumerate('12345'):
                    field = view.totp_input.entries[index]
                    field.insert(0,digit)
                    view.totp_input._key_released(SimpleNamespace(keysym=digit),index)
                self.pump(.1)
                view.auth_service.authenticate_totp_only.assert_not_called()
                view.totp_input.entries[5].insert(0,'6')
                view.totp_input._key_released(SimpleNamespace(keysym='6'),5)
                self.wait_for(lambda:view.auth_service.authenticate_totp_only.call_count==1 and not view.busy)
                view.auth_service.authenticate_totp_only.assert_called_once_with(email='synthetic@example.invalid',code='123456')
                self.assertIn('Invalid authenticator',view.status_var.get())
                self.assertEqual(view.totp_input.get_code(),'')
                view.totp_input.entries[3].focus_set()
                view.totp_input._key_released(SimpleNamespace(keysym='BackSpace'),3)
                self.pump(.03)
                self.assertEqual(view.focus_get(),view.totp_input.entries[2]._entry)
                view.totp_input.clipboard_clear()
                view.totp_input.clipboard_append('654321')
                view.totp_input._paste()
                self.wait_for(lambda:view.auth_service.authenticate_totp_only.call_count==2 and not view.busy)
                self.assertEqual(view.auth_service.authenticate_totp_only.call_args.kwargs['code'],'654321')
                # A mode change cancels pending verification for the destroyed six boxes.
                view.totp_input.set_code('111111')
                view.show_password_form()
                self.pump(.15)
                self.assertEqual(view.auth_service.authenticate_totp_only.call_count,2)
                view.destroy()


if __name__ == '__main__':
    unittest.main()
