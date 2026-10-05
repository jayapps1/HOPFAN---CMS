# User administration, RBAC and ministry scopes

Implemented in the existing HOPFAN project. Local database deployment is **complete** at migration `a91c73d5f204`. On 2026-10-05, the seeded-admin sign-in failure was traced to the database remaining at `e8b4026d9f10`, without `users.require_password_change`, `users.auth_revision` or `security_audit_logs`. The configured seed password matched the active account; its credentials did not need resetting. After a fresh verified backup and approval of the repair, the forward migration was applied successfully.

The forward migration was executed and checked successfully in both a private test transaction and the local database. Existing users, password hashes, encrypted authenticator data, roles, grants, memberships, attendance history and church positions were retained. Seeded-admin authentication with both email and username, session validation and administration access passed. Verification-only login changes were rolled back, and original-column fingerprints still match for all 18 existing application tables.

## 1. Files created

- `src/models/security_audit.py`: account, role and authentication audit model.
- `src/security/administration_permissions.py`: explicit administration permission catalogue.
- `src/services/authorization_service.py`: central authorization context and service API.
- `src/services/administration_base.py`: shared transactions, delegation checks, recovery protection and audit queries.
- `src/services/user_service.py`: account directory, creation, profiles, role/scope assignment and security actions.
- `src/services/role_service.py`: software role lifecycle and permission catalogue.
- `src/database/seed_access.py`: repeatable catalogue seeding that preserves existing configuration.
- `src/ui/administration/__init__.py`, `administration_view.py`, `dialogs.py`, `role_dialogs.py`: administration workspace and forms.
- `src/ui/login/account_security_dialogs.py`: verified temporary-password change and own-account authenticator enrollment.
- `migrations/versions/a91c73d5f204_user_administration.py`: forward schema migration and conservative baseline catalogue.
- `scripts/__init__.py`, `scripts/upgrade_guard.py`: verified backup and original-column fingerprint checks.
- `tests/administration_preview.py`, `test_administration.py`, `test_administration_migration.py`, `test_ui_administration.py`: synthetic desktop fixtures and database/security/migration tests.
- This report and synthetic screenshots under `docs/screenshots/user_administration/`.

## 2. Files changed

- `src/models/user.py`, `attendance_support.py`, `__init__.py`: required user/scope fields and model registration.
- `src/security/attendance_permissions.py`: compatibility API now delegates to the central authorization service.
- `src/security/application_permissions.py`: administration navigation follows specific granted capabilities.
- `src/services/auth_service.py`: preserved alternate sign-in methods and lockout; added proof-bound recovery, required password changes, session revisions and audit events.
- `src/services/member_service.py`, `ministry_service.py`, `ministry_leadership_service.py`, `attendance_service.py`: shared authorization, consistent denial exceptions and preserved historical scope restrictions.
- `src/database/seed.py`: rerunning bootstrap no longer reactivates an existing account or restores a revoked administrator role.
- `src/ui/dashboard/dashboard_view.py`: real administration navigation, technical-account dashboard and own-account authenticator entry.
- `src/ui/login/login_view.py`: verified first-login password change and email/username sign-in.
- `src/ui/ministries/leadership_view.py`: explicit Grant system access action for members without an account.
- `src/ui/components/multi_select_dropdown.py`: selected-role summaries use the correct category name.
- `src/ui/components/modern.py`: readable locked/suspended account badges.
- `hopfan.py`, `tests/test_session.py`: audited logout/idle expiry, credential revision checks, and stale-result protection.
- `docs/attendance_upgrade_report.md`: link to this report.

## 3. Database changes

Existing normalized tables `users`, `roles`, `permissions`, `user_roles`, `role_permissions` and `user_ministry_scopes` are preserved. The one-to-one `users.member_id` constraint and unique user/ministry scope constraint remain.

Additions:

| Table | Change |
| --- | --- |
| `users` | `require_password_change`, non-null Boolean, existing accounts default false |
| `users` | `auth_revision`, non-null integer, existing accounts default zero |
| `user_ministry_scopes` | `legacy_attendance_limits`, non-null Boolean, existing grants default true |
| `user_ministry_scopes` | nullable `created_by_user_id`, FK to users with SET NULL |
| `security_audit_logs` | new indexed audit table with actor, optional target account/role, action, safe before/after data and timestamp |

