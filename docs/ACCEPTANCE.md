# Acceptance and verification

## Final scope

Independent web CRM, API, PostgreSQL persistence, durable workers, public website, platform-owner workspace, team operations and deployment packaging. **WhatsApp remains excluded. The user explicitly added the Android call-sync APK on 18 October 2026**, superseding the earlier Android exclusion. The APK syncs call metadata and accessible recordings created by the built-in Phone app. It does not capture cellular audio itself. No original source repository or production resource was modified. No site was deployed or repository pushed.

## ViaCRM brand identity — 25 October 2026

The owner selected ViaCRM. Public/login/workspace identity, browser titles,
favicon, preview labels, API brand default and local configuration now use the
new name and connected V mark. The kit includes outlined SVG masters for light,
dark and single-color use, transparent PNGs (1428×320 wordmarks, 1024×1024 icon),
a palette presentation and usage notes. All 11 files in the brand ZIP were checked;
PNG transparency and ZIP integrity passed. The existing presentation company's
legacy placeholder brand was updated through its audited settings API, preserving
all other settings. Other company names, custom brands/logos and Android remain
unchanged.

Five Chromium production-bundle journeys passed: default ViaCRM identity,
company-brand overrides, public interactions, core-page accessibility, and long
company names at 320–1440px. The focused login Axe scan reported no serious or
critical violations. Build, lint, formatting and backend Ruff checks passed.
The live API reports ViaCRM and API/database/worker health remains good.
Evidence and the downloadable kit are in `artifacts/viacrm-brand/`.
No full backend, other browser-engine or native suite was rerun for this
branding-only change.

## Telecaller → field executive → visit and follow-up — 25 October 2026

Early attendance follow-up: an assigned executive/admin/manager can explicitly
confirm that the client attended before the scheduled time and record the actual
past attendance time. The original schedule stays intact. Future actual times,
missing/naive times, unrelated-action timing fields and early no-shows are
rejected. Failed next-step validation rolls attendance back atomically; stale
retries cannot duplicate follow-up tasks. Actual attendance appears in Field work,
Site visits and the audit. Additive migration `0009` preserves existing records
and refuses rollback if actual-time history exists.

**271 backend tests passed (117.94s); 12 Chromium browser journeys passed (25.0s)**
against the production bundle, including field handoffs and existing real-estate,
company branding/payment and narrow-screen journeys. Web build/lint, Ruff and
serious/critical Axe/390px checks passed. An initial browser timestamp assertion
compared two equivalent timezone strings; it now compares instants. The final
run has no failed/skipped/retried cases. Local upgrade checked unchanged contents
and counts across nine business tables, and the corrected form was opened in the
user's Chrome. The user's real outcome was left unsaved pending actual visit time
and a future follow-up time. Android remains unchanged; Firefox/WebKit/native
suites were not rerun for this follow-up. Evidence:
`artifacts/field-handoff/early-visit/`.

Client-context clarification: arranging a handoff from a lead profile now shows
that client's name and phone as a fixed selection, without another search or
client dropdown. Changing profiles resets the handoff panel. The general Field
work page retains client search/selection. All **7 field-work Chromium journeys
passed** against the production bundle, including same-name clients with different
phone numbers, both profile contexts, cancellation/reopening, a persisted general
page handoff, 390px containment and serious/critical Axe checks. Web lint and build
passed. Evidence: `artifacts/field-handoff/client-context-tests.txt` and
`client-context/browser-tests.json`. This frontend-only follow-up did not rerun
the backend/native or Firefox/WebKit suites below.

The owner explicitly chose shared access: the field executive takes responsibility
while the caller stays involved. Admins create the new Field executive role in
Team directory. A caller schedules a confirmed property visit and records the
meeting point/discussion brief. The executive accepts, reviews client history and
recordings, records attendance/no-show/feedback and saves a dated next action or
booking-review request. Matching booking confirmation closes ready field work.

One current handoff, request idempotency, version checks, organization locks,
clash prevention, stale-update rejection and atomic outcome/task changes are
enforced. Reassignment removes the previous executive's client/file access and
requires new acceptance. Active work blocks inappropriate employee removal,
archival or closed lead outcomes. Recording deletion is denied for field staff.
Field access is limited to assigned/self-owned clients and own private work.

**269 backend tests passed, with 90.77% coverage**, including 17 new field tests.
Five focused browser journeys passed in each of Chromium, Firefox and WebKit.
The final serial full suites passed **70 journeys in each engine**, with zero
failures, skipped cases or retries. The final field-role approval control is
covered by **7 additional focused checks per engine**, including the existing
approval flow. All passed after the final control change.
Visual review corrected cramped mobile filters. A delayed-response regression
also verifies retention of a selected property during visit rescheduling. The
local additive migration to 0008 preserved business records; live web/API/worker,
history and authenticated recording download checks passed. No test business data
was inserted in the working CRM. All Android source/configuration/APK hashes are
unchanged; executives use the responsive web CRM. Native suites were not rerun.

See [focused verification](../artifacts/field-handoff/QA_REPORT.md) and
[machine-readable results](../artifacts/field-handoff/verification.json).

## Super-admin accounts, branding and UPI/COD payments — 25 October 2026

Super admin can create/edit/deactivate/reactivate company administrators, reset
their passwords, and upload/replace/remove company logos. Company creation opens
management immediately. Company boundaries, owner authority, seat limits,
last-admin protection, session revocation and credential redaction are enforced
on the server. Existing support and team-role flows remain available.

Payment configuration enables UPI/QR, cash collection (COD), both or neither. COD
means cash collected in person, as explicitly confirmed by the owner. Cash needs
no QR/UTR and stays pending until super admin explicitly confirms receipt while
approving. UPI retains manual bank verification and legacy references. Both methods
share pending/idempotency/price guards; concurrent approval activates once.

**252 backend tests passed with 90.41% line coverage. All 65 production browser
journeys passed separately in Chromium, Firefox and WebKit**, with no failed,
skipped, flaky or retried cases in the final runs. Ruff, ESLint, focused Prettier,
TypeScript/build and migration compatibility checks passed. The safe local upgrade
to `0007` preserved business row counts; the running web/API/database/worker smoke
passed. Test mutations used disposable databases. All 70 Android source/config
files and the existing 1.1.4 APK retain their hashes; no Android code or call-sync
contract changed, and native suites were not rerun for this extension.

No actual bank/cash receipt, deployment or push is claimed. Paid plan prices,
receiving QR/account and enabled cash instructions remain the owner's setup.
See the [focused report](../artifacts/super-admin-payments/QA_REPORT.md) and
[verification JSON](../artifacts/super-admin-payments/verification.json).

## Android history recovery — Aven Realty 1.1.4, 25 October 2026

The visible emulator error was reproduced, and manual retry loaded Poonam's
23 calls/11 files. The original failed response was unavailable, so no precise
upstream outage cause is asserted. Controlled testing found that HTML 404 errors
were incorrectly described as lead access loss. The screen now uses structured
CRM error codes, explains company suspension separately and retries a failed
history screen when it resumes. Pending calls and collection settings stay intact;
file-picker return does not restart a successfully loaded history.

**25 Android 15 instrumentation cases**, **4 repeats at 320dp/130% text**, **32 JVM
tests**, debug/release lint and debug/test/minified signed builds passed. The
in-place code-8 update kept the caller login, loaded 23 real calls/11 recordings
and decoded an uploaded recording through HTTPS to **Finished, 6s / 6s**. All 14
core calling/auth/storage classes retain their hashes. No backend/web runtime or
call-sync contract changed. Their previous full audit and 13-case lifecycle
results below were not rerun for this screen-only correction. No physical handset
or Android 16/API 26 runtime check is claimed for this update.

Delivery: `artifacts/android/aven-realty-1.1.4.apk` and
`artifacts/aven-realty-android-source-1.1.4.zip`. See the
[focused report](../artifacts/android/history-recovery/REPORT.md) and
[verification JSON](../artifacts/android/history-recovery/verification.json).

## Full website and Android audit — 25 October 2026, Aven Realty 1.1.3

The latest audit passed **242 backend/API tests**, **90.17% line coverage**,
**61 production browser journeys in each of Chromium, Firefox and WebKit**,
**38 Android 15 instrumentation cases**, **13 lifecycle checks**, **32 JVM tests**,
and **4 repeated native history cases at 320dp/130% text**. Final browser runs
have zero failures, skipped cases or retries. Ruff, ESLint, TypeScript, Prettier,
Android debug/test/release builds, signature checks, fresh migration/rollback
and isolated database/storage restore passed.

Fixed category/stage loading and retry inside the lead-filter dialog; drafts and
saved choices remain visible. A shared retry button now uses type=button so it
cannot accidentally submit a surrounding form. A force-stop/cold-start check
found an orphaned private playback file; process-specific previews and launch
cleanup now remove it while preserving pending calls and paused collection.
All 14 original calling/recording/scheduling/storage/auth classes retain their
pre-interface hashes. No backend runtime/API contract changed in this audit.

Real API/Android CallLog/SAF integration uploaded synthetic WAV audio. Web and
native history matched 20 calls, 2 recordings, 1 note and 1 task on the isolated
lead; native access to history/audio was revoked on reassignment. The signed
version-code-7 APK updated in place, retained the existing caller session, and
loaded the working lead's 23 synced calls and 11 recordings with native playback.
That working company was read only; business mutations used disposable `_test`
databases and fictional workspaces. Debug/test apps and temporary test services
are removed during cleanup; the working website/API and signed emulator app stay
available. No deployment or push was performed.

The isolated browser runner now creates/migrates/seeds its own database and starts
its own API, worker and website on unused ports. It snapshots built assets for
production runs and cleans up its resources. Local verification and CI use it;
CI was configured and verified locally, not run on GitHub. Initial failures and
their diagnoses are retained, including Safari's macOS Option-Tab behavior and
a concurrent rebuild that interrupted the first Firefox run.

