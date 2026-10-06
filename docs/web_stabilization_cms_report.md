# HOPFAN Phase 6 web stabilization and publishing foundation

Implementation and verification in the existing HOPFAN workspace.

## 1. Connection root cause

The frontend existed on localhost:3000 while the API was not listening on localhost:8000. Health/readiness/version requests returned WinError 10061 connection refused. This was a missing backend, not a credential or CORS failure.

## 2. API URL before and after

The correct configured/default URL remains http://localhost:8000. The combined development launcher now starts the missing backend instead of requiring a second manual terminal.

## 3. CORS

Exact localhost:3000/3001 development origins; credentials allowed; GET/POST/PATCH. No authenticated wildcard origin.

## 4. Cookies

Host-only HttpOnly SameSite=Lax cookie; Secure=false only in development. Production retains Secure=true and the __Host- cookie requirement.

## 5. CSRF

The client obtains and sends the session's CSRF token on every authenticated mutation. Origin checks and CSRF remain enabled.

## 6. Login routes

POST /api/v1/auth/password-login and totp-login; GET auth/csrf and /me; POST auth/logout.

## 7. Login UI

A 1040px compact surface, 42/58 brand/form balance, 46px inputs, compact OTP/tabs, restrained branding, and a short mobile brand header.

## 8. Responsive login

All seven requested sizes were checked in both themes. At 1366x768 and 390x844 the form fits without unnecessary scrolling; browser accessibility checks passed.

## 9. Authentication proof

The existing seeded administrator logged into the real localhost browser portal, loaded /me, refreshed the authenticated page and logged out. Credentials were kept in process memory and never printed. Fourteen isolated login/browser checks also passed, including TOTP and wrong-password classification.

## 10. Events

Scoped draft creation/editing, submit/approve/publish/withdraw/archive, protected API routes and /portal/events. Global publication requires explicit permission and approval.

## 11. Announcements

The same scoped review workflow, publication audience and time window; protected portal and separate public projection.

## 12. Visitors/follow-up

Private visitor/contact queues, assignees, notes/status updates and reviewed duplicate-aware conversion through MemberService. Anonymous submissions never create Members.

## 13. CMS foundation

Structured content with private drafts and separate published snapshots; website settings, reviewed media, sermons, gallery, ministry/leadership editorial profiles and audit events.

## 14. Migration

e3acdfa4cbf6 adds eight tables and explicit content grants. Sensitive pastoral grants are separate and are not automatically given to the administrator.

## 15. Tests

Publication/API tests and the additive migration test passed. The final combined results are recorded in the Phase 7 report.

## 16. Desktop

Existing desktop starts independently of Node. Original pre-migration record fingerprints were preserved after the forward migration.

## 17. Backend command

`.venv\\Scripts\\python.exe run_api.py` from D:\\HOPFAN.

## 18. Frontend command

`npm.cmd run dev` from D:\\HOPFAN\\web starts or reuses the local API and frontend.

## 19. Browser URL

Public website http://localhost:3000/; staff login http://localhost:3000/login; API http://localhost:8000/api/v1/health.
