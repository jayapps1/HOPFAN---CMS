# HOPFAN Phase 7 public website and CMS publishing

Implementation and verification in the existing HOPFAN workspace.

## 1. Existing components reused

One Next.js codebase, existing portal/auth/security client, domain services, logo, theme tokens, PostgreSQL and Alembic.

## 2. Backend files

content models/contracts/base, PublishingService, CommunicationService, InquiryService, PublicSiteService and WebsiteMediaService; dedicated internal/public schemas and content router.

## 3. Frontend files

Public Server Components and small navigation/forms/gallery clients; CMS content/settings/media/communications/follow-up editors; app/(public) and app/(secure) groups.

## 4. Migration

e3acdfa4cbf6: website_content, website_settings, website_media, website_content_media, church_events, church_announcements, public_inquiries and content_audit_logs. No existing business tables were reset.

## 5. Public routes

/, about, leadership, ministries/detail, Sunday School, events/detail, announcements, sermons/detail, gallery/detail, prayer-request, new-here, contact, give and optional published testimonies.

## 6. Public APIs

/api/v1/public/site, pages, ministries, leadership, events, announcements, sermons, gallery, testimonies and approved media. Only visitor/contact/prayer intake routes accept anonymous writes.

## 7. Homepage

CMS-managed hero/buttons/section choices/featured URL names; welcome, service times, events, sermons, ministries, announcements, gallery and private-intake CTAs. Empty content sections are omitted.

## 8. Ministry publication

An explicit editorial profile links an internal ministry. Public names/descriptions/meeting/contact text are separately authored and published; no member counts or internal details are projected.

## 9. Leadership publication

An explicit editorial profile, reviewed website image and public title/bio. No private phone/address, member number, role, permission or internal assignment is exposed. Linked child profiles require a separate consent reference.

## 10. Events/announcements

Only PUBLISHED publicly visible events and active PUBLIC/BOTH notices appear. Past events remain available through the past filter; approval is enforced before publication.

## 11. Sermons

Structured CMS content stores speaker, date, scripture, series, summary and approved YouTube/Vimeo/audio URLs. Videos are not uploaded into PostgreSQL.

## 12. Gallery/media

Validated JPEG/PNG/WebP uploads stay private; thumbnails at 320/960/1920 strip original metadata. Publication requires review, alt text and consent. Assets are publicly served only while linked to published content or a public published event. LocalWebsiteStorage provides a storage abstraction.

## 13. Prayer requests

Public POST creates a private queue entry and returns only a received status. Rate limits, origin checks, validation and honeypot protection apply. Reading requires explicit PRAYER_REQUEST_VIEW.

## 14. Visitor/new-here

Private inquiries, consent/preferred-contact fields and optional visit date. No automatic Member creation. A reviewed conversion uses duplicate checks, row/advisory locking and the existing Member service atomically.

## 15. Contact

CMS-published contact/service/social/map settings and a protected anonymous intake route. Unprovided live facts remain blank; none were fabricated.

## 16. Giving

CMS content foundation and an honest unavailable message when no approved giving content exists. No payment/card secrets or fake processing.

## 17. CMS improvements

Overview, content sections, private preview, draft editors, settings/service/social editors, media review, publication/withdraw/archive confirmations and follow-up queues.

## 18. SEO

Published content supplies titles/descriptions/Open Graph. Escaped Organization structured metadata uses only approved public settings. Canonical URLs require an explicitly configured approved HTTPS origin.

## 19. Sitemap/robots

Published slugs only; portal/login/APIs excluded. Without SITE_PUBLIC_ORIGIN, local/staging pages remain noindex and robots disallows crawling; no production domain is fabricated.

## 20. Privacy

Public schemas are separate explicit allowlists. Public SSR sends no cookies and never reads internal member/ministry endpoints. Authentication providers exist only inside the protected route group.

## 21. Child protection

No public student/guardian/attendance/household endpoints or internal photographs. Website media is stored separately from member photos and requires explicit consent review.

## 22. Responsive tests

Public pages were exercised at all seven requested sizes. Seventy synthetic public screenshots are under docs/screenshots/public-website; portal/attendance screenshots are separate.

## 23. Accessibility

Browser WCAG 2 A/AA and 2.2 AA checks cover public pages at 390 and 1366 pixels, plus compact login and shared operational controls; keyboard gallery/drawer behavior is tested.

## 24. Backend results

140 backend tests passed, including authentication/security, business scope, operations, publishing, intake and migration preservation.

## 25. Frontend results

34 unit tests passed; lint/typecheck and production compilation passed. All 32 combined Chromium tests passed, including login, operations, publishing, public/private separation and all requested responsive widths.

## 26. Portal regression

Authentication, dashboards, members, ministries, attendance, Sunday School, scoped events, CMS publishing and private intake are covered by the combined browser suite.

## 27. Desktop regression

The existing desktop launched without Node, stayed open for 31 observed seconds and closed cleanly. Earlier seven actual desktop attendance/school UI checks and 52 domain cases passed; 93 final existing service regression tests passed.

## 28. Public URL

http://localhost:3000/

## 29. Portal URL

http://localhost:3000/login and /portal/dashboard.

## 30. API URL

http://localhost:8000/api/v1/health; development docs at /docs.

## 31. Configuration and remaining deployment work

Approved live church wording, contacts, service times, photographs and sermons must be entered and published by authorized users. Sensitive prayer access requires an explicitly approved pastoral grant. SITE_PUBLIC_ORIGIN/HTTPS/proxy configuration and production object storage are deployment decisions; the local storage adapter remains the configured implementation. Paystack integration is outside this giving foundation. No public content was fabricated or automatically seeded into the live database.


Final verification: 140 backend + 93 existing domain + 34 frontend unit + 32 browser + 7 desktop UI cases = 306 automated tests passed. The actual desktop startup check and live seeded-account browser proof also passed. Production build, TypeScript, ESLint, and dependency audit passed; the audit reported zero vulnerabilities.

The fresh verified pre-migration backup is `backups/before_user_administration_20261006T222952Z.dump`. Original records in all 36 pre-migration tables were preserved. Disposable browser schemas remaining: zero. Live website content and intake rows: zero; no synthetic church information was seeded.
