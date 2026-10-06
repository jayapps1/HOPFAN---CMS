# HOPFAN online platform: Phase 4 implementation report

Verified on 2026-10-06 in the existing D:\HOPFAN workspace. This phase adds authenticated business reads and real portal summaries using the existing PostgreSQL database, member identities, RBAC and domain services.

## 1. Existing code inspected

Inspected the Member/MemberMinistry/Ministry/MinistryPosition/MinistryLeadershipAssignment models; household and Sunday School relationships; MemberService, MinistryService, MinistryLeadershipService, AttendanceService, household and school services; AuthorizationService and its global equivalents/legacy attendance restrictions; FastAPI database/session/CSRF dependencies and error handling; and the Next.js authentication, workspace, permission, navigation, dashboard and client contracts.

## 2. Backend files created

- src/services/online_workspace_service.py: safe read projections and orchestration over shared domain services.
- src/services/member_photo_service.py: authorized reads from the existing private photo directory.
- src/api/schemas/workspace.py: explicit nested response allowlists and paginated contracts.
- src/api/v1/workspace.py: thin synchronous authenticated routes.
- tests/test_online_workspace.py: 20 PostgreSQL API integration cases.
- scripts/check_desktop_startup.py: observe and close only the actual test application instance.

## 3. Backend files extended

MemberService shares visibility, filtering, sorting, paging and aggregate counts between desktop and API; its original list return type and default stats keys remain compatible. MinistryService accepts an optional ministry filter and allows API reads to skip desktop-only dependency reflection. SundaySchoolReportService supports class-specific dashboard counts, attendance and absence queries. API dependencies borrow the existing request session and translate domain authorization/database failures into safe responses. The v1 router and published-route contract test include the new routes. The controlled browser fixture now has synthetic business relationships in its disposable schema.

## 4. Frontend files created

New static directory and nested profile routes under web/src/app/portal/members and ministries. web/src/features/workspace contains directories, profiles, record/feedback components and use-resource.ts. web/src/lib/api/workspace.ts defines and validates the business response contracts. web/tests/workspace.test.ts and web/e2e/workspace.spec.ts verify private reads and browser behavior.

## 5. Frontend files extended

Dashboard now loads real metrics and recent permitted members. WorkspaceProvider adds global member-directory filter options and preserves/reset URL page state appropriately. ApiClient adds typed authenticated GETs with cancellation and no-store, and bounded member-photo URL construction. Sidebar/breadcrumbs recognize detail routes. Permission navigation follows actual ministry configuration visibility. Existing CSS gains tables, mobile cards, profile sections, metrics and ministry tabs.

## 6. Implemented GET endpoints

All business endpoints require the existing browser session. UUIDs, filter values, search lengths and pagination are validated.

| Endpoint | Purpose |
| --- | --- |
| /api/v1/members | Scoped/global member directory |
| /api/v1/members/options | Permitted active ministry metadata for member filters |
| /api/v1/members/{member_id} | Safe member profile |
| /api/v1/media/member-photo/{member_id} | Authorized bounded private photo |
| /api/v1/ministries | Scoped/global ministry directory |
| /api/v1/ministries/{ministry_id} | Safe overview and permitted counts |
| /api/v1/ministries/{ministry_id}/members | Current roster with pagination/search/status/sort |
| /api/v1/ministries/{ministry_id}/leadership | Configured current appointments with pagination |
| /api/v1/dashboard | Permission-checked live summaries; optional ministry_id/class_id |

## 7. Member permission rules

MEMBERS_VIEW_ALL reads the master directory without individual scope assignments. MEMBERS_VIEW_OWN_MINISTRY reads members with current memberships in active assigned ministries. The existing authorization context intersects permissions with ministry grants; a title or ministry leadership appointment grants no software access. Out-of-scope profile/photo/filter requests return 403. One master Member is returned once even when it belongs to Youth and Choir. Scoped profile/list ministry labels are restricted to permitted ministries.

