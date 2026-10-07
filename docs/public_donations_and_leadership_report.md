# Public donations and leadership refinement

This change extends the existing public route group, header, footer, stylesheet, CMS projections and API client. Desktop UI and internal church operational modules are unchanged. A shared donation model/API and a small protected portal finance view were necessary for payment persistence and private donor visibility.

| Requested item | Implementation |
| --- | --- |
| 1. Navigation | **Donate** in the existing desktop/mobile navigation and footer. Home links directly to `/donate`. |
| 2. Donate page | `/donate` contains Support the Ministry, backend purpose selection, donor name/email, optional phone/note, amount validation and hosted checkout. `/give` permanently redirects to it. |
| 3. Payment integration | Repository inspection found no existing payment integration or financial record entities, only a finance workspace placeholder. One shared backend `PaystackService` now initializes and verifies hosted TEST checkout and validates signed webhooks; no second provider implementation exists. |
| 4. Persistence | `donations` stores one record per browser attempt: reference, private donor details, exact decimal amount, currency, category snapshot, note, provider references, TEST mode, status, created/updated/paid timestamps. `donation_categories` supplies seven initial purposes, active status and explicit ordering. No donation records are seeded. |
| 5. Home CTA | Support the Mission with a Donate Now button, using existing public colors and spacing. |
| 6. Leadership source | Existing published `website_content` LEADERSHIP snapshots and approved linked media. Private Member records, contact details and unpublished draft changes are excluded. |
| 7. Home count | Up to **eight distinct published profiles**, prioritizing existing featured URL names then published display order with stable tie breakers. Fewer real profiles render fewer cards; no names or people are fabricated. |
| 8. Full leadership page | `/leadership` lists the complete published roster through existing pagination, ordered by published display order. Cards show public name, role, short summary and a biography link. Group headings are omitted because the existing data has no leadership group field. |
| 9. Responsive/accessibility | Four leadership columns on desktop, two on tablet/small phones, one below 420px. Donation layout stacks on tablet/mobile. Missing and failed portraits use initials, including failures before hydration. Labels, keyboard controls, errors and receipt states use the existing accessible public components. |
| 10. Validation | See the final validation results below. All payment tests use an isolated synthetic TEST provider and disposable PostgreSQL schemas; no real Paystack charges are executed. |

## Paystack TEST setup

1. Keep the existing backend `.env`, database configuration and `APP_ENCRYPTION_KEY`. Add `PAYSTACK_SECRET_KEY` containing your **TEST secret key** and `PAYSTACK_CURRENCY` matching the merchant account (GHS is the configurable default). Never put this secret in the web environment or a `NEXT_PUBLIC_*` variable.
2. Set backend `WEB_PUBLIC_ORIGIN` to the actual website origin. Local development uses `http://localhost:3000`. Hosted staging must use HTTPS. The integration fixes the callback to `/donate/result`; cancel checkout returns there with the reference as well.
3. Set the Paystack dashboard's **TEST webhook URL** to your publicly reachable backend `/api/v1/payments/paystack/webhook`. Localhost cannot receive provider webhooks; use a protected development tunnel or staging API with the existing host/CORS configuration. The application verifies SHA512 HMAC over the original request bytes.
4. Apply `python -m alembic upgrade head` on other installations, then restart the API. This release accepts TEST keys exclusively and explicitly labels test checkout. No live-key activation is included.
5. Open `/donate`. Use the provider's documented TEST payment details, complete hosted checkout, then return to the same browser tab for the receipt. Failed/cancelled payments offer retry and Home links; pending payments can be checked again. Do not treat an unconfirmed payment as paid.

Checkout intentionally remains unavailable until the backend credentials are configured. The form explains this and links to the church contact page. Publishing actual leadership profiles in the existing CMS immediately feeds both Home and `/leadership`.

## Payment verification and privacy

Initialization persists before checkout. UUID idempotency keys and PostgreSQL locking prevent repeated/concurrent submissions from creating duplicate checkout records. Settlement locks the existing donation, checks reference, amount in minor units, currency, TEST domain, provider transaction ID and payment timestamp, and never downgrades a successful record. Duplicate notifications settle once.

A donation reference alone cannot read a receipt. A purpose-specific receipt capability stays in the checkout browser's tab storage, expires after 30 days, and never appears in the callback URL. Public receipts contain only amount, purpose, reference, status and paid timestamp. Names, email, phone, notes, provider instrument data and credentials are never public. Only the explicit `DONATIONS_VIEW` permission can access `/api/v1/finance/donations` and `/portal/finance`. The additive migration grants it to ADMINISTRATOR and FINANCE_OFFICER, without giving technical admins or ministry officers automatic financial access.

Provider calls use a fixed HTTPS API, bounded response sizes, timeouts and no redirects. Webhook payload sizes are bounded. Existing origin checks, request limits, safe errors, authorization and secret-free logging remain in use.

The integration follows Paystack's [hosted checkout](https://paystack.com/docs/payments/accept-payments/), [verification](https://paystack.com/docs/payments/verify-payments/), [webhook signature](https://paystack.com/docs/payments/webhooks/) and [cancel redirect](https://paystack.com/docs/payments/metadata/) contracts.

## Final validation results

- Backend: **175 passed**, including 34 donation validation/privacy/signature/settlement/concurrency checks and the new additive migration test, plus existing authentication, publishing, sessions, attendance and Sunday School API regression checks.
- Frontend unit tests: **38 passed**, including safe giving contracts and anonymous API-client behavior.
- Production build, `tsc --noEmit`, ESLint and Python compilation passed.
- Local migration applied: `f8a62e931d04`; `alembic check` reports no pending schema operations. The verified backup is `backups/before_user_administration_20261007T145558Z.dump`, with its matching fingerprint snapshot. Every original row in the 44 existing tables was preserved.
- Local API returns seven dynamic purposes, TEST mode and `enabled=false` while no Paystack TEST key is configured. There are zero seeded donation records and zero invented public leadership profiles.
- Browser regression: **40 distinct scenarios passed across runs**. The initial full run passed 34 before its test web server stopped during screenshot collection; the six interrupted checks and all eight new giving/leadership scenarios passed in the final fresh-server run (**14/14**). Paystack was simulated only inside the disposable test fixture; no real provider network or live charges were used. Windows emitted transport-reset notices during intentionally aborted test requests; PowerShell marked the redirected command nonzero after stderr output, while Playwright reported every final test passed and fixture cleanup returned 200.
- Review images in `docs/screenshots/public-giving` use only clearly synthetic, disposable CMS content.
