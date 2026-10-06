# HOPFAN secure portal: Phase 3

Current work now includes [Phase 5 operations](online_operations_report.md),
[Phase 6 stabilization and CMS](web_stabilization_cms_report.md), and the
[Phase 7 public website](public_website_report.md). Use `npm.cmd run dev` from
`web/` to start the missing local backend and the frontend together.

Phase 4 now provides real dashboard summaries, member directories/profiles,
ministry directories/rosters/leadership and private authorized photos. See the
[Phase 4 implementation and validation report](online_business_workspace_report.md)
for endpoint contracts, scope rules, run commands and current test results.

The portal lives in `web/`, independently of the Windows desktop application and
FastAPI source. It uses Next.js 16.3.8 App Router, React 19.3.0, and TypeScript 6.0.3.
The compatible validation stack uses ESLint 10, Vitest, React Testing Library,
Playwright Chromium, and axe browser accessibility checks. npm and
`web/package-lock.json` are the single package-manager/lockfile pair.

## Run locally on Windows

Start the backend in one PowerShell terminal, from `D:\HOPFAN`:

```powershell
.venv\Scripts\python.exe run_api.py
```

Or use the canonical development command:

```powershell
.venv\Scripts\python.exe -m uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
```

In a second terminal:

```powershell
cd D:\HOPFAN\web
npm.cmd ci --cache .npm-cache
npm.cmd run dev
```

Portal: <http://localhost:3000/login>. Dashboard:
<http://localhost:3000/portal/dashboard>. API: <http://localhost:8000/api/v1/health>.
The backend listens on loopback 127.0.0.1 and accepts the localhost Host header.
`npm.cmd` avoids the blocked npm.ps1 launcher under Windows execution policies;
no policy change is required.

The frontend defaults to `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`.
`web/.env.local.example` documents that public origin. Copy it to `.env.local`
only when needed, preserving any existing local configuration. No PostgreSQL,
encryption, payment, or SMS settings belong in the frontend environment. The API
base must be an HTTP(S) origin without a path, query, fragment, or credentials;
remote production API origins require HTTPS.

Use **localhost for both browser-facing services**. Mixing a localhost portal
with a 127.0.0.1 API changes the browser's SameSite relationship. Production should
use approved HTTPS subdomains of the same site, with matching backend CORS and
cookie configuration. Current backend defaults permit localhost:3000 and :3001.
See [backend configuration](online_api_setup.md) for production proxy and cookie
requirements. No backend configuration or database migration was needed for Phase 3.

## API integration and session flow

The browser calls FastAPI directly. Next.js does not proxy credentials, maintain
another identity store, verify passwords, or copy backend cookies into client
state. Server Components provide static layout/metadata and route structure;
interactive authentication, navigation, and workspaces use Client Components.
No protected user data is fetched or embedded during Next.js server rendering.

The typed client in `web/src/lib/api/` uses the actual Phase 2 contracts:

| Endpoint | Request/response used |
| --- | --- |
| `GET /api/v1/me` | Safe user/member, roles, permissions, ministry/class scopes, dashboard hint |
| `GET /api/v1/auth/csrf` | `csrf_token`, `authenticated`; backend sets/recovers the HttpOnly cookie |
| `POST /api/v1/auth/password-login` | `email`, `password`; response `status: authenticated`, rotated `csrf_token` |
| `POST /api/v1/auth/totp-login` | `email`, six-digit `code`; same response shape |
| `POST /api/v1/auth/logout` | Current cookie/CSRF header; response `status: signed_out` |

All calls include `credentials: include` and no-store caching. State-changing
requests acquire a CSRF token in memory and send `X-CSRF-Token`; a specific
`CSRF_INVALID` denial refreshes it and retries once. Successful login adopts the
rotated token and then loads `/me`. Requests have a bounded timeout, including
response-body parsing. Runtime decoders project only known public fields.
Error rendering uses controlled friendly messages, not raw responses or traces.

