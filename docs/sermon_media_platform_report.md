# HOPFAN sermon media platform

Implementation and local verification: 8 October 2026. This extends the existing public website and Website CMS. A sermon remains one existing content record with attached video, audio and study materials. No synthetic sermons, speakers, series, categories or media were inserted into the production database.

## Required implementation report

| Item | Result |
| --- | --- |
| 1. Existing sermon code reused | Existing `ContentEntry(kind=SERMON)`, draft/published snapshots, Website CMS navigation, API session/CSRF/RBAC, public layout, reviewed website images and homepage composition are retained. Legacy website sermon mutations delegate to the new sermon authority; they cannot bypass sermon permissions or readiness checks. |
| 2. Models | Five new tables: `sermon_media_assets`, `sermon_series`, `sermon_categories`, `sermon_metrics`, `sermon_playback_receipts`. Existing content JSONB holds sermon metadata and selected asset references; media binaries remain outside PostgreSQL. Guest speakers need no Member record. Private member/ministry associations never appear in public DTOs. |
| 3. Migration | Forward revision `bc73e2a94d16`, following homepage revision `ab61d4f83c02`, creates those tables, expands status validation only for sermons, adds a partial publication/date index and ten explicit permissions. Sermon Editor and Sermon Publisher roles are added without assigning them to users. Corresponding existing website permissions receive sermon grants; System Administrator does not acquire publishing through technical administration. Applied locally; Alembic reports no pending model changes. |
| 4. Storage architecture | `MediaStorageService` is the single storage boundary for private upload, deletion, streaming and short-lived signed delivery. Provider SDK calls remain in that adapter. Metadata records hold generated keys, MIME, size, checksum, duration, dimensions, bitrate, quality and job status. Browser DTOs omit keys, credentials and local paths. |
| 5. Development storage | Default private root is `storage/dev/sermons/`. Staging uses `.staging/<asset UUID>.part`; validated objects use `objects/sermons/<sermon UUID>/<asset UUID>.<format>`. The folder is ignored by Git. Files are available only through controlled API URLs; there is no static mount of this directory. |
| 6. Production storage readiness | A private S3-compatible adapter uses managed uploads and signed GET redirects with inline/attachment response headers. boto3 is imported lazily, keeping desktop/API startup independent of media configuration. Adapter behavior is tested with a mocked S3 client. No provider account, bucket, production CDN or real cloud upload was configured or tested. |
| 7. Video streaming | HOPFAN-owned H.264 MP4 and supported WebM upload/playback; approved external HTTPS media and validated YouTube/Vimeo embeds are supported. Native video supplies seek, volume, fullscreen and browser picture-in-picture, with conservative metadata preload and playback speed. External embeds load only after an explicit watch action. |
| 8. Range requests | Local delivery uses Starlette FileResponse, with tested HTTP 206, Content-Range, Accept-Ranges, correct lengths and invalid-range HTTP 416. Requests cannot specify arbitrary filesystem paths; multipart ranges are rejected. Files are streamed without loading the whole video into memory. Private object delivery redirects to a short-lived signed URL; the provider must support range delivery. |
| 9. Audio | MP3, AAC M4A and supported PCM WAV are inspected and played through native audio controls. Approved external audio URLs are optional. Automatic video-to-audio extraction is reserved for a future worker; third-party video is never extracted. |
| 10. Downloads | Audio and video downloads have separate CMS switches, controlled endpoints, clean `HOPFAN-<slug>-<speaker>.<format>` filenames and visible sizes. PDF notes and text transcripts can be downloaded separately when their asset permission permits it. |
| 11. Download authorization | Every download rechecks current publication, PUBLIC visibility, selected READY asset, ownership/rights and asset distribution permission. Audio/video additionally require the matching published sermon download flag. Disabling the asset flag revokes new downloads immediately and is audited; stale version changes are rejected. Issued object-storage URLs can remain usable until their configured expiry. |
| 12. Thumbnails | Custom JPEG/PNG/WebP uploads are decoded, EXIF oriented, cropped to 16:9 and compressed to JPEG up to 1280px without upscaling. Administrators may also select existing approved website imagery. Library, homepage, watch and related cards retain consistent ratios and safe branded fallbacks. |
| 13. Series/playlists | Actual CMS-managed series have names, stable slugs, descriptions, ordering, approved cover imagery and draft/published snapshots. `/sermons/series/<slug>` shows published collection metadata, sermon count and matching public messages. |
| 14. Categories/tags | Categories are CMS-managed records with publication and ordering. Tags are bounded sermon metadata, editable as comma-separated values and included in server search. No fixed production category seed or separate many-to-many tag catalog is introduced. |
| 15. CMS screens | `/portal/website/sermons` provides real status counts, recent uploads, search/status filtering, media/download badges, series, visibility and permitted play/download totals. Dedicated new/edit screens provide Basic Information, Organization, Media Sources and Publishing; drag/drop progress/cancel, previews, previous asset selection, replacement, failed inspection retry, per-asset download permission and confirmed deletion are functional. Series/categories have create/edit/publish/archive controls and artwork selection. |
| 16. Publishing workflow | Drafts default PRIVATE. Explicit publication requires SERMON_PUBLISH and usable authorized selected media. Metadata/media edits retain the existing public snapshot until republished. Scheduled records freeze their snapshot and publish automatically when due; the active publisher's permission is rechecked. Archive/unpublish removes new public access. Public URLs remain stable after publication. |
| 17. Public library | `/sermons` is server-rendered with featured/latest message, 16:9 media cards, series previews, pagination and server search over title, speaker, scripture, descriptions, series, category and tags. Filters support series, speaker, category, year and media type. Popular sorting uses actual aggregate plays; it is never fabricated. Listing cards do not load video/audio files. |
| 18. Watch page | `/sermons/<slug>` has a large player/content column with related messages beside it on desktop and below it on mobile. Public description, speaker/date, scripture, tags, series/category, optional transcript, caption track, study notes, copy link, accurate media structured data and canonical metadata are supported. Approved public speaker profiles may be linked. |
| 19. Watch/listen switch | Native video/audio modes switch within one sermon record, pausing the previous player. Homepage Listen opens the same sermon in audio mode. Neither mode autoplays with sound. |
| 20. Related sermons | Deterministic ordering prioritizes the next same-series message, other same-series messages, category, speaker and recent published messages. No private/draft records or artificial recommendations are exposed. |
| 21. Analytics | Separate aggregate counters track video plays, audio plays and download initiations. The hosted player reports a play after its timeline reaches ten seconds; an anonymous tab/day token deduplicates the same event for 24 hours. Card loads do not count, external-provider plays are not estimated, and no member progress history is stored. Public counts are aggregate summaries; detailed CMS counters require SERMON_VIEW_ANALYTICS on the backend. These are modest traffic counters, not fraud-resistant billing or completed-download measurements. |
| 22. Bandwidth | No listing autoplay/preload, lazy compressed thumbnails, native progressive seeking, metadata-only player preload, audio mode and visible download sizes reduce unnecessary transfers. Video quality is reported from the source; no artificial quality ladder is advertised. |
| 23. Upload security | Authenticated streamed uploads enforce Origin/CSRF, sermon permissions, declared type, extension, actual inspected container/codec, size, generated paths and rights/consent attestation. Safe ffprobe arguments disable network protocols, set a 45-second timeout and bounded metadata response. Images reject decompression bombs; captions/text reject active HTML/script content; PDFs reject common active-action/embedded-program markers. Uploads are private until READY and explicitly published. This is format inspection, not a general malware scanning service. |
| 24. Backend tests | The broader backend regression run passed 205 tests before the final refinements. The final sermon, migration, storage and publishing run passed all 25 tests. Coverage includes real fixture media, large streamed upload, download revocation/concurrency, range/invalid range, visibility, legacy snapshot preservation, scheduling, series/search, deletion, ownership/permission rejection, private S3 adapter behavior and interrupted inspection recovery. Tests use temporary isolated schemas and local synthetic files. |
| 25. Frontend tests | 44 unit tests passed. TypeScript and ESLint passed. The production Next.js build passed. All 13 sermon and public giving browser checks passed. Across the sermon, giving, homepage/CMS and existing portal runs, 52 distinct browser checks passed; the final three sermon checks were additionally repeated after the last refinements. |
| 26. Responsive tests | Public library/watch/series tested at 1920, 1366, 768 and 390px. CMS list/new/edit tested at 1366 and 390px. Overflow and WCAG A/AA checks cover public and CMS screens. Final screenshots are in `docs/screenshots/sermon-platform/`; these show synthetic fixtures confined to the browser test database. The final library, watch, series, CMS list and new/edit screens were visually inspected at desktop and mobile widths; all 18 screenshots are retained. The three final sorting/artwork/media-metadata/responsive checks also passed after the last refinements.. |
| 27. Existing portal regression | The 13 homepage/public CMS browser regressions passed, covering public Home, events, ministries, gallery, publication and public/private separation. All 26 existing login, RBAC, workspace, attendance, Sunday School and portal browser regressions passed, including responsive light/dark themes. Existing backend authentication, workspace, attendance, Sunday School, events, inquiries and finance regressions passed in the broader suite. |
| 28. Desktop regression | `python -m scripts.check_desktop_startup` opened the actual HOPFAN desktop application, kept it running for 31 seconds and closed it cleanly. No desktop screens were redesigned. Private media SDK initialization is deferred to media operations. |
| 29. Exact limits/configuration | VIDEO 2 GiB; AUDIO 200 MiB; THUMBNAIL 8 MiB; DOCUMENT 20 MiB; CAPTION and TRANSCRIPT each 2 MiB by default. Exact byte values and environment names are below. CMS reads limits from the backend and the backend independently enforces them. |
| 30. Remaining production infrastructure | Choose/configure a private S3-compatible provider, verify real provider upload/range/CORS behavior, configure public HTTPS origins and proxy upload limits, and establish storage backup/lifecycle/monitoring. HLS rendition ladders, durable distributed queues, transcoding/audio extraction, generated thumbnails, resumable browser uploads, CDN signing, PWA background audio, account progress and richer provider analytics remain future infrastructure. Uploaded media is accepted only in the documented playable formats. |