Physical OPPO/native two-speaker recording, other Android versions for this
release, actual IndiaMART/Justdial delivery, real bank receipt verification,
permanent hosting, overnight handset endurance and production-scale load remain
separate environment checks. The app does not claim automatic QR bank
reconciliation. Non-fatal existing lint/Gradle/bundle warnings remain visible.
Finite regression testing is not an all-device/all-scenario certification.

See [full audit](../artifacts/full-audit-20261025/QA_REPORT.md),
[verification JSON](../artifacts/full-audit-20261025/verification.json) and
[Android QA matrix](../android/QA_MATRIX.md). Delivery:
`artifacts/android/aven-realty-1.1.3.apk` and
`artifacts/aven-realty-android-source-1.1.3.zip`.

## Aven Realty mobile UI — 1.1.0, 25 October 2026

Android now presents Home, Leads, Calls and More in a real-estate design with
native text scaling, labelled controls, property branding and simpler call/audio
states. The read-only property catalogue uses existing CRM APIs for inventory,
search, property type, sale/rent filters, 24-item pages and type-aware details.
Plots do not display bedroom/bathroom fields; prices show both compact lakh/crore
values and exact INR amounts. No properties, calls or business metadata are
invented by the production interface.

The owner's selected ZIP logic remains authoritative. **All 14 calling, recording,
storage, scheduling, receiver and authentication classes are byte-identical to
the pre-UI baseline.** Changes are presentation, the read-only catalogue and its
regressions. Inventory closes when authentication expires; a delayed response
retains an unfinished search. Those cases preserve queued calls.

Executed checks: **32 JVM tests**, a final **15-test Android 15/API 35 suite**, and
**15 unique Android 16/API 36 cases** (13-test full regression plus the six latest
EstateUiTest cases, including two additional regressions). All six estate UI
cases also passed at **320dp width and 130% font** on Android 16. Both OS versions
passed **13 lifecycle checks each**: background cellular simulation, offline queue,
force-stop/reopen, permission revoke/regrant, notification denial, reboot/unlock,
forced idle and duplicate prevention. The actual isolated API/CallLog/SAF path
uploaded, downloaded and decoded synthetic WAV files and rejected duplicates.
An additional controlled delayed-response test covers input preservation.

Debug/instrumentation and minified signed release builds pass; debug/release lint
have zero errors and 14/13 warnings. The signed release retains `com.aven.calls`,
uses the original certificate, increments versionCode to 4 and versionName to
1.1.0. Actual HTTPS sign-in on the old signed 1.0.2 APK, in-place upgrade retaining
the signed-in account, catalogue loading with the company's 12 existing demo
properties and sign-out all passed on Android 16. Call collection stayed off for
that main-workspace smoke test; only authentication sessions/audits were created.

Functional mutations ran in a dedicated `_test` database with temporary backend/
worker on port 8018. Initial interrupted runs, helper assumptions and the old
Android 15 emulator's missing SIM are retained in the evidence. A fresh cellular
AVD passed the final Android 15 suite and all lifecycle checks. There was no
physical handset test or API 26 runtime test here. The APK's current ngrok URL
requires the local backend/tunnel to remain running. No web/backend source or
call-sync API contract changed, and nothing was deployed or pushed.

Delivery: `artifacts/android/aven-realty-1.1.0.apk` and
`artifacts/aven-realty-android-source-1.1.0.zip`. Evidence, scope, screenshots and
integrity records are under `artifacts/android/real-estate-ui/`.

## User-selected Android ZIP logic — 25 October 2026

The owner explicitly prioritized the tested `aven-calls-android.zip` as the
Android baseline. Its eight changed source/test/wrapper files were imported.
The timestamp-based recording matcher, closest eligible call selection,
30-second timestamp margins, empty-file rechecks, expedited WorkManager uploads
and foreground information are preserved. Matcher, scheduler, worker and activity
remain byte-identical to that ZIP. Old phone-required matching expectations were
intentionally replaced with the owner's policy and expanded boundary tests.

Lint identified two API-33-only Java overloads despite minimum API 26, and a
missing WorkManager foreground service type. Equivalent UTF-8 calls and a
`dataSync` manifest declaration fix these compatibility issues without changing
the imported matching/scheduling policy. The ZIP's Gradle 8.14.5 is retained.

Executed checks: **27 JVM tests**, **9 Android 15/API 35 instrumentation/UI tests**
and **13 system lifecycle checks passed**. The real isolated API/SAF path verifies
an empty contact-name recording recheck, stable-file upload, private download,
WAV decoding and duplicate-upload prevention. Lifecycle checks cover background
capture, force-stop/reopen, offline durable queue/reconnect, revoked/regranted
call-log permission, notification denial, reboot/unlock, forced idle and duplicate
identities. Debug/instrumentation and minified unsigned release builds pass;
debug/release lint have zero errors and 13/12 existing warnings, respectively.

Tests used a dedicated `_test` database, temporary backend/worker on port 8018
and the dedicated emulator on port 5580. The fixture was archived and temporary
services/emulator stopped. Web/backend source, the main CRM database and previously
distributed signed APK were not changed for this integration. Physical handset
testing is reported by the owner; none was executed here. API 26/API 36 runtime
checks were not rerun, and the unsigned release build is not a distributed update.

Evidence: `artifacts/android/zip-logic-priority/verification.json`, build/lint
reports, `unit-tests.json`, `device-tests-api35.txt`, `lifecycle.json` and
`source-integration.json`. Future UI work must follow `android/LOGIC_BASELINE.md`.

## Office and calling salary estimates — separate rates

The user chose the policy **8 office hours including 2 call hours = 6 office
hours + 2 call hours, each at its own rate**. Payroll now supports this through
**Edit rate → Office + calling — separate rates**. Existing employees retain their
previous Approved work hours method and configured rate until explicitly changed.

The screen shows recorded/approved/pending office time, synced answered-call time,
separate pay components, the monthly total and a daily breakdown. CSV export uses
the same service/data. Only approved closed attendance produces office pay in the
new method. Call overlap is deducted from office time, while calls outside approved
attendance are paid at the calling rate. Overlapping device intervals count once;
manual declarations and linked outcomes add no calling pay. A recording upload is
not required. Late call-duration updates/retries update the same calculation.

The calculation clips intervals to the selected workplace-local month/day and a
single captured current time, uses actual elapsed time for 23/25-hour DST days,
and retains historical employee calls when a customer is reassigned/archived.
Each salary component rounds once using Decimal half-up; the total adds those
rounded components. Rates/targets remain admin-only. Legacy profile updates that
omit the new fields preserve their stored calculation method and calling rate.

| Executed verification | Result |
| --- | --- |
| Full backend regression, dedicated `_test` DB | **242 passed**, no failures/errors/skips; 85.73 seconds |
| New backend regressions in full suite | **13 passed**: overlap/duplicates, outside-office calls, pending/rejected/manual sources, open attendance, sync duration updates/idempotency, timezones/month edges, 23/25-hour DST days, rounding/reconciliation, validation/access control and migration preservation |
| Focused browser journeys on isolated QA services | **2 passed**: office review + real sync API + two rates + detailed result/export; failure retry + mobile/settings accessibility |
| Full Chromium browser regression | **60 passed**, no failures/retries/skips; 3.4 minutes |
| Responsive/accessibility | Payroll/settings/breakdown at 320/768/1440px, no page/dialog horizontal overflow, zero serious/critical Axe findings in focused dialogs |
| Ruff, ESLint, TypeScript/production build and whitespace | Passed |
| Migration 0006 | Upgrade/downgrade/re-upgrade on `_test` DB; existing rate preserved; new defaults preserve original work method |
| Alembic check | No new upgrade operations detected |
| Working CRM | Private DB backup, migration applied, old rates/methods preserved, business-record counts/digests unchanged, API/database/worker healthy |
| Live UI | Actual employee office/calling totals and the separate-rate selector/fields reviewed at 319px; draft cancelled without saving rates |
| Android | No source/APK or call-sync contract changes; APK hash unchanged |

The main example journey created an isolated employee and a closed 8-hour office
session, synced a 2-hour answered call, configured ₹100/hour office and ₹150/hour
calling, approved the attendance through the UI, and verified **₹600 + ₹300 = ₹900**.
Updating that same call to 2.5 hours produced **₹550 + ₹375 = ₹925** after reload;
retry created no new call and CSV matched. Existing hourly-work browser regression
still verifies **2.5 × ₹125.25 = ₹313.13**. Other checks include missing recordings,
missed/rejected/unknown and future call exclusion, future/unsupported calendar
months, company isolation, forbidden manager/caller actions and legacy API updates.

Accessibility review caught the daily table's scroll region lacking keyboard focus;
it now has a labelled, focusable region and passes the rerun. Existing nonfatal
Vite chunk-size and backend dependency/serializer warnings remain visible.

Call placement uses phone-reported start plus duration. The sync contract has no
separate connected-at timestamp, so allocation at office boundaries is approximate.
Attendance is recorded check-in/out, not continuous location monitoring. Estimates
are live; rates apply across months, and syncing/approvals can change earlier
figures. This feature does not finalize payroll, transfer money, or calculate
tax/statutory deductions/commissions. No physical phone/emulator was retested for
this web feature, no working employee rates were altered, and no deployment/push
occurred. Evidence: `artifacts/office-call-pay/full-backend.xml`,
`focused/browser-tests.json`, `full/browser-tests.json`, `live-migration.json`,
`live-pay-settings.png`, `full/screenshots/salary-6-office-2-call.png` and
`verification.json`.

