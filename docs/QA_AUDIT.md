# Final product QA audit

Scope of this original audit: the complete independent web CRM, API, persistence, worker, public site, local setup and packaging. WhatsApp remains excluded. Android was added afterward on 18 October 2026; see its separate [QA matrix](../android/QA_MATRIX.md) and the [current acceptance record](ACCEPTANCE.md). This audit checks the original brief against real controls and saved records, beyond the earlier passing regression suite. Live provider accounts, physical GPS behavior and production deployment are separate verification environments.

## Release gates

- All permitted features must be reachable from the normal workspace and remain usable after reload.
- Each state-changing workflow must validate inputs, preserve data on failure, enforce current role/org boundaries, and expose a useful retry path.
- Search, filters, dates, pagination, exports and histories must agree, including datasets larger than the initial page.
- Form defaults, required/custom fields, keyboard interaction, slow responses, failed secondary queries, session refresh and account changes must behave consistently.
- Worker concurrency/idempotency, attendance/payroll arithmetic, provider failure isolation, private-file access and recovery must pass PostgreSQL-backed checks.
- The production bundle must be exercised independently of the Vite development server. Chromium and Firefox are target desktop browser checks, with 360/768/1440px responsive review.
- Final lint/type/build, backend regression/coverage, browser regression, migrations, restore and packaging checks must run against the final source. Evidence must distinguish an executed local check from a dependency awaiting real credentials or infrastructure.

## Findings corrected and regression coverage

| ID | Finding | Required verification |
| --- | --- | --- |
| Q01 | Required boolean custom fields can incorrectly force true; fields arriving after a delayed definitions request miss defaults | Create/edit required false and delayed defaults; persist after reload |
| Q02 | Native dialog Escape can hide an in-flight form while its React state stays mounted | Delayed failed save, Escape, visible error, successful retry |
| Q03 | Related-lead task selector only exposes the first 100 leads | Search and retain a selected older lead; caller scoping |
| Q04 | Task calendar can retain an out-of-range list page | Change view/month after page 2; show matching tasks |
| Q05 | Saved lead date filters are applied but not displayed; stage/ordinary interest filters are missing | Apply/reload saved view; visible controls, list/export reconciliation |
| Q06 | Lead history is silently limited to 500 records | Page through older notes/calls/files/activity with stable ordering and current access checks |
| Q07 | Reopening an interaction from a closed custom stage leaves the lead in that closed stage | Preserve an open custom stage; closed status mapping and reopening |
| Q08 | Some date filters accept naive or reversed ranges | Consistent explicit validation on leads/tasks/phone calls/reports |
| Q09 | Manager audit filtering occurs after pagination; older operational rows can disappear | Sensitive rows before page 1; consistent list/export exclusion |
| Q10 | A temporary refresh-service failure is treated as an expired login; initial restoration has no outage retry | Refresh + 503 retry; retain identity and show retryable error |
| Q11 | A corrupt integration credential can break the whole integrations response; long provider IDs can collide when truncated | Per-provider error isolation; long ID deduplication; oversized provider batches do not advance cursor |
| Q12 | Lead selection and empty pagination state can outlive a changed view | Switch saved/reset filters after selecting; recover after final-page deletion |
| Q13 | Several auxiliary form queries can fail without a visible retry | Inject definitions/directory failure and recover in the same form |
| Q14 | A PDF signature alone passes upload validation | Reject truncated/signature-only files; valid/encrypted PDF round trips; private access |
| Q15 | Attendance/time/leave lists have silent lifetime caps | Stable scoped pagination and visible previous/next controls |
| Q16 | Retiring a select option blocks unrelated edits to existing leads | Preserve unchanged historical value; reject its use on a different/new record |
| Q17 | Restore verification compares a consistent dump against later live counts, creating false failures during browser writes | Export one repeatable-read snapshot for both pg_dump and source counts |
| Q18 | Database commits occur after HTTP success headers, allowing false save acknowledgments or stale reads | Observe committed rows at response start; force commit failure and require rollback/conflict before response |
| Q19 | Loading skeletons have an aria-label without a compatible role | Explicit status/live-region semantics; Axe checks while page/form data is deliberately delayed |
| Q20 | A non-ASCII webhook token can trigger a comparison exception | Byte comparison rejects malformed headers with 401 and imports no data |
| Q21 | Mobile source/status dropdowns truncate both visible labels | Two-column responsive controls; actual text-width assertion at 360px in both browsers |

