"""Real family widgets and workflows with synthetic members and households."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest
import customtkinter as ctk
from PIL import ImageGrab
from tests import test_ui_smoke as smoke
from tests.household_preview import PreviewHouseholdService, PreviewFamilyMemberService
from src.ui import theme
from src.ui.components.modern import ConfirmationDialog
from src.ui.households.households_view import HouseholdsView, HouseholdProfileDialog
from src.ui.households.dialogs import AddFamilyMemberDialog, HouseholdMemberPicker
from src.ui.members.members_view import MemberProfileDialog
from src.ui.dashboard.dashboard_view import DashboardView
from src.security.household_permissions import RELATIONSHIPS


class HouseholdUiTests(unittest.TestCase):
    setUpClass = classmethod(smoke.UiSmokeTests.setUpClass.__func__)
    tearDownClass = classmethod(smoke.UiSmokeTests.tearDownClass.__func__)
    setUp = smoke.UiSmokeTests.setUp
    tearDown = smoke.UiSmokeTests.tearDown
    pump = smoke.UiSmokeTests.pump
    wait_for = smoke.UiSmokeTests.wait_for
    assert_visible_in = smoke.UiSmokeTests.assert_visible_in

    def capture(self, name):
        import ctypes
        from ctypes import wintypes
        folder = Path('docs/screenshots/households'); folder.mkdir(parents=True, exist_ok=True)
        self.pump()
        get_parent = ctypes.windll.user32.GetParent
        get_parent.restype = wintypes.HWND; get_parent.argtypes = [wintypes.HWND]
        target = self.root.grab_current() or self.root
        ImageGrab.grab(window=get_parent(target.winfo_id())).save(folder/(name+'.png'))

    def mount(self, count=30, management=True, view_all=True):
        service = PreviewHouseholdService(count, management, view_all)
        members = PreviewFamilyMemberService(service)
        shell = ctk.CTkFrame(self.root, fg_color=theme.BACKGROUND); shell.pack(fill='both', expand=True)
        sidebar = ctk.CTkFrame(shell, width=theme.SIDEBAR_WIDTH, fg_color=theme.SIDEBAR)
        sidebar.pack(side='left', fill='y'); sidebar.pack_propagate(False)
        view = HouseholdsView(shell, service, members)
        view.pack(side='left', fill='both', expand=True)
        self.wait_for(lambda:view.cards['total'].value.cget('text')!='—', timeout=10)
        self.pump()
        return shell, view, service, members

    def test_layouts_both_themes_all_sizes_and_fixed_footers(self):
        for width,height in ((1366,768),(1600,900),(1920,1080)):
            scale = self.root._get_window_scaling()
            self.root.geometry(f'{int((width-30)/scale)}x{int((height-70)/scale)}+0+0')
            for mode in ('light','dark'):
                with self.subTest(width=width, mode=mode):
                    ctk.set_appearance_mode(mode)
                    try:
                        shell, view, service, members = self.mount()
                        for widget in (view.create_button, view.status, view.next_button, view.previous): self.assert_visible_in(widget, self.root)
                        row = view.rows.winfo_children()[0]
                        self.assert_visible_in(row.view_button, view.rows._parent_canvas)
                        self.assert_visible_in(row.edit_button, view.rows._parent_canvas)
                        self.capture(f'households_{width}_{mode}')
                        form = view.create(); self.pump()
                        for widget in (form.save_button, form.cancel_button): self.assert_visible_in(widget, form)
                        self.capture(f'household_form_{width}_{mode}'); form.destroy()
                        profile = view.view(service.households[0]['id'])
                        self.wait_for(lambda:profile.household is not None)
                        self.assertEqual(profile.cards['children'].value.cget('text'), '1')
                        for widget in (profile.edit_button, profile.add_button, profile.cancel_button, profile.mode): self.assert_visible_in(widget, profile)
                        self.assert_visible_in(profile.member_rows.winfo_children()[0], profile.content._parent_canvas)
                        self.capture(f'household_profile_{width}_{mode}')
                        add = profile.add_member(); self.pump()
                        for widget in (add.save_button, add.cancel_button): self.assert_visible_in(widget, add)
                        self.capture(f'family_member_form_{width}_{mode}')
                        add.destroy(); profile.destroy()
                        empty = view.view(service.households[1]['id']); self.wait_for(lambda:empty.household is not None)
                        self.assertEqual(empty.household['member_count'], 0)
                        self.assert_visible_in(empty.add_button, empty)
                        empty.destroy()
                    finally:
                        for child in list(self.root.winfo_children()): child.destroy()
                        self.pump()

    def test_create_edit_head_remove_archive_restore_and_unused_delete(self):
        shell, view, service, members = self.mount(count=2)
        count = len(service.members)
        form = view.create(); form.name.insert(0,'New family')
        form.selected(service.members[4]); form.save()
        self.wait_for(lambda:not form.winfo_exists())
        household = service.households[-1]
        profile = view.view(household['id']); self.wait_for(lambda:profile.household is not None)
        add = profile.add_member(); add.selected(service.members[5]); add.save()
        self.wait_for(lambda:not add.winfo_exists())
        self.wait_for(lambda:profile.household['member_count']==2)
        edit = profile.edit(); edit.name.delete(0,'end'); edit.name.insert(0,'Renamed family'); edit.save()
        self.wait_for(lambda:not edit.winfo_exists())
        self.wait_for(lambda:profile.household['household_name']=='Renamed family')
        rows = service.get_household_members(household['id'])['rows']
        new_head = profile.change_head(rows[1]); new_head.previous.set('Spouse'); new_head.save()
        self.wait_for(lambda:not new_head.winfo_exists())
        self.wait_for(lambda:profile.household['head_member_id']==service.members[5]['id'])
        removed = profile.remove_member(service.get_household_members(household['id'])['rows'][0]); removed.save()
        self.wait_for(lambda:not removed.winfo_exists() or bool(removed.error_var.get()))
        self.assertEqual(removed.error_var.get(), '')
        self.wait_for(lambda:profile.household['member_count']==1)
        archive = profile.lifecycle('archive'); archive.save()
        self.wait_for(lambda:not archive.winfo_exists()); self.wait_for(lambda:profile.household['status']=='ARCHIVED')
        profile.mode.set('Past memberships'); profile.refresh(True)
        self.wait_for(lambda:len(profile.member_rows.winfo_children())==2)
        self.assertEqual(len(service.members), count)
        restore = profile.lifecycle('restore'); restore.save()
        self.wait_for(lambda:not restore.winfo_exists()); self.wait_for(lambda:profile.household['status']=='ACTIVE')
        self.assertEqual(profile.household['member_count'], 0)
        self.assertNotIn('Delete unused household', profile.action_menu.actions)
        profile.destroy()
        empty = service.create_household(dict(household_name='Unused'))
        profile = view.view(empty['id']); self.wait_for(lambda:profile.household is not None)
        delete = profile.lifecycle('delete'); delete.save()
        self.wait_for(lambda:not profile.winfo_exists())
        self.assertFalse(any(row['id']==empty['id'] for row in service.households))
        self.assertEqual(len(service.members), count)
        shell.destroy()

    def test_move_cancellation_confirmation_and_head_replacement(self):
        shell, view, service, members = self.mount(count=2)
        target = service.get_household(service.households[1]['id'])
        form = AddFamilyMemberDialog(view, service, members, target, service.capabilities(), Mock(), service.members[1])
        form.save(); self.wait_for(lambda:isinstance(self.root.grab_current(), ConfirmationDialog))
        self.root.grab_current().destroy(); form.grab_set()
        self.assertEqual(service.get_household(service.households[0]['id'])['member_count'], 4)
        form.save(); self.wait_for(lambda:isinstance(self.root.grab_current(), ConfirmationDialog))
        self.root.grab_current().confirm(); self.wait_for(lambda:not form.winfo_exists())
        self.assertEqual(service.get_household(target['id'])['member_count'], 1)
        self.assertEqual(service.get_household_members(service.households[0]['id'], history=True)['total'], 1)
        target = service.get_household(service.households[0]['id'])
        form = AddFamilyMemberDialog(view, service, members, target, service.capabilities(), Mock(), service.members[5])
        form.relationship.set(RELATIONSHIPS['HEAD']); form.head.set('Yes'); form.save()
        self.wait_for(lambda:isinstance(self.root.grab_current(), ConfirmationDialog))
        self.root.grab_current().confirm(); self.wait_for(lambda:not form.winfo_exists())
        current = service.get_household_members(target['id'])['rows']
        self.assertEqual(sum(row['is_household_head'] for row in current), 1)
        self.assertEqual(service.get_household(target['id'])['head_member_id'], service.members[5]['id'])
        shell.destroy()

    def test_relationship_edit_saves_notes_without_worker_widget_access(self):
        shell, view, service, members = self.mount(count=1)
        profile = view.view(service.households[0]['id']); self.wait_for(lambda:profile.household is not None)
        member = service.get_household_members(profile.household_id)['rows'][1]
        form = profile.edit_relationship(member)
        form.relationship.set('Relative'); form.notes.insert('1.0','Updated family relationship')
        form.save(); self.wait_for(lambda:not form.winfo_exists() or bool(form.error_var.get()))
        self.assertEqual(form.error_var.get(), '')
        current = next(row for row in service.get_household_members(profile.household_id)['rows'] if row['id']==member['id'])
        self.assertEqual(current['relationship'], 'RELATIVE')
        self.assertEqual(current['notes'], 'Updated family relationship')
        profile.destroy(); shell.destroy()

    def test_normal_add_member_returns_one_master_record_to_family_flow(self):
        shell, view, service, members = self.mount(count=1)
        before = len(service.members)
        form = AddFamilyMemberDialog(view, service, members, service.get_household(service.households[0]['id']), service.capabilities(), Mock())
        new = form.new_member()
        self.wait_for(lambda:new.save_button.cget('state')=='normal')
        new.variables['first_name'].set('New'); new.variables['last_name'].set('FamilyMember')
        new.save(); self.wait_for(lambda:not new.winfo_exists(), timeout=10)
        self.pump(); self.assertEqual(self.root.grab_current(), form)
        self.assertEqual(len(service.members), before+1)
        self.assertEqual(form.member['id'], service.members[-1]['id'])
        form.save(); self.wait_for(lambda:not form.winfo_exists())
        self.assertEqual(service.get_household(service.households[0]['id'])['member_count'], 5)
        self.assertEqual(len(service.members), before+1)
        shell.destroy()

    def test_member_profile_integration_and_own_family_readonly_controls(self):
        service = PreviewHouseholdService(count=1, management=False, view_all=False)
        members = PreviewFamilyMemberService(service)
        profile = MemberProfileDialog(self.root, members, service.members[0]['id'], Mock(), household_service=service)
        self.wait_for(lambda:profile.member is not None)
        profile.content._parent_canvas.yview_moveto(1); self.pump()
        household = profile.view_household(); self.wait_for(lambda:household.household is not None)
        self.assertEqual(household.mode.cget('values'), ['Current members'])
        self.assertFalse(household.add_button.winfo_ismapped()); self.assertFalse(household.edit_button.winfo_ismapped())
        self.assertIsNone(household.action_menu)
        self.assertFalse(any(hasattr(row,'action_menu') for row in household.member_rows.winfo_children()))
        self.capture('own_household_readonly')
        household.destroy(); profile.destroy()

    def test_unassigned_insight_search_and_pagination(self):
        shell, view, service, members = self.mount()
        view.page(1); self.wait_for(lambda:len(view.rows.winfo_children())==5)
        self.assertEqual(view.previous.cget('state'), 'normal')
        picker = view.without_household(); self.wait_for(lambda:picker.total==31)
        picker.search.insert(0, 'family34@example.invalid'); picker.search.submit()
        self.wait_for(lambda:picker.total==1)
        self.assertEqual(picker.content.winfo_children()[0].member['id'], service.members[34]['id'])
        self.capture('members_without_household_search')
        picker.content.winfo_children()[0].select_button.invoke()
        self.pump(); opened = self.root.grab_current()
        self.assertIsInstance(opened, MemberProfileDialog)
        self.wait_for(lambda:opened.member is not None)
        self.assertIsNone(opened.member['household']); opened.destroy(); shell.destroy()

    def test_family_only_dashboard_does_not_query_member_directory(self):
        service = PreviewHouseholdService(count=1, management=False, view_all=False)
        members = Mock(); attendance = Mock()
        attendance.capabilities.return_value = dict(permissions=['HOUSEHOLD_VIEW'], scope_ids=[], can_view=False)
        user = SimpleNamespace(id='preview-family', username='Family viewer', email='family@example.invalid', roles=[])
        with patch('src.ui.dashboard.dashboard_view.MemberService', return_value=members), \
             patch('src.ui.dashboard.dashboard_view.AttendanceService', return_value=attendance), \
             patch('src.ui.dashboard.dashboard_view.HouseholdService', return_value=service):
            dashboard = DashboardView(self.root, user, Mock())
            self.pump(); members.stats.assert_not_called()
            dashboard.select_menu('Members')
            self.wait_for(lambda:isinstance(dashboard.body_frame, HouseholdsView))
            self.wait_for(lambda:dashboard.body_frame.cards['total'].value.cget('text')=='1')
            members.list_members.assert_not_called()
            dashboard.destroy()

    def test_family_and_attendance_dashboard_keeps_member_stats_private(self):
        service = PreviewHouseholdService(count=1, management=False, view_all=False)
        members, attendance = Mock(), Mock()
        attendance.capabilities.return_value = dict(permissions=['HOUSEHOLD_VIEW','ATTENDANCE_VIEW_ALL'],
            scope_ids=[], can_view=True, church_wide=True, can_report=False)
        attendance.list_ministries.return_value = []
        attendance.list_sessions.return_value = dict(total=0, rows=[])
        attendance.overview.return_value = dict(sunday=dict(date=None, count=0), trend=[], open=0, meetings=0)
        user = SimpleNamespace(id='preview-family-attendance', username='Family and attendance', email='family@example.invalid', roles=[])
        with patch('src.ui.dashboard.dashboard_view.MemberService', return_value=members), \
             patch('src.ui.dashboard.dashboard_view.AttendanceService', return_value=attendance), \
             patch('src.ui.dashboard.dashboard_view.HouseholdService', return_value=service):
            dashboard = DashboardView(self.root, user, Mock())
            self.wait_for(lambda:dashboard.body_frame.sunday_detail.cget('text')=='No Sunday service has been recorded in your view.')
            members.stats.assert_not_called(); attendance.overview.assert_called_once()
            dashboard.select_menu('Members')
            self.wait_for(lambda:isinstance(dashboard.body_frame, HouseholdsView))
            dashboard.destroy()


if __name__=='__main__': unittest.main()
