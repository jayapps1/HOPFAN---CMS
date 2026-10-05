"""Ministry layouts and administrator/leader workflows on a Windows desktop."""
from types import SimpleNamespace
import unittest
import customtkinter as ctk
from src.ui import theme
from src.ui.ministries.ministries_view import MinistriesView
from src.ui.ministries.dialogs import MinistryFormDialog,LifecycleConfirmation
from src.ui.members.member_form_dialog import MemberFormDialog
from tests import test_ui_smoke as smoke
from tests.ministry_preview import PreviewMinistryService
from unittest.mock import Mock


class MinistryUiTests(unittest.TestCase):
    setUpClass=classmethod(smoke.UiSmokeTests.setUpClass.__func__)
    tearDownClass=classmethod(smoke.UiSmokeTests.tearDownClass.__func__)
    setUp=smoke.UiSmokeTests.setUp
    tearDown=smoke.UiSmokeTests.tearDown
    pump=smoke.UiSmokeTests.pump
    wait_for=smoke.UiSmokeTests.wait_for
    assert_visible_in=smoke.UiSmokeTests.assert_visible_in
    capture=smoke.UiSmokeTests.capture

    def mount(self,service):
        shell=ctk.CTkFrame(self.root,fg_color=theme.BACKGROUND)
        shell.pack(fill='both',expand=True)
        sidebar=ctk.CTkFrame(shell,width=theme.SIDEBAR_WIDTH,fg_color=theme.SIDEBAR,corner_radius=0)
        sidebar.pack(side='left',fill='y')
        sidebar.pack_propagate(False)
        view=MinistriesView(shell,SimpleNamespace(id='preview'),service=service)
        view.pack(side='left',fill='both',expand=True)
        self.wait_for(lambda:view.cards['total'].value.cget('text')!='—')
        self.pump()
        return shell,view

    def test_directory_all_resolutions_themes_filters_pagination_and_menu(self):
        for width,height in ((1366,768),(1600,900),(1920,1080)):
            scale=self.root._get_window_scaling()
            self.root.geometry(f'{int((width-30)/scale)}x{int((height-70)/scale)}+0+0')
            for mode in ('light','dark'):
                ctk.set_appearance_mode(mode)
                service=PreviewMinistryService()
                shell,view=self.mount(service)
                self.assert_visible_in(view.add_button,self.root)
                self.assert_visible_in(view.next_button,self.root)
                self.assert_visible_in(view.status,self.root)
                row=view.rows.winfo_children()[0]
                self.assert_visible_in(row.view_button,self.root)
                self.assert_visible_in(row.edit_button,self.root)
                self.assert_visible_in(row.action_menu,self.root)
                self.capture(f'ministry_directory_{width}_{mode}')
                row.action_menu.open_popup()
                self.pump()
                self.assertIsNotNone(row.action_menu.popup)
                row.action_menu.close_popup()
                view.page(1)
                self.wait_for(lambda:view.offset==20 and len(view.rows.winfo_children())==6)
                view.status.set('Archived')
                view.refresh(reset=True)
                self.wait_for(lambda:len(view.rows.winfo_children())==1)
                self.assertEqual(view.rows.winfo_children()[0].ministry['status'],'ARCHIVED')
                view.status.set('All')
                view.search.insert(0,'YOUTH')
                view.search.submit()
                self.wait_for(lambda:len(view.rows.winfo_children())==1 and view.rows.winfo_children()[0].ministry['code']=='YOUTH')
                shell.destroy()
                self.pump(.05)

    def test_empty_add_edit_profile_archive_restore_delete_and_confirmations(self):
        for mode in ('light','dark'):
            ctk.set_appearance_mode(mode)
            service=PreviewMinistryService(count=0)
            shell,view=self.mount(service)
            self.capture('ministry_empty_'+mode)
            dialog=view.add_ministry()
            self.pump()
            self.assert_visible_in(dialog.save_button,self.root)
            self.assert_visible_in(dialog.cancel_button,self.root)
            dialog.name_var.set('Drama Ministry')
            dialog.suggestion.invoke()
            self.assertEqual(dialog.code_var.get(),'DRAMA')
            self.pump()
            self.capture('ministry_form_top_'+mode)
            dialog.content._parent_canvas.yview_moveto(1)
            self.pump()
            self.capture('ministry_form_'+mode)
            dialog.save()
            self.wait_for(lambda:len(service.rows)==1 and not dialog.winfo_exists())
            self.wait_for(lambda:len(view.rows.winfo_children())==1 and hasattr(view.rows.winfo_children()[0],'ministry'))
            ministry_id=service.rows[0]['id']
            view.edit_ministry(ministry_id)
            self.wait_for(lambda:isinstance(self.root.grab_current(),MinistryFormDialog))
            edit=self.root.grab_current()
            edit.name_var.set('Drama & Creative Arts Ministry')
            edit.status.set('Inactive')
            confirm=edit.save()
            self.pump()
            self.assert_visible_in(confirm.confirm_button,self.root)
            confirm.destroy()
            self.assertEqual(edit.grab_current(),edit)
            confirm=edit.save()
            self.pump()
            confirm.confirm()
            self.wait_for(lambda:not edit.winfo_exists())
            self.assertEqual(service.rows[0]['id'],ministry_id)
            self.assertEqual(service.rows[0]['name'],'Drama & Creative Arts Ministry')
            profile=view.view_ministry(ministry_id)
            self.wait_for(lambda:profile.ministry is not None)
            self.assert_visible_in(profile.cancel_button,self.root)
            self.capture('ministry_profile_'+mode)
            profile.destroy()
            for action,target in (('archive','ARCHIVED'),('restore','ACTIVE')):
                confirm=view.change(action,service.get_ministry(ministry_id))
                self.pump()
                if action=='restore':
                    confirm.restore_status.set('Active')
                self.assert_visible_in(confirm.confirm_button,self.root)
                self.capture('ministry_'+action+'_'+mode)
                confirm.confirm()
                self.wait_for(lambda:not confirm.winfo_exists())
                self.assertEqual(service.get_ministry(ministry_id)['status'],target)
            confirm=view.change('delete_unused',service.get_ministry(ministry_id))
            self.pump()
            confirm.confirm()
            self.assertIn('exact ministry code',confirm.error_var.get())
            confirm.code_confirm.insert(0,'DRAMA')
            confirm.confirm()
            self.wait_for(lambda:not confirm.winfo_exists())
            self.assertEqual(service.rows,[])
            self.assertIn(('deleted',ministry_id),service.changes)
            shell.destroy()

    def test_used_code_lock_leader_actions_and_archived_member_options(self):
        service=PreviewMinistryService(count=3)
        shell,view=self.mount(service)
        used=service.get_ministry(service.rows[0]['id'])
        edit=MinistryFormDialog(view,service,lambda _result:None,used,view.capabilities)
        self.pump()
        self.assertEqual(edit.code_entry.cget('state'),'disabled')
        self.assertTrue(edit.code_locked)
        edit.destroy()
        shell.destroy()
        service=PreviewMinistryService(management=False,count=3)
        shell,view=self.mount(service)
        self.assertIsNone(view.add_button)
        row=view.rows.winfo_children()[0]
        self.assertFalse(hasattr(row,'edit_button'))
        self.assertFalse(hasattr(row,'action_menu'))
        self.capture('ministry_leader_readonly')
        shell.destroy()
        members=Mock()
        members.list_ministries.return_value=[dict(id='archived-id',name='Old Ministry',status='ARCHIVED'),
            dict(id='active-id',name='Youth Ministry',status='ACTIVE')]
        member=dict(id='preview-member',full_name='Synthetic Member',member_no='PREVIEW-1',first_name='Synthetic',
            last_name='Member',ministry_ids=['archived-id'])
        dialog=MemberFormDialog(self.root,members,lambda:None,member=member)
        self.wait_for(lambda:len(dialog.ministry_select.options)==2)
        members.list_ministries.assert_called_once_with(member_id='preview-member')
        self.assertIn('Archived',dialog.ministry_select.variable.get())
        self.assertEqual(dialog.ministry_select.get(),['archived-id'])
        dialog.destroy()


if __name__=='__main__':
    unittest.main()