Responses explicitly select identity, operational contact and membership fields. Existing leadership, household and Sunday School services determine which optional sections may appear. Household projection contains only its identity/status and the member relationship; school projection contains enrollment/teaching summaries. Notes, household contact details, guardian records, welfare/finance information, account-existence flags, audit internals, password/TOTP fields and local photo paths are excluded. Unauthorized optional sections are omitted.

## 8. Ministry authorization rules

MINISTRIES_VIEW_ALL reads all configuration. MINISTRIES_VIEW_OWN is restricted to assigned ministries, with existing historical access rules retained. Roster reads additionally require member permission for that ministry. Leadership additionally requires MINISTRY_LEADERSHIP_VIEW_ALL or the scoped leadership grant. Member counts are null when member permission is absent; leadership summaries/tabs are absent or disabled when leadership permission is absent. Leadership names, office codes, holders and dates come from existing configured positions and assignments.

## 9. Dashboard metrics implemented

Member access provides total and active members, members added in the last 30 days and five recent entries. Ministry access provides active ministry counts. A selected permitted ministry also exposes its current appointments and vacancies when leadership access is granted. School access provides permitted class/student/teacher counts and attendance rate when corresponding grants/data exist; class selection restricts students as well as classes. Attendance readers receive actual operational counts; selected ministries receive scoped visible session counts and latest closed Sunday attendance when available. Shared service attendance is counted through existing roster scope checks.

Each metric is independently permission-checked. Missing permission/data is represented by an unavailable category or omitted metric, with genuine zero counts retained. No finance, giving, welfare or administration totals are emitted.

## 10. Photo and media strategy

The photo route authorizes the member before filesystem access and uses the existing assets/member_photos storage. Canonical paths must remain within that directory; extensions, file size and pixel counts are bounded. Missing, corrupt or escaped paths return a safe 404. The server emits a JPEG thumbnail of at most 512 pixels per side and strips original metadata by re-encoding. Images and all private JSON responses use no-store. The portal requests the private image directly and falls back to initials after failure.

## 11. Pagination and search behavior

Lists return items/page/page_size/total/pages. Default page size is 25 and maximum is 100. Database filters, counts, limits and offsets are applied before materializing results. Member search covers full name, member number, phone and email with escaped literal wildcard characters. Member statuses and ministry/category statuses are whitelisted. Member sorts are name/member_no/joined_date with asc/desc direction and an ID tiebreaker. The internal dashboard recent sort is not exposed as an arbitrary public SQL sort.

## 12. Global versus scoped behavior

Administrator reads without assigned ministries return global data. A church secretary with global member access and no ministry administration permission can read/filter all members and receive member summaries, while ministry configuration remains denied. Revoking an administrator role's other permissions immediately removes member reads/counts even though the role still has an administrator title.

Youth officer/leader grants and Women officer/leader grants are isolated. Shared scoped officer grants also cover the youth-secretary and treasurer read capability pattern; the backend reads effective permissions, not office titles. API tests exercise admin, global church secretary, Youth, Women, multi-ministry treasurer, Sunday School teacher and a position-only account. Browser tests cover administrator, secretary, overseer, Youth officer, multi-scope officer and teacher presentations. Teachers without member/ministry read grants cannot open those directories or profiles.

## 13. Multi-scope behavior

Youth+Choir viewers can select either workspace and see the same shared master member. Women remains denied. Direct member, ministry, roster, leadership, photo and dashboard identifier tampering is tested through actual authenticated endpoints and browser requests. Authorized-to-denied profile navigation hides the previous profile. Scope switching updates live data without refetching the entire authentication context.

## 14. Tests and results

- 115 API/session/readiness/migration tests passed, including all 20 new business integration cases.
- 23 frontend unit tests passed.
- 17 Chromium browser tests passed.
- 57 existing ministry, leadership, administration/session and Sunday School service tests passed.
- 4 actual Windows desktop member/ministry UI tests passed.
- TypeScript, ESLint and production builds passed.

Total: 216 automated test cases. Business browser views were verified at 1920, 1600, 1366, 1024, 768 and 390 pixels in light and dark themes with no horizontal overflow. axe WCAG 2 A/AA checks passed for the new views at 1366 and 390 pixels in both themes, alongside existing login/dashboard checks. Forty-eight synthetic business screenshots are in [screenshots/online-workspaces](screenshots/online-workspaces/).

