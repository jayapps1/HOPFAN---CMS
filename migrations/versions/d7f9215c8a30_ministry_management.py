"""Add ministry management without rewriting church records.

Revision ID: d7f9215c8a30
Revises: c603420e8020
"""
import uuid
import json
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'd7f9215c8a30'
down_revision = 'c603420e8020'
branch_labels = depends_on = None


def upgrade():
    # Retain is_active: all current assignment/attendance selectors already use it.
    # archived_at distinguishes archived from inactive; existing rows stay unarchived.
    op.add_column('ministries', sa.Column('category', sa.String(20), nullable=False, server_default='MINISTRY'))
    for column in ('created_by_user_id','updated_by_user_id','archived_by_user_id'):
        op.add_column('ministries', sa.Column(column, postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(f'fk_ministry_{column}', 'ministries', 'users', [column], ['id'], ondelete='SET NULL')
    op.add_column('ministries', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint('ck_ministry_category','ministries',"category IN ('MINISTRY','FELLOWSHIP','DEPARTMENT','UNIT','OTHER')")
    op.create_check_constraint('ck_ministry_archive_inactive','ministries','archived_at IS NULL OR NOT is_active')
    op.create_index('ix_ministries_category','ministries',['category'])
    op.create_index('ix_ministries_archived_at','ministries',['archived_at'])
    # Fail atomically on legacy case duplicates instead of renaming or dropping rows.
    op.create_index('uq_ministry_code_case','ministries',[sa.text('upper(code)')],unique=True)
    op.create_index('uq_ministry_name_case','ministries',[sa.text('lower(name)')],unique=True)
    inspector = sa.inspect(op.get_bind())
    for table in ('member_ministries','user_ministry_scopes','attendance_sessions'):
        for fk in inspector.get_foreign_keys(table):
            if fk['referred_table']=='ministries':
                op.drop_constraint(fk['name'],table,type_='foreignkey')
                op.create_foreign_key(fk['name'],table,'ministries',fk['constrained_columns'],fk['referred_columns'],ondelete='RESTRICT')
    op.create_table('ministry_audit_logs',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),
        # Deliberately retain the UUID snapshot after a permitted unused-row deletion.
        sa.Column('ministry_id',postgresql.UUID(as_uuid=True),nullable=False),
        sa.Column('actor_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='SET NULL')),
        sa.Column('action',sa.String(40),nullable=False),
        sa.Column('old_values',postgresql.JSONB),sa.Column('new_values',postgresql.JSONB),
        sa.Column('occurred_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index('ix_ministry_audit_logs_ministry_id','ministry_audit_logs',['ministry_id'])
    op.create_index('ix_ministry_audit_logs_occurred_at','ministry_audit_logs',['occurred_at'])
    definitions = {
        'MINISTRIES_CREATE':'Create church ministries','MINISTRIES_EDIT':'Edit and activate church ministries',
        'MINISTRIES_DEACTIVATE':'Deactivate church ministries','MINISTRIES_ARCHIVE':'Archive church ministries',
        'MINISTRIES_RESTORE':'Restore archived church ministries','MINISTRIES_DELETE_UNUSED':'Permanently delete unused ministries'}
    bind = op.get_bind()
    for code,name in definitions.items():
        bind.execute(sa.text("INSERT INTO permissions (id,code,name,module,is_active) VALUES (:id,:code,:name,'Ministries',true) ON CONFLICT (code) DO NOTHING"),dict(id=uuid.uuid4(),code=code,name=name))
        bind.execute(sa.text("INSERT INTO role_permissions (role_id,permission_id) SELECT r.id,p.id FROM roles r CROSS JOIN permissions p WHERE r.code='ADMINISTRATOR' AND p.code=:code ON CONFLICT DO NOTHING"),dict(code=code))
    for actor in bind.execute(sa.text("SELECT ur.user_id FROM user_roles ur JOIN roles r ON r.id=ur.role_id WHERE r.code='ADMINISTRATOR'")).scalars():
        bind.execute(sa.text("INSERT INTO authorization_audit_logs (id,target_user_id,action_type,new_values) VALUES (:id,:actor,'MIGRATION_MINISTRY_GRANTS',:details)"),dict(id=uuid.uuid4(),actor=actor,details=json.dumps({'permissions':list(definitions)})))


def downgrade():
    raise RuntimeError('Forward-only ministry upgrade; restore a verified backup to recover the previous schema.')
