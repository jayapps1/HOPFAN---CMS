# HOPFAN Household and Family Management

Implemented in the existing desktop project on 5 October 2026. Local migration **b62d08e4c715** is applied. Restart HOPFAN and open **Members → Households**. The Administrator can create families, link existing members, manage heads, move/remove members and inspect retained history.

The verified backup is `backups/before_user_administration_20261005T221104Z.dump`, with its matching `_snapshot.json`. Original-column fingerprints match across all 19 existing application tables, including the 70 ministry positions and current leadership/attendance records. The module adds no example households or duplicate members. Seeded-admin sign-in, household permissions and member-profile integration passed against the upgraded database; verification-only login changes were rolled back.

## 1. Files created

- `src/models/household.py`: Household, HouseholdMember and HouseholdAuditLog.
- `src/security/household_permissions.py`: permissions, friendly relationship labels and minor-age policy.
- `src/services/household_service.py`: authorization, validation, pagination, atomic relationships and audit.
- `src/ui/households/__init__.py`, `households_view.py`, `dialogs.py`: workspace, profiles, forms and confirmations.
- `migrations/versions/b62d08e4c715_household_management.py`: additive forward migration.
- `tests/test_household.py`, `test_household_migration.py`: PostgreSQL rules, access, concurrency and migration preservation.
- `tests/household_preview.py`, `test_ui_household.py`: synthetic desktop fixtures and interaction/layout tests.
- This report and synthetic screenshots in `docs/screenshots/households/`.

## 2. Files changed

- `src/models/__init__.py`: model registration.
- `src/security/application_permissions.py`: permission catalogue and family navigation.
- `src/services/member_service.py`: authorized live household summary on member profiles.
- `src/ui/members/members_view.py`: Households action and Household / Family section.
- `src/ui/dashboard/dashboard_view.py`: household routing and a family-only workspace without member-directory queries.
- `src/ui/dashboard/home_view.py`: member statistics require member-directory access even when family access supplies the Members navigation entry.
- `src/ui/components/modern.py`: optional compact StatCard variant used by family profiles.
- `tests/test_administration_migration.py`: retains pinned preservation assertions, then upgrades to the current head before comparing current metadata.
- `docs/attendance_upgrade_report.md`: report link. Attendance implementation is unchanged.

## 3. Models and tables

`households` uses UUID identity, editable non-unique name, generated unique code, optional primary address/phone/notes, Active/Inactive/Archived status, actor identifiers and timestamps. Names do not identify records.

`household_members` stores its UUID, existing household/member UUIDs, relationship, head flag, joined/left DATE values, current flag, optional relationship notes and timestamps. It contains no copied member names, DOB, gender, contact fields or photographs. Each person remains one master Member.

Partial unique indexes enforce one current household per member and one current head per household. Checks enforce supported relationships, head/relationship consistency and coherent dates/current state. Household/member foreign keys use RESTRICT, preventing household deletion from cascading into members.

`household_audit_logs` retains household/member/membership snapshot identifiers, actor, action, before/after metadata and timestamp. Household identifiers are snapshots so creation/deletion audits survive deletion of an unused household. Private addresses, phone values and notes are excluded from audit payloads; contact edits record changed field names. Generic logs receive exception types only.

## 4. Alembic revision

**b62d08e4c715**, parent **a91c73d5f204**, adds three tables, checks/indexes and eight permissions. No existing Member IDs, columns, ministry relationships, user credentials or attendance records are rewritten.

The real migration chain passed in a disposable schema with original-row preservation checks. The backed-up local forward upgrade and preservation guard also passed. Alembic reports **No new upgrade operations detected**. Downgrade is forward-only; the verified pre-upgrade archive remains available.

## 5. Permissions

| Permission | Access |
| --- | --- |
| `HOUSEHOLD_VIEW` | Read the current household linked to the account's own Member |
| `HOUSEHOLD_VIEW_ALL` | Read all households, retained relationships and audit |
| `HOUSEHOLD_CREATE` | Create households |
| `HOUSEHOLD_EDIT` | Edit household metadata, current relationships and heads |
| `HOUSEHOLD_ADD_MEMBER` | Add existing members |
| `HOUSEHOLD_REMOVE_MEMBER` | End a membership; also required for moving |
| `HOUSEHOLD_ARCHIVE` | Archive and restore households |
| `HOUSEHOLD_DELETE_UNUSED` | Delete households with no membership history |

The established Administrator receives these grants once during migration, with a security audit event. Ministry leaders and technical System Administrators receive no automatic family grants. Active account, role, permission and required-password-change state are checked on every request.

Writes require View All plus the operation permission. Master-member search additionally requires `MEMBERS_VIEW_ALL`; creating a missing member follows `MEMBERS_CREATE` in the normal MemberService. Moving requires Add and Remove; replacing a head also requires Edit. Own-family viewers receive current family data without unassigned-member, past-membership, audit or unrestricted family-directory access.

## 6. Service methods

`HouseholdService` provides `capabilities`, `list_households`, `get_household`, `get_household_stats`, `create_household`, `update_household`, `archive_household`, `restore_household`, `delete_unused_household`, `candidate_members`, `get_household_members`, `get_member_household`, `add_member`, `move_member`, `remove_member`, `update_relationship`, `change_household_head` and `audit_events`.

The shared `member_household` query supplies authorized profile summaries. Directory head/count/history are obtained through aggregate/subqueries; query count is independent of the number of rows. Search and family results are paginated and bounded to 100 rows per request. UI callbacks call services rather than SQL.

All writes run under a PostgreSQL transaction advisory lock; unique indexes provide another safeguard. Moves and head transitions commit together or roll back completely. Timestamp checks reject stale confirmations and edits.

