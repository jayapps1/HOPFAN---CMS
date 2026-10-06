"""Review the real additive Sunday School migration in a private transaction."""
import unittest
import uuid
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect,text
from src.config.database import engine
from src.security.sunday_school_permissions import PERMISSIONS,TEACHER_PERMISSIONS


class SundaySchoolMigrationTests(unittest.TestCase):
    def test_forward_upgrade_preserves_every_existing_table_and_role(self):
        schema='hcms_school_migration_'+uuid.uuid4().hex
        with engine.connect() as connection:
            transaction=connection.begin()
            try:
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                config=Config('alembic.ini');config.attributes['connection']=connection
                command.upgrade(config,'b62d08e4c715')
                member,user,household,link,ministry,position=[uuid.uuid4() for _ in range(6)]
                connection.execute(text("INSERT INTO members(id,member_no,first_name,last_name,status,baptized) VALUES (:id,'SCHOOL-PRESERVE','Preserved','Person','ACTIVE',false)"),dict(id=member))
                connection.execute(text("INSERT INTO users(id,username,password_hash,status,failed_login_attempts,totp_enabled,totp_secret) VALUES (:id,'school-preserve','unchanged-hash','SUSPENDED',3,true,'unchanged-encrypted-placeholder')"),dict(id=user))
                connection.execute(text("INSERT INTO user_roles(user_id,role_id) SELECT :id,id FROM roles WHERE code='ADMINISTRATOR'"),dict(id=user))
                connection.execute(text("INSERT INTO households(id,household_name,status) VALUES (:id,'Preserved household','ACTIVE')"),dict(id=household))
                connection.execute(text("INSERT INTO household_members(id,household_id,member_id,relationship,is_household_head,is_active) VALUES (:id,:household,:member,'HEAD',true,true)"),dict(id=link,household=household,member=member))
                connection.execute(text("INSERT INTO ministries(id,code,name,is_active) VALUES (:id,'SCHOOL-PRESERVE','Preserved ministry',true)"),dict(id=ministry))
                connection.execute(text("INSERT INTO ministry_positions(id,ministry_id,code,name,is_active,is_leadership,max_current_holders) VALUES (:id,:ministry,'LEADER','Preserved Leader',true,true,1)"),dict(id=position,ministry=ministry))
                quote=connection.dialect.identifier_preparer.quote;original={}
                for table in inspect(connection).get_table_names(schema=schema):
                    if table=='alembic_version':continue
                    sql='SELECT md5(row_to_json(t)::text) FROM (SELECT * FROM '+quote(table)+') t'
                    original[table]=(sql,set(connection.execute(text(sql)).scalars()))
                command.upgrade(config,'c84e26f7a930')
                for table,(sql,expected) in original.items():
                    actual=set(connection.execute(text(sql)).scalars())
                    if table in ('roles','permissions','role_permissions','security_audit_logs'):self.assertTrue(expected.issubset(actual),table)
                    else:self.assertEqual(expected,actual,table)
                tables=[table for table in inspect(connection).get_table_names(schema=schema) if table.startswith('sunday_school_')]
                self.assertEqual(len(tables),12)
                for table in tables:self.assertEqual(connection.scalar(text('SELECT count(*) FROM '+quote(table))),0)
                def grants(role):
                    return set(connection.execute(text('SELECT p.code FROM permissions p JOIN role_permissions rp ON p.id=rp.permission_id JOIN roles r ON r.id=rp.role_id WHERE r.code=:role'),dict(role=role)).scalars())
                self.assertTrue(set(PERMISSIONS).issubset(grants('ADMINISTRATOR')))
                self.assertEqual(grants('SUNDAY_SCHOOL_TEACHER'),TEACHER_PERMISSIONS)
                self.assertNotIn('SUNDAY_SCHOOL_VIEW_ALL',grants('SYSTEM_ADMIN'))
                self.assertNotIn('SUNDAY_SCHOOL_STUDENT_VIEW',grants('MINISTRY_ATTENDANCE_LEADER'))
                # Compare current metadata after any later additive migrations.
                command.upgrade(config,'head')
                command.check(config)
            finally:transaction.rollback()


if __name__=='__main__':unittest.main()
