"""Real ministry configuration checks, isolated from production church records."""
from datetime import date
import unittest
import uuid
from sqlalchemy import event, select, text
from sqlalchemy.exc import IntegrityError
from src.models import Ministry, MinistryAuditLog, MemberMinistry, Permission, UserStatus
from src.services.ministry_service import MinistryService, MinistryServiceError, MinistryAuthorizationError
from src.services.member_service import MemberService, MemberServiceError
from src.services.attendance_service import AttendanceServiceError
from tests import test_attendance as attendance


class MinistryTests(unittest.TestCase):
    setUpClass=classmethod(attendance.AttendanceTests.setUpClass.__func__)
    tearDownClass=classmethod(attendance.AttendanceTests.tearDownClass.__func__)
    tearDown=attendance.AttendanceTests.tearDown
    youth=attendance.AttendanceTests.youth

    def setUp(self):
        attendance.AttendanceTests.setUp(self)
        self.service=MinistryService(self.users['Admin'].id,self.factory)

    def drama(self):
        return self.service.create_ministry(dict(name='Drama Ministry',code='drama',category='MINISTRY',description='Creative ministry.'))

    def test_create_dynamic_selectors_and_same_id_edit(self):
        created=self.drama()
        self.assertEqual(created['code'],'DRAMA')
        member_service=MemberService(self.users['Admin'].id,self.factory)
        self.assertIn(created['id'],[item['id'] for item in member_service.list_ministries()])
        self.assertIn(created['id'],[item['id'] for item in self.services['Admin'].list_ministries('create')])
        member_service.create_member(dict(first_name='Drama',last_name='Member'),[created['id']])
        original=self.db.scalar(select(MemberMinistry).where(MemberMinistry.ministry_id==uuid.UUID(created['id'])))
        relationship_id=original.id
        data=dict(created,name='Drama & Creative Arts Ministry')
        updated=self.service.update_ministry(created['id'],data,created['updated_at'])
        self.assertEqual(updated['id'],created['id'])
        self.db.expire_all()
        self.assertEqual(self.db.get(MemberMinistry,relationship_id).ministry_id,uuid.UUID(created['id']))
        self.assertEqual(self.service.get_ministry(created['id'])['member_count'],1)
        with self.assertRaisesRegex(MinistryServiceError,'code is locked'):
            self.service.update_ministry(created['id'],dict(updated,code='NEW_CODE'))

    def test_lifecycle_restore_ids_audit_and_active_selectors(self):
        created=self.drama()
        member_service=MemberService(self.users['Admin'].id,self.factory)
        member=member_service.create_member(dict(first_name='Drama',last_name='Member'),[created['id']])
        self.service.deactivate_ministry(created['id'])
        self.assertNotIn(created['id'],[item['id'] for item in member_service.list_ministries()])
        self.assertNotIn(created['id'],[item['id'] for item in self.services['Admin'].list_ministries('create')])
        self.assertIn(created['id'],[item['id'] for item in self.services['Admin'].list_ministries('view')])
        with self.assertRaises(AttendanceServiceError):
            self.services['Admin'].create_session(title='Inactive meeting',session_type='MINISTRY_MEETING',
                scope_type='MINISTRY',ministry_id=created['id'],session_date=date.today())
        self.service.archive_ministry(created['id'])
        archived=self.service.get_ministry(created['id'])
        self.assertEqual(archived['status'],'ARCHIVED')
        self.assertIsNotNone(archived['archived_at'])
        self.assertEqual(archived['member_count'],1)
        self.assertEqual(member_service.get_member(member['id'])['ministry_ids'],[created['id']])
        restored=self.service.restore_ministry(created['id'])
        self.assertEqual((restored['id'],restored['status']),(created['id'],'INACTIVE'))
        self.service.activate_ministry(created['id'])
        self.service.archive_ministry(created['id'])
        restored=self.service.restore_ministry(created['id'],status='ACTIVE')
        self.assertEqual(restored['id'],created['id'])
        self.assertIn(created['id'],[item['id'] for item in member_service.list_ministries()])
        actions={row['action'] for row in self.service.audit_history(created['id'])}
        self.assertTrue({'CREATED','DEACTIVATED','ARCHIVED','RESTORED','ACTIVATED'}.issubset(actions))
        self.assertTrue(all(row['actor'] for row in self.service.audit_history(created['id'])))

    def test_edit_member_retains_archived_participation_and_allows_explicit_removal(self):
        member_service=MemberService(self.users['Admin'].id,self.factory)
        member_id=self.members['Ama'].id
        original=member_service.get_member(member_id)
        youth_id=str(self.ministries['Youth'].id)
        association=self.db.scalar(select(MemberMinistry).where(MemberMinistry.member_id==member_id,
            MemberMinistry.ministry_id==self.ministries['Youth'].id))
        association_id=association.id
        self.service.archive_ministry(youth_id)
        profile=member_service.get_member(member_id)
        self.assertIn(youth_id,profile['ministry_ids'])
        options=member_service.list_ministries(member_id=member_id)
        self.assertEqual(next(item['status'] for item in options if item['id']==youth_id),'ARCHIVED')
        member_service.update_member(member_id,profile,profile['ministry_ids'])
        self.db.expire_all()
        self.assertTrue(self.db.get(MemberMinistry,association_id).is_active)
        self.assertEqual(self.db.get(MemberMinistry,association_id).position_title,'Leader')
        with self.assertRaises(MemberServiceError):
            member_service.create_member(dict(first_name='New',last_name='Member'),[youth_id])
        member_service.update_member(member_id,profile,[mid for mid in profile['ministry_ids'] if mid!=youth_id])
        self.db.expire_all()
        self.assertFalse(self.db.get(MemberMinistry,association_id).is_active)
        self.assertIsNotNone(self.db.get(MemberMinistry,association_id).left_at)
        with self.assertRaises(MemberServiceError):
            member_service.update_member(member_id,profile,original['ministry_ids'])

    def test_unused_delete_requires_confirmation_and_preserves_audit(self):
        ministry=self.drama()
        self.service.update_ministry(ministry['id'],dict(ministry,code='DRAMA_ARTS'))
        with self.assertRaisesRegex(MinistryServiceError,'confirmation'):
            self.service.delete_unused_ministry(ministry['id'])
        self.service.delete_unused_ministry(ministry['id'],confirmed=True)
        self.db.expire_all()
        self.assertIsNone(self.db.get(Ministry,uuid.UUID(ministry['id'])))
        logs=self.db.scalars(select(MinistryAuditLog).where(MinistryAuditLog.ministry_id==uuid.UUID(ministry['id']))).all()
        deleted=next(row for row in logs if row.action=='DELETED_UNUSED')
        self.assertEqual(deleted.old_values['code'],'DRAMA_ARTS')
        self.assertEqual(deleted.actor_user_id,self.users['Admin'].id)

    def test_used_delete_blocks_historical_memberships_and_database_cascade(self):
        mid=self.ministries['Youth'].id
        with self.assertRaisesRegex(MinistryServiceError,'Archive it instead'):
            self.service.delete_unused_ministry(mid,confirmed=True)
        self.db.query(MemberMinistry).filter(MemberMinistry.ministry_id==mid).update(dict(is_active=False))
        self.db.commit()
        with self.assertRaisesRegex(MinistryServiceError,'Archive it instead'):
            self.service.delete_unused_ministry(mid,confirmed=True)
        with self.assertRaises(IntegrityError):
            with self.db.begin_nested():
                self.db.execute(text(f'DELETE FROM "{self.schema}".ministries WHERE id=:mid'),dict(mid=mid))

    def test_delete_blocks_attendance_and_future_table_references(self):
        ministry=self.drama()
        self.services['Admin'].create_session(title='Drama meeting',session_type='MINISTRY_MEETING',scope_type='MINISTRY',
            ministry_id=ministry['id'],session_date=date.today())
        with self.assertRaisesRegex(MinistryServiceError,'Archive it instead'):
            self.service.delete_unused_ministry(ministry['id'],confirmed=True)
        other=self.service.create_ministry(dict(name='Future Ministry',code='FUTURE'))
        self.db.execute(text(f'CREATE TABLE "{self.schema}".future_dues (ministry_id uuid REFERENCES "{self.schema}".ministries(id) ON DELETE CASCADE)'))
        self.db.execute(text(f'INSERT INTO "{self.schema}".future_dues VALUES (:mid)'),dict(mid=uuid.UUID(other['id'])))
        self.db.flush()
        with self.assertRaisesRegex(MinistryServiceError,'Archive it instead'):
            self.service.delete_unused_ministry(other['id'],confirmed=True)

    def test_name_code_category_validation_uniqueness_and_search_filters(self):
        ministry=self.drama()
        for change in (dict(name=''),dict(code=''),dict(code='HAS SPACE'),dict(code='9BAD'),dict(category='UNKNOWN')):
            with self.assertRaises(MinistryServiceError):
                self.service.create_ministry(dict(dict(name='Another Ministry',code='ANOTHER'),**change))
        for data in (dict(name='Different Name',code='drama'),dict(name='DRAMA MINISTRY',code='DIFFERENT')):
            with self.assertRaises(MinistryServiceError):
                self.service.create_ministry(data)
        self.assertEqual(self.service.list_ministries(search='dram',status='ACTIVE',category='MINISTRY')['total'],1)
        self.assertEqual(self.service.list_ministries(category='FELLOWSHIP')['total'],0)
        self.service.archive_ministry(ministry['id'])
        self.assertEqual(self.service.list_ministries(status='ARCHIVED')['total'],1)
        self.assertEqual(self.service.get_ministry_stats()['archived'],1)

    def test_service_grants_scoped_leader_and_revocation(self):
        leader=MinistryService(self.users['Youth'].id,self.factory)
        self.assertEqual(leader.list_ministries()['total'],1)
        youth=self.service.get_ministry(self.ministries['Youth'].id)
        self.assertFalse(leader.capabilities()['create'])
        operations=[lambda:leader.create_ministry(dict(name='Wrong',code='WRONG')),
            lambda:leader.update_ministry(youth['id'],youth),lambda:leader.activate_ministry(youth['id']),
            lambda:leader.deactivate_ministry(youth['id']),lambda:leader.archive_ministry(youth['id']),
            lambda:leader.restore_ministry(youth['id']),lambda:leader.delete_unused_ministry(youth['id'],confirmed=True),
            lambda:leader.get_ministry(self.ministries['Women'].id)]
        for operation in operations:
            with self.assertRaises(MinistryServiceError):
                operation()
        self.service.archive_ministry(youth['id'])
        self.assertEqual(leader.get_ministry(youth['id'])['status'],'ARCHIVED')
        grant=self.db.scalar(select(Permission).where(Permission.code=='MINISTRIES_CREATE'))
        grant.is_active=False
        self.db.commit()
        with self.assertRaises(MinistryAuthorizationError):
            self.drama()
        self.users['Youth'].status=UserStatus.INACTIVE
        self.db.commit()
        with self.assertRaises(MinistryAuthorizationError):
            leader.list_ministries()

    def test_aggregate_counts_pagination_and_constant_query_count(self):
        self.assertEqual(self.service.get_member_counts()[str(self.ministries['Youth'].id)],2)
        self.members['Yaw'].status=attendance.MemberStatus.INACTIVE
        self.db.commit()
        profile=self.service.get_ministry(self.ministries['Youth'].id)
        self.assertEqual((profile['member_count'],profile['active_member_count']),(2,1))
        calls=[]
        def counted(*_args):
            calls.append(1)
        event.listen(self.connection,'before_cursor_execute',counted)
        try:
            self.service.list_ministries(limit=100)
            initial=len(calls)
            event.remove(self.connection,'before_cursor_execute',counted)
            self.db.add_all([Ministry(code=f'EXTRA_{i}',name=f'Extra ministry {i}') for i in range(45)])
            self.db.commit()
            calls.clear()
            event.listen(self.connection,'before_cursor_execute',counted)
            listed=self.service.list_ministries(limit=100)
            self.assertEqual(len(calls),initial)
            self.assertEqual(listed['total'],49)
            first=self.service.list_ministries(limit=20,offset=0)
            second=self.service.list_ministries(limit=20,offset=20)
            self.assertEqual(len(first['rows']),20)
            self.assertFalse(set(row['id'] for row in first['rows']) & set(row['id'] for row in second['rows']))
        finally:
            event.remove(self.connection,'before_cursor_execute',counted)

    def test_stale_updates_and_invalid_restore_are_rejected(self):
        ministry=self.drama()
        self.service.update_ministry(ministry['id'],dict(ministry,description='Updated'))
        with self.assertRaisesRegex(MinistryServiceError,'another user'):
            self.service.archive_ministry(ministry['id'],expected_updated_at=ministry['updated_at'])
        with self.assertRaises(MinistryServiceError):
            self.service.restore_ministry(ministry['id'])
        self.service.archive_ministry(ministry['id'])
        with self.assertRaisesRegex(MinistryServiceError,'Restore'):
            self.service.activate_ministry(ministry['id'])


if __name__=='__main__':
    unittest.main()
