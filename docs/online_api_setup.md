# HOPFAN online API: Phases 1 and 2

Publishing, public contracts and private intake are described in the
[Phase 7 report](public_website_report.md). Current forward head is
`e3acdfa4cbf6`; use `.venv\Scripts\python.exe -m alembic upgrade head`
after a verified backup when upgrading another existing installation.

The Phase 3 Next.js secure portal is documented in [online_portal_setup.md](online_portal_setup.md).
Phase 4 business reads, real dashboards, scope rules and validation results are
documented in [online_business_workspace_report.md](online_business_workspace_report.md).

The FastAPI foundation runs independently of the Windows desktop application.
It uses the same authoritative PostgreSQL database, identity models, and
synchronous SQLAlchemy session factory. Phase 1 provides infrastructure endpoints;
Phase 2 adds browser authentication, server-managed sessions, and current-user data.

## Local setup

Run these commands in PowerShell from `D:\HOPFAN`. Keep the existing `.env` and
`APP_ENCRYPTION_KEY`; do not replace them with the example file.

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
# Include TestClient and pytest when running the tests:
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Existing `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` configure the
shared `src/config/database.py` engine and `SessionLocal`. The existing desktop
encryption/session/seeder variables retain their current meaning. Health and
version do not open a database session; readiness returns a safe 503 when database
configuration or connectivity is unavailable.

`src/config/environment.py` extracts the original project `.env` loader without
changing its precedence: this project's `.env` overrides process environment
values for keys present in the file. Both API settings and the desktop database
use that loader. Deployment must therefore avoid shipping a development `.env`.

Optional online settings are documented in `.env.example`:

| Setting | Development default | Staging/production behavior |
| --- | --- | --- |
| `APP_ENV` | `development` | Set `staging` or `production` explicitly |
| `API_HOST` | `127.0.0.1` | Bind only as required by backend infrastructure |
| `API_PORT` | `8000` | Must be between 1 and 65535 |
| `API_DEBUG` | `false` | `true` is rejected; HTTP tracebacks are always disabled |
| `API_DOCS_ENABLED` | `true` | Defaults to `false`; explicit opt-in is available |
| `API_ALLOWED_HOSTS` | `127.0.0.1,localhost` | Exact hostnames are required; no ports or wildcards |
| `WEB_PUBLIC_ORIGIN` | `http://localhost:3000` | Empty unless configured; require an exact HTTPS origin |
| `WEB_PORTAL_ORIGIN` | `http://localhost:3001` | Empty unless configured; require an exact HTTPS origin |

Boolean settings accept `true`/`false` or `1`/`0`. Origins contain the scheme,
hostname, and optional port, without a trailing slash, path, credentials, or
wildcard. An empty origin disables that browser origin.

## Start the API

The canonical development command uses the existing virtual environment:

```powershell
.venv\Scripts\python.exe -m uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
```

API: <http://127.0.0.1:8000/api/v1/health>. Documentation:
<http://127.0.0.1:8000/docs>, <http://127.0.0.1:8000/redoc>, and
<http://127.0.0.1:8000/openapi.json>. The root `/` has no endpoint.

The convenience launcher reads `API_HOST` and `API_PORT`, prints the API/docs
URLs, and applies the same logging and proxy defaults:

```powershell
.venv\Scripts\python.exe run_api.py
```

The CLI's `--host` and `--port` are explicit Uvicorn options; the CLI does not
automatically consume the project-specific `API_HOST`/`API_PORT` names. Neither
entry point opens a browser. `hopfan.py` remains the desktop entry point:

```powershell
.venv\Scripts\python.exe hopfan.py
```

## Endpoints

| Method and path | Successful response | Database access |
| --- | --- | --- |
| `GET /api/v1/health` | `{"status":"ok","service":"hopfan-api"}` | None |
| `GET /api/v1/ready` | `{"status":"ready","database":"available"}` | Existing session, role safety check, `SELECT 1` |
| `GET /api/v1/version` | `{"application":"HOPFAN","api_version":"v1","platform":"online"}` | None |

