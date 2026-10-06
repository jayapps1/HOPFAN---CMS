"""Forward-only normalized households; preserve existing church records."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import json
import uuid

revision = 'b62d08e4c715'
down_revision = 'a91c73d5f204'
branch_labels = None
depends_on = None

DEFINITIONS = {
    'HOUSEHOLD_VIEW': 'View the household linked to your own member record',
    'HOUSEHOLD_VIEW_ALL': 'View all household and family records',
    'HOUSEHOLD_CREATE': 'Create households',
    'HOUSEHOLD_EDIT': 'Edit households, relationships and household heads',
    'HOUSEHOLD_ADD_MEMBER': 'Add existing members to households',
    'HOUSEHOLD_REMOVE_MEMBER': 'End household memberships',
    'HOUSEHOLD_ARCHIVE': 'Archive and restore households',
    'HOUSEHOLD_DELETE_UNUSED': 'Permanently delete households without membership history',
}


def upgrade():
    uid = postgresql.UUID(as_uuid=True)
    op.create_table('households',
        sa.Column('id', uid, primary_key=True),
        sa.Column('household_name', sa.String(200), nullable=False),
        sa.Column('household_code', sa.String(40), unique=True),
        sa.Column('primary_address', sa.Text), sa.Column('primary_phone', sa.String(30)), sa.Column('notes', sa.Text),
        sa.Column('status', sa.String(16), nullable=False, server_default='ACTIVE'),
        sa.Column('created_by_user_id', uid, sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('updated_by_user_id', uid, sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('archived_at', sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('ACTIVE','INACTIVE','ARCHIVED')", name='ck_household_status'),
        sa.CheckConstraint("(status='ARCHIVED') = (archived_at IS NOT NULL)", name='ck_household_archive'))
    for column in ('household_name', 'status'):
        op.create_index('ix_households_'+column, 'households', [column])
    op.create_table('household_members',
        sa.Column('id', uid, primary_key=True),
        sa.Column('household_id', uid, sa.ForeignKey('households.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('member_id', uid, sa.ForeignKey('members.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('relationship', sa.String(20), nullable=False),
        sa.Column('is_household_head', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('joined_at', sa.Date), sa.Column('left_at', sa.Date),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'), sa.Column('notes', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("relationship IN ('HEAD','SPOUSE','SON','DAUGHTER','CHILD','FATHER','MOTHER','BROTHER','SISTER','DEPENDANT','GUARDIAN','RELATIVE','OTHER')", name='ck_household_relationship'),
        sa.CheckConstraint("is_household_head = (relationship='HEAD')", name='ck_household_head_relationship'),
        sa.CheckConstraint('left_at IS NULL OR joined_at IS NULL OR left_at >= joined_at', name='ck_household_member_dates'),
        sa.CheckConstraint('(is_active AND left_at IS NULL) OR (NOT is_active AND left_at IS NOT NULL)', name='ck_household_member_current'))
    for column in ('household_id', 'member_id', 'is_active'):
        op.create_index('ix_household_members_'+column, 'household_members', [column])
    op.create_index('uq_household_member_current', 'household_members', ['member_id'], unique=True, postgresql_where=sa.text('is_active IS true'))
    op.create_index('uq_household_current_head', 'household_members', ['household_id'], unique=True, postgresql_where=sa.text('is_active IS true AND is_household_head IS true'))
    op.create_table('household_audit_logs',
        sa.Column('id', uid, primary_key=True), sa.Column('household_id', uid, nullable=False),
        sa.Column('member_id', uid), sa.Column('membership_id', uid),
        sa.Column('actor_user_id', uid, sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('action', sa.String(40), nullable=False),
        sa.Column('old_values', postgresql.JSONB), sa.Column('new_values', postgresql.JSONB),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    for column in ('household_id', 'member_id', 'action', 'occurred_at'):
        op.create_index('ix_household_audit_logs_'+column, 'household_audit_logs', [column])
    bind = op.get_bind()
    for code, name in DEFINITIONS.items():
        bind.execute(sa.text("INSERT INTO permissions(id,code,name,module,is_active) VALUES (:id,:code,:name,'Households',true) ON CONFLICT(code) DO NOTHING"), dict(id=uuid.uuid4(), code=code, name=name))
        bind.execute(sa.text("INSERT INTO role_permissions(role_id,permission_id) SELECT r.id,p.id FROM roles r CROSS JOIN permissions p WHERE r.code='ADMINISTRATOR' AND p.code=:code ON CONFLICT DO NOTHING"), dict(code=code))
    for user_id in bind.execute(sa.text("SELECT ur.user_id FROM user_roles ur JOIN roles r ON r.id=ur.role_id WHERE r.code='ADMINISTRATOR'")).scalars():
        bind.execute(sa.text("INSERT INTO security_audit_logs(id,target_user_id,action,new_values) VALUES (:id,:user,'MIGRATION_HOUSEHOLD_GRANTS',:values)"), dict(id=uuid.uuid4(), user=user_id, values=json.dumps({'permissions': sorted(DEFINITIONS)})))


def downgrade():
    raise RuntimeError('Forward-only household migration; restore a verified pre-upgrade backup if required.')
