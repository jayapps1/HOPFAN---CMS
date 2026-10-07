from uuid import uuid4
from alembic import command
from alembic.config import Config
from sqlalchemy import text,inspect
from src.config.database import engine

def test_content_migration_is_additive_and_does_not_grant_pastoral_access_to_admin():
    schema='hcms_content_migration_'+uuid4().hex
    with engine.connect() as connection:
        transaction=connection.begin()
        try:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'));connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config=Config('alembic.ini');config.attributes['connection']=connection
            command.upgrade(config,'d95f13b8e204')
            user=uuid4();connection.execute(text("INSERT INTO users(id,username,password_hash,status,failed_login_attempts,totp_enabled,auth_revision) VALUES (:id,'preserved-user','unchanged-test-hash','ACTIVE',0,false,7)"),{'id':user})
            before=connection.execute(text('SELECT password_hash,status,auth_revision FROM users WHERE id=:id'),{'id':user}).one()
            command.upgrade(config,'e3acdfa4cbf6')
            assert connection.execute(text('SELECT password_hash,status,auth_revision FROM users WHERE id=:id'),{'id':user}).one()==before
            assert {'website_content','website_media','public_inquiries','church_events','church_announcements'}<=set(inspect(connection).get_table_names(schema=schema))
            admin=set(connection.execute(text("SELECT p.code FROM role_permissions rp JOIN roles r ON r.id=rp.role_id JOIN permissions p ON p.id=rp.permission_id WHERE r.code='ADMINISTRATOR'")).scalars())
            assert 'WEBSITE_PAGE_PUBLISH' in admin and 'PRAYER_REQUEST_VIEW' not in admin
        finally:transaction.rollback()