## Correction: real estate category choices — 24 October 2026

The previous filter tests checked filtering mechanics but did not assert the
industry-specific contents of the category dropdown. That gap allowed healthcare
defaults to remain visible after an existing company was converted to real estate.
A new regression reproduced the reported defect before the fix.

Real estate conversion now retires unchanged Pharmaceutical, Ayurvedic,
Homeopathic, Nutraceutical and Generic seed categories while keeping definitions
and customer history. Custom categories and user-renamed seeds remain intact.
Migration 0005 repairs already-converted companies and disables their pharma flag;
general companies are unaffected. Category choices use active definitions.
Explicitly selected historical categories are labelled **(previous category)** so
older saved views and lead edits remain usable without rewriting their values.
The schema downgrade retains this data correction rather than reactivating seeds.

Real estate Add/Edit lead forms now expose **Property category** with the same
choices as the filter. Saving it persists the category, the summary displays its
label, and matching list/export results follow that saved value. Healthcare-only
qualification fields remain hidden and real estate settings saves cannot enable
them. The buyer's detailed Property brief remains a separate set of requirements.

| Executed verification | Result |
| --- | --- |
| Full backend regression on dedicated `_test` DB | **229 passed**, no failures/errors/skips; 85.72 seconds |
| New backend regressions | **4 passed**: conversion/repeatability, fresh company defaults, settings guard and existing-company backfill/upgrade/downgrade/re-upgrade |
| Focused browser regressions on isolated QA services | **2 passed**: exact category contents, create/edit/reload/filter/export, previous categories and separate general-pharma workspace |
| Full Chromium regression | **58 passed**, no failures/retries/skips; 3.3 minutes |
| Ruff, ESLint, TypeScript/production build; diff whitespace | Passed |
| Alembic schema check | No new upgrade operations detected |
| Working company | Private DB backup; revision 0005 applied; before/after business-record row counts and digests identical |
| Live admin review | Actual dropdown contains Apartment, Villa, Plot, Office, Retail, Other and Warehouse; healthcare options absent; Plot selection checked and cancelled |
| Runtime | API/database/worker healthy after restart |
| Android | Source/APK unchanged; no handset/emulator tests rerun for this web correction |

Backfill and conversion preserve custom keys, renamed defaults, old categories,
interests, notes, saved views and other-company definitions. New leads cannot use
retired categories, while unchanged old categories remain valid on existing lead
edits. The browser assertions enumerate the full available option set and check
the absence of each healthcare default; this directly covers the reported gap.
No customer record was created, edited or deleted during the working-CRM review.
No deployment or push occurred. Existing nonfatal build/dependency warnings remain.
Evidence: `artifacts/category-correction/full-backend.xml`,
`focused/browser-tests.json`, `full/browser-tests.json`, `live-migration.json`,
`live-filter-accessibility.txt`, `live-category-options.png` and `verification.json`.

## Simpler lead filtering in the admin panel — 24 October 2026

Leads and Lost deals now share labelled search/status/source/owner controls and
an advanced **More filters** dialog. The dialog groups follow-up/contact,
location/requirements and creation-date choices, with a persistent action bar.
Changes apply only on **Apply filters**; Cancel discards them. Active choices are
visible as removable chips, with a matching result count and **Clear all filters**.
Resetting the advanced choices retains common selections until applied. Empty
results offer a reset; dependency failures preserve choices and offer a retry.

All existing lead filter dimensions remain supported. Calendar ranges include
the full final day in the browser timezone, with presets and one-ended ranges;
exact historical timestamp ranges remain precise. Legacy date-only saved ranges
normalize without losing their exclusive-end meaning. Legacy boolean `dnd=false`
saved filters now retain Contact allowed. City/state match full names without
case/outer-space sensitivity. Status/source/follow-up IDs validate consistently
for list and export. Inactive employees remain selectable for historical leads;
unavailable selections are visible and removable. Filter changes reset paging
and bulk selection. Lost deals cannot escape the lost scope through saved views
or Clear all. Existing role/company access rules are retained.

| Executed verification | Result |
| --- | --- |
| Ruff; ESLint; TypeScript/production build; diff whitespace | Passed |
| Full backend regression on a dedicated `_test` database | **225 passed**, no failures/errors/skips; 86.80 seconds |
| New backend filter cases | **5 passed**, including every filter, 18 filter sets, combined filters, matching CSVs, role/company isolation, invalid IDs and date boundaries |
| Focused Chromium filter journeys | **8 passed**, including draft/cancel/reset, saved filters, exports, lost scope, dates, inactive owners, paging/selection reset and service-failure retry |
| Full Chromium regression on isolated QA services/database | **56 passed**, no failures/retries/skips; 3.1 minutes |
| Responsive/accessibility | Filter controls/dialog at 320/768/1440px; no horizontal page/dialog overflow, Apply remains in view, no serious/critical Axe violations |
| Local working CRM | Latest backend running; API/database/worker health all `ok`; real admin layout reviewed at 319px without changing customer records |
| Android APK | Unchanged SHA-256: `67f94e6e1b6902c35f87e2403c1c5a15ebbaded9d9ec626f6784efc84c12c347` |

Browser checks cover full-day India boundaries, a 23-hour daylight-saving day,
reversed-date rejection, unchanged precise saved timestamps, legacy saved
dates/booleans, lost reason/reporter, filtered CSV bytes, active-filter removal,
quick-queue transitions, unavailable/inactive owners, page resets and preserved
choices after a simulated 503. Initial fixture errors were corrected to create
configured categories and valid future follow-ups; an intermittent navigation
race was corrected by waiting for the authenticated lead workspace before the
test navigates again. Final results above come from a fresh complete run.

The build retains the nonfatal Vite chunk-size warning; backend dependency and
Decimal serializer warnings remain visible in test output. No mathematical
claim of every possible input/device/browser combination is made. Synthetic data
was confined to the separate QA database. No migration, Android modification,
deployment or push was required. Evidence: `artifacts/lead-filters/full-backend.xml`,
`focused/browser-tests.json`, `full/browser-tests.json`, `full/playwright-report/`,
`admin-lead-filters.png`, `admin-filter-dialog.png` and `verification.json`.

## Telecallers cannot delete recordings — 24 October 2026

The user explicitly removed telecaller recording-deletion permission, including
their own uploaded/synced recordings. `DELETE /api/files/{id}` now rejects a
telecaller whenever the attachment is linked to a call or has an audio MIME type.
It uses the stored, content-validated type rather than trusting filename/client
MIME. The lead Files UI hides Remove for these attachments. Current company,
lead and call access checks still run before the denial. The rule also applies
when an administrator is logged in as a telecaller. Upload, playback, download,
ordinary non-audio document deletion and existing administrator/manager permissions
remain available under their existing rules.

Executed verification: Ruff, ESLint, TypeScript/production build and whitespace
checks passed; **220 backend tests passed**, including five new recording-deletion
cases. They cover linked/unlinked audio, caller/admin uploaders, a misleading
document filename/client MIME, repeated direct-API denial with bytes/state intact,
company/assignee isolation, administrator deletion and delegated telecaller login.
Existing Android sync and native-audio compatibility regressions passed.
**48 Chromium browser tests passed** with no failures, retries or skips. The new
journey verifies hidden Remove controls after reload, direct API denial, native M4A
loading/decoded duration, byte-identical download, UI audio upload, ordinary photo
removal and successful admin recording removal with the final-call audio state
updated. Synthetic fixtures were confined to the separate QA `_test` database.

The working API was restarted and API/database/worker health returned `ok`.
No working-CRM recording was deleted. No schema migration, Android source change,
APK rebuild, deployment or push was needed. Android APK SHA-256 remains
`67f94e6e1b6902c35f87e2403c1c5a15ebbaded9d9ec626f6784efc84c12c347`.
Evidence: `artifacts/recording-permissions/full-backend.xml`,
`full/browser-tests.json`, `full/screenshots/telecaller-recordings.png` and
`verification.json`.

## Direct administrator login as a team member — 24 October 2026

The user explicitly requested direct login with member actions, rather than an
inspection-only preview. In People → Team directory, company admins can click an
active telecaller/manager's name or **Log in as member**. A separate 30-minute
session uses the member's actual role, assigned records and allowed actions.
The persistent banner identifies the member and actual administrator and provides
**Return to my account**. Member passwords/authenticators are neither exposed nor
changed; their security controls are protected in this mode. Work is stored for
the member; audit events identify the initiating administrator and effective member.
Cross-company, self, peer-admin, inactive/deleted and nested access are rejected.
Original administrator authority is checked on every request. Returning rotates
the parent refresh credential and revokes the member session; logout also revokes
the source administrator session. An expired member window can return to a valid
parent; expired owner support returns only to the platform. Existing member
browser/Android sessions remain independent of entering/returning from this flow.

| Executed verification | Result |
| --- | --- |
| Ruff, ESLint, TypeScript and production build; diff whitespace | Passed |
| Full backend regression on dedicated `_test` DB | **215 passed**, including **18 new member-login cases** |
| Full Chromium browser regression on isolated QA services/DB | **47 passed**, no failures, retries or skips |
| Final member browser rerun after mobile banner adjustment | **3 passed**; actual note creation, assignment isolation, reload/return, protected security controls, failure retries, manager restriction and owner support return |
| Narrow banner and accessibility | 320px text-column/stacked-button check and serious/critical Axe check passed |
| Migration 0004 | Upgrade, schema check, downgrade to previous head, re-upgrade and schema check passed on separate `_test` DB |
| Working CRM | Private DB backup before migration; 0004 applied; API/database/worker healthy; actual Kabir entry → return → entry confirmed |
| Android APK | SHA-256 unchanged: `67f94e6e1b6902c35f87e2403c1c5a15ebbaded9d9ec626f6784efc84c12c347` |

