# HOPFAN Sunday School Management

Implemented 6 October 2026 in the existing Python desktop application. Local migration **c84e26f7a930** is applied. Sunday School references the existing Member and Household records and keeps class attendance separate from church attendance. Restart HOPFAN and open **Sunday School** in the sidebar for Overview, Students, Classes, Attendance, Lessons, Teachers and Reports.

## 1. Files created

- `src/models/sunday_school.py`: twelve normalized school, history, access and attendance models.
- `src/security/sunday_school_permissions.py`: capability catalogue and friendly teaching/guardian labels.
- `src/services/sunday_school_base.py`: shared authorization, date/identity validation, live contacts and audit.
- `src/services/sunday_school_service.py`: classes, students, enrollment, movement, teachers, guardians and recipient resolution.
- `src/services/sunday_school_attendance_service.py`: class sessions, saved rosters, marking, correction and lifecycle.
- `src/services/sunday_school_lesson_service.py`: normalized single/multiple/all-class lesson plans.
- `src/services/sunday_school_report_service.py`: scoped dashboard, ten baseline reports and CSV export.
- `src/ui/sunday_school/__init__.py`, `workspace.py`, `dialogs.py`: desktop pages, profiles, forms and confirmations.
- `migrations/versions/c84e26f7a930_add_sunday_school_classes_enrollment_.py`.
- `tests/test_sunday_school.py`, `test_sunday_school_migration.py`, `test_ui_sunday_school.py`.
- This report and synthetic captures in `docs/screenshots/sunday_school/`.
- `scripts/run_desktop_checks.py`: repeatable Tk owner-thread desktop validation runner.

## 2. Files changed

- Model registration and application permission/navigation catalogue.
- MemberService and Member profile: authorized Sunday School class, teacher and attendance summary.
- HouseholdService and household profile: authorized children's current class information, queried from enrollment.
- UserService and account dialogs: explicit Sunday School class scopes, retained inactive scopes, audit and session revision invalidation.
- DashboardView: the real Sunday School workspace replaces the future-module destination.
- The household migration test keeps its pinned assertions, then checks current metadata after upgrading to the latest head.
- Attendance report: links this report. General church attendance services/tables are unchanged.

## 3. Database tables

| Table | Purpose |
| --- | --- |
| `sunday_school_classes` | Administrator-configured names/codes, age guidance, rooms, capacities and status |
| `sunday_school_students` | One extension per existing Member; admission date/status and restricted school notes |
| `sunday_school_enrollments` | Dated class enrollment history and one current class per Member |
| `sunday_school_teacher_assignments` | Existing Member teacher/assistant/coordinator assignments and history |
| `sunday_school_guardians` | Existing Member guardian preferences, primary contact and explicit SMS consent |
| `sunday_school_user_class_scopes` | Explicit account location grants, independent of teaching assignments |
| `sunday_school_lessons` | One lesson plan and its date/topic/scripture/objective/summary/teaching notes |
| `sunday_school_lesson_classes` | A lesson shared across several classes without duplicating it |
| `sunday_school_attendance_sessions` | One class/date session, optional lesson and Draft/Open/Closed lifecycle |
| `sunday_school_roster_members` | Saved eligible Member/enrollment identifiers at opening |
| `sunday_school_attendance_records` | One result per session/Member with original marker/time |
| `sunday_school_audit_logs` | Operational changes and corrections without copied private child/contact data |

No child or teacher name, DOB, phone, address or age is stored as a duplicate identity. Student member_id is unique. Guardian member links, teacher assignments and enrollment reference the master register. Age is calculated. No medical/support-specific field was added without an agreed policy.

Partial unique indexes enforce one current enrollment per Member, one current teaching assignment per class/Member and one active primary guardian. Attendance records are unique per session/Member and have a composite foreign key to the saved roster. Enrollment also references the registered student extension. Identity/history foreign keys use RESTRICT.

## 4. Alembic revision

Forward revision **c84e26f7a930**, parent **b62d08e4c715**. The reviewed migration adds only Sunday School structures and new access-catalogue entries. It contains no existing-table drops, member/user rewrites or database reset. Downgrade is forward-only.

The real migration passed in a generated private schema. Every existing table's original rows were checked, allowing only the intended role/permission/security-audit additions. New operational school tables start empty; no class names or sample students are seeded. `alembic check` passed after the private migration.

The verified pre-upgrade archive is `backups/before_user_administration_20261006T045508Z.dump`, with its matching `_snapshot.json`. The local upgrade passed its original-row preservation checks across all 22 existing application tables. Alembic reports no pending changes. Seeded-admin sign-in and the real school directory/dashboard services passed with verification-only login changes rolled back. All twelve operational school tables start empty.

