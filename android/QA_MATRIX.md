# Android verification

## Aven Realty 1.1.4 — history error recovery

Evidence: [report](../artifacts/android/history-recovery/REPORT.md) and
[verification](../artifacts/android/history-recovery/verification.json).

The visible error recovered after a manual retry; the original failed network
response was not retained. A new regression confirms that HTML tunnel/proxy 404
responses must not be described as a lead reassignment. Structured CRM denials
still hide the lead, company suspension has its own explanation, and returning
to a failed screen retries without clearing pending calls.

**25 Android 15 directory/history/file/player cases**, **4 repeats at 320dp/130%
text**, **32 JVM tests**, debug/release lint and debug/test/signed release builds
passed. The signed code-8 update retained the existing caller login, loaded the
actual 23 calls/11 recordings and decoded uploaded audio to Finished, 6s/6s.
All 14 baseline core classes remain byte-identical. Web/backend and the earlier
system lifecycle suite were not rerun for this isolated screen fix. No new
physical handset or Android 16/API 26 run is claimed.

## Aven Realty 1.1.3 — full web/mobile audit, 25 October 2026

Evidence: [full report](../artifacts/full-audit-20261025/QA_REPORT.md) and
[verification JSON](../artifacts/full-audit-20261025/verification.json).

- Android 15 / API 35: **38 unique instrumentation cases**, **13 lifecycle checks**,
  **32 JVM tests**, and **4 repeated history cases at 320dp / 130% text** passed.
- Real API/CallLog/SAF upload produced private, downloadable and decodable WAV
  recordings without duplicate attachments. Web and mobile displayed the same
  isolated lead's 20 calls, 2 recordings, note and task. Reassignment revoked
  native history/recording reads.
- Fixed orphan playback previews after force-stop. Cold-start cleanup preserved
  the pending call, all existing call states and paused collection. Creating a
  second reader keeps the current process's active playback preview.
- The signed update retained the existing caller login, displayed the actual
  lead's 23 calls/11 recordings and decoded uploaded audio. The app was updated
  in place, uses version code 7 and retains the original signing certificate.
- All 14 core calling/auth/storage classes remain byte-identical. Debug/release
  lint: zero errors, 14/13 existing warnings. Debug, test and minified signed
  release builds passed. No QA provider/debug package is included in the APK.
- This audit also passed 242 backend tests and 61 production-web journeys in each
  of Chromium, Firefox and WebKit. Isolated test databases/services were used.

This release was not newly run on Android 16/API 26 or a physical OPPO. The
emulator does not validate two-speaker cellular audio or an OEM recorder folder.
The current ngrok workspace requires the owner's Mac, API and tunnel online.
Historical results below are not additional runtime checks for 1.1.3.

## Aven Realty 1.1.2 — CRM lead history and recording playback

Evidence: `artifacts/android/crm-history-fix/verification.json`. The normal Android
15 suite covers 13 new history/file/player cases and 8 assignment cases. Four
history journeys also run at 320dp width/130% font with control-size/truncation
checks. JVM, lint, debug/test and signed release results are recorded there.

The signed APK reads an existing assigned lead's 23 synced calls and 11 recordings
through the actual HTTPS history/files APIs. Its uploaded audio decodes in the
native player. Notes/tasks empty states match that lead's real records. History
reads leave the local call outbox untouched, respect current account permissions
and provide no recording-delete action. File export uses an explicit picker;
playback uses bounded, verified private temporary files, removed on close or
backgrounding. All five sections are visible without sideways scrolling; larger
text uses two rows. See the evidence for exact results and remaining limitations.

## Aven Realty 1.1.1 — assigned-lead loading fix

Evidence: `artifacts/android/lead-loading-fix/verification.json`. All 8 new
Android 15 HTTP/UI regression tests passed: fresh login without call permissions
or upload consent, pagination, failed second-page/cache/queue preservation,
foreign-company rejection, repeated cursor rejection, loading versus confirmed
empty, expired-session recovery and retry with search retention. All 32 JVM tests
passed; debug/release lint had zero errors (14/13 existing warnings).

