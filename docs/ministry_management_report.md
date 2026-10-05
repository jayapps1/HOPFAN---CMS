# HOPFAN Administrator Ministry Management

Implemented 5 October 2026 in the existing application. The entry point remains `hopfan.py`.

## 1. Files created

- `migrations/versions/d7f9215c8a30_ministry_management.py`
- `src/models/ministry_audit.py`
- `src/services/ministry_service.py`
- `src/ui/components/action_menu.py`
- `src/ui/components/search_field.py`
- `src/ui/ministries/__init__.py`
- `src/ui/ministries/ministries_view.py`
- `src/ui/ministries/dialogs.py`
- `src/ui/ministries/profile.py`
- `tests/ministry_preview.py`
- `tests/test_ministry.py`
- `tests/test_ministry_migration.py`
- `tests/test_ui_ministry.py`
- This report and representative synthetic screenshots in `docs/screenshots/ministry_management/`.

## 2. Existing files changed

`migrations/env.py` accepts an externally supplied migration connection for isolated migration testing. `src/database/seed_ministries.py` now creates missing bootstrap rows without overwriting administrator names or lifecycle states on a repeat run.

Models updated: `src/models/ministry.py`, `member_ministry.py`, `attendance_session.py`, `attendance_support.py` and `src/models/__init__.py`.

Permissions/services updated: `src/security/application_permissions.py`, `src/services/member_service.py` and `src/services/attendance_service.py`.

UI updated: `src/ui/components/modern.py` supplies Active/Inactive/Archived badge palettes; `select_popup.py` supports a wider contextual action menu; `src/ui/dashboard/dashboard_view.py` mounts the real ministry workspace; `src/ui/members/member_form_dialog.py` loads and labels existing inactive/archived participation.

Tests updated: `tests/test_attendance.py` uses uppercase ministry fixture codes; `tests/test_ui_smoke.py` supplies a synthetic ministry service for dashboard checks. `docs/attendance_upgrade_report.md` links this report.

## 3. Database fields and constraints

| Addition to ministries | Purpose |
| --- | --- |
| `category`, varchar(20), required, default MINISTRY | Ministry, Fellowship, Department, Unit or Other |
| `created_by_user_id`, nullable UUID | Creator of new administrator-created rows |
| `updated_by_user_id`, nullable UUID | Actor for subsequent edits/lifecycle changes |
| `archived_at`, nullable timestamptz | Distinguishes archived from inactive |
| `archived_by_user_id`, nullable UUID | Archive actor |

`is_active` remains the compatibility field used by current assignment and attendance creation services. The derived status is ARCHIVED when `archived_at` is set, otherwise ACTIVE/INACTIVE from `is_active`. A check constraint prevents an archived ministry from being active. This avoids storing two independent status representations. Existing active/inactive values, UUIDs, names, codes and timestamps are preserved. Existing rows receive category MINISTRY and no invented creator/archive actor; administrators can reclassify them.

Case-insensitive unique indexes protect codes and names, including inactive and archived rows. New codes are explicitly entered/suggested, normalized to uppercase, and validated for letters, digits and underscores. The migration fails atomically if legacy case duplicates exist rather than renaming or dropping rows.

Ministry foreign keys in member participation, user ministry scopes and attendance sessions now use RESTRICT. The Ministry ORM relationship also stops cascading child deletion. Existing records are preserved; ordinary member/attendance behavior is retained.

`ministry_audit_logs` records actor, ministry UUID, action, old/new JSON snapshots and timestamp. Its ministry UUID is a retained snapshot rather than a foreign key so audit history survives the permitted deletion of an unused ministry. Actor foreign keys use SET NULL if an account is removed.

## 4. Alembic revision and data verification

Reviewed forward revision **d7f9215c8a30**, following `c603420e8020`, was tested through the real migration chain in a disposable schema before being applied.