No user or role hard-delete operation was added. Deactivated users and roles retain associations and historical references. Existing attendance capability flags remain only for compatibility with historical grants; new administration scopes do not depend on those flags.

## 4. Alembic revision and backup

Revision: `a91c73d5f204`, parent: `e8b4026d9f10`.

The migration is forward-only. Its private migration test verifies every original column in the earlier schema and checks that old permissions, roles and role grants are retained. Alembic model comparison in that transaction reports **No new upgrade operations detected**.

Verified local backup:

- `backups/before_user_administration_20261005T204108Z.dump`
- `backups/before_user_administration_20261005T204108Z_snapshot.json`

The archive was created using PostgreSQL 18 `pg_dump` and verified with `pg_restore --list`. The snapshot contains column names and row hashes. Credentials stay in the child-process environment. Neither backups nor private authentication data are committed to Git.

Original rows across all 18 recorded application tables match the pre-upgrade snapshot after migration and sign-in verification. A comparison against the earlier leadership backup identified only an existing user's `updated_at` difference; password/authenticator values and other account fields matched. The fresh backup is the baseline for the completed upgrade.

## 5. Permissions seeded by the migration

Sixteen new, explicit administration permissions:

`USER_VIEW`, `USER_CREATE`, `USER_EDIT`, `USER_DEACTIVATE`, `USER_LOCK`, `USER_UNLOCK`, `USER_RESET_PASSWORD`, `USER_RESET_TOTP`, `USER_SCOPE_MANAGE`, `ROLE_VIEW`, `ROLE_CREATE`, `ROLE_EDIT`, `ROLE_ARCHIVE`, `ROLE_ASSIGN`, `PERMISSION_VIEW`, `SECURITY_AUDIT_VIEW`.

Existing equivalent grants retain their existing names. Examples: `MEMBERS_VIEW_ALL`, `MEMBERS_VIEW_OWN_MINISTRY`, `MEMBERS_CREATE`, `MEMBERS_EDIT`, `MINISTRIES_VIEW_ALL`, `MINISTRIES_VIEW_OWN`, existing leadership grants and attendance grants. There are no duplicate singular MEMBER/MINISTRY grants and no invented operational SMS/financial permissions for modules that are not implemented.

The established `ADMINISTRATOR` role receives the new administration grants once during this migration, with an audit event. Repeatable seeding does not restore edited grants on existing roles.

## 6. Baseline roles

| Software role | Default capability |
| --- | --- |
| Existing `ADMINISTRATOR` | Existing business access retained; new account/role administration grants added once |
| `SYSTEM_ADMIN` | Account, role, scope and security administration; no member, attendance, finance or welfare access automatically |
| `CHURCH_SECRETARY` | Member registration/editing and church-wide attendance reporting |
| Existing `MINISTRY_ATTENDANCE_LEADER` | Reused for ministry leadership access; no duplicate MINISTRY_LEADER role created |
| `MINISTRY_SECRETARY` | Own-ministry member viewing and attendance operations |
| `MINISTRY_TREASURER` | Assigned member/ministry directory access; no invented financial transaction capability |
| `ATTENDANCE_OFFICER` | Own-ministry member viewing and attendance recording |
| `FINANCE_OFFICER` | Existing Finance workspace grant only |
| `WELFARE_OFFICER` | Existing Welfare workspace grant only |
| Existing `GENERAL_OVERSEER` | Reused for attendance report viewing; no duplicate REPORT_VIEWER role created |

If the equivalent ministry/report role is absent, its baseline role is created. Existing role IDs, active states and grants are authoritative. The standard existing three-role catalogue becomes ten roles after the migration; no sample accounts are created.

## 7. Authorization architecture

`AuthorizationService` loads the current account, active roles, active permissions and scopes from the database for each service request. Account status and pending password changes are checked before business data is accessed. Church offices and free-text titles are never inputs to RBAC.

