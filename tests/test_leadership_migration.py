"""Real forward migration in a private transaction; no church records rewritten."""
import unittest
import uuid
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from src.config.database import engine


class LeadershipMigrationTests(unittest.TestCase):
    def test_forward_upgrade_preserves_records_and_separates_security(self):
        schema = 'hcms_leadership_migration_'+uuid.uuid4().hex
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                config = Config('alembic.ini')
                config.attributes['connection'] = connection
                command.upgrade(config, 'd7f9215c8a30')
                ministry, member, membership, user, admin, leader = [uuid.uuid4() for _ in range(6)]
                connection.execute(text("INSERT INTO ministries(id,code,name,is_active) VALUES (:id,'LEGACY','Legacy ministry',true)"),dict(id=ministry))
                connection.execute(text("INSERT INTO members(id,member_no,first_name,last_name,baptized,status) VALUES (:id,'MIGRATION-L','Migration','Member',false,'ACTIVE')"),dict(id=member))
                connection.execute(text("INSERT INTO member_ministries(id,member_id,ministry_id,is_active,is_primary,position_title) VALUES (:id,:member,:ministry,true,true,'Existing legacy office')"),dict(id=membership,member=member,ministry=ministry))
                connection.execute(text("INSERT INTO users(id,username,password_hash,status,failed_login_attempts) VALUES (:id,'migration-leadership','unused','ACTIVE',0)"),dict(id=user))
                connection.execute(text("INSERT INTO roles(id,code,name,is_system,is_active) VALUES (:admin,'ADMINISTRATOR','Admin',true,true),(:leader,'MINISTRY_ATTENDANCE_LEADER','Officer',true,true) ON CONFLICT(code) DO NOTHING"),dict(admin=admin,leader=leader))
                leader = connection.execute(text("SELECT id FROM roles WHERE code='MINISTRY_ATTENDANCE_LEADER'")).scalar_one()
                connection.execute(text('INSERT INTO user_roles(user_id,role_id) VALUES (:user,:admin)'),dict(user=user,admin=admin))
                protected = ('ministries','members','member_ministries','users','user_roles','attendance_sessions','attendance_records','attendance_roster_members','attendance_audit_logs','user_ministry_scopes')
                fingerprints = {table:sorted(connection.execute(text(f'SELECT md5(row_to_json(t)::text) FROM (SELECT * FROM {table}) t')).scalars()) for table in protected}
                command.upgrade(config, 'e8b4026d9f10')
                for table, hashes in fingerprints.items():
                    self.assertEqual(hashes,sorted(connection.execute(text(f'SELECT md5(row_to_json(t)::text) FROM (SELECT * FROM {table}) t')).scalars()))
                for table in ('ministry_positions','ministry_leadership_assignments','ministry_leadership_audit_logs'):
                    self.assertEqual(connection.execute(text(f'SELECT count(*) FROM {table}')).scalar_one(),0)
                def grants(role):
                    return connection.execute(text("SELECT p.code FROM permissions p JOIN role_permissions rp ON p.id=rp.permission_id WHERE rp.role_id=:role AND p.code LIKE 'MINISTRY_%'"),dict(role=role)).scalars().all()
                self.assertEqual(len(grants(admin)),10)
                self.assertCountEqual(grants(leader), ['MINISTRY_POSITION_VIEW','MINISTRY_LEADERSHIP_VIEW'])
                fks = inspect(connection).get_foreign_keys('ministry_leadership_assignments',schema=schema)
                self.assertTrue(all(fk['options']['ondelete']=='RESTRICT' for fk in fks if fk['referred_table']!='users'))
                self.assertEqual(connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one(),'e8b4026d9f10')
            finally:
                transaction.rollback()


if __name__ == '__main__': unittest.main()
