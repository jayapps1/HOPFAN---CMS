"""Explicit administration capabilities; technical roles have no business bypass."""
PERMISSIONS = {
    'USER_VIEW': 'View system user accounts',
    'USER_CREATE': 'Create system user accounts',
    'USER_EDIT': 'Edit account profiles and activate accounts',
    'USER_DEACTIVATE': 'Deactivate or suspend user accounts',
    'USER_UNLOCK': 'Unlock user accounts',
    'USER_LOCK': 'Lock user accounts',
    'USER_RESET_PASSWORD': 'Reset temporary passwords',
    'USER_RESET_TOTP': 'Reset authenticator enrollment',
    'USER_SCOPE_MANAGE': 'Assign and revoke ministry scopes',
    'ROLE_VIEW': 'View software roles',
    'ROLE_CREATE': 'Create software roles',
    'ROLE_EDIT': 'Edit software roles and their permissions',
    'ROLE_ARCHIVE': 'Activate or deactivate custom roles',
    'ROLE_ASSIGN': 'Assign and revoke software roles',
    'PERMISSION_VIEW': 'View the permission catalogue',
    'SECURITY_AUDIT_VIEW': 'View account and authentication audit events',
}
ADMIN_PERMISSIONS = set(PERMISSIONS) | {'ADMINISTRATION_VIEW'}
