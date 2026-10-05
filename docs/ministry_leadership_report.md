# HOPFAN Ministry Leadership & Positions

Implemented 5 October 2026 in the existing desktop application. Start the application with `hopfan.py`, then open **Ministries → View → Leadership**.

## 1. Files created

- `src/models/ministry_leadership.py`
- `src/services/ministry_leadership_service.py`
- `src/ui/ministries/leadership_view.py`
- `src/ui/ministries/leadership_dialogs.py`
- `migrations/versions/e8b4026d9f10_ministry_leadership.py`
- `tests/test_leadership.py`
- `tests/test_leadership_migration.py`
- `tests/test_ui_leadership.py`
- `tests/leadership_preview.py`
- This report and synthetic desktop captures in `docs/screenshots/ministry_leadership/`.

## 2. Existing files changed

`src/models/__init__.py` registers the three new models. `src/security/application_permissions.py` defines explicit office-management grants and scoped viewing grants. `src/services/ministry_service.py` recognizes positions, appointments and leadership audit records as ministry dependencies.

`src/services/member_service.py` returns permitted leadership records on profiles and prevents removal/deactivation of a current office holder before their appointments are ended. `src/services/attendance_service.py` includes structured leadership in new ministry leadership rosters while retaining legacy behavior and saved rosters.

`src/ui/ministries/profile.py` adds Overview/Leadership tabs and an overview summary. `src/ui/members/members_view.py` adds the Leadership / Positions section. `src/ui/components/modern.py` supplies Current, Historical and Vacant badge palettes. `tests/test_ministry_migration.py` tests its own named revision instead of a moving head. The attendance report links this report.

## 3. Models and design

**MinistryPosition** is scoped to one existing ministry. Name/code uniqueness is case-insensitive within that ministry, so different ministries can use their own names for similar offices. Fields include UUID, ministry UUID, code, name, description, display order, leadership flag, active flag, nullable holder limit, actor UUIDs and timestamps. A blank holder limit means Unlimited; the form defaults to one holder.

**MinistryLeadershipAssignment** stores ministry, member and position UUIDs, start/end DATE values, current flag, notes, actor UUIDs and timestamps. Appointment snapshots retain the position code and name so historical records remain meaningful after a position is renamed. Current records display the position's current name.

**MinistryLeadershipAuditLog** stores ministry, position, assignment, member and actor identifiers, action, old/new JSON details and timestamp. Position/appointment identifiers are retained snapshots; unused position deletion does not remove its audit records.

Church positions remain separate from software roles. A member can hold several positions in several ministries without owning a user account. No appointment operation changes accounts, user roles, permissions or ministry scopes. Existing `users.member_id` and the existing audited access-management workspace remain the separate foundation for software access.

## 4. Tables and constraints

New tables: `ministry_positions`, `ministry_leadership_assignments`, `ministry_leadership_audit_logs`.

No existing table or church row is rewritten. Ministry/member/position references use UUID foreign keys with RESTRICT. A composite position/ministry foreign key prevents appointments against another ministry's position. Checks require valid date order, an end date for a historical appointment, no end date for a current appointment, non-negative display order and a positive or unlimited holder limit. A partial unique index prevents duplicate current member/position appointments.

Indexes cover ministry, member, position, current status and start date, plus audit chronology and per-ministry case-insensitive position uniqueness. Holder limits are enforced by services under an exclusive position row lock, including concurrent appointment requests. There is no application operation that deletes appointments. Direct administrative SQL must honor these business rules as well.

## 5. Alembic revision and data preservation

Forward revision **e8b4026d9f10**, following **d7f9215c8a30**, was reviewed and tested through the actual migration chain in a disposable transaction before being applied locally. Alembic check reports **No new upgrade operations detected**.

The verified pre-migration PostgreSQL archive is `backups/before_ministry_leadership_20261005T182555Z.dump`; the matching `_snapshot.json` stores original-column fingerprints. The backup's archive listing was verified; a complete restore drill was not performed. Backups and database configuration remain excluded from Git.

Fingerprints matched for the original ministries, members, participation, users, role assignments, attendance sessions/records/rosters/audit, scopes and ministry audit. Existing authorization history and role grants were retained; only the requested migration grants and their authorization audit were appended. All 14 existing ministries remain, and real administrator read-only leadership/profile checks passed. No example officers, positions or appointments were inserted into the church database.

## 6. Permissions

Ten explicit permissions are added:

