# HOPFAN attendance and application correction report

Updated 5 October 2026. This report supersedes the earlier attendance-only report and follows the latest pasted attendance and full UI requirements.

The subsequent member form, dropdown and login refinements are documented in [UI refinement report](ui_refinement_report.md), including the current 36-check verification and screenshots.

Administrator ministry configuration, lifecycle, migration and member/attendance integration are documented in [Ministry Management report](ministry_management_report.md).

Configurable church positions, appointments, history and scoped profile integration are documented in [Ministry Leadership report](ministry_leadership_report.md).

## Delivered behavior

- A Sunday service is a global session with a saved whole-church roster. Administrator **All Members** and ministry filters read the same session and attendance records. Filtering never creates another session or roster.
- A leader with one assigned ministry opens Sunday attendance directly in that ministry view. Ministry and scope dropdowns are absent from that leader's ordinary workflow. Multiple-ministry users can choose only authorized ministries.
- Ministry meetings use all active ministry members automatically. Leadership meetings default to `MINISTRY_LEADERSHIP`; selected rosters are available through advanced options. Sunday creation has no advanced roster selector.
- The administrator directory includes sessions created by ministry leaders, their creator and creation time, scoped counts, state and view actions. Search, date, type, ministry and state filters use service queries. Leaders also have Upcoming, Draft, Open, Meetings and Sunday sections, with a scoped trend dialog.
- Attendance landing cards show today's sessions, open sessions, completed sessions and the weighted attendance rate for the six latest completed ministry meetings. Dashboard cards show permitted members, latest Sunday attendance, open sessions and ministry meetings, with upcoming/recent sessions and a meeting trend.
- Correction requires a reason, changes the same record, checks the expected previous status and records audit history. The original marker and mark time remain intact. Administrator corrections retain the session creator.
- Sessions support Draft, Open, Closed and Locked, with audited authorized transitions. Closing fills only the unmarked saved roster with Absent. Locked sessions require an explicit central unlock.
- The member directory and profiles enforce database permissions and ministry scope. Leaders receive read access to their assigned members; global member creation/editing requires explicit grants. Editing keeps existing ministry membership IDs and leadership positions.

## Application UI

Shared components now provide the app shell, role-aware sidebar, account/theme bar, page heading, action buttons, cards, entries, selectors, avatars, status badges, date controls, session rows, asynchronous loading and fixed-footer dialogs.

The dashboard controller, dashboard content, shell and future workspaces are separate files. The old unused member form implementation was removed; member forms and profiles use the same visual system as attendance.

Login preserves password **or** six-digit authenticator sign-in. Completing the authenticator code starts verification automatically. Database authentication runs off the UI thread. Password recovery retains its existing email → authenticator → new-password flow with a fixed action footer. Idle session expiry and persistent immediate light/dark switching remain in `hopfan.py`.

Members, Attendance, Ministries, Reports and Administration have useful, permission-aware pages. Sunday School, Finance, Welfare and SMS have consistent **Planned** workspaces; their underlying services are still future work and no financial totals or message delivery are fabricated. The leader sidebar omits church-wide Finance, Welfare and Administration unless the account receives their explicit grants.

Fonts use Segoe UI Variable with installed-font fallbacks. Image icons and adaptive light/dark colors are used throughout. Scrollable content and fixed action/pagination footers keep controls accessible on smaller desktops.

## Data and migration

The existing Alembic history is retained. Migration `4837e2db4cfd` adds the attendance lifecycle, saved rosters, scoped grants and audit tables. The subsequent reviewed forward migration `c603420e8020` changes the stored roster vocabulary from `EXECUTIVES` to `MINISTRY_LEADERSHIP` and seeds application grants. It does not rewrite saved roster members, attendance status, creators, markers or timestamps.

Before the latter migration, a PostgreSQL custom-format backup was saved at `backups/before_final_correction_20261005T120357Z.dump` and its archive listing verified. A full restore drill was not performed.

