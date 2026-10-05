"""Forward migration preserves original columns and legacy grants verbatim."""
import unittest
import uuid
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect,text
from src.config.database import engine


class AdministrationMigrationTests(unittest.TestCase):
    def test_original_records_preserved_and_new_roles_conservative(self):
        schema='hcms_administration_migration_'+uuid.uuid4().hex
        with engine.connect() as connection:
            transaction=connection.begin()
            try:
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                config=Config('alembic.ini');config.attributes['connection']=connection
                command.upgrade(config,'e8b4026d9f10')
                ministry,member,user,scope,role=[uuid.uuid4() for _ in range(5)]
                connection.execute(text("INSERT INTO ministries(id,code,name,is_active) VALUES (:id,'PRESERVE','Preserve ministry',true)"),dict(id=ministry))
                connection.execute(text("INSERT INTO members(id,member_no,first_name,last_name,baptized,status) VALUES (:id,'ADMIN-MIGRATION','Preserve','Member',false,'ACTIVE')"),dict(id=member))
                connection.execute(text("INSERT INTO users(id,username,email,member_id,password_hash,status,failed_login_attempts,totp_enabled,totp_secret) VALUES (:id,'preserve-user','preserve@example.invalid',:member,'existing-argon2-placeholder','SUSPENDED',3,true,'existing-encrypted-placeholder')"),dict(id=user,member=member))
                connection.execute(text("INSERT INTO roles(id,code,name,is_system,is_active) VALUES (:id,'ADMINISTRATOR','Existing administrator',true,true)"),dict(id=role))
                connection.execute(text('INSERT INTO user_roles(user_id,role_id) VALUES (:user,:role)'),dict(user=user,role=role))
                connection.execute(text('''INSERT INTO user_ministry_scopes(id,user_id,ministry_id,is_active,can_view_attendance,can_create_attendance,can_record_attendance,can_correct_attendance,can_close_attendance,can_view_reports)
                    VALUES (:id,:user,:ministry,true,true,false,false,false,false,false)'''),dict(id=scope,user=user,ministry=ministry))
                quote=connection.dialect.identifier_preparer.quote
                inspector=inspect(connection)
                original={}
                for table in inspector.get_table_names(schema=schema):
                    if table=='alembic_version': continue
                    columns=[c['name'] for c in inspector.get_columns(table,schema=schema)]
                    sql='SELECT md5(row_to_json(t)::text) FROM (SELECT '+','.join(quote(c) for c in columns)+' FROM '+quote(table)+') t'
                    original[table]=(sql,set(connection.execute(text(sql)).scalars()))
                command.upgrade(config,'a91c73d5f204')
                for table,(sql,hashes) in original.items():
                    actual=set(connection.execute(text(sql)).scalars())
                    if table in ('roles','permissions','role_permissions'): self.assertTrue(hashes.issubset(actual),table)
                    else: self.assertEqual(hashes,actual,table)
                self.assertTrue(connection.scalar(text('SELECT legacy_attendance_limits FROM user_ministry_scopes WHERE id=:id'),dict(id=scope)))
                self.assertFalse(connection.scalar(text('SELECT require_password_change FROM users WHERE id=:id'),dict(id=user)))
                grants=set(connection.execute(text("SELECT p.code FROM permissions p JOIN role_permissions rp ON rp.permission_id=p.id JOIN roles r ON r.id=rp.role_id WHERE r.code='SYSTEM_ADMIN'")).scalars())
                self.assertTrue({'USER_CREATE','ROLE_EDIT','USER_SCOPE_MANAGE'}.issubset(grants))
                self.assertFalse(grants.intersection({'MEMBERS_VIEW_ALL','ATTENDANCE_VIEW_ALL','FINANCE_VIEW','WELFARE_VIEW'}))
                self.assertEqual(connection.scalar(text("SELECT count(*) FROM roles WHERE code='MINISTRY_LEADER'")),0)
                self.assertEqual(connection.scalar(text("SELECT count(*) FROM roles WHERE code='REPORT_VIEWER'")),0)
                self.assertEqual(connection.scalar(text('SELECT version_num FROM alembic_version')),'a91c73d5f204')
                command.check(config)
            finally:
                transaction.rollback()


if __name__=='__main__': unittest.main()