## 15. URL tampering and stale-data tests

Direct out-of-scope member, ministry, roster, leadership, photo and dashboard identifiers return 403 through real authenticated endpoints. These checks also run from Chromium. Authorized-to-denied profile navigation hides previous details; multi-scope switching removes unrelated rows and does not refetch /me.

Directories have URL-backed search/status/category/sort/page controls and workspace ministry filtering. Desktop member tables become cards at narrow widths. Profiles have back navigation and explicit safe sections. Ministry profiles have overview/members/leadership navigation gated by server capabilities. Loading skeletons, empty results, recoverable errors/retry, unavailable summaries and access denied are implemented. Quick actions link to implemented member/ministry reads.

Response state is keyed by user, effective access, scope and request URL; changes immediately hide old responses and abort pending requests. Private data remains in memory and is cleared on session loss. No private data is embedded by Server Components or saved to browser storage.

## 16. Performance considerations

A disposable database test uses 2,126 master members, requests page 15 with 100 items, verifies the total and SQL LIMIT/OFFSET, and enforces an upper bound of 25 request SQL statements including authentication/authorization and relationship loading. Existing ministry aggregate query-count regression tests also pass. ORM select-in loading and correlated membership existence avoid per-row requests and duplicate members.

## 17. Desktop regression and database preservation

The actual hopfan.py process opened, ran for 31 observed seconds and closed cleanly without signing in. Member form and ministry workflows were exercised in both themes and desktop resolutions. Verification against backups/before_user_administration_20261006T111433Z_snapshot.json confirmed original records in all 34 existing tables were preserved. Phase 4 needs no migration and does not seed, reset or alter live identity/business records. Alembic head remains d95f13b8e204. Test schemas use strictly named disposable fixtures and are cleaned up.

## 18. Exact backend command

From D:\HOPFAN:

~~~powershell
.venv\Scripts\python.exe run_api.py
~~~

Use the existing approved environment configuration. No new migration is required.

## 19. Exact frontend command and validation commands

From D:\HOPFAN, start the existing backend:

~~~powershell
.venv\Scripts\python.exe run_api.py
~~~

In another PowerShell terminal:

~~~powershell
cd D:\HOPFAN\web
npm.cmd run dev
~~~

Open http://localhost:3000/login and sign in with an existing permitted HOPFAN account. Keep both browser-facing portal/API URLs on localhost in development. Existing production HTTPS/cookie/CORS requirements remain in [online_api_setup.md](online_api_setup.md).

Validation commands from the repository root:

~~~powershell
.venv\Scripts\python.exe -m pytest tests/test_online_workspace.py tests/test_api.py tests/test_web_auth.py tests/test_web_sessions_migration.py -q --tb=short -p no:cacheprovider
.venv\Scripts\python.exe -m unittest tests.test_ministry tests.test_leadership tests.test_administration tests.test_session tests.test_sunday_school -q
.venv\Scripts\python.exe -m scripts.run_desktop_checks tests.test_ui_smoke.UiSmokeTests.test_members_form_dates_fixed_footer_and_safe_destruction tests.test_ui_ministry
.venv\Scripts\python.exe -m scripts.check_desktop_startup
.venv\Scripts\python.exe -m scripts.upgrade_guard verify backups/before_user_administration_20261006T111433Z_snapshot.json
~~~

Frontend commands from web:

~~~powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd test
npm.cmd run test:e2e
npm.cmd run build
npm.cmd audit --audit-level=low
~~~

The browser runner owns ports 8001/3002, uses real auth/business services with synthetic data in a private schema, and writes its own build under .next-e2e. It does not sign in to the production database.

## 20. Remaining issues and later phases

Member/ministry mutations, household/Sunday School full online workspaces, attendance operations, administration, finance, welfare and public-site work remain in their separately authorized phases. Current extra modules retain the existing guarded shell/desktop availability presentation. Global dashboards omit ministry appointment totals when no single ministry is selected; school attendance rate is omitted when no denominator exists. Missing photos remain initials. This phase has been implemented locally and is not deployed or pushed to Git.
