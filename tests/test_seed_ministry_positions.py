"""Default offices and repeatable seeding in a disposable PostgreSQL schema."""
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from sqlalchemy import func, select

from tests import test_attendance as fixtures
from src.database.seed_ministry_positions import DEFAULT_POSITIONS, position_name, seed
from src.models import Ministry, MinistryPosition, MinistryLeadershipAuditLog, UserStatus
from src.services.authorization_service import AuthorizationDenied
from src.services.ministry_leadership_service import MinistryLeadershipService


class MinistryPositionSeedTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.AttendanceTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.AttendanceTests.tearDownClass.__func__)
    tearDown = fixtures.AttendanceTests.tearDown

    def setUp(self):
        fixtures.AttendanceTests.setUp(self)
        self.actor = self.users['Admin'].id
        self.service = MinistryLeadershipService(self.actor, self.factory)
        self.ministries['Youth'].name = 'Youth Ministry'
        self.ministries['Women'].name = "Women's Fellowship"
        self.ministries['Choir'].name = 'Choir / Music Ministry'
        self.ministries['Men'].name = "Men's Fellowship"
        self.db.commit()

    def seed(self):
        return seed(self.factory, self.actor)

    def positions(self):
        self.db.expire_all()
        return self.db.scalars(select(MinistryPosition).order_by(MinistryPosition.id)).all()

    def snapshot(self):
        return [(row.id, row.ministry_id, row.code, row.name, row.description,
            row.sort_order, row.is_active, row.is_leadership, row.max_current_holders,
            row.created_by_user_id, row.updated_by_user_id, row.created_at, row.updated_at)
            for row in self.positions()]

    def audit_count(self):
        return self.db.scalar(select(func.count()).select_from(MinistryLeadershipAuditLog))

    def test_all_offices_names_audit_and_repeat_are_stable(self):
        result = self.seed()
        self.assertEqual(result, dict(ministries=4, created=20, existing=0, managed=0))
        expected_codes = {code for code, _title in DEFAULT_POSITIONS}
        for ministry in self.ministries.values():
            rows = self.service.list_positions(ministry.id)
            self.assertEqual({row['code'] for row in rows}, expected_codes)
            self.assertEqual([row['name'] for row in rows], [position_name(ministry.name, title) for _code, title in DEFAULT_POSITIONS])
            self.assertTrue(all(row['is_active'] and row['is_leadership'] and row['max_current_holders'] == 1 for row in rows))
        self.assertEqual(self.service.list_positions(self.ministries['Youth'].id)[0]['name'], 'Youth Leader')
        before = self.snapshot()
        events = self.db.scalars(select(MinistryLeadershipAuditLog)).all()
        self.assertEqual(len(events), 20)
        self.assertTrue(all(event.action == 'POSITION_SEEDED' and event.actor_user_id == self.actor for event in events))
        self.assertEqual(self.seed(), dict(ministries=4, created=0, existing=20, managed=0))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.audit_count(), 20)

    def test_edits_deactivation_and_deletion_survive_repeat(self):
        self.seed()
        youth = {row['code']: row for row in self.service.list_positions(self.ministries['Youth'].id)}
        leader = youth['LEADER']
        self.service.update_position(leader['id'], dict(leader, name='Youth Chairperson', code='YOUTH_CHAIR',
            is_active=False, max_current_holders=3, sort_order=90, description='Administrator configuration'))
        self.service.delete_unused_position(youth['TREASURER']['id'], confirmed=True)
        self.service.deactivate_position(youth['ORGANIZER']['id'])
        before = self.snapshot()
        events = self.audit_count()
        result = self.seed()
        self.assertEqual(result['created'], 0)
        self.assertEqual(result['managed'], 2)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.audit_count(), events)

    def test_existing_equivalent_office_is_preserved(self):
        position = self.service.create_position(self.ministries['Youth'].id,
            dict(code='CHAIR', name='Leader', is_active=False, max_current_holders=2))
        before = next(row for row in self.snapshot() if str(row[0]) == position['id'])
        self.assertEqual(self.seed()['created'], 19)
        after = next(row for row in self.snapshot() if str(row[0]) == position['id'])
        self.assertEqual(after, before)
        youth = self.service.list_positions(self.ministries['Youth'].id)
        self.assertEqual(len(youth), 5)
        self.assertNotIn('LEADER', {row['code'] for row in youth})

    def test_inactive_and_archived_ministries_receive_inactive_offices(self):
        self.ministries['Women'].is_active = False
        self.ministries['Men'].is_active = False
        self.ministries['Men'].archived_at = datetime.now(timezone.utc)
        self.db.commit()
        self.assertEqual(self.seed()['created'], 20)
        inactive_ids = {self.ministries[key].id for key in ('Women', 'Men')}
        for row in self.positions():
            self.assertEqual(row.is_active, row.ministry_id not in inactive_ids)
        self.db.refresh(self.ministries['Men'])
        self.assertFalse(self.ministries['Men'].is_active)
        self.assertIsNotNone(self.ministries['Men'].archived_at)

    def test_repeat_populates_only_a_new_ministry(self):
        self.seed()
        before = self.snapshot()
        ministry = Ministry(code='TEST_COMMUNICATION', name='Communication Department', is_active=True)
        self.db.add(ministry)
        self.db.commit()
        self.assertEqual(self.seed()['created'], 5)
        self.assertEqual([row['name'] for row in self.service.list_positions(ministry.id)],
            ['Communication ' + title for _code, title in DEFAULT_POSITIONS])
        self.assertEqual([row for row in self.snapshot() if row[1] != ministry.id], before)

    def test_authorization_and_ambiguous_configured_actor(self):
        with self.assertRaises(AuthorizationDenied):
            seed(self.factory, self.users['Youth'].id)
        with patch.dict('os.environ', {'SEED_ADMIN_EMAIL': self.users['Youth'].email,
            'SEED_ADMIN_USERNAME': self.users['Admin'].username}):
            with self.assertRaisesRegex(RuntimeError, 'authorized administrator'):
                seed(self.factory)
        self.users['Admin'].status = UserStatus.SUSPENDED
        self.db.commit()
        with self.assertRaises(AuthorizationDenied):
            self.seed()
        self.assertEqual(self.positions(), [])
        self.assertEqual(self.audit_count(), 0)

    def test_configured_actor_and_long_ministry_name(self):
        self.ministries['Youth'].name = 'Y' * 150
        self.db.commit()
        with patch.dict('os.environ', {'SEED_ADMIN_EMAIL': self.users['Admin'].email.upper(),
            'SEED_ADMIN_USERNAME': self.users['Admin'].username.upper()}):
            self.assertEqual(seed(self.factory)['created'], 20)
        youth = self.service.list_positions(self.ministries['Youth'].id)
        self.assertTrue(all(len(row['name']) <= 150 for row in youth))
        self.assertEqual(len({row['name'] for row in youth}), 5)


if __name__ == '__main__':
    unittest.main()