The signed version-code-5 APK updated 1.1.0 in place with the same certificate,
retained Neha's login, and displayed all 26 actual assigned CRM leads. Manual
refresh worked while call uploads remained paused. The 14 core calling, storage
and authentication classes still match their pre-UI hashes. This fix was tested
on Android 15; it does not add another physical handset or Android 16 test run.

## Aven Realty 1.1.0 — previous real-estate interface

See `artifacts/android/real-estate-ui/verification.json` for the executed checks,
screenshots, signed APK metadata and limits. This covers the real-estate Home,
Leads, Calls and More screens plus the read-only company property catalogue.
The catalogue tests include live API search/type/rent filters and pagination,
plot field applicability, network failure, session expiry and a controlled
delayed-response regression for preserving an unfinished search.

The original calling/recording classes are checked against their pre-UI hashes.
Version 1.1.0 uses the same release application ID and signing certificate, with
version code 4. Signed HTTPS sign-in, in-place upgrade retaining the account,
inventory loading and sign-out were exercised separately from isolated mutation
tests; collection stayed off in that development workspace smoke check.

## Current logic baseline — 25 October 2026

The owner selected their tested source ZIP as authoritative. Its timestamp-only
recording matching and closest eligible call selection supersede the original
unique phone-and-time policy. See `LOGIC_BASELINE.md` and the executed results in
`artifacts/android/zip-logic-priority/verification.json`. Historical results below
describe earlier APKs; they are not results for the newly integrated source.

## Historical verification — 18 October 2026

This matrix distinguishes automated software checks from physical recorder validation. The app collects assigned work calls and uploads audio generated by the stock Phone app; it does not implement cellular audio capture.

## Version 1.0.2 — simpler interface

The latest signed delivery is `artifacts/android/aven-calls-1.0.2-simple-ui.apk`.
Current evidence is in `artifacts/android/simple-ui/`: **19 JVM tests**, **8 device/API/UI
tests on Android 15**, **8 on Android 16**, and **13 Android 16 lifecycle checks** passed.
The signed release itself passed real ngrok HTTPS sign-in/setup/update checks,
customer search/navigation and a 320dp/130% text layout check on both OS versions.
Screenshots were visually reviewed. Separate call-details/recording states prevent a
missing recording folder from being presented as ready audio.

Sign-in hides server configuration behind Connection settings. Setup requires explicit
authorization, provides permission recovery, and allows recordings to be configured
later while keeping that missing step visible. The UI regression checks literal
search/no results, pause/resume, masked password/input retention, authenticator retry
and recovery without dropping queued work. Older backend/browser and recorder-format
coverage below remains applicable; the original evidence files describe version 1.0.0.
Real handset recording, two voices, installer restrictions and OEM file access still
require physical acceptance.

## Original business-rule and lifecycle coverage

