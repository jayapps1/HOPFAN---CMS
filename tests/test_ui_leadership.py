"""Leadership screens and real widget flows with synthetic church data."""
import unittest
from unittest.mock import Mock
from datetime import date
import customtkinter as ctk
from tests import test_ui_smoke as smoke
from tests.ministry_preview import PreviewMinistryService
from tests.leadership_preview import PreviewLeadershipService
from src.ui.ministries.profile import MinistryProfileDialog
from src.ui.ministries.leadership_dialogs import AssignmentFormDialog, LeadershipMemberPicker, EndAssignmentDialog, AssignmentProfileDialog
from src.ui.components.modern import ConfirmationDialog
from src.ui.members.members_view import MemberProfileDialog
from src.services.ministry_leadership_service import LeadershipServiceError
from src.database.seed_ministry_positions import DEFAULT_POSITIONS, position_name


class LeadershipUiTests(unittest.TestCase):
    setUpClass=classmethod(smoke.UiSmokeTests.setUpClass.__func__)
    tearDownClass=classmethod(smoke.UiSmokeTests.tearDownClass.__func__)
    setUp=smoke.UiSmokeTests.setUp
    tearDown=smoke.UiSmokeTests.tearDown
    pump=smoke.UiSmokeTests.pump
    wait_for=smoke.UiSmokeTests.wait_for
    assert_visible_in=smoke.UiSmokeTests.assert_visible_in
    capture=smoke.UiSmokeTests.capture

    def mount(self,management=True,current=True):
        ministries=PreviewMinistryService(count=5)
        ministry=ministries.rows[0]
        service=PreviewLeadershipService(ministry,management,current)
        dialog=MinistryProfileDialog(self.root,ministries,ministry['id'],leadership_service=service)
        self.wait_for(lambda:dialog.ministry is not None)
        view=dialog.leadership()
        self.wait_for(lambda:view.cards['current'].value.cget('text')!='—')
        self.pump()
        return dialog,view,service

    def test_add_position_during_assignment_preserves_member_and_dates(self):
        for mode in ('light','dark'):
            for empty in (True,False):
                with self.subTest(mode=mode,empty=empty):
                    ctk.set_appearance_mode(mode)
                    ministry=PreviewMinistryService(count=1).rows[0]
                    service=PreviewLeadershipService(ministry,current=False)
                    if empty:
                        service.positions.clear()
                    changed=Mock()
                    form=AssignmentFormDialog(self.root,service,ministry,changed,service.capabilities(ministry['id']))
                    member=service.members[0]
                    form.selected(member)
                    start=date(2026,10,1)
                    form.start.variable.set(start.strftime('%d/%m/%Y'))
                    form.notes.insert('1.0','Youth appointment notes')
                    self.wait_for(lambda:form.position.cget('placeholder')!='Loading ministry positions…')
                    if empty:
                        self.assertEqual(form.position.value_label.cget('text'),'No active ministry positions')
                        self.assertEqual(form.position.cget('state'),'disabled')
                        self.assertEqual(form.save_button.cget('state'),'disabled')
                        self.assertIn('Add a position',form.position_notice.cget('text'))
                    self.assert_visible_in(form.add_position_button,form)
                    self.assert_visible_in(form.cancel_button,form)
                    position=form.add_position()
                    self.pump()
                    position.name.insert(0,'Leader' if empty else 'Youth Coordinator')
                    position.suggest()
                    position.save()
                    self.wait_for(lambda:not position.winfo_exists(),timeout=8)
                    self.wait_for(lambda:form.save_button.cget('state')=='normal')
                    selected=service.positions[-1]
                    self.assertEqual(form.positions[form.position.get()]['id'],selected['id'])
                    self.assertEqual(form.position.cget('state'),'readonly')
                    self.assertEqual(form.member,member)
                    self.assertEqual(form.start.get_date(),start)
                    self.assertEqual(form.notes.get('1.0','end-1c'),'Youth appointment notes')
                    changed.assert_called_once()
                    form.save()
                    self.wait_for(lambda:not form.winfo_exists(),timeout=8)
                    self.assertEqual(service.appointments[-1]['member_id'],member['id'])
                    self.assertEqual(service.appointments[-1]['position_id'],selected['id'])
                    self.assertEqual(service.appointments[-1]['start_date'],start)

    def test_position_loading_error_can_be_retried(self):
        ministry=PreviewMinistryService(count=1).rows[0]
        service=PreviewLeadershipService(ministry,current=False)
        rows=service.list_positions(ministry['id'])
        service.list_positions=Mock(side_effect=[LeadershipServiceError('Synthetic positions unavailable'),rows])
        form=AssignmentFormDialog(self.root,service,ministry,Mock(),service.capabilities(ministry['id']))
        member=service.members[0]
        form.selected(member)
        self.wait_for(lambda:bool(form.error_var.get()))
        self.assertEqual(form.position.value_label.cget('text'),'Unable to load ministry positions')
        self.assertEqual(form.save_button.cget('state'),'disabled')
        self.assertEqual(form.position.cget('state'),'disabled')
        self.assert_visible_in(form.retry_positions_button,form)
        form.retry_positions_button.invoke()
        self.wait_for(lambda:form.save_button.cget('state')=='normal')
        self.assertEqual(form.error_var.get(),'')
        self.assertFalse(form.retry_positions_button.winfo_ismapped())
        self.assertEqual(form.member,member)
        self.assertEqual(service.list_positions.call_count,2)
        form.destroy()

    def test_empty_positions_without_creation_permission(self):
        ministry=PreviewMinistryService(count=1).rows[0]
        service=PreviewLeadershipService(ministry,management=False,current=False)
        for position in service.positions:
            position['is_active']=False
        form=AssignmentFormDialog(self.root,service,ministry,Mock(),service.capabilities(ministry['id']))
        self.wait_for(lambda:form.position.cget('placeholder')!='Loading ministry positions…')
        self.assertEqual(form.position.value_label.cget('text'),'No active ministry positions')
        self.assertIn('Ask an administrator',form.position_notice.cget('text'))
        self.assertFalse(form.add_position_button.winfo_ismapped())
        self.assertIsNone(form.add_position())
        self.assertEqual(form.save_button.cget('state'),'disabled')
        self.assertEqual(len(service.positions),2)
        form.destroy()

    def test_manage_seeded_positions_from_assignment_updates_dropdown(self):
        ministry=PreviewMinistryService(count=1).rows[0]
        service=PreviewLeadershipService(ministry,current=False)
        service.positions.clear()
        for order,(code,title) in enumerate(DEFAULT_POSITIONS,start=1):
            service.create_position(ministry['id'],dict(code=code,name=position_name(ministry['name'],title),sort_order=order*10))
        form=AssignmentFormDialog(self.root,service,ministry,Mock(),service.capabilities(ministry['id']))
        self.wait_for(lambda:form.save_button.cget('state')=='normal')
        member=service.members[0]
        form.selected(member)
        secretary=next(key for key,row in form.positions.items() if row['code']=='SECRETARY')
        form.position.set(secretary)
        self.assert_visible_in(form.manage_positions_button,form)
        manager=form.manage_positions()
        self.wait_for(lambda:len(manager.positions)==5)
        rows={row['code']:row for row in manager.positions}
        edit=manager.edit(rows['SECRETARY'])
        edit.name.delete(0,'end')
        edit.name.insert(0,'Youth Administrative Secretary')
        edit.save()
        self.wait_for(lambda:not edit.winfo_exists())
        self.wait_for(lambda:form.position.get().startswith('Youth Administrative Secretary'))
        self.assertEqual(form.member,member)
        confirm=manager.change(rows['LEADER'],'deactivate')
        self.pump()
        confirm.confirm()
        self.wait_for(lambda:not confirm.winfo_exists())
        self.wait_for(lambda:len(form.positions)==4)
        self.assertNotIn('LEADER',{row['code'] for row in form.positions.values()})
        confirm=manager.change(rows['TREASURER'],'delete')
        self.pump()
        confirm.confirm()
        self.wait_for(lambda:not confirm.winfo_exists())
        self.wait_for(lambda:len(manager.positions)==4 and len(form.positions)==3)
        new=manager.add()
        new.name.insert(0,'Youth Chaplain')
        new.suggest()
        new.save()
        self.wait_for(lambda:not new.winfo_exists())
        self.wait_for(lambda:len(form.positions)==4)
        self.assertIn('YOUTH_CHAPLAIN',{row['code'] for row in form.positions.values()})
        self.assertEqual(form.member,member)
        self.assertTrue(form.position.get().startswith('Youth Administrative Secretary'))
        manager.destroy()
        form.save()
        self.wait_for(lambda:not form.winfo_exists())
        self.assertEqual(service.appointments[-1]['member_id'],member['id'])
        self.assertEqual(service.appointments[-1]['position_code'],'SECRETARY')

    def test_leadership_and_position_manager_all_sizes_both_themes(self):
        for width,height in ((1366,768),(1600,900),(1920,1080)):
            scale=self.root._get_window_scaling()
            self.root.geometry(f'{int((width-30)/scale)}x{int((height-70)/scale)}+0+0')
            for mode in ('light','dark'):
                ctk.set_appearance_mode(mode)
                dialog,view,service=self.mount()
                dialog.overview()
                self.pump()
                self.assertFalse(view.assign_button.winfo_ismapped())
                dialog.leadership()
                self.wait_for(lambda:view.assign_button.winfo_ismapped())
                self.assertIn('Youth Ministry',view.profile_title.cget('text'))
                for widget in (dialog.cancel_button,view.assign_button,view.manage_button,view.next_button,view.status): self.assert_visible_in(widget,dialog)
                row=view.rows.winfo_children()[0]
                self.assert_visible_in(row.view_button,dialog)
                self.assert_visible_in(row.action_menu,dialog)
                # A widget can be mapped while clipped by a very short scroll viewport.
                canvas=view.rows._parent_canvas
                for widget in (row,row.view_button,row.action_menu): self.assert_visible_in(widget,canvas)
                self.capture(f'leadership_{width}_{mode}')
                row.action_menu.open_popup()
                self.pump()
                row.action_menu.close_popup()
                view.status.set('Vacant')
                view.refresh(True)
                self.wait_for(lambda:hasattr(view.rows.winfo_children()[0],'position'))
                self.assertEqual(view.rows.winfo_children()[0].position['code'],'SECRETARY')
                manager=view.manage()
                self.wait_for(lambda:len(manager.positions)==2)
                self.assert_visible_in(manager.add_button,manager)
                self.assert_visible_in(manager.cancel_button,manager)
                self.capture(f'positions_{width}_{mode}')
                form=manager.add()
                self.pump()
                self.assert_visible_in(form.save_button,form)
                form.content._parent_canvas.yview_moveto(1)
                self.pump()
                self.capture(f'position_form_{width}_{mode}')
                form.destroy()
                manager.destroy()
                assignment=view.assign()
                self.wait_for(lambda:assignment.save_button.cget('state')=='normal')
                self.assert_visible_in(assignment.save_button,assignment)
                self.assertEqual(assignment.start.variable.get(),date.today().strftime('%d/%m/%Y'))
                self.capture(f'assignment_form_{width}_{mode}')
                assignment.destroy()
                dialog.destroy()
                self.pump()

    def test_position_create_edit_deactivate_unused_delete(self):
        for mode in ('light','dark'):
            ctk.set_appearance_mode(mode)
            dialog,view,service=self.mount(current=False)
            manager=view.manage()
            self.wait_for(lambda:len(manager.positions)==2)
            form=manager.add()
            self.pump()
            form.name.insert(0,'Attendance Officer')
            form.suggest()
            self.assertEqual(form.code.get(),'ATTENDANCE_OFFICER')
            form.maximum.delete(0,'end')
            form.save()
            self.wait_for(lambda:not form.winfo_exists())
            self.wait_for(lambda:len(manager.positions)==3)
            position=next(p for p in manager.positions if p['code']=='ATTENDANCE_OFFICER')
            self.assertIsNone(position['max_current_holders'])
            form=manager.edit(position)
            self.pump()
            form.description.insert('1.0','Responsible for attendance.')
            form.save()
            self.wait_for(lambda:not form.winfo_exists())
            confirm=manager.change(position,'deactivate')
            self.pump()
            confirm.confirm()
            self.wait_for(lambda:not confirm.winfo_exists())
            manager.status.set('Inactive')
            manager.render_rows()
            confirm=manager.change(position,'delete')
            self.pump()
            confirm.confirm()
            self.wait_for(lambda:not confirm.winfo_exists())
            self.assertEqual(len(service.positions),2)
            manager.destroy()
            dialog.destroy()

    def test_replace_end_history_profile_and_edit(self):
        for mode in ('light','dark'):
            ctk.set_appearance_mode(mode)
            dialog,view,service=self.mount()
            form=view.assign()
            self.wait_for(lambda:form.save_button.cget('state')=='normal')
            picker=form.choose()
            self.wait_for(lambda:picker.total==30)
            self.assert_visible_in(picker.next_button,picker)
            picker.page(1)
            self.wait_for(lambda:len(picker.content.winfo_children())==10)
            picker.search.insert(0,'Kwame')
            picker.search.submit()
            self.wait_for(lambda:picker.total==1)
            self.capture('leadership_member_picker_'+mode)
            picker.content.winfo_children()[0].select_button.invoke()
            self.pump()
            form.save()
            self.wait_for(lambda:isinstance(self.root.grab_current(),ConfirmationDialog))
            confirm=self.root.grab_current()
            self.capture('leadership_replace_'+mode)
            confirm.destroy()
            form.grab_set()
            self.assertEqual(len([a for a in service.appointments if a['is_current']]),1)
            form.save()
            self.wait_for(lambda:isinstance(self.root.grab_current(),ConfirmationDialog))
            self.root.grab_current().confirm()
            self.wait_for(lambda:not form.winfo_exists())
            self.assertEqual(len(service.appointments),2)
            current=next(a for a in service.appointments if a['is_current'])
            self.assertEqual(current['full_name'],'Kwame Mensah')
            form=view.edit(current)
            self.wait_for(lambda:form.save_button.cget('state')=='normal')
            self.assertEqual(form.position.state,'disabled')
            form.notes.insert('1.0','Term reviewed.')
            form.save()
            self.wait_for(lambda:not form.winfo_exists())
            end=view.end(service.get_assignment(current['id']))
            self.pump()
            self.assert_visible_in(end.save_button,end)
            self.capture('leadership_end_'+mode)
            end.save()
            self.wait_for(lambda:not end.winfo_exists())
            view.status.set('Historical')
            view.refresh(True)
            self.wait_for(lambda:view.total==2)
            self.capture('leadership_history_'+mode)
            profile=view.view(current['id'])
            self.wait_for(lambda:profile.assignment is not None)
            self.capture('leadership_assignment_profile_'+mode)
            profile.destroy()
            dialog.destroy()

    def test_membership_confirmation_member_profile_and_leader_readonly(self):
        dialog,view,service=self.mount()
        form=view.assign(service.positions[1]['id'])
        self.wait_for(lambda:form.save_button.cget('state')=='normal')
        form.selected(service.members[2])
        form.save()
        self.wait_for(lambda:bool(form.membership_button.winfo_manager()))
        self.assertFalse(service.members[2]['in_ministry'])
        confirm=form.enroll()
        self.pump()
        self.capture('leadership_membership_confirmation')
        confirm.confirm()
        self.wait_for(lambda:not form.winfo_exists())
        self.assertTrue(service.members[2]['in_ministry'])
        dialog.destroy()
        member=dict(id=service.members[2]['id'],full_name='Ama Mensah',member_no='PREVIEW-0003',photo_path='',phone='054 000 0000',alternate_phone='',email='',address='',gender='FEMALE',date_of_birth=None,
            marital_status='SINGLE',occupation='',date_joined=date.today(),baptized=False,baptism_date=None,ministries=['Youth Ministry'],status='ACTIVE',leadership=[service.appointments[-1]])
        members=Mock()
        members.get_member.return_value=member
        profile=MemberProfileDialog(self.root,members,member['id'],lambda:None)
        self.wait_for(lambda:profile.member is not None)
        profile.content._parent_canvas.yview_moveto(1)
        self.pump()
        self.capture('leadership_member_profile')
        profile.destroy()
        dialog,view,service=self.mount(management=False)
        self.assertFalse(view.assign_button.winfo_ismapped())
        row=view.rows.winfo_children()[0]
        self.assertFalse(hasattr(row,'action_menu'))
        manager=view.manage()
        self.wait_for(lambda:len(manager.positions)==2)
        self.assertFalse(manager.add_button.winfo_ismapped())
        self.assertFalse(hasattr(manager.content.winfo_children()[0],'edit_button'))
        self.capture('leadership_leader_readonly')
        manager.destroy()
        dialog.destroy()


if __name__=='__main__': unittest.main()