Unavailable database: HTTP 503 with code `DATABASE_UNAVAILABLE`. A superuser or
unverifiable PostgreSQL role returns 503 with `DATABASE_ACCESS_UNSAFE`. Responses
never include connection strings, database identities, SQL, or raw exceptions.
Example unknown route: HTTP 404 with
`{"error":{"code":"RESOURCE_NOT_FOUND","message":"The requested resource was not found."}}`.
Validation returns HTTP 422 with `VALIDATION_ERROR`; unexpected failures return
HTTP 500 with `INTERNAL_SERVER_ERROR` and a generic message.

## Architecture and security

`src/api/main.py` creates the app. `src/api/v1/router.py` collects the public
infrastructure routers; their paths share `API_PREFIX` from `v1/__init__.py`.
Route functions are synchronous. Dedicated Pydantic contracts under
`src/api/schemas/` allow only explicit public fields; ORM models are not serialized.

`src/api/dependencies.py` opens the existing `SessionLocal` lazily and closes it
in `finally`. Readiness uses a function-scoped dependency so cleanup finishes
before a success response is sent. SQL is confined to
`src/services/api_readiness_service.py`. The database engine, models, business
services, authentication, RBAC, and ministry/class scopes remain shared.

Exact configured browser origins receive CORS headers; unconfigured origins do
not. Phase 2 allows GET/POST preflights and browser credentials, including the
explicit `Content-Type`, `X-CSRF-Token`, and `X-Request-ID` headers. CORS does
not restrict non-browser clients and is not authorization. Exact allowed Host
headers are checked before CORS, including preflights. Forwarded Host headers
cannot override the check. Host rejects use a safe JSON error; CORS middleware
preflight rejects use its standard HTTP 400 response.

Every HTTP response has a generated `X-Request-ID`, `nosniff`, `DENY` framing,
`no-referrer`, and `no-store` headers. Logs use the standard `hopfan.api` logger
with request ID, method, registered route template, status, and duration. Unknown
paths are logged as `/<unmatched>`. Query strings, raw path parameters, bodies,
credentials, and incoming correlation headers are not logged. Unexpected errors
are caught before Uvicorn can print private tracebacks. Streaming responses that
already started cannot have their HTTP status replaced; a failure is logged
without exception details. Phase 1 has no streaming endpoints.

