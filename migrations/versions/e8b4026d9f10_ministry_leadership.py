"""Add configurable ministry positions and immutable appointment history.

Revision ID: e8b4026d9f10
Revises: d7f9215c8a30
"""
import json
import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'e8b4026d9f10'
down_revision = 'd7f9215c8a30'
branch_labels = depends_on = None


def actor_columns():
    return [sa.Column(name, postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'))
            for name in ('created_by_user_id', 'updated_by_user_id')]


def timestamps():
    return [sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
            for name in ('created_at', 'updated_at')]


def upgrade():
    op.create_table('ministry_positions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('ministry_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ministries.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('code', sa.String(60), nullable=False), sa.Column('name', sa.String(150), nullable=False),
        sa.Column('description', sa.Text), sa.Column('sort_order', sa.Integer, nullable=False, server_default='0'),
        sa.Column('is_leadership', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('max_current_holders', sa.Integer), *actor_columns(), *timestamps(),
        sa.UniqueConstraint('id', 'ministry_id', name='uq_position_ministry'),
        sa.CheckConstraint('sort_order >= 0', name='ck_position_sort_order'),
        sa.CheckConstraint('max_current_holders IS NULL OR max_current_holders > 0', name='ck_position_holders'))
    op.create_index('ix_ministry_positions_ministry_id', 'ministry_positions', ['ministry_id'])
    op.create_index('uq_position_code_case', 'ministry_positions', ['ministry_id', sa.text('upper(code)')], unique=True)
    op.create_index('uq_position_name_case', 'ministry_positions', ['ministry_id', sa.text('lower(name)')], unique=True)
    op.create_table('ministry_leadership_assignments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('ministry_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ministries.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('member_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('members.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('position_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('position_name', sa.String(150), nullable=False), sa.Column('position_code', sa.String(60), nullable=False),
        sa.Column('start_date', sa.Date, nullable=False), sa.Column('end_date', sa.Date),
        sa.Column('is_current', sa.Boolean, nullable=False), sa.Column('notes', sa.Text),
        *actor_columns(), *timestamps(),
        sa.ForeignKeyConstraint(['position_id', 'ministry_id'], ['ministry_positions.id', 'ministry_positions.ministry_id'],
                                ondelete='RESTRICT', name='fk_assignment_position_ministry'),
        sa.CheckConstraint('end_date IS NULL OR end_date >= start_date', name='ck_assignment_dates'),
        sa.CheckConstraint('(is_current AND end_date IS NULL) OR (NOT is_current AND end_date IS NOT NULL)', name='ck_assignment_current_dates'))
    for column in ('ministry_id', 'member_id', 'position_id', 'is_current', 'start_date'):
        op.create_index('ix_ministry_leadership_assignments_'+column, 'ministry_leadership_assignments', [column])
    op.create_index('uq_assignment_current_member_position', 'ministry_leadership_assignments', ['position_id', 'member_id'],
                    unique=True, postgresql_where=sa.text('is_current IS true'))
    op.create_table('ministry_leadership_audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('ministry_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ministries.id', ondelete='RESTRICT'), nullable=False),
        *[sa.Column(name, postgresql.UUID(as_uuid=True)) for name in ('position_id', 'assignment_id', 'member_id')],
        sa.Column('actor_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('action', sa.String(40), nullable=False), sa.Column('old_values', postgresql.JSONB), sa.Column('new_values', postgresql.JSONB),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    for column in ('ministry_id', 'occurred_at'):
        op.create_index('ix_ministry_leadership_audit_logs_'+column, 'ministry_leadership_audit_logs', [column])
    definitions = {
        'MINISTRY_POSITION_VIEW':'View ministry positions', 'MINISTRY_POSITION_CREATE':'Create ministry positions',
        'MINISTRY_POSITION_EDIT':'Edit ministry positions', 'MINISTRY_POSITION_ARCHIVE':'Deactivate ministry positions',
        'MINISTRY_POSITION_DELETE_UNUSED':'Delete unused ministry positions', 'MINISTRY_LEADERSHIP_VIEW':'View assigned ministry leadership',
        'MINISTRY_LEADERSHIP_VIEW_ALL':'View all ministry leadership', 'MINISTRY_LEADERSHIP_ASSIGN':'Appoint ministry officers',
        'MINISTRY_LEADERSHIP_EDIT':'Correct ministry appointments', 'MINISTRY_LEADERSHIP_END':'End or replace ministry appointments'}
    bind = op.get_bind()
    for code, name in definitions.items():
        bind.execute(sa.text("INSERT INTO permissions(id,code,name,module,is_active) VALUES (:id,:code,:name,'Ministries',true) ON CONFLICT(code) DO NOTHING"),
                     dict(id=uuid.uuid4(),code=code,name=name))
        bind.execute(sa.text("INSERT INTO role_permissions(role_id,permission_id) SELECT r.id,p.id FROM roles r CROSS JOIN permissions p WHERE r.code='ADMINISTRATOR' AND p.code=:code ON CONFLICT DO NOTHING"), dict(code=code))
    for code in ('MINISTRY_POSITION_VIEW', 'MINISTRY_LEADERSHIP_VIEW'):
        bind.execute(sa.text("INSERT INTO role_permissions(role_id,permission_id) SELECT r.id,p.id FROM roles r CROSS JOIN permissions p WHERE r.code='MINISTRY_ATTENDANCE_LEADER' AND p.code=:code ON CONFLICT DO NOTHING"), dict(code=code))
    for user in bind.execute(sa.text("SELECT ur.user_id,r.code FROM user_roles ur JOIN roles r ON r.id=ur.role_id WHERE r.code IN ('ADMINISTRATOR','MINISTRY_ATTENDANCE_LEADER')")):
        codes = list(definitions) if user.code=='ADMINISTRATOR' else ['MINISTRY_POSITION_VIEW','MINISTRY_LEADERSHIP_VIEW']
        bind.execute(sa.text("INSERT INTO authorization_audit_logs(id,target_user_id,action_type,new_values) VALUES (:id,:uid,'MIGRATION_LEADERSHIP_GRANTS',:payload)"),
                     dict(id=uuid.uuid4(),uid=user.user_id,payload=json.dumps({'permissions':codes})))
    # Existing free-text MemberMinistry.position_title is retained verbatim; no inferred appointments or security grants.


def downgrade():
    raise RuntimeError('Forward-only leadership migration; recover the preceding schema from a verified backup.')