The initial live screenshot revealed that the return button squeezed banner text
in the user's 319px pane. A layout scoped to this banner now places the return
button below the text on small screens; final focused checks and the saved live
screenshot verify the correction. QA accounts/notes stayed in the test database.
No customer records were changed in the working company during the live login
review. Evidence is in `artifacts/member-login/full-backend.xml`,
`full/browser-tests.json`, `final-focused/browser-tests.json`, `verification.json`
and `kabir-login.jpg`. Android source/APK were not modified and no handset or
emulator checks were rerun for this web feature. No deployment or push occurred.

## Property fields follow the selected type — 24 October 2026

Property creation/editing now starts with type and sale/rent. Apartments/villas
show bedrooms and bathrooms; plots show neither; office/retail/warehouse/other
show optional washrooms. Type changes clear room counts that no longer apply,
and the property API normalizes those fields on both creation and full edits.
Zero-bedroom residential listings remain supported. Existing detail cards hide
irrelevant room counts too. Area, asking price/monthly rent, handover/available-from
labels and amenity examples adapt to the selection. Building/owner/RERA references
are under an optional disclosure, expanded when existing project details are edited.
RERA is not made mandatory or removed solely because of property type.

Verification: Ruff, ESLint, TypeScript/production build and `git diff --check`
passed. **197 backend tests passed**, including seven type-specific create/edit
cases. **44 Chromium browser tests passed** with no retries or skips, including
three new scenarios covering all seven types, sale/rent wording, clearing hidden
values and switching back, persisted editing, optional disclosure/keyboard access,
zero-bedroom creation, minimum-price validation and duplicate-reference retry.
The new form passed serious/critical Axe checks and a 390px overflow check.
The existing real estate, booking, billing and readability regressions also passed.
Tests used the separate `_test` databases. No QA listings were added to the working
company, and its 12 Panipat demo properties were retained. The working API was
restarted and returned healthy; the live company form was reviewed with Plot selected.
Android source and APK were unchanged; no Android tests were rerun for this change.

Evidence: `artifacts/property-form/full-backend-junit.xml`,
`artifacts/property-form/full/browser-tests.json`,
`artifacts/property-form/verification.json` and `plot-form.jpg`.

## Real estate web product and QR subscriptions — 24 October 2026

The user explicitly authorized real estate specialization, super-admin company
profiles/branding and subscriptions paid using their own QR. The Android tree and
APK were not changed. The existing owner role is labeled Super admin in the web UI.
Company provisioning now includes a business profile, brand, first administrator,
five-seat trial and real estate definitions. Super admin can upload private company
logos, manage subscription terms, publish INR monthly/yearly plans and configure a
private payment QR/payee/instructions. Company admins have a subscription page.

QR checkout records an amount-checked transaction reference and optional private
receipt. It stays pending until super admin verifies actual bank receipt and
approves/rejects with a note. Approval is serialized and activates/extends terms
once; duplicate references, conflicting retries, repeated approvals, concurrent
claims and insufficient-seat approvals are rejected. Catalogue changes do not
rewrite pending payment snapshots. Expiry is shown; suspension remains an explicit
super-admin action, preserving Android's authentication/call-sync contract.
No bank integration, automatic debit, tax invoice, real QR/payment validation or
real money transfer was performed. The user's real QR and prices are not configured
in the working CRM; these are available through the super-admin setup UI.

Real estate features include sale/rental inventory and private photos/PDFs,
customer-confirmed buyer briefs and criteria-based property matches, agent site
visits with clash/reschedule/outcome handling, and reservation/booking/closing or
cancellation with linked inventory availability. Company/role/assignment checks
are enforced on the server. A company lock prevents concurrent unit reservations
and seat-limit races. Lead merge preserves the added property brief, visits and
bookings. Existing customer/call/file data was retained. The existing development
company was enabled for real estate defaults after a private local database backup.
Setup instructions and explicit limits are in `docs/REAL_ESTATE_GUIDE.md`.

| Final executed check | Result | Evidence |
| --- | --- | --- |
| Backend lint | Passed | Ruff over app/tests |
| Full backend regression | **190 passed**, 66.48s | `artifacts/real-estate/backend-junit.xml` |
| New domain/billing regression | **19 passed** | Included in full run; role/isolation, private media, matching, clash/boundary times, concurrent reservation/review, duplicate/reference/price checks, trial/renewal/calendar dates, seats, receipts, archive protection and merge |
| Web lint, type check and production build | Passed | ESLint and TypeScript/Vite |
| Full Chromium browser regression | **41 passed**, 2.4m | `artifacts/real-estate/full/browser-tests.json` and Playwright report |
| New web journeys | Passed | Company profile/logo/trial seats; property upload → brief → match → visit/reschedule → booking/close; QR claim → owner review → active company plan |
| Accessibility/layout | Passed | Serious/critical Axe checks; new pages at 390/768/1440px; existing 360px and 200% text preference checks retained |
| Migration lifecycle | Passed | Fresh isolated `_test` database upgrade → downgrade to 0002 → upgrade → Alembic schema check (no drift) |
| Working local services | Passed | API/database/worker returned ok on port 8010; web remains 5173 |
| Existing Android APK | Byte-identical SHA-256 | `67f94e6e1b6902c35f87e2403c1c5a15ebbaded9d9ec626f6784efc84c12c347` |

An intermediate browser run found low helper-text contrast, a mobile lead-panel
overflow after adding the new tab, and fixed pixel text that failed the retained
larger-text preference check. These were corrected without weakening accessibility
or layout assertions. Navigation/text expectations were updated for the authorized
new destinations and real estate wording. The final complete suite passes.
Browser tests used a separate `talkocrm_browser_test` database and synthetic QR/
receipt images; they did not add payment claims or fake customers to the working
CRM. Android emulator/physical-phone tests were not rerun for this web-only change.

## Recording status diagnosis — 24 October 2026

The four reported calls at 00:02–00:07 have saved call metadata and no attached
audio. The local tunnel inspector's most recent 100 requests contained no
recording-upload POSTs. This does not establish whether the phone recorded them,
which folder it exposed, or why automatic matching did not queue them. No physical
phone was connected to ADB during this check. The installed matcher's phone/date
parser already supports the earlier native `YYMMDD_HHmmss` filename format; it
intentionally refuses ambiguous matches between nearby calls.

The web CRM now displays **No audio uploaded** instead of **unavailable**, and
**Audio uploaded** for attached files, in lead Calls and Conversations. The missing
audio tooltip explains that call details and audio sync separately. Recording
filters use the same readable labels while retaining the existing API values.
This is a display clarification, not evidence that automatic uploads are fixed.

Web lint and production build passed. Live browser checks confirmed all four
reported calls show No audio uploaded, the two earlier lead recordings still show
players, and Conversations filters return six missing-audio calls versus three
attached calls in the current development dataset. No test data or Android code
was changed, and no APK was rebuilt. Physical phone recording/folder status is
still needed to diagnose the missing automatic uploads.

## Native M4A upload compatibility — 23–24 October 2026

A real native `.m4a` upload returned `422 unsupported_content`. Its audio was valid
AAC, but its ISO media brand was `3gp4`, outside the previous signature allowlist.
The same file also placed unversioned QuickTime metadata before its audio track;
Mutagen's metadata traversal missed the track and exposed only movie duration.

ISO media uploads now undergo bounded box-size/depth/count checks. A parser-only
copy ignores non-audio metadata while preserving offsets, allowing Mutagen to
inspect the audio track. Acceptance still requires a real codec, positive channels
and sample rate, and a duration within the existing limit. The stored original is
unchanged. Truncated containers, invalid extended sizes, header-only data and
video-only files remain rejected. Checked-in generated silence/video fixtures
reproduce the native metadata layout without including customer recordings.
No new runtime dependency or Android APK change was needed.

| Check | Executed result | Evidence |
| --- | --- | --- |
| Backend lint | Passed | Ruff over `app` and `tests` |
| Focused recording/file/device regression | **35 passed** | `tests/test_recording_formats.py`, existing Android sync and private-file tests |
| Full backend regression | **171 passed**, 58.77s | `artifacts/recording-format-fix/backend-junit.xml` |
| Original native recording | Full audio decode passed; 169,176 bytes, 10.389s AAC | `artifacts/recording-format-fix/native-upload-verification.json` |
| Actual HTTPS upload and download | **201**, byte-identical private download, existing lead/call linkage confirmed | Same native-upload report |
| CRM administrator verification | Files tab shows the recording; browser audio metadata ready, duration 10.389s, no media error | Live browser check and `artifacts/recording-format-fix/verification.json` |

One earlier full run hit the existing wall-clock TOTP lifecycle assertion around a
30-second boundary. It passed unchanged in isolation and in the final full run;
authentication code and test assertions were not modified. Backend tests used only
the dedicated `_test` database. The original requested upload was retried against
its existing development lead and call, without creating synthetic customer data.
The API was restarted and API/database/worker health returned `ok`. Browser-wide
and Android emulator suites were not rerun for this backend-only correction.

## Simpler Android interface 1.0.2 — 18 October 2026

The mobile companion now has **Home, Customers and Settings** instead of a single
long configuration screen. Sign-in shows account phone/password with the prefilled
workspace address behind Connection settings. Home guides first use through call
access/authorization and recording-folder setup. Recording setup can be deferred
without claiming audio is enabled. Recent calls show separate call-details/audio
results; Customers supports literal name/phone search across the complete cache
with at most 100 rows displayed. Settings holds account/sign-out, pause/resume,
country code, recording folder, phone permissions and plain-language help.