## Local usage

Start the existing API with `.venv\Scripts\python.exe run_api.py` and the website with `npm.cmd run dev` from `web/`. Open `/portal/website/sermons`, create a draft, set the speaker/date/metadata, save, then upload authorized video/audio/thumbnail files. Wait for READY, preview, choose PUBLIC visibility, set download permissions if needed and publish. YouTube/Vimeo sermons can be published with a validated provider URL without uploading a duplicate video record. Series/category drafts need their own publication.

Scheduled publication runs every 30 seconds while the API is running when `SERMON_SCHEDULER_ENABLED=true`. The command `.venv\Scripts\python.exe -m scripts.publish_scheduled_sermons` also performs an idempotent due-publication pass. Scheduling uses the browser's selected local time converted to an aware timestamp; the stored schedule is UTC.

Media inspection uses an in-process background task, not a durable distributed job queue. Failed inspections retain private staging for retry; a failed or interrupted upload may instead be replaced. For queued/failed staged files, run `.venv\Scripts\python.exe -m scripts.process_sermon_media`. **Stop all API and inspection instances first** before using `--recover-interrupted`; that option recovers unfinished UPLOADED/PROCESSING jobs after a restart. Recovery never publishes a sermon and processes at most 100 staged jobs per pass. No recovery command was run against production assets during implementation.