| Area | Cases exercised | Evidence |
|---|---|---|
| Number handling | Indian/international formats, trunk/00 prefixes, private/invalid/service/SIP numbers, misplaced plus signs, no suffix matches | 19 JVM tests across four suites; `artifacts/android/unit-tests.json` |
| Call classification | Incoming/outgoing, missed/rejected/blocked/externally answered types, zero duration, voicemail exclusion, reused native row IDs, 30-day/future time boundaries | JVM tests and real Android CallLog provider integration |
| Matching | Full phone + native timestamp, wrong number/date/modified time, multiple candidates, unanswered calls, DST ambiguity, unsupported formats | JVM tests; `RecordingMatcherTest` |
| Durable state | SQLite reopen, repeated capture, monotonic duration, known outcome preservation, reassignment pruning, growing-file observations, queued-audio retention, revoked lead IDs despite a reused number, review rows excluded from transfer scheduling | Device instrumentation |
| Credentials | Android Keystore encryption, reload, atomic access/refresh rotation, invalid password/role, authenticator rejection/restart/valid sign-in, revoked refresh cookie, queue preserved after auth failure, automatic return to sign-in and same-account recovery, account switch clearing | Device instrumentation with actual local API |
| Recording upload | SAF document provider, stable file delay, streamed synthetic WAV, lost acknowledgement retry, server deduplication, missing document, private download and audio decoding | Device instrumentation and `server-pipeline.json` |
| Foreground controls | Actual login form, explicit authorization, Android permission dialog, enable, real foreground data-transfer service, pause and resume | UiAutomator instrumentation |
| Background/system behavior | Simulated incoming cellular calls, force-stop restriction and reopen recovery, offline durable queue, permission revoke/regrant, notification denial, reboot/unlock, forced idle and duplicate reconciliation | `lifecycle.json` and `lifecycle-api36.json` |
| Release packaging | Minified signed release, signature verification, permission manifest, startup and HTTPS-only address validation | `signature.txt`, `permissions.txt`, `release-smoke.json` |
| Backend integration | Current assignment scope, pagination, per-call receipts, identity conflicts, duplicate IDs, retries, recording association/access/deduplication, separate recording upload limit | Full backend suite: **157 passed**; `backend-full.txt` |
| Web regression | Real persisted CRM journeys, call/file access, interest/score entry, saved filters, responsive typography, permissions and authentication recovery | **37 Chromium + 37 Firefox passed**; browser reports |

Runtime device details and final per-OS totals are in `artifacts/android/verification.json`. Automated native tests use an isolated temporary CRM organization; shared customer accounts are not used. Simulator call audio is not a physical two-way recording. The separate test document provider exists only in the instrumentation APK, not the delivered application.

The request-limit test caught the API middleware's old 11 MiB ceiling, and the fix keeps ordinary files at 10 MiB while permitting linked recordings up to 64 MiB. Runtime recovery tests caught a stale HTTP keep-alive read; a fresh connection now retries that GET once. Uploads and rotating refresh sessions retain explicit acknowledgement/retry handling. Review/ambiguous calls no longer count as eligible recording transfers, preventing a self-scheduling loop; an actual duplicate-lead API test verifies that no follow-up upload is queued and a review message remains visible. Test-harness fixes cover reboot package readiness and permission dialogs; no failing acceptance assertion was removed.

## Physical phone acceptance gate

These checks require the exact India-region Samsung handset, software build, SIM and recorder settings. **They have not been executed on physical hardware in this workspace.**

| Physical check | Acceptance requirement |
|---|---|
| Installer permission policy | Call-log and Phone permissions can be granted through the chosen enterprise installation method. |
| Native automatic recording | The stock Phone app automatically records incoming and outgoing work calls and exposes a readable local recording folder. |
| Both speakers | Both voices are audible for handset, speakerphone and Bluetooth routes. |
| Dual SIM and call waiting | Correct call metadata and recording association; ambiguous files require explicit selection. |
| Filename format | Actual recorder names contain a supported phone/date pattern for automatic linking. Contact-name-only recordings require manual selection. |
| Long/late recordings | Completed files settle and upload; files over 64 MiB show a clear limit error; delayed native saves reconcile later. |
| OEM power restrictions | Reboot/unlock, screen-off calls, Samsung sleeping-app settings and overnight idle preserve/recover the queue under that handset's policy. |
| Network and server | Phone can reach the configured HTTPS CRM origin; local QA can instead use the test APK and USB reverse forwarding. |

Android can defer background work, and force-stop blocks execution until the user opens the app. No ordinary APK can honestly promise immediate upload or two-way cellular recording on every model. The recommendation is one validated Samsung pilot unit before selecting a fleet. See [setup instructions](README.md) and the linked official Android/Samsung documentation.