The password stays masked by default with an explicit Show password control. Login
validation uses plain messages, verification-code entry is brought into view, and
navigation dismisses the keyboard. Android's current back callback returns to Home.
The full authenticator sequence exposed an intermittent connection failure when
signing in after earlier sessions. Explicit login now starts on a fresh connection,
without replaying POSTs, and the full sequence passes on both tested OS versions.
Permission repair preserves an already enabled collector's original capture time.
Paused calls explain that uploads must be resumed before adding a recording.

Delivered `artifacts/android/aven-calls-1.0.2-simple-ui.apk`, version code 3, signed
with the same update certificate. The current user-provided ngrok HTTPS origin is
prefilled. The final minified APK was exercised against that real HTTPS endpoint on
Android 15 and as an update on Android 16. Sign-in/consent, deferred audio setup,
customer loading/search, all three destinations, and 320dp/130% text layouts passed.
Screenshots were visually reviewed. The Android 16 update retained its signed-in
demo account and cached customers.

| Re-executed mobile check | Result |
| --- | --- |
| JVM business rules | **19 passed**, zero failures/errors/skips |
| Android 15 full device/API/UI suite | **8 passed**, 61.778s |
| Android 16 full device/API/UI suite | **8 passed**, 69.553s |
| Android 16 system lifecycle matrix | **13 passed** |
| Signed APK against ngrok HTTPS | Passed on Android 15 and 16 |
| Debug/release Android lint | Zero errors; existing warnings recorded in evidence |
| Debug/release/test build, signing and version checks | Passed |
| Packaged configured-credential/test-provider scan | Passed |

The full native suites include actual metadata sync, synthetic SAF audio upload,
download/decode/digest checks, session refresh/revocation, cancellation, account
isolation, authenticator failure/restart/success, consent, search/no-results/literal
wildcards, pause/resume and same-account queue recovery. The system matrix covers
background calls, offline persistence, force-stop/reopen, permissions, notification
denial, reboot/unlock, forced idle and duplicate prevention. The final signed-APK
checks include the final permission-help affordance added after the full Android 16
run; the Android 15 full suite uses the final code. Backend/web code was not changed
or retested for this mobile UI update; earlier web/backend results remain below.

Evidence is under `artifacts/android/simple-ui/`, with APK hashes in
`artifacts/android/apk-checksums.json`. Isolated native QA organizations were archived
after each run, preserving shared customer data. Physical OPPO audio, recording
directory and installer-policy validation remain required; emulator WAV tests do
not prove native two-way cellular recording. The Mac and ngrok must remain online.

## Shareable ngrok APK 1.0.1 — 18 October 2026

`artifacts/android/aven-calls-1.0.1-ngrok-test.apk` is a signed, minified,
non-debuggable release with the user's current
`https://1dd2-111-223-3-131.ngrok-free.app` origin prefilled. The server remains
editable, and previously saved server choices take priority. Version code 2 and the
original update certificate allow installation over 1.0.0. No account credentials
are embedded. The debug variant continues to default to the local emulator server.

The exact signed 1.0.1 APK was installed as an update on Android 16. Its prefilled
server, native telecaller sign-in through public HTTPS, consent/enable flow and
completed assigned-contact sync were verified: **24 customer records, zero queued**.
A native UI check caught `setSingleLine` replacing the password transformation;
applying the input type afterward fixes visible-password disclosure. The dedicated
instrumentation regression passed (**1 test**, 2.684s), and masking was also checked
in the signed release's accessibility tree and screenshot.

Re-executed checks: **19 JVM tests passed**, release Android lint, debug/release/test
compilation, signature/certificate comparison, version/permission inspection,
packaged configured-secret/test-provider scan, and diff whitespace. Evidence and
screenshots are in `artifacts/android/ngrok-test/`; the APK hash is recorded in
`artifacts/android/apk-checksums.json`. A Gboard stylus tutorial interfered with the
host input automation; it was dismissed and handwriting disabled on the dedicated
emulator before the successful final smoke run. The earlier broad backend, browser,
native business and lifecycle suites below are the 1.0.0 baseline, not new 1.0.1 runs.

This is a temporary connection to the running Mac API. Keep the Mac awake, API and
ngrok running, and update the editable server field if its public URL changes. No
permanent production deployment or physical OPPO recording validation is claimed.

## Android companion and final regression — 18 October 2026

Delivered a native Java Android companion with a SQLite outbox, encrypted Keystore session storage, assigned-customer allowlist, explicit recording-folder access, conservative number/time matching, manual attachment, current-permission checks, WorkManager reconciliation and a bounded user-started data-transfer foreground service. It opens the existing Phone app for dialing. The backend now exposes paginated device contacts and per-call acknowledgements; linked audio permits 64 MiB, while generic attachments retain the 10 MiB limit. Duplicate batch IDs are rejected before mutation.

| Executed check | Result |
| --- | --- |
| Full backend suite, PostgreSQL 14 | **157 passed**, 72.88s; 10 dependency/serializer warnings |
| Full Chromium suite | **37 passed**, 2.3m |
| Full Firefox suite | **37 passed**, 2.5m |
| Android JVM business rules | **19 passed**, four suites |
| Android 15 device/API/UI instrumentation | **7 passed**, 59.803s |
| Android 16 device/API/UI instrumentation | **7 passed**, 55.62s |
| Android 15 system lifecycle matrix | **13 passed** |
| Android 16 system lifecycle matrix | **13 passed** |
| Debug/release compilation and Android lint | Passed; Java 17, target/compile SDK 36, min SDK 26 |
| Gradle wrapper and dependency locks | Wrapper 8.14 verified; official distribution checksum pinned; locks recorded |
| Signed minified release | Signature and permission list verified; final APK startup and HTTP-address rejection passed |
| Frontend lint, TypeScript, production build, Ruff, diff whitespace | Passed |

Instrumentation covers real FastAPI/PostgreSQL requests, native CallLog insertion/capture, encrypted credential reload, access-token refresh, revoked refresh handling without queue loss, wrong password/role, authenticator rejection/restart/valid sign-in, SAF audio streaming, repeated upload receipts, missing files, account isolation, actual UI consent/permissions and foreground service startup. System tests use emulator cellular incoming calls and verify offline persistence, force-stop/reopen, permission revoke/regrant, notification denial, reboot/unlock and forced-idle recovery. Missed calls explicitly show that no audio is expected. Calls are never invented from contact activity or inferred customer interests.

The recording test used **synthetic WAV files**, and downloaded recordings were decoded and checked for duplicate persisted bytes. The API request-limit test found and fixed the old middleware ceiling; a 12 MiB recording succeeds, an ordinary file of that size fails, and a configured recording limit is enforced. Runtime checks found and fixed a stale HTTP keep-alive GET; mutations retain explicit acknowledgement/retry behavior. Authenticator UI testing added a restart path for a stale or invalid challenge. Final review found a follow-up scheduling loop for ambiguous/rejected metadata with queued recordings. An actual duplicate-lead API regression now verifies review status, zero eligible transfers and no newly scheduled upload; the full seven-test native suite passed afterward on both OS versions. The final native regressions also cover pending-audio retention, cancellation without read replay, expired-session UI recovery, and reassignment where a replacement lead shares the phone number. The earlier thirteen-case system matrices exercise the unaffected ordinary-call lifecycle paths. Harness fixes wait for post-reboot package readiness and handle Android permission dialogs.

The two delivered APKs are `artifacts/android/aven-calls-1.0.0.apk` (signed HTTPS release) and `aven-calls-1.0.0-local-test.apk` (local HTTP QA variant). Full synchronization was exercised with the local test variant against the running development API. Release verification covers signing, permission/backup configuration, startup and HTTPS validation; a deployed HTTPS production endpoint was not provided or created. The signing/update key stays private under `.local/android-signing/` and is excluded from the source archive.

**Physical native two-way recording remains a hardware acceptance gate.** No physical Samsung, SIM, Bluetooth audio route or OEM recording directory was available to validate. The recommendation is one India-region Samsung pilot with demonstrated native automatic recording and a selectable recording folder before a fleet purchase. Recorder filenames without a phone/date pattern require manual selection. Android may defer background work, and force-stop requires reopening. These limits are described in [Android setup](../android/README.md) and the [executed/physical QA matrix](../android/QA_MATRIX.md).

Evidence: `artifacts/android/verification.json`, `backend-full.txt`, `device-tests*.txt`, `lifecycle*.json`, `server-pipeline.json`, browser reports, build/lint/signature records, screenshots, `apk-checksums.json` and `package-check.txt`. Temporary native QA accounts were isolated in a separate organization and archived after verification. This does not claim a purge of archived test records. GitHub CI was configured for Android compilation/lint/unit tests but was not executed remotely in this session.

The web call-history empty state was updated to point to Aven Calls instead of describing a future device client. Its final lint/type/build checks and the targeted persisted call/file history journey passed after that wording change; the full 37-per-browser results above precede this final copy edit.

## Saved-filter cleanup — 18 October 2026

The confusing `Browser view <timestamp>` chips came from an older browser test writing into the shared Evergreen fixture account. **14 test lead filters and 14 matching test saved reports were removed through their owner's authenticated API. All 113 leads were preserved**, and no unrelated saved entries were removed. A private local recovery copy of the removed test definitions is excluded from the source archive.

The UI now says **Saved filters**, with **Save filters**, **Filter name**, and an explanation that a named combination can be reused later. The remove control explicitly states that leads are kept. The offending test now uses the same temporary-workspace fixture as the final QA suite, uses a readable name, verifies removal of its filter/report entries, and archives its temporary organization in a teardown `finally` block.

- Chromium: **18 passed** (63.27s), covering the saved-filter/report/worker journey, a new save/reload/apply/remove regression, and all sixteen final-QA journeys after extracting the shared fixture.
- Firefox: **3 passed** (21.42s), covering the two saved-entry journeys and saved date/stage/product filters.
- ESLint, TypeScript, production build and `git diff --check` passed. The live Evergreen lead list was reloaded and checked at 1440px and 360px with zero saved-view chips. Source packaging and its SHA-256 manifest were refreshed.