Before application, PostgreSQL backup `backups/before_ministry_management_20261005T164048Z.dump` was saved and its archive listing verified. `backups/before_ministry_management_20261005T164048Z_snapshot.json` stores fingerprints of original columns. A complete backup restore drill was not performed.

After migration, every protected fingerprint matched: 14 ministries, 1 member, 1 member/ministry relationship, 1 user and role assignment, 2 attendance sessions, 1 attendance record, 2 saved roster entries, 2 attendance audit records and existing scope rows. No church rows were reset, removed or used as writable test fixtures. Alembic reports no new upgrade operations. The real administrator's read-only directory, capabilities, profile and dynamic selector calls passed.

## 5. Permissions

Existing `MINISTRIES_VIEW_ALL` and `MINISTRIES_VIEW_OWN` are reused. Six management grants are added:

- `MINISTRIES_CREATE`
- `MINISTRIES_EDIT` (also activation)
- `MINISTRIES_DEACTIVATE`
- `MINISTRIES_ARCHIVE`
- `MINISTRIES_RESTORE`
- `MINISTRIES_DELETE_UNUSED`

The migration grants these to the existing Administrator role and records the grant change in authorization history. It grants no new management rights to ministry leaders. Services reload active account, role, permission and scope data on each request. A management operation requires both the matching action grant and `MINISTRIES_VIEW_ALL`; a role title alone provides no authority.

Scoped ministry viewing uses the existing assigned ministry grants and preserves read access to assigned inactive/archived ministry profiles. Leaders receive scoped directory/profile information without add/edit/lifecycle/delete controls. Permission revocation and inactive accounts are tested directly.

## 6. MinistryService methods

Public operations are `capabilities`, `list_ministries`, `get_ministry`, `get_ministry_stats`, `get_member_counts`, `create_ministry`, `update_ministry`, `activate_ministry`, `deactivate_ministry`, `archive_ministry`, `restore_ministry`, `delete_unused_ministry` and `audit_history`.

The directory supports escaped name/code search, status/category filtering, deterministic pagination and bounded page sizes. Member counts use a grouped set query joined to the directory, without a separate count query per ministry. Total members count active participation relationships; Active members additionally require an Active member profile.

Mutations are transactional, lock the ministry row, check permissions and append audit history. UI writes pass the previously loaded `updated_at` to reject stale edits. Codes are locked when dependent records exist. An unchanged legacy code is preserved on ordinary edits.

## 7. UI implemented

The existing Ministries sidebar destination opens the real workspace. It contains a page header and visible Add ministry action, four summary cards, a debounced search field, shared ModernSelect category/status filters, a scrolling directory, contextual actions and fixed pagination.

Rows display name, code, category, member count, lifecycle badge, update date and permitted actions. Add/Edit uses a fixed-footer modal with name, explicit code plus a suggestion, category, description and status. Used codes are visibly read-only. Status changes from Edit receive contextual confirmation. Saving a new/edited ministry adjusts filters to reveal the saved row.

The profile shows configuration, description, creation/update/archive dates, member totals and recorded configuration history. Lifecycle dialogs explain the concrete consequence of Activate/Deactivate/Archive/Restore/Delete. Restore defaults to Inactive, with an Active option. Delete requires typing the exact code and clicking Delete permanently. Empty results have a useful empty state with Add ministry when permitted.

Shared cards, inputs, image chevrons, badges, fonts and popovers support immediate light/dark switching. Database work stays off the Tk thread; widget values are captured before worker operations.

## 8. Deletion and archive rules

Archive/deactivation leave all participation, attendance, scope and historical records intact. Restore changes the same ministry row and UUID. Archive removes the ministry from active creation/assignment selectors.

Permanent deletion requires `MINISTRIES_DELETE_UNUSED`, global ministry viewing, explicit confirmation and an unused ministry. Dependency checks include inactive membership history, attendance sessions, user grants, authorization history and actual foreign-key references from future tables. Existing database references also reject raw parent deletion through RESTRICT. The UI hides deletion for known used ministries; the service remains authoritative when dependencies change or future records exist.

