"""PostgreSQL business-rule tests in a private, disposable schema.

Public church records are never used as fixtures. Each normal test rolls back its
transaction; the concurrency test commits only to the generated test schema.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import re
from threading import Barrier
import unittest
import uuid

from sqlalchemy import delete, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from src.config.database import engine
from src.database.base import Base
from src.models import (
    AttendanceAuditLog, AttendanceRecord, AttendanceRosterMember, AttendanceSession,
    AttendanceStatus, AuthorizationAuditLog, Member, MemberMinistry, MemberStatus,
    Ministry, Permission, Role, User, UserMinistryScope, UserStatus,
)
from src.security.attendance_permissions import PERMISSIONS, LEADER_PERMISSIONS, OBSERVER_PERMISSIONS
from src.security.application_permissions import PERMISSIONS as APP_PERMISSIONS, LEADER_PERMISSIONS as APP_LEADER_PERMISSIONS, navigation
from src.services.member_service import MemberService, MemberServiceError
from src.services.attendance_service import AttendanceAuthorizationError, AttendanceService, AttendanceServiceError
from src.ui.components.date_picker import display_date, parse_date


class AttendanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = "hcms_attendance_test_" + uuid.uuid4().hex
        assert re.fullmatch(r"hcms_attendance_test_[a-f0-9]{32}", cls.schema)
        cls.test_engine = engine.execution_options(schema_translate_map={None: cls.schema})
        with engine.begin() as connection:
            connection.execute(CreateSchema(cls.schema))
        Base.metadata.create_all(cls.test_engine)
        with sessionmaker(cls.test_engine)() as db:
            permissions = {code: Permission(code=code, name=name, module="Attendance", is_active=True)
                           for code, name in (PERMISSIONS | APP_PERMISSIONS).items()}
            db.add_all(permissions.values())
            db.add_all([
                Role(code="TEST_ADMIN", name="Test Administrator", is_active=True,
                     permissions=list(permissions.values())),
                Role(code="TEST_LEADER", name="Test Ministry Officer", is_active=True,
                     permissions=[permissions[p] for p in LEADER_PERMISSIONS | APP_LEADER_PERMISSIONS]),
                Role(code="TEST_OBSERVER", name="Test Overseer", is_active=True,
                     permissions=[permissions[p] for p in OBSERVER_PERMISSIONS]),
                Role(code="MINISTRY_ATTENDANCE_LEADER", name="Ministry Attendance Leader", is_active=True,
                     permissions=[permissions[p] for p in LEADER_PERMISSIONS | APP_LEADER_PERMISSIONS]),
            ])
            db.commit()

    @classmethod
    def tearDownClass(cls):
        assert re.fullmatch(r"hcms_attendance_test_[a-f0-9]{32}", cls.schema)
        with engine.begin() as connection:
            connection.execute(DropSchema(cls.schema, cascade=True))

    def setUp(self):
        self.connection = self.test_engine.connect()
        self.transaction = self.connection.begin()
        self.factory = sessionmaker(bind=self.connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
        self.db = self.factory()
        suffix = uuid.uuid4().hex[:10]
        self.ministries = {name: Ministry(code=name+suffix, name=name+" "+suffix, is_active=True)
                           for name in ("Youth", "Choir", "Women", "Men")}
        self.db.add_all(self.ministries.values())
        roles = {role.code: role for role in self.db.scalars(select(Role)).all()}
        self.users = {}
        for name, role in (("Admin", "TEST_ADMIN"), ("Youth", "TEST_LEADER"),
                           ("Choir", "TEST_LEADER"), ("Men", "TEST_LEADER"), ("Overseer", "TEST_OBSERVER")):
            user = User(username=name+suffix, email=name+suffix+"@example.invalid", password_hash="unused-test-hash",
                        status=UserStatus.ACTIVE, roles=[roles[role]])
            self.users[name] = user
            self.db.add(user)
        self.members = {name: Member(member_no="TEST-"+suffix+"-"+name, first_name=name, last_name="Test",
                                     status=MemberStatus.ACTIVE) for name in ("Ama", "Yaw", "Esi", "Kofi")}
        self.db.add_all(self.members.values())
        self.db.flush()
        for member, ministries in (("Ama", ("Youth", "Choir")), ("Yaw", ("Youth",)),
                                    ("Esi", ("Women",)), ("Kofi", ("Men",))):
            for ministry in ministries:
                self.db.add(MemberMinistry(member_id=self.members[member].id, ministry_id=self.ministries[ministry].id,
                                          is_active=True, position_title="Leader" if member == "Ama" else None))
        for ministry in ("Youth", "Choir", "Men"):
            self.db.add(UserMinistryScope(user_id=self.users[ministry].id, ministry_id=self.ministries[ministry].id,
                can_view_attendance=True, can_create_attendance=True, can_record_attendance=True,
                can_correct_attendance=True, can_close_attendance=True, can_view_reports=True, is_active=True))
        self.db.commit()
        self.services = {name: AttendanceService(user.id, self.factory) for name, user in self.users.items()}

    def tearDown(self):
        self.db.close()
        if self.transaction.is_active:
            self.transaction.rollback()
        self.connection.close()

    def sunday(self, **changes):
        return self.services["Admin"].create_session(**dict(dict(title="Sunday Worship Service",
            session_type="SUNDAY_SERVICE", scope_type="GLOBAL", session_date=date.today()), **changes))

    def youth(self, **changes):
        return self.services["Youth"].create_session(**dict(dict(title="Youth Weekly Meeting",
            session_type="MINISTRY_MEETING", scope_type="MINISTRY", ministry_id=str(self.ministries["Youth"].id),
            session_date=date(2026, 10, 8)), **changes))

    def record(self, session, name="Ama"):
        self.db.expire_all()
        return self.db.scalar(select(AttendanceRecord).where(
            AttendanceRecord.session_id == uuid.UUID(session["id"]), AttendanceRecord.member_id == self.members[name].id))

    def test_shared_sunday_roster_and_unique_constraint(self):
        session = self.sunday()
        self.services["Youth"].mark(session["id"], self.members["Ama"].id, "PRESENT")
        rows = self.services["Choir"].roster(session["id"])["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["attendance_status"], "PRESENT")
        self.assertEqual(rows[0]["marked_by"], self.users["Youth"].username)
        self.assertIsNotNone(rows[0]["marked_at"])
        with self.assertRaises(AttendanceServiceError):
            self.services["Choir"].mark(session["id"], self.members["Ama"].id, "ABSENT")
        with self.assertRaises(IntegrityError):
            with self.db.begin_nested():
                self.db.add(AttendanceRecord(session_id=uuid.UUID(session["id"]), member_id=self.members["Ama"].id,
                                             status=AttendanceStatus.ABSENT))
                self.db.flush()

    def test_correction_keeps_original_marker_and_audits_reason(self):
        session = self.sunday()
        self.services["Youth"].mark(session["id"], self.members["Ama"].id, "ABSENT")
        original = self.record(session)
        original_id, marker, marked_at = original.id, original.marked_by_user_id, original.marked_at
        with self.assertRaises(AttendanceServiceError):
            self.services["Choir"].mark(session["id"], self.members["Ama"].id, "PRESENT", expected_status="ABSENT")
        self.services["Choir"].mark(session["id"], self.members["Ama"].id, "PRESENT",
            expected_status="ABSENT", reason="Presence confirmed after roll verification.")
        record = self.record(session)
        self.assertEqual((record.id, record.marked_by_user_id, record.marked_at), (original_id, marker, marked_at))
        self.assertEqual(record.updated_by_user_id, self.users["Choir"].id)
        logs = self.services["Admin"].audit_history(session["id"], self.members["Ama"].id)
        correction = next(log for log in logs if log["action"] == "CORRECTED")
        self.assertEqual((correction["old_status"], correction["new_status"]), ("ABSENT", "PRESENT"))
        self.assertTrue(correction["reason"])
        self.assertIsNotNone(correction["changed_at"])
        with self.assertRaises(AttendanceServiceError):
            self.services["Youth"].mark(session["id"], self.members["Ama"].id, "LATE",
                expected_status="ABSENT", reason="Stale correction")

    def test_service_rejects_other_ministry_session_member_and_filter(self):
        womens = self.services["Admin"].create_session(title="Women meeting", session_type="MINISTRY_MEETING",
            scope_type="MINISTRY", ministry_id=self.ministries["Women"].id, session_date=date.today())
        with self.assertRaises(AttendanceAuthorizationError):
            self.services["Youth"].get_session(womens["id"])
        with self.assertRaises(AttendanceAuthorizationError):
            self.services["Youth"].create_session(title="Wrong scope", session_type="MINISTRY_MEETING",
                scope_type="MINISTRY", ministry_id=self.ministries["Women"].id, session_date=date.today())
        sunday = self.sunday()
        with self.assertRaises(AttendanceAuthorizationError):
            self.services["Men"].mark(sunday["id"], self.members["Ama"].id, "PRESENT")
        with self.assertRaises(AttendanceAuthorizationError):
            self.services["Youth"].roster(sunday["id"], ministry_id=self.ministries["Women"].id)
        self.services["Youth"].mark(sunday["id"], self.members["Ama"].id, "ABSENT")
        with self.assertRaises(AttendanceAuthorizationError):
            self.services["Men"].mark(sunday["id"], self.members["Ama"].id, "PRESENT", reason="Wrong scope", expected_status="ABSENT")

    def test_administrator_and_overseer_explicit_permissions(self):
        session = self.sunday()
        self.assertEqual(len(self.services["Admin"].list_ministries()), len(self.db.scalars(select(Ministry)).all()))
        self.assertEqual(self.services["Overseer"].roster(session["id"])["total"], 4)
        with self.assertRaises(AttendanceAuthorizationError):
            self.services["Overseer"].mark(session["id"], self.members["Ama"].id, "PRESENT")
        with self.assertRaises(AttendanceAuthorizationError):
            self.services["Overseer"].create_session(title="No mutation grant", session_type="OTHER",
                scope_type="GLOBAL", session_date=date.today())

    def test_ministry_close_only_marks_saved_ministry_roster_absent(self):
        session = self.youth()
        self.assertEqual({r["full_name"] for r in self.services["Youth"].roster(session["id"])["rows"]}, {"Ama Test", "Yaw Test"})
        self.services["Youth"].mark(session["id"], self.members["Ama"].id, "PRESENT")
        self.services["Youth"].close_session(session["id"])
        records = self.db.scalars(select(AttendanceRecord).where(AttendanceRecord.session_id == uuid.UUID(session["id"]))).all()
        self.assertEqual({r.member_id for r in records}, {self.members["Ama"].id, self.members["Yaw"].id})
        self.assertEqual(self.record(session, "Yaw").status, AttendanceStatus.ABSENT)

    def test_selected_roster_and_executives(self):
        session = self.youth(roster_type="SELECTED_MEMBERS", selected_member_ids=[self.members["Ama"].id])
        self.services["Youth"].close_session(session["id"])
        self.assertEqual(self.services["Youth"].session_counts(session["id"])["ABSENT"], 1)
        self.assertIsNone(self.record(session, "Yaw"))
        with self.assertRaises(AttendanceServiceError):
            self.youth(roster_type="SELECTED_MEMBERS", selected_member_ids=[self.members["Esi"].id])
        executives = self.youth(roster_type="EXECUTIVES")
        self.assertEqual(self.services["Youth"].roster(executives["id"])["total"], 1)

    def test_different_sessions_have_independent_records(self):
        sunday, youth = self.sunday(), self.youth()
        choir = self.services["Choir"].create_session(title="Choir rehearsal", session_type="MINISTRY_MEETING",
            scope_type="MINISTRY", ministry_id=self.ministries["Choir"].id, session_date=date.today())
        for service, session in (("Youth", sunday), ("Youth", youth), ("Choir", choir)):
            self.services[service].mark(session["id"], self.members["Ama"].id, "PRESENT")
        self.assertEqual(self.db.scalar(select(func.count()).select_from(AttendanceRecord).where(
            AttendanceRecord.member_id == self.members["Ama"].id)), 3)

    def test_lifecycle_closed_correction_locked_reopen_and_audit(self):
        session = self.youth(state="DRAFT")
        with self.assertRaises(AttendanceServiceError):
            self.services["Youth"].mark(session["id"], self.members["Ama"].id, "PRESENT")
        self.services["Youth"].transition(session["id"], "open")
        self.services["Youth"].close_session(session["id"])
        with self.assertRaises(AttendanceAuthorizationError):
            self.services["Youth"].mark(session["id"], self.members["Ama"].id, "PRESENT", expected_status="ABSENT", reason="After close")
        self.services["Admin"].mark(session["id"], self.members["Ama"].id, "PRESENT", expected_status="ABSENT", reason="Authorized closed correction")
        self.services["Admin"].transition(session["id"], "lock", reason="Final reviewed roster")
        with self.assertRaises(AttendanceServiceError):
            self.services["Youth"].mark(session["id"], self.members["Ama"].id, "LATE", expected_status="PRESENT", reason="Locked")
        with self.assertRaises(AttendanceAuthorizationError):
            self.services["Youth"].transition(session["id"], "unlock", reason="No central grant")
        with self.assertRaises(AttendanceServiceError):
            self.services["Admin"].transition(session["id"], "unlock")
        self.services["Admin"].transition(session["id"], "unlock", reason="Approved review")
        self.assertEqual(self.services["Admin"].get_session(session["id"])["state"], "OPEN")
        actions = {log["action"] for log in self.services["Admin"].audit_history(session["id"])}
        self.assertTrue({"SESSION_OPENED", "SESSION_CLOSED", "SESSION_LOCKED", "SESSION_UNLOCKED"} <= actions)

    def test_leader_cannot_close_global_sunday(self):
        session = self.sunday()
        with self.assertRaises(AttendanceAuthorizationError):
            self.services["Youth"].close_session(session["id"])

    def test_date_choices_validation_and_live_dashboard(self):
        self.assertEqual(parse_date("05/10/1994"), date(1994, 10, 5))
        self.assertEqual(display_date(date(1994, 10, 5)), "05/10/1994")
        with self.assertRaises(ValueError):
            parse_date("31/02/2026")
        past = self.sunday(session_date=date.today()-timedelta(days=7))
        self.services["Youth"].mark(past["id"], self.members["Ama"].id, "PRESENT")
        self.services["Youth"].mark(past["id"], self.members["Yaw"].id, "LATE")
        self.sunday(session_date=date.today()+timedelta(days=7))
        self.sunday(session_date=date.today(), state="DRAFT")
        stats = self.services["Admin"].latest_sunday_count()
        self.assertEqual((stats["PRESENT"], stats["LATE"], stats["count"], stats["rate"]), (1, 1, 2, 50.0))
        self.assertEqual(self.services["Youth"].latest_sunday_count()["rate"], 100.0)
        with self.assertRaises(AttendanceServiceError):
            self.youth(start_time="12:00", end_time="09:00")
        with self.assertRaises(AttendanceServiceError):
            self.youth(session_type="SUNDAY_SERVICE")

    def test_revoked_scope_permission_and_disabled_user(self):
        session = self.sunday()
        scope = self.db.scalar(select(UserMinistryScope).where(UserMinistryScope.user_id == self.users["Youth"].id))
        scope.is_active = False
        self.db.commit()
        with self.assertRaises(AttendanceAuthorizationError):
            self.services["Youth"].roster(session["id"])
        scope.is_active = True
        self.users["Youth"].status = UserStatus.INACTIVE
        self.db.commit()
        with self.assertRaises(AttendanceAuthorizationError):
            self.services["Youth"].list_sessions()
        with self.assertRaises(AttendanceAuthorizationError):
            AttendanceService(session_factory=self.factory).list_sessions()

    def test_scope_management_is_explicit_audited_and_restricted(self):
        grants = dict(can_view_attendance=True, can_create_attendance=True, can_record_attendance=True,
                      can_correct_attendance=False, can_close_attendance=False, can_view_reports=True, is_active=True)
        with self.assertRaises(AttendanceAuthorizationError):
            self.services["Youth"].set_ministry_scope(self.users["Men"].id, self.ministries["Women"].id, grants)
        self.services["Admin"].set_ministry_scope(self.users["Men"].id, self.ministries["Women"].id, grants, assign_leader_role=True)
        names = {m["name"] for m in self.services["Men"].list_ministries()}
        self.assertIn(self.ministries["Women"].name, names)
        self.assertTrue(self.db.scalar(select(func.count()).select_from(AuthorizationAuditLog)) >= 2)

    def test_reporting_history_and_counts_respect_scope(self):
        session = self.sunday()
        self.services["Admin"].mark(session["id"], self.members["Esi"].id, "PRESENT")
        self.services["Youth"].mark(session["id"], self.members["Ama"].id, "LATE")
        youth = self.services["Youth"]
        self.assertEqual(youth.session_counts(session["id"])["eligible"], 2)
        self.assertEqual({r["id"] for r in youth.roster(session["id"], report=True)["rows"]},
                         {str(self.members["Ama"].id), str(self.members["Yaw"].id)})
        self.assertEqual(youth.audit_history(session["id"], self.members["Esi"].id), [])
        self.assertEqual(youth.roster(session["id"], search="Ama Test")["total"], 1)
        self.assertEqual(youth.roster(session["id"], status="UNMARKED")["total"], 1)

    def test_snapshot_remains_stable_after_membership_changes(self):
        session = self.youth()
        newcomer = Member(member_no="TEST-NEW-"+uuid.uuid4().hex[:24], first_name="New", last_name="Joiner", status=MemberStatus.ACTIVE)
        self.db.add(newcomer)
        self.db.flush()
        self.db.add(MemberMinistry(member_id=newcomer.id, ministry_id=self.ministries["Youth"].id, is_active=True))
        self.db.commit()
        self.services["Youth"].close_session(session["id"])
        self.assertEqual(self.services["Admin"].session_counts(session["id"])["eligible"], 2)
        self.assertIsNone(self.db.scalar(select(AttendanceRecord).where(AttendanceRecord.member_id == newcomer.id)))

    def test_roster_query_count_does_not_grow_per_member(self):
        for index in range(40):
            member = Member(member_no="TEST-Q-"+uuid.uuid4().hex, first_name=f"Person{index}", last_name="Load", status=MemberStatus.ACTIVE)
            self.db.add(member)
            self.db.flush()
            self.db.add(MemberMinistry(member_id=member.id, ministry_id=self.ministries["Youth"].id, is_active=True))
        self.db.commit()
        session = self.youth()
        queries = []
        def record_query(_connection, _cursor, statement, _params, _context, _many):
            if statement.lstrip().upper().startswith("SELECT"):
                queries.append(statement)
        event.listen(engine, "before_cursor_execute", record_query)
        try:
            self.services["Youth"].roster(session["id"], limit=1)
            small = len(queries)
            queries.clear()
            self.services["Youth"].roster(session["id"], limit=30)
            self.assertEqual(len(queries), small)
            self.assertLessEqual(len(queries), 12)
        finally:
            event.remove(engine, "before_cursor_execute", record_query)

    def test_concurrent_leaders_cannot_insert_twice_or_overwrite(self):
        session = self.sunday()
        ids = {name: user.id for name, user in self.users.items()}
        member_id = self.members["Ama"].id
        self.db.close()
        self.transaction.commit()  # Only the private test schema receives committed fixtures.
        factory = sessionmaker(self.test_engine, expire_on_commit=False)
        barrier = Barrier(2)
        def mark(name, status):
            barrier.wait(timeout=10)
            try:
                AttendanceService(ids[name], factory).mark(session["id"], member_id, status)
                return "saved"
            except AttendanceServiceError:
                return "refresh required"
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(mark, "Youth", "PRESENT")
            b = pool.submit(mark, "Choir", "ABSENT")
            self.assertCountEqual([a.result(timeout=15), b.result(timeout=15)], ["saved", "refresh required"])
        with factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(AttendanceRecord).where(
                AttendanceRecord.session_id == uuid.UUID(session["id"]), AttendanceRecord.member_id == member_id)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(AttendanceAuditLog).where(
                AttendanceAuditLog.session_id == uuid.UUID(session["id"]), AttendanceAuditLog.action_type == "CREATED")), 1)
        # Remove only committed fixtures from this generated private schema.
        with self.test_engine.begin() as connection:
            for model in (AttendanceAuditLog, AttendanceRosterMember, AttendanceRecord, AttendanceSession,
                          AuthorizationAuditLog, UserMinistryScope, MemberMinistry, User, Member, Ministry):
                connection.execute(delete(model))


    def test_automatic_leadership_roster_and_admin_aggregation(self):
        session = self.youth(session_type="LEADERSHIP_MEETING")
        self.assertEqual(session['roster_type'], 'MINISTRY_LEADERSHIP')
        self.assertEqual([r['full_name'] for r in self.services['Youth'].roster(session['id'])['rows']], ['Ama Test'])
        data = self.services['Admin'].list_sessions(search='Weekly', session_type='LEADERSHIP_MEETING',
            date_from=date(2026, 10, 8), date_to=date(2026, 10, 8), created_by_user_id=self.users['Youth'].id)
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['rows'][0]['id'], session['id'])
        self.assertEqual(data['rows'][0]['created_by'], self.users['Youth'].username)
        self.assertIsNotNone(data['rows'][0]['created_at'])
        self.assertEqual(self.services['Admin'].overview()['meetings'], 1)
        self.assertEqual(self.services['Men'].overview()['meetings'], 0)

    def test_member_directory_and_navigation_follow_database_scope(self):
        youth = MemberService(self.users['Youth'].id, self.factory)
        self.assertEqual(youth.stats()['total'], 2)
        self.assertCountEqual([r['full_name'] for r in youth.list_members()], ['Ama Test', 'Yaw Test'])
        with self.assertRaises(MemberServiceError):
            youth.get_member(self.members['Esi'].id)
        with self.assertRaises(MemberServiceError):
            youth.update_member(self.members['Ama'].id, dict(first_name='Changed', last_name='Test'))
        with self.assertRaises(MemberServiceError):
            MemberService(None, self.factory).list_members()
        caps = self.services['Youth'].capabilities()
        pages = dict(navigation(caps))
        self.assertCountEqual(pages, ['Dashboard', 'Members', 'Attendance', 'Ministries', 'SMS', 'Reports'])
        self.assertFalse(caps['church_wide'])
        self.assertEqual(caps['scope_ids'], [str(self.ministries['Youth'].id)])
        self.assertIn('Finance', dict(navigation(self.services['Admin'].capabilities())))
        self.assertNotIn('Members', dict(navigation(self.services['Overseer'].capabilities())))

    def test_dashboard_shared_sunday_scope_and_completed_trend(self):
        session = self.sunday()
        self.services['Youth'].mark(session['id'], self.members['Ama'].id, 'PRESENT')
        self.assertEqual(self.services['Admin'].overview()['sunday']['eligible'], 4)
        self.assertEqual(self.services['Youth'].overview()['sunday']['eligible'], 2)
        self.assertEqual(self.services['Choir'].overview()['sunday']['count'], 1)
        meeting = self.youth(session_date=date.today())
        self.services['Youth'].mark(meeting['id'], self.members['Ama'].id, 'PRESENT')
        self.services['Youth'].transition(meeting['id'], 'close')
        overview = self.services['Youth'].overview()
        self.assertEqual(overview['rate'], 50.0)
        self.assertEqual(overview['trend'][0]['rate'], 50.0)
        self.assertEqual(overview['completed'], 1)

    def test_member_edit_retains_leadership_membership(self):
        service = MemberService(self.users['Admin'].id, self.factory)
        original = self.db.scalar(select(MemberMinistry).where(
            MemberMinistry.member_id == self.members['Ama'].id, MemberMinistry.ministry_id == self.ministries['Youth'].id))
        original_id = original.id
        profile = service.get_member(self.members['Ama'].id)
        profile['phone'] = '0200000000'
        service.update_member(self.members['Ama'].id, profile, [self.ministries['Youth'].id, self.ministries['Choir'].id])
        self.db.expire_all()
        row = self.db.get(MemberMinistry, original_id)
        self.assertEqual(row.position_title, 'Leader')
        self.assertTrue(row.is_active)
        session = self.youth(session_type='LEADERSHIP_MEETING')
        self.assertEqual(self.services['Youth'].roster(session['id'])['total'], 1)

if __name__ == "__main__":
    unittest.main()
