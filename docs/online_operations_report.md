# HOPFAN Phase 5 operational workflows

Implementation and verification in the existing HOPFAN workspace.

## 1. Attendance services reused

AttendanceService and the existing sessions, records, saved rosters and audit tables. Online operations do not create ministry copies of Sunday Service.

## 2. Sunday School services reused

SundaySchoolService, SundaySchoolAttendanceService, SundaySchoolLessonService, SundaySchoolReportService and SundaySchoolBase use existing Members and class scopes.

## 3. Backend files created

src/api/schemas/operations.py, src/api/v1/operations.py, src/services/online_operations_service.py and operation_errors.py; tests/test_online_operations.py.

## 4. Backend files changed

Shared service version conflicts, record correction, filtered single-row responses, class/teacher/session pagination, bounded report aggregates, and authenticated route dependencies. Existing desktop method defaults remain compatible.

## 5. Frontend files created

web/src/features/operations and lib/api/operations.ts; attendance and Sunday School operational pages under app/(secure)/portal.

## 6. Frontend files changed

Typed CSRF-protected mutation client, workspace options, private photo rendering, keyed resource updates, and operational CSS.

## 7. Attendance endpoints

GET/POST attendance/sessions; session detail, roster, summary and private photo; POST mark, record correction and open/close/reopen/lock/unlock actions.

## 8. Sunday School endpoints

Class/student/teacher reads, lesson create/edit, attendance create/roster/mark/correct/open/close/reopen, dashboard, bounded reports and permission-checked CSV.

## 9. Sunday Service behavior

One global session and saved whole-church roster per created service. Ministry filters read and update that same session_id/member_id record. The existing architecture permits separately scheduled service events; no new per-date constraint was imposed.

## 10. Ministry meeting scope

Creation requires a permitted ministry. A scoped user cannot read or write another ministry's private meeting or use a forged ministry context.

## 11. Duplicate prevention

Existing database unique pairs remain authoritative. Main writes lock the session; school writes reuse the existing transaction advisory lock.

## 12. Correction and audit

A reason and loaded version are required. Original marker/time remain intact; correction history stores old/new values, actor and timestamp. Stale versions return 409.

## 13. Class scope

Class scope comes from explicit user grants. A teaching assignment creates no account, role or portal grant. Unassigned teachers cannot read all-school published lessons.

## 14. Child privacy

Online DTOs omit DOB, household data, private notes and security fields. Guardian name/relationship/contact/consent appear only with the explicit guardian-view grant.

## 15. Mobile attendance

Shared responsive cards provide four status controls at least 44px high, saving feedback and confirmed corrections. Failed writes retain the previous saved status.

## 16. Tests

Sixteen operational API cases passed; main and school concurrency, privacy, large rosters and stale versions are covered. Combined final verification is recorded in the Phase 7 report.

## 17. IDOR/security

Foreign meeting/class/session/record/photo requests are denied; CSRF and trusted-origin checks protect each mutation.

## 18. Concurrency

Concurrent initial marks preserve one record. Conflicting updates return a controlled conflict; repeated identical school marks remain idempotent.

## 19. Performance

A 925-member church roster and 301-student class roster are paged in SQL, with fixed query-count bounds. Saving refreshes the affected row/summary, or revalidates an active status-filter page.

## 20. Desktop regression

52 shared domain regression cases and seven attendance/Sunday School desktop UI cases passed. The actual desktop opened, ran for 31 observed seconds, and closed normally.

## 21. Backend command

From D:\\HOPFAN: `.venv\\Scripts\\python.exe run_api.py`.

## 22. Frontend command

From D:\\HOPFAN\\web: `npm.cmd run dev`. The launcher starts the missing API and reuses an already-running HOPFAN frontend.

## 23. Remaining items

No offline sync or WebSockets were added. Main attendance rate uses the existing eligible-roster denominator; school rate excludes excused records, as its existing service specifies. React does not calculate either rate.