| Permission | Purpose |
| --- | --- |
| `MINISTRY_POSITION_VIEW` | Read positions in permitted ministries |
| `MINISTRY_POSITION_CREATE` | Create position definitions |
| `MINISTRY_POSITION_EDIT` | Edit/reactivate position definitions |
| `MINISTRY_POSITION_ARCHIVE` | Deactivate a position |
| `MINISTRY_POSITION_DELETE_UNUSED` | Delete an unused position after confirmation |
| `MINISTRY_LEADERSHIP_VIEW` | Read leadership in assigned ministries |
| `MINISTRY_LEADERSHIP_VIEW_ALL` | Read all permitted ministries' leadership |
| `MINISTRY_LEADERSHIP_ASSIGN` | Appoint a member |
| `MINISTRY_LEADERSHIP_EDIT` | Correct appointment dates/notes |
| `MINISTRY_LEADERSHIP_END` | End an appointment or perform replacement |

The existing Administrator role receives the ten grants. The existing ministry attendance leader role receives only Position View and scoped Leadership View. Grant changes are audited. Management also requires `MINISTRIES_VIEW_ALL`; every service request reloads the active account, roles, grants and scopes. Assigned inactive/archived ministry history remains readable through assigned ministry grants. Custom roles require explicit permission configuration.

Adding membership during appointment additionally requires `MEMBERS_EDIT` and `MEMBERS_VIEW_ALL`. Replacing a holder additionally requires Leadership End. No security permission depends on a position name or code.

## 7. Service created

`MinistryLeadershipService` reuses the existing permission-loading and ministry visibility infrastructure. Public operations include:

- `capabilities(ministry_id)`
- `list_positions`, `get_position`, `create_position`, `update_position`, `deactivate_position`, `delete_unused_position`
- `candidate_members` with bounded, paginated name/member-number/phone search
- `assign_member`, including explicit membership enrollment and controlled single-holder replacement
- `get_assignment`, `update_assignment`, `end_assignment`
- `list_leadership`, `list_current_leadership`, `list_leadership_history`
- `leadership_stats`, `get_member_leadership`, `leadership_audit`

Position counts use grouped queries, not a query per position. Mutations are transactional, update actor/timestamp fields, audit changes and reject stale UI versions. Ministry availability and member row locks coordinate assignments with lifecycle and participation changes. Position locks serialize holder changes and limit checks.

## 8. Ministry UI

The existing Ministry Profile now has Overview and Leadership tabs. Overview includes a compact current/vacancy summary and View leadership action. Leadership has compact counters, visible Assign position/Manage positions actions, search, Current/Historical/Vacant filters, paginated scrolling cards, dates/status and permitted View/Edit/End actions.

Manage Positions lists name, code, type, active status, order, current holders and limit, with active/inactive filters and permission-driven actions. Add/Edit includes explicit suggested code, description, leadership flag, sort order, holder limit and status. Used codes are read-only. Deactivation and unused deletion have contextual confirmations; deactivation requires ending current appointments first.

Assign Position uses a searchable, paginated member picker with avatars, names, membership numbers, phones and membership eligibility. Position options come from PostgreSQL. Start/end controls reuse the shared DatePicker with direct month/year navigation and DD/MM/YYYY display. Fixed footers remain visible in forms, details and confirmations.

An absent ministry membership produces a clear message and an authorized Add to ministry and continue confirmation. A single-holder conflict shows the current member and a controlled End and appoint confirmation. Appointment details show recorded audit history. Leaders receive scoped reading controls without configuration actions.

## 9. Member profile and attendance integration

Member profiles show current and historical Leadership / Positions with ministry, office and dates. Leadership visibility is independently filtered by the user's leadership grants/scopes, so Youth viewing does not disclose Choir positions merely because the member participates in both ministries. Members are not duplicated.

Removing a member's active ministry participation or changing the member to an inactive status is rejected until current appointments are explicitly ended. Ending an appointment does not delete participation.

New leadership attendance rosters use current appointments whose position has `is_leadership=True`. Existing free-text participation titles remain a compatibility source until that member has structured appointment history in that ministry. Once structured history exists, ending all their leadership appointments removes them from new leadership rosters, even if a legacy title remains. Already saved attendance rosters/records never change. No position name or code controls attendance authorization.

## 10. Leadership history behavior

End Assignment sets the selected end date and `is_current=False`, retaining the UUID, member, ministry and appointment history. Notes are preserved and extended. Historical appointments cannot be reopened by editing; a new appointment creates a new row.

Replacement checks the exact current holder and previously loaded version. The transaction ends that holder and inserts the replacement together. Failure rolls back the ended appointment, enrollment and audit changes. Historical titles survive position renaming/deactivation. Positions with any appointment history cannot be permanently deleted; an unused definition requires explicit confirmation and its dedicated permission.