API includes `has_permission`, `has_any_permission`, `get_effective_permissions`, `get_ministry_scopes`, `has_ministry_scope`, `can_access_ministry`, `require_permission` and `require_ministry_permission`. `AuthorizationContext` supplies the same checks inside an existing service transaction. Existing module exceptions inherit `AuthorizationDenied` while keeping their original module-specific error types.

Capability and location are intersected. Own-ministry grants require assigned scope; global equivalents do not need scope rows. Attendance close/export and ministry position viewing also respect their explicit capability plus global/scoped location rules. Existing service-specific business conditions, such as closed attendance correction and ministry lifecycle rules, remain in their services.

Administration mutations use a PostgreSQL transaction advisory lock. Role grants cannot exceed the actor's effective authority. A technical administrator cannot assign or edit a business role to obtain permissions they do not hold. Removing or disabling the last recoverable administrator's account or recovery permissions is rejected transactionally.

## 8. User administration features

- Paginated directory with total, active, locked and inactive/suspended summary counts.
- Search by member name/number, username, email and phone; status, role and ministry scope filters.
- Batched member, role, permission and scope loading. Query-count tests confirm fixed query count rather than one query per account.
- Create an account with optional searchable member link, validated username/email, phone, initial password, status, multiple software roles and multiple ministry scopes.
- Exact duplicate member-link message: "This member already has a HOPFAN user account."
- Separate account-profile editing, access editing and security actions.
- User profile shows linked member, roles, configured/effective permissions, ministry scopes, legacy scope restrictions, authenticator status, failed attempts, lock expiry and last login.
- Leadership lists indicate whether a member has an account. Authorized Grant system access opens account creation with that member preselected. It selects no role automatically.

## 9. Role management features

Paginated role search and status filtering show description, assigned-user count, permission count, system-role flag and active status. Create/edit forms group permissions visually by module. Role profiles show the actual permission catalogue.

Custom roles can be activated/deactivated with confirmation. System role codes are immutable and system roles cannot be deactivated through the ordinary lifecycle action. Assigned users and role associations are retained. Permission edits are audited, guard against stale saves, obey delegation limits and invalidate affected users' sessions. No permanent role deletion is exposed.

## 10. Ministry scope behavior

New scopes use role capability plus ministry location, supporting multiple ministries and unique user/ministry pairs. Scope revocation marks the row inactive and leaves historical records intact. Active ministries are required for new scopes; existing archived scopes can be retained or explicitly removed.

Historical per-attendance restrictions are preserved using `legacy_attendance_limits=true`. Changing a user's roles or saving the same scope selection does not silently remove those restrictions. An authorized administrator must explicitly select and confirm replacing legacy attendance limits with role capabilities. New or deliberately reactivated scope grants use the normalized behavior.

Global permissions are never narrowed by choosing scopes. Inactive ministries are excluded from operational attendance/member scope access; existing historical ministry/leadership workspace visibility is preserved where already supported.

The existing attendance ministry filter already provides a switcher limited to allowed ministries. Technical dashboards display account metrics and authorized navigation without querying business attendance/member metrics.

## 11. Security actions

Passwords remain Argon2 hashes. Account creation and resets reuse `AuthService.validate_new_password`: at least ten characters, uppercase, lowercase, a number and a special character. Password reset accepts a set or generated temporary password and requires a new password on the next sign-in. The reset does not silently reactivate/unlock the account.

Password and authenticator remain alternative sign-in methods. Both accept email or username. Five failed verification attempts trigger a fifteen-minute lock; permanent administrative locks also prevent login. Authorized unlock clears failed attempts and the lock and records an event.

A first-login password change requires a short-lived proof issued only after successful authentication. The previous temporary password cannot be reused. Services deny business access while this change is pending.

TOTP reset clears the encrypted secret, enabled state and confirmation timestamp, invalidates old proofs and requires new enrollment. Administrators see status only. QR/setup keys appear only in a separate user-owned enrollment flow after that user verifies their own password. Canceled enrollment removes the pending in-memory setup secret. Self-service password recovery requires verified TOTP proof and cannot reactivate a disabled account or reset another account by ID alone.

