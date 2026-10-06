"""Run the real forward migration without touching the public schema."""
import unittest
import uuid
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from src.config.database import engine
from src.security.household_permissions import PERMISSIONS


class HouseholdMigrationTests(unittest.TestCase):
    def test_forward_upgrade_preserves_master_records_and_existing_access(self):
        schema = 'hcms_household_migration_'+uuid.uuid4().hex
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                config = Config('alembic.ini'); config.attributes['connection'] = connection
                command.upgrade(config, 'a91c73d5f204')
                ministry, member, user, position = [uuid.uuid4() for _ in range(4)]
                connection.execute(text("INSERT INTO ministries(id,code,name,is_active) VALUES (:id,'FAMILY-PRESERVE','Preserved ministry',true)"), dict(id=ministry))
                connection.execute(text("INSERT INTO members(id,member_no,first_name,last_name,baptized,status) VALUES (:id,'FAMILY-PRESERVE','Preserved','Member',false,'ACTIVE')"), dict(id=member))
                connection.execute(text("INSERT INTO users(id,username,password_hash,status,failed_login_attempts,totp_enabled,totp_secret) VALUES (:id,'household-preserve','unchanged-hash','SUSPENDED',2,true,'unchanged-encrypted-secret')"), dict(id=user))
                connection.execute(text("INSERT INTO user_roles(user_id,role_id) SELECT :user,id FROM roles WHERE code='ADMINISTRATOR'"), dict(user=user))
                connection.execute(text("INSERT INTO ministry_positions(id,ministry_id,code,name,is_leadership,is_active,max_current_holders) VALUES (:id,:ministry,'LEADER','Preserved Leader',true,true,1)"), dict(id=position, ministry=ministry))
                quote = connection.dialect.identifier_preparer.quote
                original = {}
                for table in inspect(connection).get_table_names(schema=schema):
                    if table=='alembic_version': continue
                    sql = 'SELECT md5(row_to_json(t)::text) FROM (SELECT * FROM '+quote(table)+') t'
                    original[table] = (sql, sorted(connection.execute(text(sql)).scalars()))
                command.upgrade(config, 'b62d08e4c715')
                for table,(sql,expected) in original.items():
                    actual = sorted(connection.execute(text(sql)).scalars())
                    if table in {'permissions','role_permissions','security_audit_logs'}:
                        self.assertTrue(set(expected).issubset(actual), table)
                    else: self.assertEqual(expected, actual, table)
                for table in ('households','household_members','household_audit_logs'):
                    self.assertEqual(connection.scalar(text('SELECT count(*) FROM '+quote(table))), 0)
                def grants(code):
                    return set(connection.execute(text("SELECT p.code FROM permissions p JOIN role_permissions rp ON rp.permission_id=p.id JOIN roles r ON r.id=rp.role_id WHERE r.code=:code"), dict(code=code)).scalars())
                self.assertTrue(set(PERMISSIONS).issubset(grants('ADMINISTRATOR')))
                self.assertFalse(set(PERMISSIONS).intersection(grants('SYSTEM_ADMIN')))
                self.assertFalse(set(PERMISSIONS).intersection(grants('MINISTRY_ATTENDANCE_LEADER')))
                fks = inspect(connection).get_foreign_keys('household_members', schema=schema)
                self.assertTrue(all(fk['options']['ondelete']=='RESTRICT' for fk in fks))
                command.upgrade(config,'head')
                command.check(config)
            finally: transaction.rollback()


if __name__=='__main__': unittest.main()