## 5. Permissions added

Existing `SUNDAY_SCHOOL_VIEW` is reused. Twenty-seven additional permissions provide:

- Sunday School-wide access and explicit class view/create/edit/lifecycle/delete-unused.
- Student view/enrollment/movement/end/admission editing.
- Guardian operational view and preference/consent management.
- Teacher view/assignment/ending.
- Lesson view/create/edit.
- Attendance view/create/record/correct/close/reopen.
- Report view/export.

The full catalogue is in `sunday_school_permissions.py`. The existing Administrator receives new grants once; an existing removed workspace-view grant is not restored. New baseline Sunday School Teacher and Coordinator roles are created only if missing; existing roles are not reset. Technical administrators and ministry leaders receive no automatic child-data permissions.

Every service reloads active account/role/permission data and intersects non-global access with explicit account class scopes. Being a church teacher does not create a login, role or scope. Ending a teaching assignment does not silently rewrite account access; administrators manage that separately through **Administration → Users → Edit access → Sunday School class scopes**.

## 6. Services created

`SundaySchoolService` exposes class CRUD/lifecycle, class options, admission, list/get students, enroll/move/end, student status, teachers/ending, guardian preferences/candidates, profile summaries and future recipient resolution.

`SundaySchoolAttendanceService` exposes create/list/get/open sessions, saved rosters, mark/correct, close/reopen and statistics. `SundaySchoolLessonService` exposes create/list/get/update with single/multiple/all-class scopes. `SundaySchoolReportService` exposes dashboard, baseline report and authorized CSV export.

Services accept account UUIDs and injectable SQLAlchemy session factories. Domain errors distinguish denial, age guidance and controlled-move requirements. Mutations use transactions and a PostgreSQL advisory lock; unique/check/FK constraints provide additional protection. Timestamps guard stale changes. A failed move leaves the old enrollment current.

Account directory scopes are batched into one location query; the existing fixed query-count test still passes. Class/student/contact queries use joins and grouped/batched results rather than one query for each row.

## 7. UI screens

- Overview: student/class/teacher/last-Sunday/rate cards, quick actions, class attendance, upcoming lessons, absences and unassigned admission.
- Classes: age guidance, room, counts, capacities, status, create/edit/profile and protected lifecycle.
- Students: admission and attendance summary cards; class, age, status and permitted gender filters; avatars, guardian contacts and profiles.
- Teachers: current/history, existing Member selection, teacher/assistant/coordinator roles, multiple staff and dated ending.
- Lessons: Upcoming/Recent/Draft/Published/Archived, normalized multi-class selection, objectives/scripture/summary/teaching notes and publication.
- Attendance: class sessions, planned/open/closed status, compact roster, search/status filtering, fixed counters and fast mark/correct actions.
- Reports: enrollment/class size/age distribution/date/student/trend/absence/staff/unassigned/lesson delivery, date/class filters and CSV export.

All dropdowns/date controls use existing modern components. Forms have fixed action footers; long lists scroll and paginate. Child/teacher/guardian choice uses searchable Member selection rather than a giant identity dropdown. Screens are checked at 1366×768, 1600×900 and 1920×1080 in light/dark themes. Synthetic screenshots target the application window, not the desktop.

## 8. Member integration

Enrollment and teaching assignment preserve the same Member UUID. Register New Member reuses the normal member form, then returns its existing master record to admission. No separate child registration database is introduced.

Authorized Member profiles show current class, term start, attendance summary where permitted and teaching assignments. Sunday School access does not confer unrestricted Member-directory editing. Missing DOB remains Age unavailable; age ranges are guidance with an explicit audited override rather than automatic promotion.

## 9. Household integration

Household names and current relatives are read from normalized family links. Guardian preferences are separate because the Household model cannot identify each child's operational guardian, primary contact and consent. Selecting a household contact does not infer biological father/mother or modify gender.

Teachers receive only authorized class-student guardian contact information, not unrestricted family records or restricted admission notes. Names and phones are read live from Member records. Consent starts false. Recipient resolution deduplicates existing guardian members, skips deceased contacts and returns only consented phone contacts; it sends no messages and integrates no provider.

Household member rows can show their current Sunday School class when the viewer also has the relevant school permission. No household class field is stored.

## 10. Attendance implementation

School sessions/records/rosters are separate from main church attendance. Opening saves only current active students of that class whose enrollment has started. Subsequent moves/admission changes do not rewrite the saved roster.