## Backend configuration

Set configuration only in the ignored backend `.env` or the deployment secret store. Do not place storage keys in `NEXT_PUBLIC_*` variables or paste them into browser code. `.env.example` contains placeholders.

| Environment variable | Default / purpose |
| --- | --- |
| `SERMON_STORAGE_PROVIDER` | LOCAL in development; S3 otherwise. Explicit LOCAL is refused outside development. |
| `SERMON_LOCAL_ROOT` | `D:/HOPFAN/storage/dev/sermons`; also supplies private inspection staging for S3. |
| `SERMON_VIDEO_MAX_BYTES` | 2147483648 |
| `SERMON_AUDIO_MAX_BYTES` | 209715200 |
| `SERMON_THUMBNAIL_MAX_BYTES` | 8388608 |
| `SERMON_DOCUMENT_MAX_BYTES` | 20971520 |
| `SERMON_TEXT_MAX_BYTES` | 2097152, separately applied to each caption/transcript upload |
| `SERMON_FFPROBE` | `ffprobe`; a trusted executable path may be configured. FFmpeg/ffprobe was available locally during verification. |
| `SERMON_SCHEDULER_ENABLED` | true from environment; scheduler checks due publication every 30 seconds |
| `SERMON_SIGNED_URL_SECONDS` | 300; allowed range 30–900 seconds |
| `SERMON_S3_BUCKET` | Private media bucket; required for S3 operations |
| `SERMON_S3_ENDPOINT` | Optional HTTPS S3-compatible endpoint; leave empty for standard AWS S3 |
| `SERMON_S3_REGION` | us-east-1, adjust for selected provider |
| `SERMON_S3_ACCESS_KEY`, `SERMON_S3_SECRET_KEY` | Backend secrets; prefer deployment credentials/roles when supported |
| `SERMON_ALLOWED_AUDIO_HOSTS`, `SERMON_ALLOWED_VIDEO_HOSTS` | Comma-separated exact approved HTTPS hosts for external native media; empty by default. Validated YouTube/Vimeo embeds are handled separately. |

