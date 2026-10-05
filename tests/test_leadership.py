"""Church office rules against PostgreSQL in private, rolled-back schemas."""
from datetime import date, timedelta
import unittest
import uuid
from sqlalchemy import select, func, event, delete
from sqlalchemy.exc import IntegrityError
from src.models import (MemberMinistry, MinistryPosition, MinistryLeadershipAssignment as Assignment,
                        MinistryLeadershipAuditLog as Audit, Permission, UserStatus, MemberStatus)
from src.models.associations import user_roles
from src.services.ministry_leadership_service import (MinistryLeadershipService, LeadershipServiceError,
    LeadershipAuthorizationError, MembershipRequiredError, PositionConflictError)
from src.services.ministry_service import MinistryService, MinistryServiceError
from src.services.member_service import MemberService, MemberServiceError
from tests import test_attendance as attendance


class LeadershipTests(unittest.TestCase):
    setUpClass = classmethod(attendance.AttendanceTests.setUpClass.__func__)
    tearDownClass = classmethod(attendance.AttendanceTests.tearDownClass.__func__)
    tearDown = attendance.AttendanceTests.tearDown

    def setUp(self):
        attendance.AttendanceTests.setUp(self)
        self.service = MinistryLeadershipService(self.users['Admin'].id, self.factory)
        self.mid = str(self.ministries['Youth'].id)
        self.start = date.today()-timedelta(days=30)

    def position(self, name='Leader', **changes):
        return self.service.create_position(self.mid, dict(dict(name=name, code=name.replace(' ', '_'), max_current_holders=1), **changes))

    def appoint(self, position, member='Ama', **changes):
        return self.service.assign_member(self.mid, self.members[member].id, position['id'], **dict(dict(start_date=self.start), **changes))

    def test_position_scope_uniqueness_validation_and_code_lock(self):
        position = self.position(code='leader')
        self.assertEqual(position['code'], 'LEADER')
        other = self.service.create_position(self.ministries['Choir'].id, dict(name='Director', code='LEADER'))
        self.assertNotEqual(position['id'], other['id'])
        for values in (dict(name=''), dict(code='HAS SPACE'), dict(max_current_holders=0), dict(sort_order=-1), dict(is_active='false')):
            with self.assertRaises(LeadershipServiceError):
                self.service.create_position(self.mid, dict(dict(name='Other', code='OTHER'), **values))
        with self.assertRaises(LeadershipServiceError):
            self.position(name='leader')
        self.appoint(position)
        with self.assertRaisesRegex(LeadershipServiceError, 'code is locked'):
            self.service.update_position(position['id'], dict(position, code='DIRECTOR'))

    def test_appoint_without_account_and_no_security_side_effects(self):
        position = self.position()
        accounts = self.db.scalar(select(func.count()).select_from(attendance.User))
        roles = self.db.execute(select(user_roles)).all()
        result = self.appoint(position)
        self.assertTrue(result['is_current'])
        self.assertEqual(self.service.list_current_leadership(self.mid)['rows'][0]['full_name'], self.members['Ama'].full_name)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(attendance.User)), accounts)
        self.assertEqual(self.db.execute(select(user_roles)).all(), roles)
        self.assertIn('MEMBER_ASSIGNED', [row['action'] for row in self.service.leadership_audit(self.mid)])

    def test_holder_conflict_duplicate_and_controlled_replacement(self):
        position = self.position()
        first = self.appoint(position)
        with self.assertRaises(PositionConflictError) as error:
            self.appoint(position, 'Yaw')
        self.assertEqual(error.exception.holders[0]['id'], first['id'])
        with self.assertRaisesRegex(LeadershipServiceError, 'already holds'):
            self.appoint(position)
        second = self.appoint(position, 'Yaw', start_date=date.today(), replace_assignment_id=first['id'], expected_replaced_updated_at=first['updated_at'])
        self.assertEqual(self.service.get_assignment(first['id'])['end_date'], date.today())
        self.assertFalse(self.service.get_assignment(first['id'])['is_current'])
        self.assertEqual(self.service.list_current_leadership(self.mid)['rows'][0]['id'], second['id'])
        self.assertEqual(self.service.list_leadership_history(self.mid)['total'], 1)

    def test_replacement_rollback_restores_previous_holder(self):
        position = self.position()
        first = self.appoint(position)
        # Add a historical conflicting appointment for the prospective replacement.
        self.appoint(position, 'Yaw', start_date=self.start, end_date=date.today())
        with self.assertRaisesRegex(LeadershipServiceError, 'overlap'):
            self.appoint(position, 'Yaw', start_date=self.start+timedelta(days=1), replace_assignment_id=first['id'])
        self.assertTrue(self.service.get_assignment(first['id'])['is_current'])
        self.assertEqual(self.service.list_current_leadership(self.mid)['total'], 1)

    def test_multiple_positions_multiple_ministries_and_member_profile(self):
        first, second = self.position('Secretary'), self.position('Welfare Officer', max_current_holders=None)
        choir = self.service.create_position(self.ministries['Choir'].id, dict(name='Treasurer', code='TREASURER'))
        self.appoint(first)
        self.appoint(second)
        self.appoint(second, 'Yaw')
        self.service.assign_member(self.ministries['Choir'].id, self.members['Ama'].id, choir['id'], self.start)
        profile = MemberService(self.users['Admin'].id, self.factory).get_member(self.members['Ama'].id)
        self.assertEqual(len(profile['leadership']), 3)
        self.assertEqual(len({row['ministry_id'] for row in profile['leadership']}), 2)
        self.assertEqual(self.service.leadership_stats(self.mid)['current'], 3)
        youth_profile = MemberService(self.users['Youth'].id, self.factory).get_member(self.members['Ama'].id)
        self.assertEqual(len(youth_profile['leadership']), 2)
        self.assertTrue(all(row['ministry_id']==self.mid for row in youth_profile['leadership']))
        self.assertEqual(len(MinistryLeadershipService(self.users['Choir'].id,self.factory).get_member_leadership(self.members['Ama'].id)),1)

    def test_membership_required_explicit_enrollment_and_atomic_rollback(self):
        position = self.position()
        with self.assertRaises(MembershipRequiredError):
            self.appoint(position, 'Esi')
        self.assertIsNone(self.db.scalar(select(MemberMinistry).where(MemberMinistry.member_id == self.members['Esi'].id, MemberMinistry.ministry_id == self.ministries['Youth'].id)))
        self.appoint(position)
        with self.assertRaises(PositionConflictError):
            self.appoint(position, 'Esi', add_membership=True)
        self.assertIsNone(self.db.scalar(select(MemberMinistry).where(MemberMinistry.member_id == self.members['Esi'].id, MemberMinistry.ministry_id == self.ministries['Youth'].id)))
        other = self.position('Secretary')
        result = self.appoint(other, 'Esi', add_membership=True)
        self.assertTrue(result['is_current'])
        self.assertTrue(self.db.scalar(select(MemberMinistry).where(MemberMinistry.member_id == self.members['Esi'].id, MemberMinistry.ministry_id == self.ministries['Youth'].id)).is_active)

    def test_ending_archiving_history_snapshots_and_protected_deletion(self):
        position = self.position()
        first = self.appoint(position)
        with self.assertRaises(LeadershipServiceError):
            self.service.deactivate_position(position['id'])
        self.service.end_assignment(first['id'], date.today(), 'Term completed', first['updated_at'])
        renamed = self.service.update_position(position['id'], dict(position, name='Ministry Coordinator'))
        self.assertEqual(self.service.get_assignment(first['id'])['position_name'], 'Leader')
        self.service.deactivate_position(position['id'], renamed['updated_at'])
        self.assertEqual(self.service.list_leadership_history(self.mid)['total'], 1)
        with self.assertRaisesRegex(LeadershipServiceError, 'history'):
            self.service.delete_unused_position(position['id'], confirmed=True)
        with self.assertRaises(MinistryServiceError):
            MinistryService(self.users['Admin'].id, self.factory).delete_unused_ministry(self.mid, confirmed=True)
        with self.assertRaises(IntegrityError):
            with self.db.begin_nested():
                self.db.execute(delete(MinistryPosition).where(MinistryPosition.id == uuid.UUID(position['id'])))

    def test_unused_delete_requires_confirmation_retains_audit(self):
        position = self.position()
        with self.assertRaises(LeadershipServiceError):
            self.service.delete_unused_position(position['id'])
        self.service.delete_unused_position(position['id'], confirmed=True)
        self.assertIsNone(self.db.get(MinistryPosition, uuid.UUID(position['id'])))
        self.assertEqual(self.db.scalar(select(Audit).where(Audit.action == 'POSITION_DELETED_UNUSED')).old_values['code'], 'LEADER')

    def test_assignment_edit_stale_identity_and_date_guards(self):
        position = self.position()
        first = self.appoint(position)
        updated = self.service.update_assignment(first['id'], dict(notes='Corrected', start_date=self.start-timedelta(days=2)), first['updated_at'])
        self.assertEqual(updated['notes'], 'Corrected')
        with self.assertRaises(LeadershipServiceError):
            self.service.end_assignment(first['id'], date.today(), expected_updated_at=first['updated_at'])
        for values in (dict(member_id=self.members['Yaw'].id), dict(end_date=date.today()), dict(start_date=date.today()+timedelta(days=1))):
            with self.assertRaises(LeadershipServiceError):
                self.service.update_assignment(first['id'], values)
        with self.assertRaises(LeadershipServiceError):
            self.service.end_assignment(first['id'], self.start-timedelta(days=3))
        with self.assertRaises(LeadershipServiceError):
            self.service.update_position(position['id'], dict(position, max_current_holders=0))

    def test_vacancies_search_and_scoped_read_without_management(self):
        position, vacant = self.position(), self.position('Secretary')
        self.appoint(position)
        leader = MinistryLeadershipService(self.users['Youth'].id, self.factory)
        self.assertEqual(leader.list_current_leadership(self.mid)['total'], 1)
        self.assertEqual(self.service.list_leadership(self.mid, 'VACANT')['rows'][0]['id'], vacant['id'])
        self.assertEqual(self.service.list_current_leadership(self.mid, search=self.members['Ama'].member_no)['total'], 1)
        self.assertEqual(self.service.list_current_leadership(self.mid, search='Leader')['total'], 1)
        with self.assertRaises(MinistryServiceError):
            leader.list_current_leadership(self.ministries['Women'].id)
        # Global ministry configuration viewing does not widen scoped office/member data.
        self.users['Youth'].roles[0].permissions.append(self.db.scalar(select(Permission).where(Permission.code=='MINISTRIES_VIEW_ALL')))
        self.db.commit()
        self.assertEqual(MinistryService(self.users['Youth'].id,self.factory).get_ministry(self.ministries['Women'].id)['id'],str(self.ministries['Women'].id))
        self.assertFalse(leader.capabilities(self.ministries['Women'].id)['view'])
        self.assertTrue(leader.capabilities(self.mid)['view'])
        for operation in (lambda:leader.create_position(self.mid, dict(name='No', code='NO')),
            lambda:leader.update_position(position['id'], position), lambda:leader.deactivate_position(position['id']),
            lambda:leader.assign_member(self.mid, self.members['Yaw'].id, vacant['id'], self.start),
            lambda:leader.end_assignment(self.service.list_current_leadership(self.mid)['rows'][0]['id'], date.today()),
            lambda:leader.delete_unused_position(vacant['id'], confirmed=True)):
            with self.assertRaises(LeadershipAuthorizationError):
                operation()
        grant = self.db.scalar(select(Permission).where(Permission.code == 'MINISTRY_LEADERSHIP_ASSIGN'))
        grant.is_active = False
        self.db.commit()
        with self.assertRaises(LeadershipAuthorizationError):
            self.appoint(vacant, 'Yaw')
        self.users['Youth'].status = UserStatus.INACTIVE
        self.db.commit()
        with self.assertRaises(MinistryServiceError):
            leader.list_current_leadership(self.mid)

    def test_member_removal_and_status_require_ending_positions(self):
        first = self.appoint(self.position())
        member = MemberService(self.users['Admin'].id, self.factory)
        data = member.get_member(self.members['Ama'].id)
        with self.assertRaisesRegex(MemberServiceError, 'End current position'):
            member.update_member(data['id'], data, [])
        with self.assertRaises(MemberServiceError):
            member.update_member(data['id'], dict(data, status='INACTIVE'), data['ministry_ids'])
        self.service.end_assignment(first['id'], date.today())
        member.update_member(data['id'], data, [])
        self.assertEqual(len(member.get_member(data['id'])['leadership']), 1)

    def test_attendance_structured_leadership_and_saved_roster_preservation(self):
        position = self.position()
        legacy = self.db.scalar(select(MemberMinistry).where(MemberMinistry.member_id == self.members['Ama'].id,
            MemberMinistry.ministry_id == self.ministries['Youth'].id))
        legacy.position_title = None
        self.db.commit()
        first = self.appoint(position, 'Yaw')
        query = self.services['Admin']._candidate_query(self.ministries['Youth'].id, executives=True)
        self.assertEqual([row.id for row in self.db.scalars(query)], [self.members['Yaw'].id])
        session = self.services['Admin'].create_session(title='Leadership meeting', session_type='LEADERSHIP_MEETING', scope_type='MINISTRY',
            ministry_id=self.mid, session_date=date.today(), roster_type='MINISTRY_LEADERSHIP')
        self.service.end_assignment(first['id'], date.today())
        self.assertEqual(self.services['Admin'].roster(session['id'])['rows'][0]['id'], str(self.members['Yaw'].id))
        self.assertEqual(list(self.db.scalars(query)), [])

    def test_legacy_attendance_titles_remain_until_structured_member_history(self):
        position = self.position()
        query = self.services['Admin']._candidate_query(self.ministries['Youth'].id, executives=True)
        self.assertEqual([row.id for row in self.db.scalars(query)], [self.members['Ama'].id])
        first = self.appoint(position)
        self.service.end_assignment(first['id'], date.today())
        self.assertEqual(list(self.db.scalars(query)), [])

    def test_concurrent_single_holder_limit_is_serialized(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from sqlalchemy.orm import sessionmaker
        position = self.position()
        actor = self.users['Admin'].id
        members = [self.members['Ama'].id, self.members['Yaw'].id]
        self.db.close()
        self.transaction.commit()  # Fixtures exist only in this generated test schema.
        factory = sessionmaker(self.test_engine, expire_on_commit=False)
        barrier = Barrier(2)
        def appoint(member):
            barrier.wait(timeout=10)
            try:
                MinistryLeadershipService(actor, factory).assign_member(self.mid, member, position['id'], self.start)
                return 'saved'
            except PositionConflictError:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(appoint, member) for member in members]
            self.assertCountEqual([result.result(timeout=20) for result in results], ['saved', 'conflict'])
        with factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Assignment).where(Assignment.position_id == uuid.UUID(position['id']), Assignment.is_current.is_(True))), 1)
        with self.test_engine.begin() as connection:
            for model in (Audit, Assignment, MinistryPosition, attendance.AuthorizationAuditLog,
                attendance.UserMinistryScope, MemberMinistry, attendance.User, attendance.Member, attendance.Ministry):
                connection.execute(delete(model))

    def test_database_cross_ministry_duplicate_current_and_date_constraints(self):
        position = self.position()
        first = self.appoint(position)
        values = dict(ministry_id=self.ministries['Youth'].id, member_id=self.members['Ama'].id, position_id=uuid.UUID(position['id']),
            position_name='Leader', position_code='LEADER', start_date=self.start, is_current=True)
        for changes in (dict(ministry_id=self.ministries['Choir'].id), dict(), dict(member_id=self.members['Yaw'].id, end_date=date.today()),
                        dict(member_id=self.members['Yaw'].id, end_date=self.start-timedelta(days=1), is_current=False)):
            with self.assertRaises(IntegrityError):
                with self.db.begin_nested():
                    self.db.add(Assignment(**dict(values, **changes)))
                    self.db.flush()

    def test_member_search_photo_phone_and_constant_aggregate_queries(self):
        self.members['Ama'].phone = '0541234567'
        self.db.commit()
        result = self.service.candidate_members(self.mid, search='054123')
        self.assertEqual(result['total'], 1)
        self.assertIn('photo_path', result['rows'][0])
        self.assertTrue(result['rows'][0]['in_ministry'])
        calls=[]
        def counted(*_args): calls.append(1)
        self.position()
        event.listen(self.connection, 'before_cursor_execute', counted)
        self.service.list_positions(self.mid)
        initial=len(calls)
        event.remove(self.connection, 'before_cursor_execute', counted)
        for index in range(20): self.position('Officer '+str(index))
        calls.clear()
        event.listen(self.connection, 'before_cursor_execute', counted)
        try:
            self.service.list_positions(self.mid)
            self.assertEqual(len(calls), initial)
        finally:
            event.remove(self.connection, 'before_cursor_execute', counted)


if __name__ == '__main__':
    unittest.main()
