# Working on this project

Keep this independent CRM isolated from the reference repositories and production resources. WhatsApp remains excluded. The user explicitly added an Android call-sync APK on 18 October 2026; it must use the phone's built-in recordings with explicit folder access and report device limitations honestly. Do not add pricing/subscriptions or deploy/push without an explicit instruction.

On 25 October 2026 the owner selected ViaCRM as the web product brand and
authorized a new logo. Use the connected V masters in `web/public/brand/`, retain
company-specific brand/logo overrides, and leave the native Android app unchanged.

The owner also requested professional admin/telecaller dashboards with charts.
Use real role-scoped data and workplace time buckets; keep linked-call remarks
deduplicated. Current priority work excludes closed/DND/archived clients. Retain
readable text, keyboard-accessible chart data and explicit period/current labels.

The callback bell is automatic: count unresolved overdue callbacks using current
tenant/role/lead access, exclude closed/DND/archived clients, and keep alerts after
viewing or phone sync until a result is saved or the callback is rescheduled.
Callback tasks clear through their own completion flow. Use the paged
`/api/notifications/inbox`; retain the legacy notifications array contract. Keep
honest loading/error states, active-tab refresh, readable keyboard/mobile access
and the Android source/APK unchanged.

On 24 October 2026 the user explicitly authorized adapting the web product for real estate, super-admin company onboarding/branding and company subscriptions paid through the user's QR. QR payment claims require super-admin verification; do not claim automated bank confirmation. Do not modify the Android source, APK or its call-sync API contract for this work. Deployment/push remains separately authorized.

On 25 October 2026 the user explicitly made their tested `aven-calls-android.zip` the Android logic baseline (archive SHA-256 `cbd6945b58960f0ffd2d441056ad82dc1d9e0badbdf6726666d217cf233e05e9`). Preserve its timestamp-based recording matching, closest eligible call selection, expedited uploads with quota fallback and recheck of empty recording files. Future UI work must preserve these behaviors. Compatibility fixes and regression tests may extend this baseline; do not restore the old phone-number-required matcher without a new user instruction. See `android/LOGIC_BASELINE.md`.

The user then explicitly authorized a real-estate Android UI and proper testing.
This is Aven Realty 1.1.0: Home, Leads, Calls, More and a read-only property
catalogue using existing real-estate APIs. Preserve the tested calling logic and
same application ID/signing key for updates. See `android/REAL_ESTATE_UI.md`.

The 1.1.1 fix fetches assigned leads after sign-in independently of call-upload
consent/permissions. `LeadDirectory` uses the existing assigned-contacts API and
sync lock; never enable collection to read assignments. Preserve complete-page
account/company checks, cached-data retention on errors and honest empty states.

The 1.1.2 lead View history screen reads the existing permission-filtered CRM
history and files APIs. Keep CRM history separate from the local call outbox.
Recordings use authenticated, bounded private downloads and in-app playback;
stop playback and remove its temporary file on background/session changes.
Telecallers must not get any recording-delete action. WhatsApp remains excluded.

Version 1.1.3 cleans up prior-process playback previews on MainActivity startup.
Keep process-specific preview filenames, preserve active previews created by the
current process, and never delete pending call/upload data during this cleanup.

The user subsequently authorized super-admin company administrator management,
logo controls and subscription payments through UPI or COD. They explicitly
confirmed COD means cash collected in person, with super-admin receipt confirmation
before activating a plan. Preserve pending-payment/idempotency/seat/last-admin
guards and existing UPI history. Cash starts disabled until configured. This web/API
extension must leave Android source/APK and call-sync contracts unchanged.

Version 1.1.4 retries a failed history screen when it resumes. Do not interpret
an HTML/unstructured proxy 404 as a confirmed lead reassignment; use the CRM
error code. Preserve current-permission checks and file-picker exports.

- Backend: FastAPI, SQLAlchemy and PostgreSQL only. Run from `backend/` with the root `.venv`.
- The user added a dedicated field-executive visit/handoff/follow-up flow and
  explicitly confirmed shared coordination: caller keeps access, executive takes
  responsibility. Preserve primary caller ownership/Android allowlists. Scope the
  new role to current handoffs/self-owned leads and own private work. Require
  executive acceptance, dated next steps, version checks and company locks. Keep
  recordings non-deletable for callers/executives; reassigning revokes former
  executive access. The Android APK/source remains unchanged by this web feature.
  Early attended visits require explicit confirmation and an actual past time;
  retain the original schedule and keep future no-shows blocked. Revision 0009
  preserves this actual attendance separately and guards data-losing rollback.
- Apply and extend Alembic migrations; never replace them with automatic production `create_all`.
- Preserve the server permission matrix in `docs/ARCHITECTURE.md`. Check current account/org state and use the organization lock for mutations that affect invariants.
- Keep credentials, session hashes and private storage keys out of serializers/audits. File access must use current lead/call permissions.
- Use `backend/requirements.lock` and `web/package-lock.json`; update locks intentionally.
- `bash scripts/dev.sh` starts the dedicated local environment. `bash scripts/test.sh` runs local checks with PostgreSQL running. Browser checks must use `scripts/test_browser.py` and its disposable database/services; direct Playwright runs may mutate the selected CRM.
- Tests may truncate only a dedicated database whose name ends in `_test`. Never point tests at a production or development database.
- Backend: `../.venv/bin/ruff check app tests` and `../.venv/bin/pytest -q`.
- Web: `npm run lint`, `npm run build`, `npx playwright test`.
- Record verification truthfully in `docs/ACCEPTANCE.md`. Provider mocks do not prove real integration. Docker configuration validation does not prove container deployment.