## 7. UI implemented

Members → Households includes Create Household, four summary cards, household/member/code/phone search, status filters, scrolling pagination, View/Edit actions and empty states. The Members Without Household card opens a searchable unassigned-member list when permitted.

Profiles show head, contact details, total/adults/children/dependants, avatars, relationship, calculated age/DOB, phone, member status and membership dates. Current Members, Past Memberships and Audit History are separate views. Create/edit, add, relationship editing, controlled head change, effective-date removal, archive/restore and unused-household deletion use fixed-footer dialogs. Status/relationship inputs use ModernSelect; dates use the shared DatePicker with direct month/year navigation.

Move and head-replacement dialogs identify the existing relationship. Cancel preserves it. The previous head's new relationship is chosen explicitly when promoting an existing family member. Background workers receive captured form values; they do not read Tk fields. Member selection and nested form closure restore the proper modal focus.

Synthetic captures: [1366 light directory](screenshots/households/households_1366_light.png), [1920 dark directory](screenshots/households/households_1920_dark.png), [household profile](screenshots/households/household_profile_1366_light.png), [create household](screenshots/households/household_form_1366_light.png), [add family member](screenshots/households/family_member_form_1366_dark.png), [unassigned search](screenshots/households/members_without_household_search.png), [own-family view](screenshots/households/own_household_readonly.png).

## 8. Member integration

The Member profile reads household name, relationship, head and current family count through normalized links. View Household opens the authorized family profile. Ministry-member access alone supplies no family payload.

Add New Member launches the existing member form, then selects its returned master record in the household flow. It creates one Member. Household changes leave personal details, marital status, ministry participation, roles and scopes to their respective modules. There is no redundant spouse column or duplicate child database.

## 9. History and lifecycle

Removal sets `left_at` and `is_active=False`, preserving the UUID, joined date, relationship and notes. Historical links are retained; rejoining creates a new link. A known joined date cannot predate the last exit. Changing head atomically demotes the previous head and promotes the selected member, with audit history.

Archive closes current memberships on the chosen effective date and retains history. Restore makes the household Active without reopening old links. Inactive households retain current links but reject new assignment. Permanent deletion requires confirmation and no membership history. Creation audits reserve generated household codes even after unused-household deletion, preventing code reuse. No lifecycle operation deletes church members.

## 10. Tests performed

Fourteen household service cases cover required A–K behavior, optional-head creation/moves, one-current/head constraints, rollback, concurrency, stale changes, archive/restore, protected deletion, retained codes, relationship edits, age/unknown DOB, dependants, search and constant directory query count. The real migration case verifies original records, RESTRICT links and explicit family grants.

Nine desktop cases cover the three sizes/both themes, fixed footers, household lifecycle, canceled/confirmed moves, head replacement, notes editing, normal member creation, profile integration, own-family controls, unassigned insight and family-only/mixed-access dashboards. Screenshots target synthetic application windows. The final compact profile check verifies that the whole first family row fits the actual minimum-size scroll viewport.

**127 distinct tests passed** across database/session and desktop checks: 75 existing database/session cases, 14 household service cases, one household migration case, 28 existing desktop cases and nine household desktop cases. The combined existing desktop run had one Administration directory mount timeout; that layout case passed in isolation at all sizes/themes. Household failures found during implementation were corrected and their affected cases rerun successfully. The final compact layout and operational/technical dashboard checks also passed. Syntax compilation and `git diff --check` pass.

## 11. Exact commands

From `D:\HOPFAN`:

```powershell
.venv\Scripts\python.exe -m compileall -q src migrations tests scripts
.venv\Scripts\python.exe -m unittest tests.test_household tests.test_household_migration -v
.venv\Scripts\python.exe -m unittest tests.test_ui_household -v
.venv\Scripts\python.exe -m unittest tests.test_administration tests.test_attendance.AttendanceTests tests.test_ministry.MinistryTests tests.test_leadership.LeadershipTests tests.test_session tests.test_seed_ministry_positions tests.test_administration_migration tests.test_ministry_migration tests.test_leadership_migration -q
.venv\Scripts\python.exe -m unittest tests.test_ui_smoke tests.test_ui_refinement tests.test_ui_ministry tests.test_ui_leadership tests.test_ui_administration -q
.venv\Scripts\python.exe hopfan.py
```

Installation/preservation commands already completed locally:

```powershell
.venv\Scripts\python.exe -m scripts.upgrade_guard backup
.venv\Scripts\python.exe -m alembic upgrade b62d08e4c715
.venv\Scripts\python.exe -m scripts.upgrade_guard verify backups/before_user_administration_20261005T221104Z_snapshot.json
.venv\Scripts\python.exe -m alembic check
```

The preservation snapshot verifies this upgrade, rather than unrelated later administrator changes. Desktop tests require an interactive Windows desktop. A checkout using another database needs its own verified backup and `alembic upgrade head`.

## 12. Remaining policy decisions

- Minor classification uses age 18, defined in `household_permissions.MINOR_AGE`. Unknown DOB remains unknown. An administrator setting can be added later.
- Own-family access follows explicitly linked `User.member_id`. Further family delegation would need its own explicit scopes; ministry scopes confer no family access.
- Heads are optional during setup. Removing/moving a head leaves a vacancy until explicitly replaced. Gender and replacement choices are never inferred.
- Archiving closes current links; restoration requires new assignments. Member status changes do not silently change family links.
- Sunday School, welfare, emergency-contact changes, future-dated transitions and automatic relationship inference remain separate work. Existing Member/emergency-contact fields are preserved. A full backup restore drill remains a separate operational check.