Marking is idempotent for the same status; changing an existing mark requires correction permission and a reason. Correction updates the same record and retains the original marker/time, adding audit history. Closing adds Absent only for unmarked saved members of that class. Ordinary scoped teachers cannot correct or reopen closed sessions; that requires Sunday School-wide authority.

Future sessions can be planned, then opened on/after their date. Published lessons must apply to the class and match the session date. Used lesson date/class scope cannot be changed incompatibly. Reopening preserves roster, marks and history.

Attendance rate counts Present/Late against eligible closed-session students excluding Excused. Dashboard rates cover 30 days; Last Sunday is the actual latest Sunday date. Lessons Delivered counts published lesson links on closed class sessions.

## 11. API-readiness decisions

Models and services import no CustomTkinter. Authorization and business rules are enforced by services, not hidden buttons. Responses use dictionaries, UUID strings, dates and timestamps suitable for a future FastAPI serialization layer. Session factories/account identities can be injected per request.

No FastAPI server, portal/PWA, unsafe bulk promotion, SMS provider or automatic birthday movement is built here. Existing normalized references, class scopes and domain methods are their foundation. CSV output neutralizes spreadsheet formula prefixes and requires explicit export permission.

## 12. Tests performed

The full isolated database/session run passed **105 cases**, including Sunday School service/migration tests plus the existing household, member, church-attendance, ministry, leadership, user administration and session suites.

School coverage includes identity preservation, one current class, atomic movement/rollback, age overrides/capacity, staff without account creation, service-driven class denial, same-record correction, saved roster closure, DB uniqueness/eligibility, live guardians/consent, shared lessons, planned sessions, reports/CSV, constant class query count, restricted notes, account scopes and profile integration.

**146 distinct checks passed**: 105 database/session cases, four Sunday School desktop cases and all 37 existing desktop regressions. The final desktop runs collect Tk widget cycles on the owner thread, avoiding Python 3.14 worker-thread cleanup errors seen during the initial combined validation. School cases cover all pages/sizes/themes/forms, admission/search/movement/staff, class-scoped roster marking/correction/closure and account class-scope selection. Seventy-two synthetic screenshots were captured with one modal open at a time. The private UI schema was removed. Syntax, migration validation, local upgrade and original-row preservation pass.

Representative captures: [student directory](screenshots/sunday_school/students_1366_dark.png), [class roster](screenshots/sunday_school/roster_1366_light.png), [overview](screenshots/sunday_school/overview_1366_light.png), [class form](screenshots/sunday_school/class_form_1366_light.png), [lesson form](screenshots/sunday_school/lesson_form_1366_dark.png).

## 13. Exact commands

From `D:\HOPFAN`:

```powershell
.venv\Scripts\python.exe -m compileall -q src migrations tests scripts
.venv\Scripts\python.exe -m unittest tests.test_sunday_school tests.test_sunday_school_migration -v
.venv\Scripts\python.exe -m unittest tests.test_ui_sunday_school -v
.venv\Scripts\python.exe -m scripts.run_desktop_checks
.venv\Scripts\python.exe -m unittest tests.test_administration tests.test_attendance.AttendanceTests tests.test_ministry.MinistryTests tests.test_leadership.LeadershipTests tests.test_session tests.test_seed_ministry_positions tests.test_household tests.test_household_migration tests.test_administration_migration tests.test_ministry_migration tests.test_leadership_migration tests.test_sunday_school tests.test_sunday_school_migration -q
.venv\Scripts\python.exe -m alembic upgrade c84e26f7a930
.venv\Scripts\python.exe -m scripts.upgrade_guard verify backups/before_user_administration_20261006T045508Z_snapshot.json
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe hopfan.py
```

Migration/preservation checks apply immediately to this backup/upgrade. Future administrator changes legitimately alter its baseline. Other databases need their own verified backup before `alembic upgrade head`.

## 14. Remaining decisions

- Class names, age ranges, capacities and teacher limits are configured by administrators; none are seeded as church policy.
- Current policy allows one class per student and one session per class/day. Exceptions, future-dated transitions and reviewed bulk promotion require an agreed extension.
- Class scopes are explicit account administration. Teaching membership and account privileges remain separate.
- Medical/support-specific information, child pickup authority, parent portal authentication and messaging consent/provider policy require separate decisions.
- Guardian identity/relationship/primary contact are explicit; household head or spouse is not automatically a biological parent.
- Existing private child notes remain office-only. A broader staff-note policy needs explicit permission design.
- A full backup restore drill and future API/PWA deployment are separate operational tasks.