Used ministries receive: “This ministry cannot be permanently deleted because it has related church records. Archive it instead.” Successful unused deletion retains actor, original UUID and details in the audit table.

## 9. Member and attendance integration

Add Member loads active database ministries. Edit Member also loads its existing active participation in inactive/archived ministries, labels their lifecycle state and retains their IDs in the member profile. Saving unrelated member details keeps those relationship IDs and leadership positions. An administrator may explicitly remove participation; that deactivates the association with its history retained. An inactive/archived ministry cannot be newly assigned or an already-ended association reactivated through this exception.

New active ministries appear in attendance creation on the next workspace load without a source change. Administrator history filters also include inactive/archived ministries; new attendance creation still requires an active ministry. Availability checks hold shared ministry row locks through member assignment and attendance creation, coordinating them with lifecycle changes. Attendance marking, saved rosters, corrections, session lifecycle and permission rules are unchanged.

## 10. Verification

All **50 tests passed**: 36 database/migration/session checks and 14 desktop checks. The database suite includes 22 attendance/member regressions, 3 idle-session cases, 10 ministry service cases and the full forward migration case. These cover the requested A–J scenarios, archive/restore identity, permission denial/revocation, historical participation retention/removal, stale writes, case uniqueness, future dependency rejection, audit survival and constant directory query count as rows grow.

Desktop verification covers administrator/leader controls, the three requested desktop viewports, both themes, filtered/paginated directory rows, contextual menus, empty state, add/edit, code suggestion/locking, profiles, lifecycle confirmations, typed delete confirmation, fixed footers and archived member options. Existing attendance, login, member-form and dropdown desktop regressions are included. GUI cases use synthetic services; writable PostgreSQL tests use private schemas that are rolled back or removed.

Viewports represent 1366x768, 1600x900 and 1920x1080 with Windows chrome excluded at the installed DPI. Physical monitor settings are not changed. Representative synthetic captures are saved in `docs/screenshots/ministry_management/`:

- Directory: [1366 light](screenshots/ministry_management/ministry_directory_1366_light.png), [1600 dark](screenshots/ministry_management/ministry_directory_1600_dark.png), [1920 dark](screenshots/ministry_management/ministry_directory_1920_dark.png).
- Add/Edit: [form fields](screenshots/ministry_management/ministry_form_top_light.png), [status and fixed footer](screenshots/ministry_management/ministry_form_dark.png).
- Details and lifecycle: [profile](screenshots/ministry_management/ministry_profile_dark.png), [archive](screenshots/ministry_management/ministry_archive_light.png), [restore](screenshots/ministry_management/ministry_restore_dark.png).
- Access and empty results: [leader workspace](screenshots/ministry_management/ministry_leader_readonly.png), [empty state](screenshots/ministry_management/ministry_empty_light.png).

## 11. Remaining issues and limits

Leadership operations, dues, welfare, SMS and ministry-specific reports remain future modules. They can reference the stable ministry UUID; no financial records, delivery results or leaders were invented. Categories of existing ministries default to Ministry for administrator review. A future dependency should use a proper foreign key to ministry ID to participate in deletion protection.

The desktop checks cover the available Windows environment and DPI, not every operating system or monitor configuration. Custom management roles require explicit grants; ministry workspace access does not imply administration rights. The verified pre-migration backup is local and intentionally excluded from Git.

## 12. Exact commands

From `D:\HOPFAN`:

```powershell
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m compileall -q src migrations tests
.venv\Scripts\python.exe -m unittest tests.test_attendance tests.test_session tests.test_ministry tests.test_ministry_migration -v
.venv\Scripts\python.exe -m unittest tests.test_ui_smoke tests.test_ui_refinement tests.test_ui_ministry -v
.venv\Scripts\python.exe hopfan.py
```

The migration is already applied locally; `upgrade head` is repeatable. Run desktop checks on an interactive Windows desktop.
