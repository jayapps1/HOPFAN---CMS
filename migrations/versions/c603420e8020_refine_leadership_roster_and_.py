"""refine leadership roster and application grants

Revision ID: c603420e8020
Revises: 4837e2db4cfd
Create Date: 2026-10-05 12:02:28.618437

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import uuid
import json


# revision identifiers, used by Alembic.
revision: str = 'c603420e8020'
down_revision: Union[str, Sequence[str], None] = '4837e2db4cfd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Reviewed after autogeneration: roster vocabulary and grants are data changes.
    # Keep the saved roster, records, creator, marker and history untouched.
    op.drop_constraint('ck_attendance_roster_scope', 'attendance_sessions', type_='check')
    op.execute("UPDATE attendance_sessions SET roster_type = 'MINISTRY_LEADERSHIP' WHERE roster_type = 'EXECUTIVES'")
    op.create_check_constraint('ck_attendance_roster_scope', 'attendance_sessions',
        "(scope_type = 'GLOBAL' AND roster_type IN ('WHOLE_CHURCH', 'SELECTED_MEMBERS')) OR (scope_type = 'MINISTRY' AND roster_type IN ('ALL_MINISTRY_MEMBERS', 'SELECTED_MEMBERS', 'MINISTRY_LEADERSHIP'))")
    bind = op.get_bind()
    definitions = {
        'MEMBERS_VIEW_ALL': 'View the church member directory',
        'MEMBERS_VIEW_OWN_MINISTRY': 'View members of assigned ministries',
        'MEMBERS_CREATE': 'Register church members', 'MEMBERS_EDIT': 'Edit church member profiles',
        'MINISTRIES_VIEW_ALL': 'View all ministries', 'MINISTRIES_VIEW_OWN': 'View assigned ministries',
        'SUNDAY_SCHOOL_VIEW': 'View Sunday School workspace', 'FINANCE_VIEW': 'View finance workspace',
        'WELFARE_VIEW': 'View welfare workspace', 'SMS_VIEW_ALL': 'View church SMS workspace',
        'SMS_VIEW_OWN': 'View assigned ministry SMS workspace',
        'ADMINISTRATION_VIEW': 'View administration workspace',
    }
    for code, name in definitions.items():
        bind.execute(sa.text("""INSERT INTO permissions (id, code, name, module, is_active)
            VALUES (:id, :code, :name, :module, true) ON CONFLICT (code) DO NOTHING"""),
            dict(id=uuid.uuid4(), code=code, name=name, module=code.split('_')[0].title()))
    grants = {'ADMINISTRATOR': list(definitions),
              'MINISTRY_ATTENDANCE_LEADER': ['MEMBERS_VIEW_OWN_MINISTRY', 'MINISTRIES_VIEW_OWN', 'SMS_VIEW_OWN']}
    for role, permissions in grants.items():
        for permission in permissions:
            bind.execute(sa.text("""INSERT INTO role_permissions (role_id, permission_id)
                SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
                WHERE r.code = :role AND p.code = :permission ON CONFLICT DO NOTHING"""),
                dict(role=role, permission=permission))
        for user_id in bind.execute(sa.text("""SELECT ur.user_id FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id WHERE r.code = :role"""), dict(role=role)).scalars():
            bind.execute(sa.text("""INSERT INTO authorization_audit_logs
                (id, target_user_id, action_type, new_values)
                VALUES (:id, :user_id, 'MIGRATION_APPLICATION_GRANTS', :payload)"""),
                dict(id=uuid.uuid4(), user_id=user_id, payload=json.dumps({'role': role, 'permissions': permissions})))


def downgrade() -> None:
    raise RuntimeError("Forward-only production upgrade; use the verified backup to restore the earlier state.")
