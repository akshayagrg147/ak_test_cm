# ViaCRM

Live production: **[https://13.234.72.21](https://13.234.72.21)**, hosted on the
dedicated EC2 instance in AWS Mumbai (`ap-south-1`).

Production deployment and automatic updates from Git are described in the
[AWS deployment guide](docs/AWS_DEPLOYMENT.md). A push to `main` deploys only
after the required checks pass and preserves database/upload volumes.

The web product now supports **real estate inventory, buyer briefs, site visits,
bookings and super-admin company subscriptions paid through your QR or cash collection**. See the
[real estate and subscription setup guide](docs/REAL_ESTATE_GUIDE.md). Android is
unchanged by this extension. Super admin creates company admin logins, manages
branding/logos and confirms UPI or collected cash before subscription activation.
Configure your payment methods and publish your own plans in Super admin.

An independent CRM built from the supplied acceptance brief. **WhatsApp is excluded.** The user added an Android call-sync companion on 18 October 2026, using the phone's built-in recordings and explicit folder access. See the [Android setup and limitations](android/README.md). The original local implementation kept reference repositories and production resources isolated; hosting now uses a separate, explicitly authorized AWS environment.

## Automatic production updates

Commit changes and push them to `main` in
[`akshayagrg147/ak_test_cm`](https://github.com/akshayagrg147/ak_test_cm):

```bash
git add .
git commit -m "Describe your change"
git push origin main
```

[GitHub Actions](https://github.com/akshayagrg147/ak_test_cm/actions) runs the
required checks, publishes immutable images, backs up production data and
replaces the application containers. Failed checks prevent deployment. Database,
uploads, encryption keys and login accounts persist across releases. Updates
have a short maintenance window. See the [operations guide](docs/AWS_DEPLOYMENT.md).

## Start locally

Requires Python 3.12+, Node 22.12+ (Node 24 recommended), npm and PostgreSQL command-line tools. Use the pinned dependencies in `backend/requirements.lock` and `web/package-lock.json`.

```bash
cd /Users/akshay/Documents/ChatGPT/test_ak/talkocrm
bash scripts/dev.sh
```

Open [the CRM](http://localhost:5173) and [interactive API documentation](http://localhost:8010/api/docs). The script starts a **dedicated PostgreSQL cluster on 127.0.0.1:55432**, applies Alembic migrations, creates explicit development fixtures when the database is empty, and starts the API, worker and web server. Ctrl+C stops the application processes; PostgreSQL data remains in `.local/postgres`. Stop that cluster with `pg_ctl -D .local/postgres stop` when no longer needed. Local PostgreSQL uses trust authentication on loopback only; use password authentication in a separate production environment.

Development fixture password: **`LocalCRM!2026`**. These fictional accounts are created only by an explicit development seed command, never by production startup.

| Role | Login phone | Workspace |
| --- | --- | --- |
| Platform owner | +919900000001 | Organization administration |
| Organization administrator | +919900000002 | Evergreen |
| Manager | +919900000003 | Evergreen |
| Telecaller | +919900000004 | Evergreen |
| Second telecaller | +919900000005 | Evergreen |
| Other organization administrator | +919900000006 | Northstar |

Companies are onboarded by the super admin. **Companies → Manage** adds/edits admin logins and changes/removes the company logo. **Plans & payments → Payment methods & instructions** enables UPI, cash collection (COD) or both. Payment requests remain pending until super admin verifies receipt; cash approval requires an explicit cash-received confirmation. Bank confirmation is not automatic. Public contact actions use `CONTACT_EMAIL` / `CONTACT_PHONE`; when absent the site shows a setup-required message. Configure brand and contact text in `.env`. Organization branding and qualification fields are configurable inside Studio → Workspace profile. Default workplace location is deliberately absent; configure a real workplace before checking in.

## What is included

- Telecaller-to-field-executive handoffs with shared caller coordination, confirmed
  site visits, acceptance, client history, next-action tasks and booking review.
  Create the Field executive role in People → Team directory; use Property →
  Field work or the client's Visit & field executive panel. See the
  [workflow guide](docs/REAL_ESTATE_GUIDE.md#telecaller--field-executive--booking).
- Real estate website; super-admin company/subscription management and company admin, manager and caller workspaces.
- Phone/password login, optional TOTP, short-lived bearer access, rotating HttpOnly refresh cookie, session revocation, deliberate support access, organization suspension and last-admin guards.
- Leads, queues, filters, private saved views, exports, CSV/XLSX preview/import/error download, explicit assignment and locked round robin.
- Complete lead workspace with rule-based score, notes, private documents, manual outcomes, callback scheduling, lost-deal manager handoff, task and assignment history, and transactional merge.
- Tasks, calendar, reminders, internal automations and durable PostgreSQL worker with retries and execution history.
- Geofenced attendance, timezone-specific midnight catch-up, pending attendance-derived time, employee time/leave submissions and role-limited reviews.
- Admin-only pay configuration, work schedule/holiday exceptions and decimal-safe payroll estimates with documented source-overlap policy.
- Analytics, saved report definitions, notifications, team management, audit export and application JSON snapshots.
- Encrypted IndiaMART polling adapter, token-protected Justdial webhook, provenance deduplication, visible setup/error/sync states.
- Idempotent device-call ingestion, private recording upload/playback, filters, reassignment-based access revocation and call-count deduplication.
- Migrations, OpenAPI, CI, Docker Compose, same-origin reverse proxy, optional HTTPS edge, backup/restore and rollback runbook.

## Verification

The initial AWS release passed **288 backend tests**, **86 Chromium browser
journeys**, **7 deployment-tool tests**, Android unit/build/lint checks and a
Docker restart/persistence drill. Public HTTPS, API/database/worker health and
the separately initialized production-owner login were verified on the server.
Historical `artifacts/` links below refer to local evidence excluded from Git;
current automated results and downloadable reports are in GitHub Actions.

The field-executive extension passed **269 backend tests** (90.77% line coverage)
and **70 full browser journeys per Chromium, Firefox and WebKit**. Further focused
checks cover the final phone layout and field-staff time approval. Android source
and the existing APK retain their hashes. See the
[handoff and field-work verification](artifacts/field-handoff/QA_REPORT.md).

The super-admin/payment extension passed **252 backend tests** (90.41% coverage)
and **65 production browser journeys per Chromium, Firefox and WebKit**. Admin
accounts, company branding, cash receipt confirmation and legacy UPI behavior are
covered; Android source/APK hashes remain unchanged. See the
[super-admin/payment verification report](artifacts/super-admin-payments/QA_REPORT.md).

The 25 October audit passed **242 backend tests** (90.17% line coverage), **61 production-website journeys in each of Chromium, Firefox and WebKit**, **38 Android 15 instrumentation cases**, **13 lifecycle checks**, and **32 JVM tests**. Four mobile history cases also passed at 320dp/130% text. The latest signed **Aven Realty 1.1.4** history-recovery fix additionally passed 25 directory/history checks, 4 small-screen checks and 32 JVM tests; it retained the existing account and decoded the actual uploaded recording to completion. See its [focused verification](artifacts/android/history-recovery/REPORT.md). See the [full audit and remaining environment checks](artifacts/full-audit-20261025/QA_REPORT.md), [acceptance record](docs/ACCEPTANCE.md) and [Android matrix](android/QA_MATRIX.md). Physical OEM recording, live provider delivery and permanent hosting still require their respective environments.

With the dedicated local PostgreSQL cluster running and Node selected through `.nvmrc`:

```bash
bash scripts/test.sh
```

Backend tests use `talkocrm_test` and refuse databases whose name does not end in `_test`. They truncate **only that dedicated test database**. They test real PostgreSQL transactions and concurrency. `scripts/test_browser.py` creates a disposable `_test` database, applies migrations, seeds fictional accounts, and starts its own API, worker and website on unused ports. It stops those processes and removes that database after the run. `--production` tests the built website; use `--browser firefox` or `--browser webkit` after installing the respective Playwright engines. `DATABASE_URL` supplies the PostgreSQL connection, whose user must be allowed to create test databases. Running Playwright directly uses `E2E_BASE_URL` and can mutate that selected workspace; prefer the isolated runner.

Individual commands:

```bash
cd backend
../.venv/bin/alembic upgrade head
../.venv/bin/ruff check app tests
../.venv/bin/pytest -q --cov=app --cov-report=term-missing
cd ../web
npm ci
npm run lint
npm run build
npx playwright install chromium
cd ..
.venv/bin/python scripts/test_browser.py --production
```

Read [acceptance and test results](docs/ACCEPTANCE.md), [permissions and domain rules](docs/ARCHITECTURE.md), [deployment and recovery](docs/OPERATIONS.md), and [provider setup](docs/INTEGRATIONS.md). Test output, coverage, browser report and responsive screenshots are in `artifacts/`. No finite test suite proves every possible edge case; the checklist records what was exercised and what remains dependent on external systems.

## Production boundary

Do not use development accounts or local database configuration in production. The AWS installation uses a fresh database, private storage, unique production secrets and a separately initialized owner. For a new independent environment, provision fresh storage and secrets, set `ENVIRONMENT=production` and a unique HTTPS `PUBLIC_ORIGIN`, apply migrations and create the first owner using `python -m app.seed --bootstrap-owner`. Provider accounts must be configured and verified with real delivery. See the [AWS deployment and recovery guide](docs/AWS_DEPLOYMENT.md).

## Client presentation and visual identity

**Home → Overview** has separate admin/manager and telecaller dashboards with
workplace-date activity charts, priority clients, tasks and visits. Use Today,
Last 7 days or Last 30 days; admins can select a team member. Callers see their
permitted clients and own activity. Charts have exact-value tables and honest
empty states. Super admin has company subscription/team-size charts. Booking
and portfolio figures remain current company totals, as labeled.

The product uses **ViaCRM**, with a connected V symbol, cobalt blue and mint accents. Public pages, login, navigation, page titles and the favicon share the identity. Company brands/logos remain configurable. Export-ready SVG/transparent PNG variants and a preview are in `artifacts/viacrm-brand/`; web masters are in `web/public/brand/`. See [design and presentation notes](docs/DESIGN.md).

`bash scripts/dev.sh` also creates a separate, fictional **Meridian Studio** workspace when it does not exist. It never resets existing workspaces. Demo admin: `+919900000007`; password: `LocalCRM!2026`. Manager: `+919900000008`; callers: `+919900000009` and `+919900000010`, with the same development password. These fixtures are disabled outside development.

For an existing local installation, run `cd backend && ../.venv/bin/python -m app.pitch_demo` once. Capture all presentation screens with `cd web && node scripts/capture-pitch.mjs` while the local services are running. The isolated browser runner creates its own fixtures, keeping test records out of the working CRM.

Set `BRAND_NAME` in `.env` for the public site and login. An organization administrator can set a workspace name, brand and logo in **Studio → Workspace profile**. A browser refresh picks up new organization branding; server environment changes require an API restart.

## Recording customer interests

In **Sales → Leads → Open a lead → Edit details**, enter **Products/services of interest**, one item per line. This field is available for every business type. The **Lead score** card also provides **Add interests / Edit interests** for a focused editor. Your team records what the customer tells them; the application does not infer interest from notes or calls.

Any recorded interests contribute 15 points in total. More items do not add more points. Clearing the field removes those 15 points. The score remains automatic. Entries are trimmed, deduplicated without case sensitivity, and limited to 30 items of 160 characters each. CSV/XLSX imports use the `interests` column with `|` between items; exports include that column.

For versioned browser evidence, run `.venv/bin/python scripts/test_browser.py --production --artifacts artifacts/interests` from the repository root.