## Requirements and evidence matrix

The final execution results are in [ACCEPTANCE.md](ACCEPTANCE.md), with machine-readable reports in `artifacts/qa-final/`. `backend/tests/test_final_qa.py` adds 41 PostgreSQL-backed checks; `web/tests/final-qa.spec.ts` adds 16 real-browser journeys. All twenty-one findings above are corrected. Existing open custom stages already survived ordinary outcomes; Q07 specifically fixes reopening from a *closed custom* stage.

Coverage areas: public site/configuration; owner organizations/support; authentication/2FA/session lifecycle; all role boundaries; team lifecycle; lead fields/scoring/queues; assignment/imports; notes/outcomes/history/merge/files; planner/calendar; automations/worker; attendance; time/leave/payroll; reporting/export/saved views/notifications; integrations; custom definitions/branding; audit/snapshots; fresh setup/backup/restore; production bundle/browser/accessibility.

| Area | Automated evidence | Boundary/exception checks |
| --- | --- | --- |
| Public site and independent navigation | `crm.spec.ts` public, work-area, long-branding and responsive journeys | Missing contact configuration, mobile dismissal, deep links, role-specific destinations |
| Owner organizations/support | `test_access_and_auth.py`, `test_providers_files_platform.py`, owner browser journey | Suspended/deleted organizations, explicit support, expiration/exit, last administrator and cross-org access |
| Authentication and sessions | `test_access_and_auth.py`; new refresh, bootstrap, authenticator and account-switch browser journeys | Revocation, concurrent refresh, TOTP invalid/replay, transient outage, logout failure and retries |
| Leads, score, qualification and queues | `test_leads_imports_calls.py`, `test_interests.py`, `test_final_qa.py`; lead browser journeys | All roles/business modes; confirmed interests, literal search, DND, invalid/custom values, retired choices, date ranges and list/export agreement |
| Ownership/imports/merges | Existing import/distribution/merge tests; new search/merge/page browser journeys | Caller ownership forgery, duplicate/BOM/Excel/numeric/error limits, concurrent round-robin, all dependent histories, >100 selector reachability |
| Notes/calls/files/history | Existing file/call and new final QA tests; browser notes, older history, file download and merge | 507 tied-time notes without gaps/duplicates, current assignment/author/file permissions, valid/corrupt audio/images/PDFs, encrypted PDFs, linked recordings |
| Planner/automations/worker | `test_workforce_jobs_reports.py`, `test_regressions.py`; planner and running-worker browser journeys | All five triggers, obsolete callbacks, retries/idempotency, disabled actors, slow-organization isolation, calendar after page 2, failed directory retry |
| Attendance/time/leave/payroll | Workforce suite and browser permission/time/review/payroll journeys | Exact/outside geofence, denial/poor accuracy, midnight/DST cutoff semantics, duplicate races, source overlap, daily limits, overlap/reviews, decimal rounding, scoped pagination and rate secrecy |
| Reporting/views/audit | Report/regression/final QA suites; saved filters and reports/export browser journeys | Linked-call deduplication, actual totals, historical periods, invalid saved dates/types, user privacy, sensitive audit rows filtered before pagination |
| Configuration/integrations/snapshots | Provider/platform/regression suites and settings browser coverage | Secret redaction, bad ciphertext, credential replacement, long external IDs, oversized batches/cursor retention, mocked provider failures, private snapshots |
| Forms and failure recovery | New required-false, delayed save/Escape, definitions/directory, refresh and sign-in browser journeys | Defaults after async queries; save blocked without required data; draft survives failed save; successful retry persists exactly once |
| Build/container/recovery | Ruff, ESLint/TypeScript/Vite; `verify_recovery.py`, `verify_container.py`, production-bundle browser suite | Fresh migrations up/check/down/up, restored counts/file hashes, independent database/storage volumes, proxy headers, session/data/file retention across container restart |

Coverage records executable scenarios, rather than a claim that all possible inputs or environments are proven. Provider delivery remains mocked/local until real customer credentials are supplied. Physical GPS/network/provider behavior, production-domain TLS, host failover, and sustained large-scale load are not represented as verified by these checks.
