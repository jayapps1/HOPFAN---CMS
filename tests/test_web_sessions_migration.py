"""The additive web-security migration preserves every existing table."""
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from src.config.database import engine


def test_web_security_migration_preserves_existing_identity_and_business_data():
    schema = "hcms_web_migration_" + uuid4().hex
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config = Config("alembic.ini"); config.attributes["connection"] = connection
            command.upgrade(config, "c84e26f7a930")
            member, user = uuid4(), uuid4()
            connection.execute(text("INSERT INTO members(id,member_no,first_name,last_name,status,baptized) VALUES (:id,'WEB-PRESERVE','Synthetic','Preserved','ACTIVE',false)"), {"id": member})
            connection.execute(text("INSERT INTO users(id,username,password_hash,status,failed_login_attempts,totp_enabled,totp_secret) VALUES (:id,'web-preserve','unchanged-synthetic-hash','SUSPENDED',3,true,'unchanged-synthetic-encrypted-secret')"), {"id": user})
            quote = connection.dialect.identifier_preparer.quote
            before = {}
            for table in inspect(connection).get_table_names(schema=schema):
                if table != "alembic_version":
                    query = "SELECT md5(row_to_json(t)::text) FROM (SELECT * FROM " + quote(table) + ") t"
                    before[table] = (query, set(connection.execute(text(query)).scalars()))
            command.upgrade(config, "d95f13b8e204")
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "d95f13b8e204"
            for table, (query, rows) in before.items():
                assert set(connection.execute(text(query)).scalars()) == rows, table
            for table in ["web_sessions", "web_rate_limits"]:
                assert connection.scalar(text("SELECT count(*) FROM " + quote(table))) == 0
            assert {index["name"] for index in inspect(connection).get_indexes("web_sessions", schema=schema)} >= {
                "ix_web_sessions_expires_at", "ix_web_sessions_user_id", "ix_web_sessions_revoked_at"
            }
            command.downgrade(config, "c84e26f7a930")
            for table, (query, rows) in before.items():
                assert set(connection.execute(text(query)).scalars()) == rows, table
            assert "web_sessions" not in inspect(connection).get_table_names(schema=schema)
        finally:
            transaction.rollback()