Evidence: `artifacts/saved-filters/cleanup.json`, `verification.json`, browser reports, screenshots, `lint.txt`, `build.txt` and `package-check.txt`. Organization deletion archives data and revokes access; it does not claim a database purge. Backend application code was unchanged.

## Balanced text-size follow-up — 18 October 2026

After the user found the initial larger-text pass oversized, the UI was reduced to **16px main/form text, 14px secondary text, 28–30px CRM page headings and 20px section headings**. The rail is 104px wide, dialogs are up to 700px wide, and controls retain a 44px minimum height. Stronger contrast, clear labels, rem-based browser text scaling and responsive containment remain.

- Chromium: **8 targeted journeys passed** (43.69s), including real lead/note/task actions, accessibility scans, responsive layout, mobile navigation, long branding and all three readability journeys.
- Firefox: **3 readability journeys passed** (25.44s), measuring all sixteen CRM pages at 360/768/1440px, public/login at 320–1440px, lead editors and doubled browser text size.
- ESLint, TypeScript, production build and `git diff --check` passed. Desktop login/dashboard and mobile screenshots were reviewed. The backend was unchanged and not rerun.

Evidence: `artifacts/readability-balanced/verification.json`, browser reports, screenshots, `lint.txt` and `build.txt`. The 18px result below is historical; this balanced scale supersedes it. The current source archive and manifest were refreshed, with the checksum recorded in `artifacts/readability-balanced/package-check.txt`.

## Initial readability pass — 18 October 2026

The user requested larger text suitable for older readers. The web UI now defaults to **18px body/form text and at least 16px secondary text**, with larger headings, darker secondary text, 48px primary controls, larger checkboxes, wider navigation and more room in dialogs. Typography uses shared rem units; mobile cards and filters stack instead of shrinking their text.

| Check | Executed result | Evidence |
| --- | --- | --- |
| Chromium / local web + real API | **36 passed**, 124.38 seconds; no failed/skipped/flaky tests | `artifacts/readability/chromium/browser-tests.json`, `chromium-tests.txt` |
| Firefox / local web + real API | **36 passed**, 136.66 seconds; no failed/skipped/flaky tests | `artifacts/readability/firefox/browser-tests.json`, `firefox-tests.txt` |
| ESLint, TypeScript and production build | Passed | `artifacts/readability/lint.txt`, `build.txt` |
| Rendered text and layout | All sixteen admin pages checked at 360/768/1440px; public/login at 320/360/768/1440px; lead editor at three widths | `web/tests/readability.spec.ts`, browser screenshots |
| Larger browser text preference | Doubled default font preserves navigation, form entry, cancellation and page containment | `readable-text-200-percent.png` in each browser screenshot folder |
| Accessibility regression | Existing automated serious/critical Axe checks and keyboard journeys passed within both complete suites | `web/tests/crm.spec.ts`, `web/tests/final-qa.spec.ts` |

Screenshots of login, the dashboard, lead list/detail, workspace settings and lead editor were visually reviewed. The new checks found and corrected a smaller checkbox label and header overflow with doubled text. Browser-font scaling is tested directly; a usability study with older adults and every assistive technology combination are not claimed. Backend behavior was unchanged, so its earlier 151-test audit below was not rerun for this CSS update. The current source archive includes these changes and evidence; its refreshed manifest and checksum are recorded in `artifacts/readability/package-check.txt`.

## Executed final audit — 18 October 2026

The product was reviewed against the complete accepted brief after the missing interest-field issue. [QA_AUDIT.md](QA_AUDIT.md) records the requirement matrix and **21 corrected findings**. The audit adds **41 backend regression cases** and **16 browser journeys**. Existing tests remain in the suites; note assertions now require the persisted note card, and authenticator tests wait for the completed save before reload.

| Check | Executed result | Evidence |
| --- | --- | --- |
| Backend / native PostgreSQL 14.15 | **151 passed**, 88.28 seconds | `artifacts/qa-final/backend-tests.txt` |
| Backend / isolated Linux PostgreSQL 17 | **151 passed**, 77.31 seconds | `artifacts/qa-final/container-backend-tests.txt` |
| Chromium against nginx production bundle | **33 passed**, 81.22 seconds; zero failed/skipped/flaky | `artifacts/qa-final/chromium/browser-tests.json`, `chromium-tests.txt` |
| Firefox against local web/API | **33 passed**, 123.37 seconds; zero failed/skipped/flaky | `artifacts/qa-final/firefox/browser-tests.json`, `firefox-tests.txt` |
| Backend statement / branch coverage | **86.52% / 72.07%** across all application modules, including development seeders | `artifacts/qa-final/coverage.json`, `coverage-html/index.html` |
| Ruff, ESLint, TypeScript and production Vite build | Passed | `artifacts/qa-final/ruff.txt`, `lint.txt`, `build.txt` |
| Fresh migration up/check/down/up and restore | **13 checks passed**; matching exported database snapshot and private-file hashes | `artifacts/qa-final/recovery-tests.txt` |
| Docker images, migrations, API, worker, database and nginx | Built and executed successfully in a separate loopback-only QA stack | `artifacts/qa-final/container-*-build.txt` |
| Container restart/persistence | **11 checks passed**: refresh session, Unicode lead, private-file bytes, logout revocation, health and proxy headers | `artifacts/qa-final/container-tests.txt` |
| Source/image match | Container backend Python files exactly match delivered source | `artifacts/qa-final/source-image-match.txt` |
| Accessibility and responsive review | Zero serious/critical Axe violations on the scanned public/login/admin pages, interest editor and deliberately delayed loading states; 360/768/1440px checks and screenshots | Both browser reports and `screenshots/` |
| OpenAPI | 64 paths exported, including bearer authentication | `docs/openapi.json`, `/api/docs` |

Runtime verification used Python 3.12.7 / Node 25.2.1 / PostgreSQL 14.15 locally and Python 3.12.15 / Node 24 / PostgreSQL 17 / nginx in containers. CI configuration is supplied; no remote CI run or production deployment is claimed. Raw backend logs retain dependency deprecation/Decimal-default serializer warnings; no test failures are hidden or skipped. Coverage is below 100%, and no finite suite proves every possible environment or input.

The save/commit regression is verified at the HTTP boundary: committed rows must already be visible when success headers are emitted, while an injected commit failure must roll back and return a redacted conflict response. Both cases failed before correction and pass afterward. All request database dependencies now close before the response is sent.

## Feature/role acceptance checklist

| Area | Implemented and checked |
| --- | --- |
| Public website | Custom-development offering, original interactive illustrative preview, services, process, customization, industries, FAQs and separated login. Contact setup is truthful when missing; no subscriptions, checkout, invented testimonials or performance statistics. |
| Platform owner | Two-organization provisioning/isolation, member statistics, suspend/reactivate/archive, explicit support access and audit, persistent banner, exit after support expiry. Logo management is available through the recorded support workspace. |
| Account lifecycle | Country-aware phone normalization, wrong credentials, rate limiting, optional TOTP lifecycle/replay guard, refresh rotation/replay rejection, logout, password changes, expired sessions, deactivation and suspension. |
| Permission boundaries | Direct forged requests cannot change roles/owners/orgs. Caller, manager and admin access differs on the server. Payroll, rates, snapshots, settings and credentials remain admin-only. Cross-org details, files, exports and reports are denied/empty. |
| Membership | Admin provisioning/role changes, manager-limited active changes, concurrent last-admin protection, member removal requiring a manager handoff, assignment audit and immediate old-session revocation. |
| Lead creation and queues | Caller self-assignment; admin/manager unassigned; international/local normalization; duplicate warning; overdue/old never-contacted ordering; filtered list/export and private saved views. |
| Distribution | Zero, one and multiple callers, inactive callers, concurrent distribution, persisted cursor, existing assignment preservation and audit. Organization locks serialize ingestion/distribution membership changes. |
| Imports | Preview before persistence; actual CSV and XLSX; BOM/header aliases, numeric/zero-prefixed Excel phones, blanks, malformed files, duplicate aliases/headers, missing/unknown/forged columns, duplicate file/org phones, invalid values, row/file limits, partial successes and idempotent concurrent retries. Error download and formula-safe export checked. |
| Lead workspace | Rule-based factors/score, edit, notes, manual outcomes, callback validation/clearing, DND restrictions, tasks, private files, lost-manager handoff/reason and confirmed archival. A simulated secondary-history 503 leaves the main lead usable and retryable. |
| Merge | Notes, audio attachment, manual outcome, phone call, task, assignment history and lead notes preserved/reparented in a real transaction; cross-org merge denied; source archived; file access revoked after reassignment. Provider provenance, pending jobs, execution and audit references are also explicitly reparented. |
| Customization | Server-validated custom fields, required select choices and inactive historical values; categories; ordered stages; in-use migration; protected default stage semantics; branding, logos and optional pharma fields. |
| Tasks/calendar | Ownership checks, lead association, create/edit/delete, state transitions/reopening, filters, due flags, calendar and bounded pagination. Empty month selection remains usable. |
| Internal automations | All five exposed triggers executed in PostgreSQL tests; task, note and selected-manager actions; disabled/inactive-manager failures; execution visibility, idempotency and recursion protection. A browser-configured rule created a persisted note through the separate running worker. Obsolete scheduled callbacks are ignored. |
| Attendance | No automatic check-in on login, missing setup, invalid coordinates, poor accuracy, outside and exact boundary, explicit check-in, concurrent duplicate, before-check-in/duplicate checkout and too-short session. Saved timezone cutoff, worker downtime catch-up, manual/worker race and exactly one pending time entry checked. GPS tamper-proofing is not claimed. |
| Time/leave | Own submissions, employee/admin distinctions, self-review prohibition, manager/telecaller boundary, approved/pending/rejected states, daily hours limit, future-work rejection, concurrent overlapping leave, ordered/cross-month dates and other-org denial. |
| Payroll | Decimal rate/hours, attendance/manual source overlap policy, pending/rejected exclusion, working weekends/holidays, monthly target/leave intersection, rate secrecy and matching export. Browser-created 2.5 hours approved at ₹125.25 produced **₹313.13**, half-up. |
| Device phone data | Four calls to one lead remain four entries; repeated sync creates none; installation identity isolation, personal-number exclusion, ambiguous matching, current-assignment revalidation, organization isolation and reassignment access revocation. Device and linked manual metrics do not double-count. These are API simulations, not physical phone tests. |
| Recordings/private files | Real untagged WAV accepted; fake audio/image and oversized/empty inputs rejected; signature/container validation, transparent logo preservation, filename traversal handling, protected download, duplicate audio and reuse across calls, missing recording visibility and permission changes. No device recording-discovery claim is made. |
| Analytics | Actual records, consistent period totals, source/status/hourly reconciliation, equivalent prior period, linked-call deduplication, observed vs declared seconds, decimal order amounts, employee/city tables, saved definitions and export. |
| Provider adapters | IndiaMART response mapping, successful mocked ingestion, duplicate replay, HTTP 429/503, invalid/rejected payload, timeout retries, encrypted/masked credentials and isolation. Justdial valid/invalid token, payload/size/count validation, replay, pause/disconnect and reconnection-required state. **All provider tests use mocks/local payloads.** |
| Audit/snapshots | Scoped activity, filters/exports, sensitive audit categories hidden from managers, snapshot creation/download and absence of credential/password/session secrets; other-org denial. |
| Responsive/accessibility | Public and core CRM at 360/768/1440 px, no page-wide overflow; screenshots captured and visually inspected. Axe serious/critical violations: **zero** on public, overview, leads, tasks, attendance, payroll and settings. Keyboard dialog Escape and labeled controls checked. This does not assert every possible assistive-technology combination was manually tested. |