The start commands disable Uvicorn's separate access log, which otherwise may
record raw query strings, and disable proxy header trust by default. A deployment
behind a trusted proxy may explicitly enable `--proxy-headers` with a narrowly
configured `--forwarded-allow-ips` list. Never use `*` to trust arbitrary sources;
network controls must prevent bypassing that proxy. This follows
[Uvicorn's proxy and logging settings](https://www.uvicorn.org/settings/).

Deployment requires HTTPS, explicit allowed hosts, exact HTTPS frontend origins,
and disabled or access-restricted documentation. An explicitly enabled docs
setting does not add authentication; restrict docs at the proxy until real web
authentication is implemented. Frontend origins follow the
[FastAPI CORS configuration](https://fastapi.tiangolo.com/tutorial/cors/).

Use a least-privileged PostgreSQL application login, never a superuser. Both the
session login and effective database role are checked before an API session is
yielded. No database users, grants, or credentials are changed automatically.
Desktop and API can eventually use separately controlled credentials for the
same database; that operational change is outside this foundation. PostgreSQL
must stay private to backend infrastructure and never be exposed to a browser.

Migrations remain an explicit deployment step:

```powershell
.venv\Scripts\python.exe -m alembic upgrade head
```

API startup does not create tables, run migrations, or seed anything. Phase 2 adds
the explicit additive migration `d95f13b8e204`, following `c84e26f7a930`, for
`web_sessions` and `web_rate_limits`. Apply it before starting authentication
traffic. Future private/admin routers must use `get_current_user()`, the existing
`AuthorizationService`, permission checks, and ministry/class scopes. URL names
and church appointments do not grant access.

## Browser authentication

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/auth/csrf` | Bootstrap a short-lived pre-session and obtain its CSRF token; authenticated browsers can recover their current token |
| `POST /api/v1/auth/password-login` | Existing email/username and password authentication |
| `POST /api/v1/auth/totp-login` | Existing email/username and six-digit authenticator authentication, independently of password login |
| `POST /api/v1/auth/logout` | Revoke the current server session, clear its cookie, and record logout |
| `GET /api/v1/me` | Safe current-user, role, permission, ministry scope, and Sunday School class scope data |

Login requests use `{"email":"user@example.com","password":"..."}` or
`{"email":"user@example.com","code":"123456"}`. The `email` field also accepts
an existing username, matching desktop lookup. Password and TOTP remain
alternative sign-in methods. Existing `AuthService` controls Argon2 verification,
encrypted TOTP verification, account state, failed attempts, five-attempt
temporary lockout, last login, and existing audit events. Browser orchestration
borrows the request's database session; it creates no duplicate engine or users.

Wrong credentials, locked/inactive/suspended accounts, and disabled authenticator
sign-in return generic HTTP 401 `INVALID_CREDENTIALS` errors, without revealing
whether an account exists. Malformed input returns safe HTTP 422 validation errors.
A verified account with `require_password_change` receives controlled HTTP 403
`PASSWORD_CHANGE_REQUIRED`: complete its existing desktop password-change flow
before online sign-in. That flag is never bypassed and no recovery/enrollment or
password-change web endpoints are introduced in this phase.

### Cookies and sessions

The browser receives an opaque random 256-bit credential in an HttpOnly,
host-only cookie with path `/`. PostgreSQL stores its SHA-256 hash, never the raw
cookie. The session contains only UUID identifiers, account revision, method,
timestamps, and revocation metadata. A short-lived anonymous pre-session in the
same security table protects login itself; it has no User identity or permissions.
Authenticated sessions reference the existing `users` table.

Staging/production require Secure cookies and a `__Host-` cookie name; the default
is `__Host-hopfan_session`. Development defaults to `hopfan_session` without
Secure for local HTTP. SameSite defaults to Lax and can be set to Strict. Broad
cookie domains and SameSite=None are intentionally unavailable. The cookie has
no persistent Max-Age/Expires: there is no Remember me option. Browser session
restoration can retain cookies, so server-side expiry is always authoritative.

Every successful login rotates both cookie and CSRF token and revokes the prior
pre-session/session. Each device can have its own session. Logout revokes the
current record before clearing the cookie; replaying it cannot restore access.
Missing, revoked, expired, or invalidated sessions receive HTTP 401 and invalid
authenticated cookies are cleared. A valid anonymous pre-session remains usable
when `/me` reports that sign-in is required.

`get_current_user()` resolves the session, verifies expiry, loads the existing
`AuthorizationService`, and checks `auth_revision` on every request. Deactivation,
suspension, password resets, temporary-password requirements, and normal role or
scope administration invalidate sessions according to existing revision policy.
Changes to active grants are also reflected by fresh authorization queries.
Authenticated requests update activity; fetching CSRF does not extend idle time.
An absolute expiry never slides. This follows the
[OWASP session-management guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).

### CSRF request flow

1. Fetch `/api/v1/auth/csrf` with `credentials: 'include'`.
2. Keep the returned `csrf_token` in application memory.
3. Send it as `X-CSRF-Token` on login and every authenticated state-changing
   request, again with `credentials: 'include'`.
4. After login, replace that in-memory token with the new token in the login
   response. Then fetch `/api/v1/me`.
5. Submit logout with the current token, then discard cached profile/token data.

The token is a domain-separated HMAC derived from the opaque cookie credential.
It does not reveal that credential and is stable across legitimate tabs for one
session. Validation requires a real, live server-side session/pre-session as
well as a constant-time token match: inventing a cookie and its token is denied.
It is invalidated by cookie rotation. Authentication credentials are accepted
only through cookies, never Bearer headers, localStorage, or sessionStorage.

State-changing requests must include an Origin equal to a configured trusted
frontend origin or the validated API's own origin. Null, absent, or unconfigured
origins are rejected. Provided origins on auth/current-user GET requests are
checked too. Staging/production accept only HTTPS origins. These checks apply to
both login methods and logout; `get_current_user()` automatically requires CSRF
for future authenticated unsafe requests. Follow this dependency pattern for
all later business routes. The pre-session/rotation and origin/header controls
follow [OWASP CSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).

For local browser development, use the same hostname for portal and API, for
example `http://localhost:3001` and `http://localhost:8000`. Mixing localhost and
127.0.0.1 changes the browser's site relationship. Production portal/API should
share an HTTPS site, such as approved subdomains of one domain, or use an
appropriate same-site proxy. CORS permission alone does not override SameSite.

Example for the future portal, with no browser token persistence:

```javascript
const api = 'http://localhost:8000/api/v1';
const pre = await fetch(`${api}/auth/csrf`, { credentials: 'include' });
let { csrf_token } = await pre.json();
const signedIn = await fetch(`${api}/auth/password-login`, {
  method: 'POST', credentials: 'include',
  headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf_token },
  body: JSON.stringify({ email, password }),
});
if (!signedIn.ok) throw new Error('Unable to sign in.');
({ csrf_token } = await signedIn.json());
const me = await fetch(`${api}/me`, { credentials: 'include' });
```

### Current-user contract and authorization

`/me` explicitly returns `id`, `username`, `email`, a nullable linked-member
summary (`id`, `member_no`, `full_name`, `photo_url: null`), active software roles,
effective permissions, exact ministry scopes, Sunday School class scopes, and a
non-security `dashboard_profile` hint. Missing member linkage does not block
technical/admin accounts. No password hash, TOTP material, failed-attempt data,
recovery proof, account revision, database settings, or local photo path is returned.

Ministry scopes come from the existing authorization context, including retained
legacy restrictions; Sunday School scopes reuse `SundaySchoolBase.access`.
Global permissions work without fabricated per-ministry scope rows. Multiple
assigned scopes are returned without unrelated ministries. Leadership positions
are never queried to grant access. Dashboard hints do not grant access.

Reusable dependencies are `require_permission(code)`,
`require_any_permission(*codes)`, and
`require_ministry_permission(code, parameter='ministry_id')`. They apply existing
permission/global-versus-scoped rules and return safe HTTP 403 denials. No business
endpoints or dashboard UI are added here.

### Rate limiting, auditing, and maintenance

PostgreSQL upserts maintain shared IP and normalized login-identifier buckets
across API instances/workers. Password and TOTP login share those buckets.
Attempts are counted before credential verification, including unsuccessful
attempts. HTTP 429 responses include a safe Retry-After value. CSRF bootstrap has
its own IP quota to bound anonymous session creation. Subject keys are stored as
hashes; passwords and authenticator codes never enter rate-limit records.

Only `request.client.host` supplies the peer address; application code does not
interpret X-Forwarded-For. Production must configure narrowly trusted Uvicorn
proxy addresses so proxy traffic is attributed correctly. Add edge abuse controls
for deployment-specific traffic; the database limiter remains shared protection.

Existing security audits remain intact. Additional events are `WEB_LOGIN_SUCCESS`,
`WEB_LOGIN_FAILED`, `WEB_TOTP_LOGIN_SUCCESS`, `WEB_TOTP_LOGIN_FAILED`, `WEB_LOGOUT`,
`WEB_SESSION_EXPIRED`, and `WEB_SESSION_REVOKED`. Audit metadata contains safe
record UUIDs and controlled reasons, never cookie credentials/hashes, CSRF tokens,
passwords, codes, or encrypted TOTP material. Automatic expiry/revocation events
have no fabricated user actor; authenticated actions record their actor.

`WebSessionService.revoke_all()` is a future administration hook: self-revocation
or the existing `USER_DEACTIVATE` permission, freshly checked. It exposes no public
administration route. Trusted maintenance can invoke
`WebRateLimitService.purge_expired()` and `WebSessionService.purge_anonymous()`
using the existing session factory. Schedule these after deployment; they remove
expired buckets and old anonymous pre-sessions while preserving authenticated
session/audit history. Choose authenticated-history retention under church policy.

### Additional configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| `WEB_SESSION_IDLE_MINUTES` | `30` | Authenticated inactivity timeout |
| `WEB_SESSION_MAX_HOURS` | `12` | Absolute lifetime, independent of activity |
| `WEB_CSRF_SESSION_MINUTES` | `10` | Anonymous sign-in pre-session lifetime |
| `WEB_COOKIE_SECURE` | false in development; true otherwise | Production/staging reject false |
| `WEB_COOKIE_SAMESITE` | `lax` | `lax` or `strict` only |
| `WEB_SESSION_COOKIE_NAME` | automatic | `hopfan_session` locally; `__Host-hopfan_session` for HTTPS |
| `WEB_LOGIN_RATE_WINDOW_SECONDS` | `900` | Shared login bucket lifetime |
| `WEB_LOGIN_RATE_IP_LIMIT` | `30` | Combined password/TOTP attempts per IP/window |
| `WEB_LOGIN_RATE_ACCOUNT_LIMIT` | `10` | Combined attempts per normalized identifier/window |
| `WEB_CSRF_RATE_WINDOW_SECONDS` | `60` | CSRF bootstrap quota window |
| `WEB_CSRF_RATE_IP_LIMIT` | `60` | CSRF fetches per IP/window |

Timeouts and quotas must be positive and within validated bounds. Existing `.env`
values and encryption key remain unchanged. No new package is required for Phase 2.

## Tests and verification

```powershell
.venv\Scripts\python.exe -m pytest tests/test_api.py -q
.venv\Scripts\python.exe -m pytest tests/test_api.py tests/test_web_auth.py tests/test_web_sessions_migration.py -q --tb=short -p no:cacheprovider
.venv\Scripts\python.exe -m unittest tests.test_administration tests.test_session tests.test_sunday_school_migration -q
.venv\Scripts\python.exe -m compileall -q src tests/test_api.py tests/test_web_auth.py tests/test_web_sessions_migration.py
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m alembic check
```

The API suite uses FastAPI TestClient with the supported `httpx2` transport.
Database outcomes are simulated by replacing the shared session factory; no
production data is written. Test-only validation/failure routes are added to
fresh app instances and are absent from the shipped application. The existing
administration suite uses a disposable PostgreSQL schema and exercises Argon2,
TOTP, account states, roles/scopes, and audits. Session tests preserve desktop
idle and revocation behavior. The current transport is documented by
[Starlette TestClient](https://starlette.dev/testclient/); dependency cleanup
follows [FastAPI yield scopes](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/).

Verified on 2026-10-06:

- 36 API tests passed, covering public contracts, database failure/cleanup,
  superuser rejection, safe validation/errors, CORS, hosts, headers, secret-free
  logging, production configuration, and independent desktop/API imports.
- 17 existing authentication/RBAC/session tests passed.
- An actual Uvicorn process on loopback port 8000 returned HTTP 200 for all three
  endpoints; readiness confirmed the existing PostgreSQL database. The
  configured database login is not a superuser. The verification server stopped.
- `hopfan.py` created its normal application window, completed initialization,
  and closed normally with exit code 0. No credentials were entered.
- Compile checks and dependency compatibility checks passed; all 21 original
  desktop package versions were preserved. Alembic found no new upgrade
  operations, and the existing migration revision remains `c84e26f7a930`.

## Phase 1 implementation report (historical)

1. **Inspected:** `hopfan.py`; config/database/services/security/UI; all existing
   User/Role/Permission/association/scope, Member, Household, Ministry,
   MemberMinistry, leadership and Sunday School models; audit/logging; `.env`
   keys without printing values; requirements and Alembic configuration/history.
2. **Created:** the eleven `src/api/` package files listed above;
   `src/config/environment.py`, `src/config/online_settings.py`,
   `src/services/api_readiness_service.py`, `run_api.py`, `requirements-dev.txt`,
   `tests/test_api.py`, and this guide.
3. **Changed for this phase:** `src/config/database.py` only extracts its existing
   loader; `requirements.txt` adds API dependencies; `.env.example` adds optional
   online settings. Existing household/Sunday School working changes are retained.
4. **Packages:** FastAPI 0.142.2 and Uvicorn standard 0.54.0, with verified
   Starlette 1.7.0 and Pydantic 2.13.5 pins; development pytest 9.1.1 and HTTPX2
   2.13.1, plus their required dependencies. Pydantic-settings is
   unnecessary because the existing dotenv loader is reused. Original desktop
   package pins are unchanged.
5. **Structure:** app factory, DB dependency, safe errors, three middleware
   controls, versioned health/system routers, and explicit public schemas.
6. **Endpoints:** only `/api/v1/health`, `/api/v1/ready`, `/api/v1/version`, plus
   configurable documentation.
7. **Database:** shared synchronous `SessionLocal` and existing PostgreSQL; no
   new engine, model, identity table, migration, or business-data write.
8. **Configuration:** environment, bind host/port, safe debug logging, docs,
   exact hosts, and exact public/portal origins, all from the shared loader.
9. **Security:** safe schemas/errors, no traceback responses, exact CORS/hosts,
   correlation IDs/security headers, sanitized logs, and superuser rejection.
10. **Tests:** 53 automated tests passed and three real API endpoint probes
    passed; compilation, package compatibility, and Alembic schema checks passed.
11. **Desktop:** real `hopfan.py` startup and normal shutdown confirmed.
12. **API start:** use the exact Uvicorn command under “Start the API”, or
    `.venv\Scripts\python.exe run_api.py` for configured bind settings.
13. **Test command:** `.venv\Scripts\python.exe -m pytest tests/test_api.py -q`;
    the separate desktop authentication/session command is documented above.
14. **Unresolved Phase 1 issues:** none. Remote authentication, business
    endpoints, website, portal, dashboards, and deployment remain later phases.

## Phase 2 implementation report

1. **Reused:** `AuthService`, Argon2, encrypted `TotpService`, lockout/account-state
   logic, `AuthorizationService`, ministry/class scope rules, existing identities,
   security audits, `.env` loader, and synchronous `SessionLocal`.
2. **Created:** `src/models/user_session.py`; `web_security.py`,
   `web_session_service.py`, `web_auth_service.py`, `web_rate_limit_service.py`, and
   `current_user_service.py` under services; API security package/cookie/CSRF
   modules; auth/user schemas; auth/me routers; migration `d95f13b8e204`; and
   `tests/test_web_auth.py` / `tests/test_web_sessions_migration.py`.
3. **Changed:** online settings, model exports, API main/router/dependencies/errors,
   `.env.example`, API foundation tests, prior Sunday School migration comparison,
   and this guide. Desktop authentication implementation is unchanged.
4. **Migration:** two security metadata tables, no business-table or identity
   changes. Applied locally after verified backup/fingerprints; all 34 existing
   tables retained their original records; Alembic reports no new upgrade operations.
5. **Sessions:** random opaque cookies, SHA-256 hashes in PostgreSQL, pre-session
   protection, login rotation, multiple devices, idle/absolute expiry, and revocation.
6. **Cookies:** HttpOnly, host-only, path `/`, SameSite Lax/Strict; Secure and
   `__Host-` names required outside development; no persistent Remember me lifetime.
7. **CSRF:** session-bound HMAC token, Origin checks, bootstrap, rotation, and
   header validation on login/logout and authenticated unsafe requests.
8. **Auth endpoints:** password-login, totp-login, logout, and justified csrf bootstrap.
9. **Current user:** safe self identity/member, roles, effective permissions,
   ministry/class scopes, and non-security dashboard hint.
10. **RBAC:** existing permissions and scope intersections, global-access support,
    no office-title inference, and reusable dependencies.
11. **Rate limits:** shared PostgreSQL counters for IP/identifier and CSRF bootstrap,
    safe 429/Retry-After, no arbitrary forwarded-header trust.
12. **Audits:** the seven WEB events above supplement existing authentication
    events; no credentials or token material in metadata/logs.
13. **Validation:** 95 API/security/migration tests and 18 existing desktop
    authentication/session/migration tests passed: 113 total. Compilation,
    package compatibility, record-preservation, and Alembic schema checks passed.
14. **Desktop:** actual `hopfan.py` initialized, ran normally for 31 seconds,
    produced no traceback, and closed with exit code 0. All 21 original desktop
    package versions are preserved, and core desktop authentication is unchanged.
15. **Start:** `.venv\Scripts\python.exe run_api.py`, or the canonical Uvicorn
    command above with access logs and proxy trust disabled locally.
16. **Tests:** run the combined pytest and existing unittest commands above.
17. **Deployment decisions:** approved domains/proxy addresses, quota tuning,
    cleanup schedule and authenticated-history retention. Temporary-password
    changes remain in the desktop workflow; TOTP remains an alternative login.

Current Phase 2 verification on 2026-10-06 also started a real Uvicorn process on
loopback port 8000. Health, readiness, version, and CSRF bootstrap returned HTTP
200; anonymous `/me` returned 401, and login without CSRF returned 403 before
credential verification. The verification server stopped. All valid-password,
TOTP, multi-device, revocation, permission, isolation, and concurrent rate-limit
checks use real existing services against disposable PostgreSQL schemas, without
changing live user credentials or identity records.

The local migration was protected by the verified backup
`backups/before_user_administration_20261006T111433Z.dump` and its fingerprint
snapshot. Verification after migration and live probes confirmed original rows
in all 34 existing tables remain intact. Current Alembic head is `d95f13b8e204`.