Original-column row fingerprints match the pre-upgrade snapshot for every existing member, ministry, user, attendance session and attendance record. Production contains the original 1 member, 14 ministries, 1 user, 1 session and 1 record. Test schemas are isolated and removed after the PostgreSQL suite. Alembic reports no pending schema operations.

The migration is intentionally forward-only. Production restoration uses the backup rather than deleting audit history through a destructive downgrade.

## Permissions and eligibility policy

Permissions come from active database roles; church titles and usernames do not imply access. Every attendance and member service request reloads the actor's grants. Attendance requires both the relevant permission and an active ministry assignment for scoped operations.

There are 16 attendance permissions and 12 application permissions. The existing Administrator role receives the application grants; the generic Ministry Attendance Leader role receives own-ministry member, ministry and SMS workspace grants. The latter grants do not implement SMS sending. Existing users are not automatically assigned new ministries. Scope management uses the Administration/Attendance access dialog and writes authorization history.

Leadership roster eligibility uses the existing active `MemberMinistry.position_title` field: active ministry members with a nonblank assigned position are included. No church title grants software access. Saved rosters are frozen when a session is created, including Draft sessions; later membership changes do not silently alter historical eligibility.

Ordinary leaders can correct Open sessions in their assigned scope. Correcting Closed sessions requires `ATTENDANCE_CORRECT_CLOSED`; reopening, locking and unlocking have separate grants.

## Verification

30 checks passed: 20 PostgreSQL business-rule tests, 3 idle-session tests and 7 desktop UI tests. The PostgreSQL and idle-session suites cover shared Sunday views and record uniqueness, direct-service scope denials, selected and leadership rosters, leader-created session oversight, original-marker preservation, reason-required correction history, lifecycle rules, stale/concurrent marking, revoked grants, scoped exports/audit, bounded query counts, real scoped dashboard aggregates, scoped member access and membership preservation.

The desktop suite uses synthetic data and checks both roles, all three requested display sizes (1366×768, 1600×900, 1920×1080), both themes, fixed footers, safe retry after a photo failure, scoped navigation, Sunday defaults, progressive roster options, unchanged row reuse, alternative sign-in paths, date/year selection and modal handling. Screenshots are under `logs/ui_smoke/`; representative synthetic screenshots are included under `docs/screenshots/`.

Desktop checks simulate the client viewport at the installed Windows DPI; they do not change the physical monitor settings. Window captures prevent the taskbar from covering the larger simulated viewport. Manual screenshot review checked the three sizes, both themes, login, dashboards, member directory/form/profile, attendance, creation and future-module shells. A compact header and nonempty calendar icons were corrected during this review.

- [Administrator dashboard, light](screenshots/admin_home_1366_light.png)
- [Leader dashboard, dark](screenshots/leader_home_1366_dark.png)
- [Leader attendance, light](screenshots/leader_attendance_landing_1366_light.png)
- [Administrator attendance, dark, 1920 viewport](screenshots/admin_attendance_landing_1920_dark.png)
- [Login, light](screenshots/login_password_1366_light.png)
- [Member profile, dark](screenshots/leader_member_profile_1366_dark.png)

```powershell
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m unittest tests.test_attendance tests.test_session
.venv\Scripts\python.exe -m unittest tests.test_ui_smoke
.venv\Scripts\python.exe hopfan.py
```

Roster pages contain at most 30 rows, member directory pages 40, and session pages 25. Searches are debounced and database work runs in worker threads. Unchanged attendance rows are retained during refresh; only changed rows are rebuilt. Counts and permission checks use bounded joins/set queries instead of per-member database queries.

## Remaining operational setup

Assign actual officer accounts to their ministries through the access dialog. No production leader accounts or memberships were invented. Finance, Welfare, Sunday School and SMS need their own services before those planned workspaces become operational. Leadership positions must be maintained in the existing ministry membership data for the leadership roster to be populated.

User administration, RBAC and ministry scopes: [implementation report](user_administration_report.md).
