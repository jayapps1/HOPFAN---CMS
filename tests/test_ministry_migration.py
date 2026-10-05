"""Exercise the actual forward migration and legacy rows in a private schema."""
import re
import unittest
import uuid
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from src.config.database import engine


class MinistryMigrationTests(unittest.TestCase):
    def test_forward_upgrade_preserves_existing_records_and_grants(self):
        schema='hcms_ministry_migration_'+uuid.uuid4().hex
        assert re.fullmatch(r'hcms_ministry_migration_[a-f0-9]{32}',schema)
        with engine.connect() as connection:
            transaction=connection.begin()
            try:
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                config=Config('alembic.ini')
                config.attributes['connection']=connection
                command.upgrade(config,'c603420e8020')
                active,inactive,member,membership,role,user=[uuid.uuid4() for _ in range(6)]
                connection.execute(text("INSERT INTO ministries(id,code,name,is_active) VALUES (:active,'ACTIVE_LEGACY','Legacy Active',true),(:inactive,'INACTIVE_LEGACY','Legacy Inactive',false)"),dict(active=active,inactive=inactive))
                connection.execute(text("INSERT INTO members(id,member_no,first_name,last_name,baptized,status) VALUES (:member,'MIGRATION-TEST','Migration','Test',false,'ACTIVE')"),dict(member=member))
                connection.execute(text("INSERT INTO member_ministries(id,member_id,ministry_id,is_primary,is_active) VALUES (:membership,:member,:active,true,true)"),dict(membership=membership,member=member,active=active))
                connection.execute(text("INSERT INTO roles(id,code,name,is_system,is_active) VALUES (:role,'ADMINISTRATOR','Migration Test Admin',true,true)"),dict(role=role))
                connection.execute(text("INSERT INTO users(id,username,password_hash,status,failed_login_attempts) VALUES (:user,'migration-test','unused','ACTIVE',0)"),dict(user=user))
                connection.execute(text('INSERT INTO user_roles(user_id,role_id) VALUES (:user,:role)'),dict(user=user,role=role))
                fingerprints={table:connection.execute(text(f'SELECT id::text,md5(row_to_json(t)::text) FROM (SELECT * FROM {table} ORDER BY id) t')).all() for table in ('members','member_ministries','users')}
                original=connection.execute(text('SELECT id,code,name,is_active,created_at,updated_at FROM ministries ORDER BY id')).all()
                command.upgrade(config,'d7f9215c8a30')
                self.assertEqual(original,connection.execute(text('SELECT id,code,name,is_active,created_at,updated_at FROM ministries ORDER BY id')).all())
                for table,rows in fingerprints.items():
                    self.assertEqual(rows,connection.execute(text(f'SELECT id::text,md5(row_to_json(t)::text) FROM (SELECT * FROM {table} ORDER BY id) t')).all())
                rows=connection.execute(text('SELECT id,is_active,archived_at,category FROM ministries')).all()
                self.assertEqual(len(rows),2)
                self.assertTrue(all(row.archived_at is None and row.category=='MINISTRY' for row in rows))
                grants=connection.execute(text("SELECT p.code FROM permissions p JOIN role_permissions rp ON rp.permission_id=p.id WHERE rp.role_id=:role"),dict(role=role)).scalars().all()
                self.assertIn('MINISTRIES_DELETE_UNUSED',grants)
                self.assertEqual(len([item for item in grants if item.startswith('MINISTRIES_')]),6)
                for table in ('member_ministries','user_ministry_scopes','attendance_sessions'):
                    fks=inspect(connection).get_foreign_keys(table,schema=schema)
                    self.assertEqual(next(fk['options'].get('ondelete') for fk in fks if fk['referred_table']=='ministries'),'RESTRICT')
                self.assertEqual(connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one(),'d7f9215c8a30')
            finally:
                transaction.rollback()


if __name__=='__main__':
    unittest.main()