One root authentication provider bootstraps `/me`, deduplicates concurrent
requests, and holds the safe profile in memory. Protected layouts show a loading
state until authentication succeeds; unauthenticated visits redirect to `/login`.
Generation guards prevent stale requests restoring a logged-out profile.
Authenticated 401 responses clear the profile/token and return to login with an
expiry message. Wrong login credentials stay on the login form.

Logout calls the backend before clearing local authenticated state. A network
failure remains visible and retryable rather than claiming the session ended.
Passive five-minute/focus checks use the existing CSRF endpoint, which validates
the session without extending backend idle activity. Central navigation refreshes
can reload `/me` after user activity; there is no perpetual `/me` heartbeat.

Passwords and authenticator codes live only in form memory and are cleared after
submission/method changes. Authentication credentials are never put in
localStorage/sessionStorage. Only the Light/Dark/System **visual preference** is
persisted (`hopfan-theme`). Workspace selection is in memory and may be reflected
in a validated URL query. Cookie security and authorization remain backend
responsibilities, consistent with
[Next.js authentication guidance](https://nextjs.org/docs/app/guides/authentication).

## Portal presentation and permissions

`/login` uses the official HOPFAN logo, local Inter fonts, a restrained navy/blue/
green/gold identity, two alternative login tabs, password visibility control,
accessible six-box OTP entry, automatic advance, Backspace/arrow navigation,
paste, and single auto-submit. Duplicate submissions are disabled. Account
recovery help directs users to the existing desktop flow or church administrator.

`/portal` redirects to `/portal/dashboard`. A persistent layout supplies a
sidebar, top bar, workspace selector, account/profile menu, logout, theme control,
and compact mobile drawer. Keyboard focus, escape/close behavior, semantic labels,
skip navigation, screen-reader errors, and reduced-motion styling are included.

Sidebar/module guards use actual persisted permission codes, including plural
`MEMBERS_*` and `MINISTRIES_*`. Scoped ministry destinations require an assigned
ministry; global permissions work without artificial scope rows. Administration,
Finance and Welfare appear only for their own explicit grants. Household-only
access respects member linkage; class-limited Sunday School views show only
assigned classes. Events have no read permission/API in the inspected system,
so an invented Events grant or destination is not introduced.

Presentation configurations support Administrator, Church Secretary, General
Overseer, Ministry Officer, Sunday School, and Standard User. Existing Secretary
and Overseer role codes refine the coarse backend dashboard hint; **only
presentation** uses these names. Every module/action still checks permissions.
Church offices, ministry names, and dashboard hints never grant access.

Multiple ministry/class scopes create a selector populated only from `/me`.
Single scopes are automatic. A global account defaults to church-wide access
without being forced to select a ministry. Invalid ministry/class query IDs show
Access denied within the shell. Backend checks remain authoritative, including
requests made directly without the frontend.

Member and ministry directories/profiles now read authorized business records,
and the dashboard shows permitted database counts. Its quick actions link to
those implemented reads. Household, attendance, Sunday School, messaging,
report, administration, finance and welfare full workflows retain their guarded
workspace shells and desktop availability guidance pending later phases.

## Validation

From `web/`:

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd test
npm.cmd run build
npm.cmd audit
```

For browser validation:

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH='D:\HOPFAN\web\.playwright'
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

The end-to-end runner builds a separate `.next-e2e` artifact with portal port
3002 and API port 8001. It starts `tests.portal_preview_api`, which uses real
authentication/authorization against a strictly named disposable PostgreSQL
schema and synthetic users. Production users, passwords, permissions, and
business records are untouched. Fixture-only routes never enter `src.api.main`.
Normal teardown and the guarded fallback remove that fixture schema. No production
credentials are embedded in tests. Network traces/video are disabled; screenshots
contain only synthetic profiles and blank login fields.

Responsive captures are in `docs/screenshots/portal/`, covering 1920×1080,
1600×900, 1366×768, 1024 tablet, 768 tablet, and 390 phone in both themes. Browser
checks cover real password/TOTP login, bootstrap redirects, HttpOnly cookies,
logout/replay denial, navigation persistence, permission/module isolation,
backend ministry denial, workspace switching, expiry, and accessibility.

Backend regression command, from the repository root:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_api.py tests/test_web_auth.py tests/test_web_sessions_migration.py -q --tb=short -p no:cacheprovider
```

Desktop remains independently runnable:

```powershell
.venv\Scripts\python.exe hopfan.py
```

## Phase 3 implementation report

1. **Framework:** Next.js 16.3.8 App Router, React 19.3.0, TypeScript 6.0.3; Node
   24.15+ supports the selected development/browser-test tools.
2. **Created:** `web/` app routes, components, auth/dashboard/workspace features,
   typed contracts/API client, styles, public logo, npm lockfile/config/environment
   example, unit/browser tests, and browser runner; isolated Python preview fixture
   and this guide. The root gitignore adds frontend build/test/cache exclusions.
3. **Contracts:** actual Phase 2 auth, CSRF, logout, and current-user schemas;
   infrastructure endpoints remain intact.
4. **Authentication:** direct cookie-based FastAPI calls; alternative password/TOTP,
   no duplicate verification or identity store.
5. **CSRF:** in-memory bootstrap, header, rotation, and bounded refresh/retry.
6. **Bootstrap:** one profile provider, loading gate, deduplication, expiry/401 handling,
   stale-result guards, confirmed backend logout.
7. **Login UI:** official logo/local fonts, professional responsive composition,
   accessible alternative tabs, password reveal, OTP typing/paste/auto-submit, errors.
8. **Layout:** persistent sidebar/top bar/content/account shell and mobile drawer.
9. **Navigation:** actual permissions and assigned scopes; no title-based grants.
10. **Workspaces:** assigned options only, single-scope automatic, church-wide global
    default, invalid query rejection, class-aware school context.
11. **Dashboards:** six reusable presentation profiles; real safe self/scope data and
    clear availability states, with no fabricated operational metrics.
12. **Responsive:** all six required sizes, cards/stacks/drawer, no horizontal overflow.
13. **Themes:** Light/Dark/System CSS variables, persisted visual preference only,
    system media changes and storage-unavailable fallback.
14. **Tests:** 18 component/API-client tests, 12 real-browser tests, 95 backend
    API/security tests, and 17 existing desktop authentication/session tests
    passed: **142 total**. Production build, TypeScript, ESLint and full npm audit
    passed; the audit reports zero known vulnerabilities. Axe WCAG 2 A/AA checks
    passed for password/OTP login and portal views in both light and dark themes.
15. **Backend:** `.venv\Scripts\python.exe run_api.py` or the exact Uvicorn command above.
16. **Frontend:** `cd D:\HOPFAN\web`, `npm.cmd ci`, then `npm.cmd run dev`.
17. **URLs:** portal localhost:3000; API localhost:8000; separate controlled E2E
    portal localhost:3002/API localhost:8001.
18. **Remaining decisions:** approved production domains/deployment, backend quota/
    proxy configuration and cleanup policy; business-record APIs and online actions
    belong to subsequent phases. No public church website was created.

Verified on 2026-10-06. The real desktop application initialized, ran normally
for 31 seconds and closed with exit code 0. All original records across the 34
existing church/identity tables passed fingerprint verification. Database head
remains `d95f13b8e204`, and no disposable portal schemas remain. The official logo
was copied without alteration; 24 synthetic login/dashboard screenshots capture
both themes at all requested viewport sizes.

Windows build validation also confirmed that the normal Admin account can update
the three Next.js-managed files (`next-env.d.ts`, `tsconfig.json`, and
`tsconfig.tsbuildinfo`) after narrowly granting Modify access to those files.
Directory-wide permission changes were unnecessary.