Size overrides must be between 1 byte and 10 GiB. Raising limits also requires sufficient staging disk, proxy/body/time limits and provider policy. Browser uploads currently stream through the authenticated API; they are not resumable browser multipart uploads. Storage changes do not automatically move existing objects: migrate existing keys/files before changing provider/root/bucket.

For S3, set `APP_ENV=production`, `SERMON_STORAGE_PROVIDER=S3`, bucket/region/HTTPS endpoint as appropriate, and backend credentials. Keep the bucket private. Restrict object permissions to the media prefix and configure its CORS for the actual public/portal origin, GET/HEAD and Range, exposing Content-Range/Content-Length/Accept-Ranges/Content-Disposition. Confirm signed URL expiry and upload/seek/download behavior with owned test media before launch. No permanent public bucket URL is required. Use HTTPS API/public origins and existing secure-cookie production settings.

Accepted formats: H.264 MP4 with AAC/MP3 audio; WebM with VP8/VP9/AV1 video and Opus/Vorbis audio; MP3; AAC M4A; supported PCM WAV; JPEG/PNG/WebP thumbnails; UTF-8 TXT; WebVTT; PDF without detected active actions. Unsupported codecs need conversion outside the HTTP request. Local ffprobe inspection uses a maximum duration of seven days and a 45-second process timeout.

## Data preservation

A verified pre-migration PostgreSQL backup and fingerprint snapshot are retained locally under ignored `backups/`. The migration test preserves legacy sermon snapshots, slugs, credentials and authorization revision exactly. The migration contains table/index/constraint creation and append-only permission/role grants; it does not update users or church operational records.

The audit of all original live tables matched church/content records and retained original append-only rows. Runtime rate-limit bucket values, the user record and session rows changed during the running local system; those security/runtime tables were therefore not asserted byte-for-byte unchanged, and were not restored over active sessions. No production sermons, series, categories or sermon assets were seeded. A read-only comparison of the live user with the verified backup identified only last_login_at and updated_at changes; password hash, authorization revision and TOTP settings were preserved. All five new live sermon tables remain empty..

## Validation commands

```powershell
.venv\Scripts\python.exe -m pytest tests/test_sermon_media.py tests/test_sermon_migration.py tests/test_sermon_storage.py tests/test_content_publishing.py -q --tb=short -p no:cacheprovider
.venv\Scripts\python.exe -m scripts.check_desktop_startup
.venv\Scripts\python.exe -m alembic check
```

From `web/`:

```powershell
npm.cmd test -- --maxWorkers=1
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
npm.cmd run test:e2e -- sermons.spec.ts donations-leadership.spec.ts
npm.cmd run test:e2e -- homepage-redesign.spec.ts public-cms.spec.ts
npm.cmd run test:e2e -- operations.spec.ts workspace.spec.ts portal.spec.ts login-stability.spec.ts
npm.cmd run test:e2e -- sermons.spec.ts --grep "public library|watch/listen|responsive"
```

Browser test startup creates and later removes an isolated fixture schema and private synthetic media. No real payment or external video download is performed.

Implementation references: [Starlette FileResponse range behavior](https://www.starlette.dev/responses/), [Boto3 private signed URLs](https://docs.aws.amazon.com/boto3/latest/guide/s3-presigned-urls.html), [FFprobe inspection options](https://ffmpeg.org/ffprobe.html).

## Review evidence

- Public desktop/mobile: `screenshots/sermon-platform/library_1366.png`, `library_390.png`, `watch_1366.png`, `watch_390.png`.
- CMS desktop/mobile: `cms_1366.png`, `cms_390.png`, `editor_1366.png`, `editor_390.png`, `edit_1366.png`, `edit_390.png` in the same directory.
- Series and wider/tablet public captures are retained alongside these files.
- Final normal production build and ESLint passed; the generated Next.js type imports point back to the normal build directory.
- Live API health returned HTTP 200, public sermon/series/category endpoints returned HTTP 200 with zero synthetic records, and unauthenticated CMS access returned HTTP 401.