## Browser journeys executed

1. Public offering, interactive preview, FAQ and setup-required contact state.
2. Admin creates a lead, logs a converted outcome, adds a note, creates and completes a task.
3. CSV validation preview, partial row errors, persisted valid import.
4. Telecaller role restrictions and an optional history failure.
5. Denied geolocation gives a clear, retryable explanation.
6. Responsive public, overview, lead list, attendance, payroll and settings pages.
7. Platform owner creates an organization, enters its empty workspace through support and exits.
8. Public/core-page accessibility scans and keyboard dialog behavior.
9. Provisioned employee submits time, admin approves it, and the payroll estimate agrees with decimal arithmetic.
10. Saved lead view, saved analytics definition, a background automation, and an empty calendar-month input.
11. Simulated sign-out service failure preserves the workspace and displays an error; retry revokes the session and returns to login.

## Screenshots reviewed

`artifacts/screenshots/` includes public, overview, lead list, attendance, payroll and settings at 360, 768 and 1440 pixels, plus lead detail and a browser-verified payroll result. Desktop and mobile composition, clipping, table containment and text contrast were reviewed. These screenshots are development fixtures; they do not prove backend correctness by themselves.

## Dependency-bound verification

- **IndiaMART and Justdial live delivery:** not verified. Supply separate provider credentials/entitlements and confirm the contracted mapping, then follow `INTEGRATIONS.md` with a genuine enquiry/push.
- **Public contact actions:** configure the real contact phone/email. No fake contact or false enquiry success was added.
- **Production-domain HTTPS and deployment:** not performed. Local container builds, runtime and restart persistence are verified above; target-host rollout/DNS/TLS need a separately configured environment and explicit deployment instruction.
- **Physical-device geolocation:** browser permission denial was simulated; real workplace accuracy should be checked on intended browsers/devices.
- **WhatsApp:** remains excluded. Android was excluded from the original web audit; the separately authorized Android delivery and its physical-phone acceptance gate are recorded in [the Android QA matrix](../android/QA_MATRIX.md).

## Limits of the test claim

This is a broad, reproducible acceptance suite, not proof of every possible input, timing, browser, device or provider behavior. Coverage is explicitly below 100%. No load-test capacity or formal security certification is claimed. Operator restore/purge, real provider delivery, target-host rollout/TLS and physical GPS conditions must be validated in their real environments. No unrun check is counted as passing.


## Earlier verification history: Aven redesign — 17 October 2026

The user requested a professional design and navigation distinct from the previous reference-inspired presentation. The redesign introduces the configurable Aven identity, an original geometric mark, graphite work-area rail, contextual section navigation, cobalt actions, new dashboard action hub, redesigned public website/login and shared surfaces across every existing workflow. Existing URLs and server permissions are retained. WhatsApp remains excluded; Android was added after this web redesign.

A separate **Meridian Studio** development organization provides 24 fictional leads, four users, conversations, notes and six tasks for presentations. Its seeder was executed twice: the second invocation preserved all records. Its non-development refusal was exercised with `environment=test`. The original workspaces were preserved.

| Redesign check | Executed result | Evidence |
| --- | --- | --- |
| Backend regression suite | **88 passed**, 33.62 seconds | `artifacts/redesign/backend-tests.txt` |
| Full browser suite | **14 passed**, 54.6 seconds | `artifacts/redesign/browser-test-log.txt`, `artifacts/redesign/browser-tests.json`, `artifacts/redesign/playwright-report/index.html` |
| Accessibility | Zero serious/critical Axe violations on public site, login, and all 16 admin CRM destinations | Browser accessibility journey |
| Navigation | All 16 admin, 13 manager and 8 caller destinations exercised; deep links retain selected area | Browser navigation journey |
| Mobile controls | Keyboard entry, Escape/focus restoration, backdrop/route dismissal, desktop resize and search checked; active section revealed within horizontal navigation | Browser mobile journey |
| Long client identity | Contained at 320, 360, 768, 1024 and 1440px; header stays compact | Browser branding journey (presentation-only response fixture) |
| Presentation capture | 35 screenshots; all 16 pages at 360/1440px plus lead detail; no page overflow, browser exceptions or page error boxes | `artifacts/redesign/pitch-checks.txt`, `artifacts/redesign/pitch/` |
| Web lint, TypeScript, production build and formatting | Passed | `artifacts/redesign/frontend-*.txt` |
| Backend lint | Passed | `artifacts/redesign/backend-lint.txt` |

Desktop and mobile overview, public pages, login, leads, lead detail, reports and workspace settings were visually inspected. Review corrected a narrow-card currency wrap, a menu focus-restoration timing issue, the account link's accessible name, active-tab visibility on small screens and cramped form-panel headings. All business journeys from the original delivery remain in the full browser regression suite.

This historical section records the earlier redesigned build. Current final results are at the top. External-provider, physical-device and production deployment limits remain; the earlier Docker limitation has been resolved by local container verification. No claim that every conceivable edge case is covered is made.


## Customer-interest field and score correction — 17 October 2026

The score previously awarded interest points while the normal lead form hid its interest input behind the pharma flag. This gap is corrected. **Products/services of interest** is now available in every lead create/edit form, with an additional **Add interests / Edit interests** action on the Lead score card. Entries are manually recorded by the team, not inferred from notes or calls. The factor is labeled **Interests recorded**. Saved entries add 15 points once; clearing them removes those points.

The existing JSON interest list is retained, so no schema migration or reset is needed. Legacy category-key entries remain readable. General product/service text is accepted independently of optional pharma fields; primary-category validation remains enforced. CSV templates, imports and exports include the interest list. Merge deduplicates entries and refuses over-limit results before moving history.

| Check | Executed result | Evidence |
| --- | --- | --- |
| Full backend regression | **110 passed**, 55.82 seconds | `artifacts/interests/backend-tests.txt` |
| Focused interest checks | **22 passed**, 7.38 seconds | `artifacts/interests/backend-focused.txt` |
| Full browser regression | **17 passed**, 60.9 seconds; zero skipped/flaky/failed | `artifacts/interests/browser-test-log.txt`, `browser-tests.json`, `playwright-report/index.html` |
| Focused browser journeys | **3 passed**, 6.9 seconds | `artifacts/interests/browser-focused.txt` |
| Web lint, TypeScript, production build and formatting | Passed | `artifacts/interests/frontend-*.txt` |
| Backend lint | Passed | `artifacts/interests/backend-lint.txt` |
| Runtime | API, database and separate worker healthy after restart | `/api/health` returned all `ok` |

Checks cover standard/pharma modes; admin, manager and caller writes; unauthorized caller/cross-org denial; persisted create/edit/clear behavior; score increases/decreases; duplicate/case/whitespace normalization; malformed, blank, null, control-character and oversized entries; item count; Unicode import/export; spreadsheet-formula escaping; legacy category entries; merge preservation and atomic refusal; old blank entries awarding no points; failed UI saves remaining editable; mobile editor/keyboard behavior; and a serious/critical Axe scan of the focused editor. Existing business, role, responsive and accessibility journeys remain in the full browser suite.

The normal presentation workspace was also opened and both entry points captured without changing its customer records: `artifacts/interests/score-card.png`, `interest-editor.png`, and `lead-form-field.png`. Existing external-provider and deployment limitations remain unchanged.
# Android assigned-lead loading fix — 25 October 2026

Aven Realty 1.1.1 (version code 5) reads the assigned-contact directory after
sign-in and on foreground refresh without enabling call collection. Leads has a
Refresh leads button, loading/error/retry states and a confirmed-empty state only
after a successful response. A failed or partial response retains the complete
previous list and queued calls; account/company response checks remain enforced.

