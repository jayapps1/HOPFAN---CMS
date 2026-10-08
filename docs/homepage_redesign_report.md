# Public homepage redesign

The public Home page now uses a large CMS-backed hero, substantial weekly service panels, a primary events carousel and larger editorial previews. The existing public layout/navigation, content publication workflow, Events model, finance integration and secure portal remain in place.

| Required report item | Result |
| --- | --- |
| 1. Homepage files | Public Home is in `web/src/features/public/home.tsx`; `home.css` scopes the larger typography, imagery and spacing to Home. `public-photo.tsx`, `events-carousel.tsx`, `home-format.ts` supply focused visual/interactive helpers. Root Home metadata, public types and event date display were updated. |
| 2. CMS files | Existing content/settings managers and validated CMS contracts were extended; `service-times-editor.tsx` adds functional service controls. Existing portal components/styles are reused. |
| 3. Service storage | Existing `website_settings.draft_data` / `published_data` JSONB snapshots contain structured service records: ID, name, weekday, start/end local time, description, location, display order, active/featured flags, created/updated timestamps. Legacy reviewed schedule strings remain readable. No duplicate service or Event store was added. |
| 4. Initial schedule | One-time migration `ab61d4f83c02` seeds Sunday 07:00?10:00, Wednesday 09:00?12:00, Friday Evening 18:30?21:00 only when both existing service lists are empty. Existing administrator service edits are preserved. Unpublished contact drafts are never released by the seed. |
| 5. Events API | Existing public Event service and `/api/v1/public/events` remain the source. Existing `/portal/events` creates/submits/approves/publishes the same records. |
| 6. Carousel | Native horizontal scrolling and CSS scroll snap show one substantial event with a next-event preview on desktop; mobile presents a large swipeable event. Previous/next controls and slide selectors are implemented. No additional carousel dependency or UI framework was installed. |
| 7. Publication rules | Home selects only PUBLISHED, PUBLIC/BOTH events whose start is at or after now, chronologically. Drafts, submitted/approved-only, internal, archived and past events are excluded. Unpublishing removes an event immediately; republishing still requires the existing approval workflow. |
| 8. API composition | Existing `/api/v1/public/site` composes settings, services, bounded events, ministries, latest sermon, public Sunday School page, announcements, leadership and gallery previews. React request caching reuses server reads across layout, metadata and Home. No new parallel Home API was created. |
| 9. Service management | `/portal/website/service-times` offers add/edit/remove, active/featured flags, ordering, weekday/start/end time, public description/location and church timezone. Save a draft, then publish settings to update the website. |
| 10. Accessibility | Carousel controls have names, native keyboard behavior, visible focus, slide/group semantics and reduced-motion scrolling. It does not autoplay or trap Tab. Service panels use semantic headings/time elements; fallback imagery is decorative with content labels retained. |
| 11. Responsive behavior | Desktop hero is 640px; mobile hero is compact at 500px. Desktop service panels are substantial, tablet uses two columns, mobile stacks. Split stories stack on mobile; ministries use responsive previews; gallery uses a desktop mosaic and two mobile columns; Home leadership remains compact in two mobile columns. |
| 12. Image optimization | Approved CMS image variants at 320/960/1920 are reused with correct width descriptors, sizes, eager/high-priority hero loading, lazy below-the-fold loading, fixed ratios and cover cropping. Missing or failed images use branded native graphics. Only approved linked public media is requested. |
| 13. Tests | Structured-time validation, legacy compatibility, timezone validation, publication/concurrency/permissions, active ordering, bounded previews, event selection/unpublishing/failure isolation and safe idempotent schedule seeding are automated. Browser tests cover controls, touch, CMS editing/publishing, empty states, image errors and responsive accessibility. See completed results below. |
| 14. Portal regression | Existing authentication, member/ministry, attendance, Sunday School, Events and CMS tests are retained. Portal UI was not redesigned; the requested service editor is the new management surface. |
| 15. Preview sizes | Tested 1920?1080, 1600?900, 1366?768, 1024?768, 768?1024, 430?932 and 390?844. Actual local Home was run and visually inspected at 1366?768 and 390?844, with no overflow and three services. Screenshots are in `docs/screenshots/homepage-redesign`; `live_*` shows actual approved local data, other captures use isolated synthetic fixtures. |
| 16. Remaining content | Publish approved worship/church photographs, About, ministry profiles, sermons, Sunday School introduction, gallery albums, announcements and public contact/location details through the existing CMS. These richer sections appear dynamically as approved content is published. No fake production events, staff or imagery were seeded. |

## Editing the homepage

Open `/portal/website/homepage` to edit the existing Home draft. Hero headline/text/image/buttons, section visibility/order, events/ministry/announcement/gallery preview counts and featured published URL names are configurable. Publish the draft after review. Default order starts Weekly Services ? Upcoming Events ? Welcome ? Ministries; Leadership and Donate are preserved alongside the requested sections.

Open `/portal/website/service-times` for recurring services, or `/portal/website/settings` for general approved church details. The church timezone is an IANA value, initially UTC because no church timezone was previously configured; change it to the church's actual timezone and publish. Event instants use this timezone; service clocks retain their configured local hours regardless of the visitor's device timezone. Date-only sermon dates retain their calendar date.

## Data safety and performance

Backup before the schedule seed: `backups/before_user_administration_20261007T195718Z.dump` and matching fingerprint snapshot. All original records across 46 tables were verified unchanged. The only expected data change is a single website-settings row in the previously empty table containing the three explicitly supplied services. No Member, attendance, household, Sunday School, user, donation or Event data was seeded or modified.

Home event count is bounded at eight (default six). Ministries are bounded at four (default three), latest sermon at one, announcements at three, selected gallery albums at two and preview photos at five per selected album. Home body/summary text is trimmed for previews; full detail endpoints retain full content. Event reads use a savepoint so event-query failure returns a controlled unavailable state without losing the rest of Home.

The carousel uses the [W3C carousel semantics](https://www.w3.org/WAI/ARIA/apg/patterns/carousel/) and native [CSS scroll snap](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Scroll_snap). No automatic rotation is used.

## Completed validation

- New Home/service backend and existing publishing checks: 22 passed.
- Frontend unit tests: 42 passed.
- Home/public CMS browser checks: 13 passed, including touch and reduced-motion controls, live event unpublishing, service publication and seven screen sizes.
- Actual local Home: HTTP 200, three configured services and no overflow at both required inspection sizes.
- Full backend regression: 189 passed, plus the new preview/detail boundary test passed separately, for **190 distinct backend tests**.
- Portal/Donate regression: 33 passed in the main run; the existing Sunday School report heading exceeded its initial wait and passed on the fresh-server rerun. Combined with the 13 Home/public CMS scenarios, **47 distinct browser scenarios passed across runs**. No private portal implementation changes were required.
- Normal production build, TypeScript type check, ESLint and Python compilation passed. `alembic check` reports no pending schema operations.
- Browser fixtures were disposed after validation; screenshots use synthetic content only where clearly identified. Live screenshots show only the actual approved service schedule and public data.
