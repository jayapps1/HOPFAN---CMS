from uuid import uuid4
from alembic import command
from alembic.config import Config
from sqlalchemy import text,inspect
from src.config.database import engine

def test_donation_migration_preserves_records_and_limits_finance_access():
    schema='hcms_donation_migration_'+uuid4().hex
    with engine.connect() as connection:
        transaction=connection.begin()
        try:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'));connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config=Config('alembic.ini');config.attributes['connection']=connection
            command.upgrade(config,'e3acdfa4cbf6')
            user=uuid4();connection.execute(text("INSERT INTO users(id,username,password_hash,status,failed_login_attempts,totp_enabled,auth_revision) VALUES (:id,'preserved-donation-user','unchanged-hash','ACTIVE',0,false,9)"),{'id':user})
            before=connection.execute(text('SELECT password_hash,status,auth_revision FROM users WHERE id=:id'),{'id':user}).one()
            command.upgrade(config,'head')
            assert connection.execute(text('SELECT password_hash,status,auth_revision FROM users WHERE id=:id'),{'id':user}).one()==before
            assert {'donations','donation_categories'}<=set(inspect(connection).get_table_names(schema=schema))
            assert connection.scalar(text('SELECT count(*) FROM donations'))==0
            assert connection.scalar(text('SELECT count(*) FROM donation_categories'))==7
            grants=set(connection.execute(text("SELECT r.code FROM roles r JOIN role_permissions rp ON rp.role_id=r.id JOIN permissions p ON p.id=rp.permission_id WHERE p.code='DONATIONS_VIEW'")).scalars())
            assert grants=={'ADMINISTRATOR','FINANCE_OFFICER'}
            command.check(config)
        finally:transaction.rollback()