Verification in `artifacts/android/lead-loading-fix/verification.json`: 8 new
Android 15 HTTP/UI regression tests and 32 JVM tests passed. Debug/release builds
and lint passed with zero errors (14/13 existing warnings). All 14 original
calling/session/storage class fingerprints match the pre-UI baseline. The signed
APK updated 1.1.0 without clearing Neha's session, displayed 26 live assigned
leads, and passed manual refresh with uploads still paused. API/database/worker
were healthy. This fix used controlled local HTTP tests plus read-only live CRM
checks; no leads or recordings were created, reassigned or deleted. No new
physical handset or Android 16 test run is claimed for 1.1.1.

## Android CRM lead history and playback — 25 October 2026

Aven Realty 1.1.2 (version code 6) replaces the lead's local-only five-call dialog
with View history, reading the same existing lead/history APIs as the web CRM.
Calls, manual call remarks, notes, activity, tasks and files come from authorized
CRM history with older/newer pages. This does not insert historical server calls
into the device upload outbox. All five section buttons remain visible; larger
text uses two rows. No WhatsApp or recording-delete action was added.

Recordings use authenticated file requests, never bearer tokens in a URL. Private
preview files have size/digest checks and are removed on close/background/session
changes; the player supports pause, seeking and replay, and pauses on audio-focus
loss. Explicit Save file uses Android's file picker. Server permission failures
hide unavailable lead history instead of pretending it has no calls.

Evidence: `artifacts/android/crm-history-fix/verification.json`. Final Android 15
runs passed **21 unique regression tests** (13 history/file/player and 8 directory)
and **4 repeated journeys at 320dp/130% font**. All **32 JVM tests** passed. Debug,
test and minified signed builds and lint passed with zero errors. All **14 core
calling, recording, session and storage classes** retain their pre-UI hashes.
Normal signing identity and app data are retained. Existing non-fatal lint/Gradle
warnings remain; the exact counts are in the verification JSON.

A separate signed HTTPS check read Poonam's actual 23 synced calls and 11 uploaded
recordings, decoded an existing recording in the native player, and checked that
empty notes/tasks match CRM data. The working CRM's business records were not
changed. The emulator has audio output enabled and stays on that lead's history;
only the separate debug/test packages were removed. No physical OPPO or new
Android 16 test was performed for this change. Audio decoding/completion was
observed; speaker audibility was not independently measured. The current ngrok
workspace still needs this Mac, backend and tunnel online.

## ViaCRM admin and telecaller dashboards — 25 October 2026

Home → Overview now has role-specific charts and current work. Admins/managers
see team calls, enquiries/sources, pipeline, converted leads, priority clients and
team calling activity. Telecallers see their assigned clients, own calls/talk
time, call outcomes, private tasks and direct next actions. Super admin's Companies
page adds subscription health and company team-size charts. Period/team controls,
refresh, exact trend data, zero/error/retry states and responsive readable text
are included. Figures use real scoped records and workplace calendar dates;
linked manual outcomes add no duplicate calls. Current priorities exclude closed
status/stage, DND and archived clients, including inactive custom closed stages.

| Check | Executed result | Evidence under `artifacts/dashboard/` |
| --- | --- | --- |
| Final full backend suite | **279 passed**, 134.46 s; 28 non-fatal warnings | `backend-full-final.txt`, `backend-junit-final.xml` |
| Focused dashboard backend cases | **8 passed**, 4.14 s | `backend-focused-final.txt` |
| Full Chromium browser suite on production UI | **79 passed**, 158.52 s; no skipped/flaky/failed | `chromium-verified/browser-tests.json` |
| Chromium dashboard repeat after final closed-stage API refinement | **4 passed**, 12.93 s | `dashboard-final/browser-tests.json` |
| Firefox dashboard journeys | **4 passed**, 16.61 s | `firefox-final/browser-tests.json` |
| WebKit dashboard journeys | **4 passed**, 21.17 s | `webkit-final/browser-tests.json` |
| TypeScript/build, ESLint, full backend Ruff, dashboard formatting, whitespace | Passed | `build.txt`, `lint.txt`, `ruff-final.txt` |
| Working CRM smoke | Chart sums matched admin/caller API totals; priority excludes closed clients; login HTTP 200 and API/database/worker healthy | `local-smoke-final.json` |

Browser checks cover real persisted data, team/period controls, private caller
data, chart data/keyboard access, retry, 320/390/768/1440 px, doubled text at 320 px
and serious/critical Axe scans. Backend checks cover time boundaries, invalid
periods, tenancy/role/current field access, deduplication, exclusions, sorting
and truncation. The full Chromium suite used the final UI bundle; its dashboard
journeys and all backend tests were repeated after the last closed-stage API fix.
Firefox/WebKit checked that same unchanged UI bundle before this API refinement.

No new dependencies, migration, native source/APK change or call-sync contract
change was needed. Business records in the working CRM were read only; fixtures
used disposable test databases. See `QA_REPORT.md` and `verification.json` for
scope, screenshots, resolved failures and existing non-fatal warnings. The local
services were restarted and left running on web 5173 / API 8010.

## Hourly call chart display correction — 25 October 2026

Insights → Reports now displays the actual count above each hour, a numbered
count scale, AM/PM labels and the workplace timezone. Zero-call hours have no
bar; an entirely empty report has an explicit message. Selecting an hour exposes
its total, and **View hourly data** opens all 24 interval/count rows. Narrow
layouts keep scrolling inside the chart/table, with keyboard access. The team
and city report tables also received their existing keyboard-scroll labels.
Date/employee/role scoping and manual/device call deduplication use the unchanged
analytics API. The caption explains that hours aggregate the selected dates.

| Check | Executed result | Evidence under `artifacts/hourly-call-chart/` |
| --- | --- | --- |
| Full Chromium browser regression, production UI | **82 passed**, 173.20 s; no skipped/flaky/failed | `chromium-full/browser-tests.json` |
| Focused persisted hourly-chart journeys | **3 passed**, 8.48 s | `focused-verified/browser-tests.json` |
| Firefox / WebKit repeats | **3 + 3 passed**, 16.40 / 14.29 s | `firefox/browser-tests.json`, `webkit/browser-tests.json` |
| TypeScript/build, ESLint, Prettier and whitespace | Passed | `build.txt`, `lint.txt`, `format.txt` |
| Working CRM API and Chrome UI | All 24 buckets sum to 65 calls; selecting 6–7 PM shows 8; API/database/worker healthy | `live-data-check.json`, `hourly-fixed-live.jpg` |

New checks cover every displayed count, true zero-height bars, complete table
values, linked-outcome deduplication, employee/date filters, caller privacy,
midnight/noon labels, keyboard interaction, empty reports, 320–1440 px and doubled
text at 320 px, with serious/critical Axe scans. The first run's accessible-name
and table-scroll findings were fixed before the final successful runs; diagnostic
logs are retained. No backend/schema/native change or new dependency was needed.
Business records in the working CRM were read only, smoke sessions were signed
out, and disposable test databases/services were removed. See `QA_REPORT.md` and
`verification.json` for exact scope and source hashes.

## Automatic callback bell — 26 October 2026

The top-bar bell now shows a red overdue callback count and a paged, scoped inbox.
Each callback includes its client, responsible employee, workplace due time and
elapsed overdue time, with a direct link to the relevant work. Reading does not
dismiss an action. Saving a result or rescheduling resolves lead callbacks;
separate tasks retain their own Planner/Field work completion flow. Active tabs
check every 30 seconds. Optional Studio workflows require no setup for this.

| Check | Executed result | Evidence under `artifacts/callback-alerts/` |
| --- | --- | --- |
| Full backend regression | **288 passed**, 121.24 s; 28 non-fatal warnings | `backend-full.txt`, `backend-junit.xml` |
| Focused inbox backend cases | **9 passed**, 3.99 s | `backend-focused-final.txt` |
| Full Chromium suite on production UI | **86 passed**, 226.58 s; no skipped/flaky/failed | `chromium-full/browser-tests.json` |
| Focused Chromium callback journeys | **4 passed**, 43.40 s | `focused-final/browser-tests.json` |
| Firefox / WebKit callback journeys | **4 + 4 passed**, 50.77 / 47.71 s | `firefox/browser-tests.json`, `webkit/browser-tests.json` |
| TypeScript/build, ESLint, full backend Ruff, modified frontend formatting, whitespace | Passed | `build.txt`, `lint.txt`, `ruff.txt`, `format.txt` |
| Running CRM API and Chrome UI | Admin 6 overdue / caller 3; totals and legacy array checked; web HTTP 200, API/database/worker healthy | `live-smoke.json`, `final-health.json`, `callback-alerts-live.jpg` |

Backend coverage includes due boundaries/timezones, all closed/DND/deleted
exclusions, future callbacks, role/company privacy, immediate reassignment,
field task transfer and revoked access, callback result/reschedule/completion,
invalid queries, legacy response shape and 105-item exact counts/paging/clamping.
Browser journeys exercise real persisted records, correct links, UI results and
rescheduling, pagination after resolution, honest loading/error/retry, outside
click/Escape/focus, automatic 30-second refresh, 320–1440 px, doubled text at
320 px and serious/critical Axe checks. Both initial accessibility/error-state
findings were fixed; diagnostic logs remain available.

No schema/dependency/native source/APK or call-sync contract changes were needed.
QA fixtures used disposable databases only; no business records were edited in
the working CRM. Temporary QA databases/services were removed. Web 5173 and API
8010 remain running. This adds in-CRM alerts, not closed-browser push messages.
See `QA_REPORT.md` and `verification.json` for evidence and verified source hashes.
