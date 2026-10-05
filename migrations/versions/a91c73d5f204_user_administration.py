"""Forward-only user administration preserving all existing RBAC/auth data."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid
import json

revision='a91c73d5f204'
down_revision='e8b4026d9f10'
branch_labels=None
depends_on=None

NEW_PERMISSIONS={
    'USER_VIEW':'View system user accounts','USER_CREATE':'Create system user accounts',
    'USER_EDIT':'Edit account profiles and activate accounts','USER_DEACTIVATE':'Deactivate or suspend user accounts',
    'USER_LOCK':'Lock user accounts','USER_UNLOCK':'Unlock user accounts',
    'USER_RESET_PASSWORD':'Reset temporary passwords','USER_RESET_TOTP':'Reset authenticator enrollment',
    'USER_SCOPE_MANAGE':'Assign and revoke ministry scopes','ROLE_VIEW':'View software roles',
    'ROLE_CREATE':'Create software roles','ROLE_EDIT':'Edit software roles and their permissions',
    'ROLE_ARCHIVE':'Activate or deactivate custom roles','ROLE_ASSIGN':'Assign and revoke software roles',
    'PERMISSION_VIEW':'View the permission catalogue','SECURITY_AUDIT_VIEW':'View account and authentication audit events',
}
TECHNICAL_GRANTS=set(NEW_PERMISSIONS)|{'ADMINISTRATION_VIEW'}
OWN_READ={'MEMBERS_VIEW_OWN_MINISTRY','MINISTRIES_VIEW_OWN','MINISTRY_POSITION_VIEW','MINISTRY_LEADERSHIP_VIEW',
          'ATTENDANCE_VIEW_OWN_MINISTRY','ATTENDANCE_VIEW_AUDIT','ATTENDANCE_EXPORT'}
OWN_OPERATIONAL=OWN_READ|{'ATTENDANCE_CREATE_OWN_MINISTRY','ATTENDANCE_RECORD_OWN_MINISTRY','ATTENDANCE_CORRECT_OWN_MINISTRY','ATTENDANCE_CLOSE_SESSION'}
BASELINES={
    'SYSTEM_ADMIN':('System Administrator','Technical account and role administration; no automatic business-data access.',TECHNICAL_GRANTS),
    'CHURCH_SECRETARY':('Church Secretary','Member registration and church-wide attendance reporting.',
        {'MEMBERS_VIEW_ALL','MEMBERS_CREATE','MEMBERS_EDIT','MINISTRIES_VIEW_ALL','MINISTRY_POSITION_VIEW','MINISTRY_LEADERSHIP_VIEW_ALL','ATTENDANCE_VIEW_ALL','ATTENDANCE_VIEW_AUDIT','ATTENDANCE_EXPORT'}),
    'MINISTRY_LEADER':('Ministry Leader','Operational access within assigned ministry scopes.',OWN_OPERATIONAL),
    'MINISTRY_SECRETARY':('Ministry Secretary','Member and attendance operations within assigned ministry scopes.',OWN_OPERATIONAL),
    'MINISTRY_TREASURER':('Ministry Treasurer','Assigned ministry directory; financial transactions require a separate implemented capability.',{'MEMBERS_VIEW_OWN_MINISTRY','MINISTRIES_VIEW_OWN'}),
    'ATTENDANCE_OFFICER':('Attendance Officer','View and record attendance within assigned ministry scopes.',
        {'MEMBERS_VIEW_OWN_MINISTRY','ATTENDANCE_VIEW_OWN_MINISTRY','ATTENDANCE_RECORD_OWN_MINISTRY'}),
    'FINANCE_OFFICER':('Finance Officer','Finance workspace access; financial records are a future module.',{'FINANCE_VIEW'}),
    'WELFARE_OFFICER':('Welfare Officer','Welfare workspace access; case management is a future module.',{'WELFARE_VIEW'}),
    'REPORT_VIEWER':('Report Viewer','Church-wide attendance viewing and export.',{'ATTENDANCE_VIEW_ALL','ATTENDANCE_VIEW_AUDIT','ATTENDANCE_EXPORT'}),
}


def seed_missing(bind):
    """Append catalogue entries; never restore edited grants on an existing role."""
    schema=bind.get_execution_options().get('schema_translate_map',{}).get(None)
    previous=None
    if schema:
        previous=bind.scalar(sa.text("SELECT current_setting('search_path')"))
        quoted=bind.dialect.identifier_preparer.quote(schema)
        bind.execute(sa.text("SELECT set_config('search_path',:path,true)"),dict(path=quoted))
    try:
        for code,name in NEW_PERMISSIONS.items():
            bind.execute(sa.text("INSERT INTO permissions(id,code,name,module,is_active) VALUES (:id,:code,:name,'Administration',true) ON CONFLICT(code) DO NOTHING"),dict(id=uuid.uuid4(),code=code,name=name))
        definitions=dict(BASELINES)
        if bind.scalar(sa.text("SELECT id FROM roles WHERE code='MINISTRY_ATTENDANCE_LEADER'")):
            definitions.pop('MINISTRY_LEADER')
        if bind.scalar(sa.text("SELECT id FROM roles WHERE code='GENERAL_OVERSEER'")):
            definitions.pop('REPORT_VIEWER')
        if not bind.scalar(sa.text("SELECT id FROM roles WHERE code='ADMINISTRATOR'")):
            grants=set(bind.execute(sa.text('SELECT code FROM permissions WHERE is_active=true')).scalars())-{'FINANCE_VIEW','WELFARE_VIEW'}
            definitions['ADMINISTRATOR']=('Church Administrator','Church operational administration; confidential modules require explicit grants.',grants)
        for code,(name,description,grants) in definitions.items():
            rid=bind.execute(sa.text("INSERT INTO roles(id,code,name,description,is_system,is_active) VALUES (:id,:code,:name,:description,true,true) ON CONFLICT DO NOTHING RETURNING id"),
                dict(id=uuid.uuid4(),code=code,name=name,description=description)).scalar()
            if rid:
                for permission in sorted(grants):
                    bind.execute(sa.text('INSERT INTO role_permissions(role_id,permission_id) SELECT :rid,id FROM permissions WHERE code=:code ON CONFLICT DO NOTHING'),dict(rid=rid,code=permission))
    finally:
        if previous is not None:
            bind.execute(sa.text("SELECT set_config('search_path',:path,true)"),dict(path=previous))


def upgrade():
    op.add_column('users',sa.Column('require_password_change',sa.Boolean,server_default='false',nullable=False))
    op.add_column('users',sa.Column('auth_revision',sa.Integer,server_default='0',nullable=False))
    op.add_column('user_ministry_scopes',sa.Column('legacy_attendance_limits',sa.Boolean,server_default='true',nullable=False))
    op.add_column('user_ministry_scopes',sa.Column('created_by_user_id',postgresql.UUID(as_uuid=True),nullable=True))
    op.create_foreign_key('fk_scope_created_by_user','user_ministry_scopes','users',['created_by_user_id'],['id'],ondelete='SET NULL')
    op.create_table('security_audit_logs',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),
        sa.Column('actor_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='SET NULL')),
        sa.Column('target_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='RESTRICT')),
        sa.Column('target_role_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('roles.id',ondelete='RESTRICT')),
        sa.Column('action',sa.String(50),nullable=False),sa.Column('old_values',sa.Text),sa.Column('new_values',sa.Text,nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    for column in ('actor_user_id','target_user_id','target_role_id','action','created_at'):
        op.create_index('ix_security_audit_logs_'+column,'security_audit_logs',[column])
    bind=op.get_bind()
    seed_missing(bind)
    # One-time explicit access to the new workspace for the established business
    # administrator. All existing grants, role edits and account states survive.
    for code in NEW_PERMISSIONS:
        bind.execute(sa.text("INSERT INTO role_permissions(role_id,permission_id) SELECT r.id,p.id FROM roles r CROSS JOIN permissions p WHERE r.code='ADMINISTRATOR' AND p.code=:code ON CONFLICT DO NOTHING"),dict(code=code))
    for uid in bind.execute(sa.text("SELECT ur.user_id FROM user_roles ur JOIN roles r ON r.id=ur.role_id WHERE r.code='ADMINISTRATOR'")).scalars():
        bind.execute(sa.text("INSERT INTO security_audit_logs(id,target_user_id,action,new_values) VALUES (:id,:uid,'MIGRATION_ADMINISTRATION_GRANTS',:values)"),dict(id=uuid.uuid4(),uid=uid,values=json.dumps({'permissions':sorted(NEW_PERMISSIONS)})))


def downgrade():
    raise RuntimeError('Forward-only authentication migration; restore a verified pre-upgrade backup if necessary.')
