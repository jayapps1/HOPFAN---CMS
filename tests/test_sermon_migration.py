from uuid import uuid4
from alembic import command
from alembic.config import Config
from sqlalchemy import text,inspect
from src.config.database import engine

def test_sermon_migration_preserves_content_and_credentials_and_grants_explicit_roles():
    schema='hcms_sermon_migration_'+uuid4().hex
    with engine.connect() as connection:
        transaction=connection.begin()
        try:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'));connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config=Config('alembic.ini');config.attributes['connection']=connection
            command.upgrade(config,'ab61d4f83c02')
            uid=uuid4();cid=uuid4()
            connection.execute(text("INSERT INTO users(id,username,password_hash,status,failed_login_attempts,totp_enabled,auth_revision) VALUES (:id,'preserved-sermon-user','original-hash','ACTIVE',0,false,11)"),{'id':uid})
            connection.execute(text("INSERT INTO website_content(id,kind,slug,title,status,draft_data,published_data) VALUES (:id,'SERMON','preserved-message','Original message','PUBLISHED',cast(:snapshot AS jsonb),cast(:snapshot AS jsonb))"),{'id':cid,'snapshot':'{"kind":"SERMON","slug":"preserved-message","title":"Original message","summary":"Original summary","body":"Original description","data":{"speaker":"Original speaker","sermon_date":"2026-10-01","youtube_url":"https://youtu.be/dQw4w9WgXcQ"}}'})
            before=connection.execute(text('SELECT draft_data,published_data,status,slug FROM website_content WHERE id=:id'),{'id':cid}).one()
            command.upgrade(config,'head')
            assert connection.execute(text('SELECT draft_data,published_data,status,slug FROM website_content WHERE id=:id'),{'id':cid}).one()==before
            assert connection.execute(text('SELECT password_hash,auth_revision FROM users WHERE id=:id'),{'id':uid}).one()==('original-hash',11)
            assert {'sermon_media_assets','sermon_series','sermon_categories','sermon_metrics','sermon_playback_receipts'}<=set(inspect(connection).get_table_names(schema=schema))
            assert connection.scalar(text("SELECT count(*) FROM sermon_media_assets"))==0
            technical=set(connection.execute(text("SELECT p.code FROM roles r JOIN role_permissions rp ON rp.role_id=r.id JOIN permissions p ON p.id=rp.permission_id WHERE r.code='SYSTEM_ADMIN'")).scalars())
            assert 'SERMON_PUBLISH' not in technical
            command.check(config)
        finally:transaction.rollback()
