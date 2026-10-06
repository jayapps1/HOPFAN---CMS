"""Family rules, authorization and transactions in a disposable PostgreSQL schema."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import unittest
import uuid

from sqlalchemy import delete, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from tests import test_attendance as fixtures
from src.models import (Household, HouseholdMember, HouseholdAuditLog, Member, MemberMinistry,
    Role, Permission, User, UserMinistryScope, AuthorizationAuditLog, UserStatus)
from src.services.household_service import HouseholdService, HouseholdServiceError, HouseholdAuthorizationError, HouseholdMoveRequired, HouseholdHeadConflict, age_on
from src.services.member_service import MemberService


class HouseholdTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.AttendanceTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.AttendanceTests.tearDownClass.__func__)
    tearDown = fixtures.AttendanceTests.tearDown

    def setUp(self):
        fixtures.AttendanceTests.setUp(self)
        self.service = HouseholdService(self.users['Admin'].id, self.factory)
        self.joined = date.today()-timedelta(days=60)

    def household(self, name='Owusu Household', **kwargs):
        return self.service.create_household(dict(household_name=name, **kwargs))

    def add(self, household, member='Ama', relationship='SPOUSE', **kwargs):
        return self.service.add_member(household['id'], self.members[member].id, relationship,
            **dict(dict(joined_at=self.joined), **kwargs))

    def test_create_head_spouse_and_member_profile(self):
        count = self.db.scalar(select(func.count()).select_from(Member))
        household = self.household()
        head = self.add(household, 'Yaw', 'HEAD')
        self.add(household)
        detail = self.service.get_household(household['id'])
        self.assertEqual(detail['member_count'], 2)
        self.assertEqual(detail['head_member_id'], str(self.members['Yaw'].id))
        self.assertEqual(detail['head_membership_id'], head['id'])
        profile = MemberService(self.users['Admin'].id, self.factory).get_member(self.members['Ama'].id)
        self.assertEqual(profile['household']['id'], household['id'])
        self.assertEqual(profile['household']['relationship'], 'SPOUSE')
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Member)), count)
        self.assertRegex(household['household_code'], r'^HH-\d{4}-\d{4}$')

    def test_duplicate_current_and_controlled_move_preserve_history(self):
        first, second = self.household(), self.household('Mensah Family')
        link = self.add(first)
        with self.assertRaisesRegex(HouseholdServiceError, 'already belongs'):
            self.add(first)
        with self.assertRaises(HouseholdMoveRequired) as conflict:
            self.add(second)
        self.assertEqual(conflict.exception.current['id'], link['id'])
        effective = date.today()-timedelta(days=10)
        new = self.service.move_member(link['id'], second['id'], self.members['Ama'].id,
            'SPOUSE', effective_date=effective, expected_updated_at=link['updated_at'])
        old = self.service.get_household_members(first['id'], history=True)['rows'][0]
        self.assertEqual(old['left_at'], effective)
        self.assertFalse(old['is_active'])
        self.assertEqual(new['joined_at'], effective)
        self.assertEqual(self.service.get_member_household(self.members['Ama'].id)['id'], second['id'])

    def test_move_head_conflict_rolls_back_source_and_new_household(self):
        first, second = self.household(), self.household('Second household')
        original = self.add(first)
        self.add(second, 'Yaw', 'HEAD')
        with self.assertRaises(HouseholdHeadConflict):
            self.service.move_member(original['id'], second['id'], self.members['Ama'].id,
                'HEAD', effective_date=date.today())
        self.assertEqual(self.service.get_member_household(self.members['Ama'].id)['id'], first['id'])
        self.assertEqual(self.service.get_household_members(first['id'], history=True)['total'], 0)
        before = self.service.list_households(status='ALL')['total']
        with self.assertRaises(HouseholdMoveRequired):
            self.service.create_household(dict(household_name='Not saved'), self.members['Ama'].id)
        self.assertEqual(self.service.list_households(status='ALL')['total'], before)

    def test_head_transition_and_add_new_head_are_explicit(self):
        household = self.household()
        first = self.add(household, 'Yaw', 'HEAD')
        spouse = self.add(household)
        with self.assertRaises(HouseholdHeadConflict):
            self.service.change_household_head(household['id'], spouse['id'])
        self.service.change_household_head(household['id'], spouse['id'], current_head_id=first['id'],
            expected_updated_at=spouse['updated_at'], expected_head_updated_at=first['updated_at'], previous_relationship='SPOUSE')
        rows = self.service.get_household_members(household['id'])['rows']
        self.assertEqual(sum(row['is_household_head'] for row in rows), 1)
        current = next(row for row in rows if row['is_household_head'])
        with self.assertRaises(HouseholdHeadConflict):
            self.add(household, 'Esi', 'HEAD')
        self.add(household, 'Esi', 'HEAD', replace_head_id=current['id'], expected_head_updated_at=current['updated_at'])
        self.assertEqual(self.service.get_household(household['id'])['head_member_id'], str(self.members['Esi'].id))

    def test_remove_archive_restore_and_delete_never_delete_members(self):
        household = self.household()
        link = self.add(household, 'Yaw', 'HEAD')
        self.add(household)
        self.service.remove_member(link['id'], date.today(), 'Moved away', link['updated_at'])
        self.service.archive_household(household['id'])
        self.assertEqual(self.service.get_household(household['id'])['status'], 'ARCHIVED')
        self.assertEqual(self.service.get_household_members(household['id'])['total'], 0)
        self.assertEqual(self.service.get_household_members(household['id'], history=True)['total'], 2)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Member)), 4)
        with self.assertRaisesRegex(HouseholdServiceError, 'history'):
            self.service.delete_unused_household(household['id'], confirmed=True)
        self.service.restore_household(household['id'])
        self.assertEqual(self.service.get_household_members(household['id'])['total'], 0)
        empty = self.household('Empty')
        with self.assertRaisesRegex(HouseholdServiceError, 'confirmation'):
            self.service.delete_unused_household(empty['id'])
        self.service.delete_unused_household(empty['id'], confirmed=True)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Member)), 4)

    def test_permissions_own_family_and_ministry_scope_do_not_leak(self):
        first, second = self.household(), self.household('Other family')
        self.add(first)
        self.add(second, 'Esi')
        officer = HouseholdService(self.users['Youth'].id, self.factory)
        for operation in (lambda:officer.get_household(first['id']), lambda:officer.list_households(),
            lambda:officer.add_member(first['id'], self.members['Yaw'].id, 'HEAD')):
            with self.assertRaises(HouseholdAuthorizationError): operation()
        profile = MemberService(self.users['Youth'].id, self.factory).get_member(self.members['Ama'].id)
        self.assertNotIn('household', profile)
        permission = self.db.scalar(select(Permission).where(Permission.code == 'HOUSEHOLD_VIEW'))
        role = Role(code='TEST_FAMILY', name='Own family', is_active=True, permissions=[permission])
        self.users['Youth'].roles.append(role)
        self.users['Youth'].member_id = self.members['Ama'].id
        self.db.commit()
        self.assertEqual(officer.list_households()['total'], 1)
        self.assertEqual(officer.get_household(first['id'])['member_count'], 1)
        self.assertIsNone(officer.get_household_stats()['without'])
        with self.assertRaises(HouseholdAuthorizationError): officer.get_household(second['id'])
        with self.assertRaises(HouseholdAuthorizationError): officer.get_household_members(first['id'], history=True)
        with self.assertRaises(HouseholdAuthorizationError): officer.candidate_members()
        with self.assertRaises(HouseholdAuthorizationError): officer.archive_household(first['id'])

    def test_dates_validation_stale_writes_and_duplicate_names(self):
        first, second = self.household(), self.household()
        self.assertNotEqual(first['id'], second['id'])
        self.assertNotEqual(first['household_code'], second['household_code'])
        with self.assertRaises(HouseholdServiceError): self.add(first, joined_at=date.today()+timedelta(days=1))
        link = self.add(first)
        with self.assertRaises(HouseholdServiceError): self.service.remove_member(link['id'], self.joined-timedelta(days=1))
        self.service.update_household(first['id'], dict(household_name='Renamed'))
        with self.assertRaisesRegex(HouseholdServiceError, 'changed'):
            self.service.update_household(first['id'], dict(household_name='Stale'), first['updated_at'])
        inactive = self.household('Inactive', status='INACTIVE')
        with self.assertRaises(HouseholdServiceError): self.add(inactive, 'Yaw')

    def test_household_code_is_not_reused_after_unused_deletion(self):
        household = self.household('Unused')
        self.service.delete_unused_household(household['id'], confirmed=True)
        replacement = self.household('New household')
        self.assertNotEqual(replacement['household_code'], household['household_code'])

    def test_create_with_confirmed_head_move_returns_complete_summary(self):
        first = self.household()
        source = self.add(first)
        household = self.service.create_household(dict(household_name='New household'), self.members['Ama'].id,
            move_from_membership_id=source['id'], expected_source_updated_at=source['updated_at'])
        self.assertEqual(household['head_member_id'], str(self.members['Ama'].id))
        self.assertEqual(household['member_count'], 1)
        self.assertEqual(self.service.get_household_members(first['id'], history=True)['total'], 1)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Member)), 4)

    def test_relationship_edit_notes_and_stale_head_change(self):
        household = self.household()
        head = self.add(household, 'Yaw', 'HEAD')
        spouse = self.add(household)
        self.service.update_relationship(spouse['id'], 'GUARDIAN', 'Private relationship notes', spouse['updated_at'])
        row = next(row for row in self.service.get_household_members(household['id'])['rows'] if row['id']==spouse['id'])
        self.assertEqual(row['relationship'], 'GUARDIAN')
        self.assertEqual(row['notes'], 'Private relationship notes')
        with self.assertRaisesRegex(HouseholdServiceError, 'changed'):
            self.service.change_household_head(household['id'], spouse['id'], current_head_id=head['id'], expected_updated_at=spouse['updated_at'])
        with self.assertRaisesRegex(HouseholdServiceError, 'controlled'):
            self.service.update_relationship(head['id'], 'RELATIVE')
        self.assertNotIn('Private relationship notes', str(self.service.audit_events(household['id'])))

    def test_stats_ages_dependants_and_unassigned_search(self):
        self.members['Ama'].date_of_birth = date(1990, 1, 1)
        self.members['Yaw'].date_of_birth = date(2016, 6, 14)
        self.members['Esi'].phone = '0549911000'
        self.members['Esi'].email = 'search@example.invalid'
        self.db.commit()
        household = self.household()
        self.add(household, 'Ama', 'HEAD')
        self.add(household, 'Yaw', 'SON')
        self.add(household, 'Esi', 'DEPENDANT')
        stats = self.service.get_household(household['id'])['stats']
        self.assertEqual((stats['total'], stats['adults'], stats['children'], stats['dependants'], stats['unknown_age']), (3, 1, 1, 1, 1))
        self.assertEqual(self.service.get_household_stats()['without'], 1)
        self.assertEqual(self.service.candidate_members(unassigned_only=True)['rows'][0]['id'], str(self.members['Kofi'].id))
        self.assertEqual(self.service.candidate_members(search='search@example.invalid')['total'], 1)
        self.assertEqual(self.service.list_households(search='0549911000')['total'], 1)
        self.assertIsNone(age_on(None))
        self.assertEqual(age_on(date(2008, 10, 6), date(2026, 10, 5)), 17)

    def test_database_indexes_and_restrict_member_deletion(self):
        first, second = self.household(), self.household('Other')
        head = self.add(first, 'Ama', 'HEAD')
        for values in (
            dict(household_id=uuid.UUID(second['id']), member_id=self.members['Ama'].id, relationship='SPOUSE', is_household_head=False),
            dict(household_id=uuid.UUID(first['id']), member_id=self.members['Yaw'].id, relationship='HEAD', is_household_head=True),
            dict(household_id=uuid.UUID(first['id']), member_id=self.members['Yaw'].id, relationship='SON', is_household_head=True)):
            with self.assertRaises(IntegrityError):
                with self.db.begin_nested():
                    self.db.add(HouseholdMember(**values)); self.db.flush()
        with self.assertRaises(IntegrityError):
            with self.db.begin_nested():
                self.db.execute(delete(Member).where(Member.id == self.members['Ama'].id))

    def test_constant_directory_query_count_and_private_audit(self):
        household = self.household(notes='Private family notes', primary_address='Private address')
        self.add(household)
        calls = []
        def counted(*_args): calls.append(1)
        event.listen(self.connection, 'before_cursor_execute', counted)
        self.service.list_households()
        initial = len(calls)
        event.remove(self.connection, 'before_cursor_execute', counted)
        for index in range(20): self.household('Family '+str(index))
        calls.clear()
        event.listen(self.connection, 'before_cursor_execute', counted)
        try:
            self.service.list_households()
            self.assertEqual(len(calls), initial)
        finally:
            event.remove(self.connection, 'before_cursor_execute', counted)
        events = self.service.audit_events(household['id'])['rows']
        self.assertTrue(events)
        self.assertNotIn('Private family', str(events))
        self.assertNotIn('Private address', str(events))

    def test_simultaneous_membership_only_one_current(self):
        self.db.close(); self.transaction.rollback()
        factory = sessionmaker(bind=self.test_engine, expire_on_commit=False)
        suffix = uuid.uuid4().hex[:16]
        with factory() as db:
            role = db.scalar(select(Role).where(Role.code == 'TEST_ADMIN'))
            actor = User(username='family-race-'+suffix, password_hash='unused', status=UserStatus.ACTIVE, roles=[role])
            member = Member(member_no='FAMILY-RACE-'+suffix, first_name='Concurrent', last_name='Member', baptized=False)
            db.add_all([actor, member]); db.commit()
            actor_id, member_id = actor.id, member.id
        service = HouseholdService(actor_id, factory)
        households = [service.create_household(dict(household_name='Race '+str(index))) for index in range(2)]
        def add(household):
            try:
                HouseholdService(actor_id, factory).add_member(household['id'], member_id, 'RELATIVE')
                return 'saved'
            except HouseholdMoveRequired:
                return 'move_required'
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = [pool.submit(add, household) for household in households]
                self.assertCountEqual([future.result(timeout=20) for future in results], ['saved', 'move_required'])
            with factory() as db:
                self.assertEqual(db.scalar(select(func.count()).select_from(HouseholdMember).where(HouseholdMember.is_active.is_(True))), 1)
        finally:
            with self.test_engine.begin() as connection:
                for model in (HouseholdAuditLog, HouseholdMember, Household, AuthorizationAuditLog, UserMinistryScope, MemberMinistry, User, Member, fixtures.Ministry):
                    connection.execute(delete(model))


if __name__ == '__main__': unittest.main()