## 11. Validation rules

- Required name/code, bounded lengths, uppercase code format, per-ministry case-insensitive uniqueness and a stable used code.
- Integer display order and a positive or unlimited holder limit; reducing capacity below current holders is rejected.
- Active, visible member; active ministry and position for a new appointment; matching ministry/position IDs; current participation or explicitly authorized enrollment.
- Duplicate current appointments and holder conflicts are rejected. Repeat appointments for the same member/office cannot have overlapping dates; adjacent boundary dates are allowed.
- Start dates must be on or before today. End dates must be between the start and today. A provided past/completed end date records a historical appointment; an open term is current. Scheduled future terms/automatic expiry are deferred.
- Member, ministry and position identities on an appointment are immutable. Corrections use Edit; transfers/reappointments use End and a new appointment.
- Notes/description limits, stale-version checks and live permission revocation checks apply at the service layer.

## 12. Tests performed

All **71 tests passed**: 53 database/session cases and 18 desktop cases. The database suite includes the existing 36 cases plus 16 leadership cases and one full leadership migration case. Coverage includes required A–J scenarios, account/role separation, explicit enrollment, replacement rollback, simultaneous single-holder appointments, case uniqueness, member profile scope, history retention, protected deletion, query count stability, date/identity/stale guards and saved attendance roster preservation. The final scoped-permission changes passed all 16 leadership service cases again.

The desktop suite covers the existing 14 login/member/attendance/ministry cases and four new leadership cases. New cases exercise all three desktop sizes in both themes, position management, assignment forms, member search/pagination/avatars, replacement cancellation/confirmation, membership confirmation, ending/editing/history, profiles and leader controls. The minimum-size screenshot review prompted compact summaries and tab-bar actions, with a further check that the whole first appointment row fits its actual scroll viewport.

Database writes use generated private schemas/rolled-back migration transactions. Desktop tests use in-memory synthetic services. Syntax compilation and `git diff --check` passed. The full 18-case desktop run passed, followed by all four leadership desktop cases again with stronger checks against the actual scroll viewport and Overview/Leadership switching.

Representative synthetic captures:

- Leadership: [1366 light](screenshots/ministry_leadership/leadership_1366_light.png), [1920 dark](screenshots/ministry_leadership/leadership_1920_dark.png), [history](screenshots/ministry_leadership/leadership_history_dark.png).
- Configuration and appointment: [positions](screenshots/ministry_leadership/positions_1366_dark.png), [position form](screenshots/ministry_leadership/position_form_1366_dark.png), [assignment form](screenshots/ministry_leadership/assignment_form_1600_light.png), [member search](screenshots/ministry_leadership/leadership_member_picker_dark.png).
- Confirmations: [replacement](screenshots/ministry_leadership/leadership_replace_dark.png), [end assignment](screenshots/ministry_leadership/leadership_end_light.png), [membership](screenshots/ministry_leadership/leadership_membership_confirmation.png).
- Integration and access: [member profile](screenshots/ministry_leadership/leadership_member_profile.png), [leader reading controls](screenshots/ministry_leadership/leadership_leader_readonly.png).

## 13. Exact commands

From `D:\HOPFAN`:

```powershell
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m compileall -q src migrations tests
.venv\Scripts\python.exe -m unittest tests.test_attendance tests.test_session tests.test_ministry tests.test_ministry_migration tests.test_leadership tests.test_leadership_migration -v
.venv\Scripts\python.exe -m unittest tests.test_ui_smoke tests.test_ui_refinement tests.test_ui_ministry tests.test_ui_leadership -v
.venv\Scripts\python.exe hopfan.py
```

The migration is already applied locally. `upgrade head` is repeatable. Desktop tests require an interactive Windows desktop. Open Ministries, View a ministry, then Leadership; define positions before appointing officers.

## 14. Remaining decisions and limits

Administrators must choose each ministry's actual position titles and capacity; no default offices were guessed or hardcoded. Existing free-text participation titles are retained for review and are not automatically converted into dated assignments. Dates and office holders should be confirmed before those records are entered.

Scheduled future appointments and automatic term expiry require a separate agreed lifecycle. This module records already-started/open or completed terms. Software account creation and role/scope assignment continue through the existing separate administration process; recommendations based on offices are not automatically granted.

Dues, welfare, SMS, meetings, reporting pages and a redesigned dashboard remain future modules. The stable identifiers, current/history/vacancy service queries and audit records provide their foundation. Desktop verification covers the installed Windows DPI at 1366x768, 1600x900 and 1920x1080, with Windows chrome excluded, rather than every monitor/OS configuration. A full backup restore drill is still a separate operational check.