Credential/security changes and role/scope changes increment session revisions. The desktop checks them every fifteen seconds and closes stale sessions; data services still reload permissions on every request. Logout and idle expiry are audited.

## 12. Audit behavior

Security audit covers account creation/profile/access/status changes, unlocks, password resets/changes/recovery, authenticator enrollment/reset, role creation/permission/status changes, sign-in success/failure/rejection, account lockout, logout, idle expiry and session revocation.

Events retain actor/target references and safe change data. No password, password hash, authenticator code, encrypted/decrypted TOTP secret, provisioning URI or proof token is included. Existing attendance/authorization/leadership audit tables remain intact. Audit lists are paginated and their detail dialogs show the safe before/after record.

User-facing timestamps use `DD/MM/YYYY HH:MM`, converted to the workstation's local timezone. PostgreSQL timestamps remain timezone-aware.

## 13. Tests performed

Database/session suite: **68 tests passed**. This includes all twelve new account/RBAC tests, the existing attendance/ministry/leadership tests, three real forward migration tests and five session tests. The updated administration migration additionally passes Alembic model comparison.

Desktop regressions: **18 existing tests passed**. Final administration desktop suite: **6 tests passed**, covering six checks covering three resolutions, both themes, user directory, member picker, role permission groups, profile/security forms, restricted controls, technical dashboard and own-account authenticator setup. Synthetic captures cover seven administration views at all six size/theme combinations.

The integration tests cover requested cases A-K: account/member/role/scope creation; Youth-only and multiple ministry access; global access without scope rows; deactivation/history; lockout/unlock audit; Argon2 reset with no secret logging; TOTP invalidation and reenrollment; office/role independence; direct service denial; and constant-query account listing. Desktop checks cover L, including footer/action visibility and readable themes.

**92 distinct tests passed** across the database/session and desktop suites. Syntax compilation and `git diff --check` pass. All test fixtures are synthetic, and private test schemas/transactions are cleaned up. Screenshot capture targets the synthetic application window rather than the desktop.

## 14. Exact commands

From `D:\HOPFAN`:

```powershell
.venv\Scripts\python.exe -m compileall -q src migrations tests scripts
.venv\Scripts\python.exe -m unittest tests.test_administration tests.test_attendance.AttendanceTests tests.test_ministry.MinistryTests tests.test_leadership.LeadershipTests tests.test_session tests.test_administration_migration tests.test_ministry_migration tests.test_leadership_migration -q
.venv\Scripts\python.exe -m unittest tests.test_ui_administration tests.test_ui_smoke tests.test_ui_refinement tests.test_ui_ministry tests.test_ui_leadership -v
```

The local repair used these migration and preservation checks, followed by rollback-only verification of seeded-admin sign-in. To launch the updated application, use the final command:

```powershell
.venv\Scripts\python.exe -m alembic upgrade a91c73d5f204
.venv\Scripts\python.exe -m scripts.upgrade_guard verify backups/before_user_administration_20261005T204108Z_snapshot.json
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe hopfan.py
```

Optional repeatable baseline seeding, after the schema upgrade:

```powershell
.venv\Scripts\python.exe -m src.database.seed_access
```

A fresh backup can be made with `.venv\Scripts\python.exe -m scripts.upgrade_guard backup`. Set `PG_BIN` to the installed PostgreSQL binary directory if PostgreSQL 18 is not installed in its standard path.

## 15. Deployment status and remaining modules

The local migration is applied and Alembic reports **No new upgrade operations detected**. Seeded-admin sign-in succeeds with the existing credentials. Close and reopen any running application before trying again. The previous approval blocker was resolved during the sign-in repair.

Existing global `MEMBERS_EDIT` is retained; a separate own-ministry member editing/membership-management workflow is not introduced under an unused permission. SMS sending, confidential financial records, welfare case notes, counselling, Settings and a Backup administration screen remain their separate future modules. Their business rules and approval policy require their own implementation; no fake operational flows were added here.

Role suggestions from church office titles are intentionally optional and currently not offered. Grant system access requires the administrator to explicitly select roles and scopes. No office automatically creates login access.
