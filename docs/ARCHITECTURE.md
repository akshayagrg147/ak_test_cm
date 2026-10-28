# Architecture and permission contract

React + TypeScript + React Router + TanStack Query connect to FastAPI through a same-origin `/api` client. Access tokens live in memory; refresh tokens are random, stored hashed in PostgreSQL, rotated through an HttpOnly SameSite cookie, and protected with a required custom header and origin validation. Passwords use Argon2. TOTP and provider credentials use Fernet encryption. Protected operations resolve current session, user, role and organization state on every request. Mutations lock the organization and recheck session state after acquiring the lock.

PostgreSQL is the only supported persistence backend. SQLite is intentionally not substituted for locking tests. Alembic revisions create the schema. A separate Python worker processes durable jobs, due callbacks, provider polling and attendance closure. Browser closure does not affect job execution. The organization row provides a consistent lock order for ownership, membership, imports, attendance and review operations. Different organizations have independent transaction boundaries. Jobs use unique keys, transactional completion, retry limits, exponential delay and execution records. Automation actions do not emit recursive automation events.

Private file bytes live outside the web root under server-generated UUID keys. Downloads resolve current organization, lead access and call privacy before serving bytes. Image headers and decoding are verified; audio containers are parsed with Mutagen. PDFs are checked by signature and downloaded as attachments. There is no claim of malware scanning. Transparent logo bytes are preserved. Removed-file bytes remain for the operator's retention and orphan-collection policy, avoiding a rollback that refers to a prematurely removed object.

## Permission matrix

| Capability | Owner | Organization admin | Manager | Telecaller |
| --- | --- | --- | --- | --- |
| Create/suspend/archive organizations | Yes | No | No | No |
| Create/edit/deactivate company admin logins; company branding | Yes, explicit company-scoped routes | Own company through existing team/profile routes | No | No |
| Payment methods/plans and payment approval | Yes; cash approval requires receipt confirmation | Submit own company UPI/cash requests only | No | No |
| Read organization data directly | Explicit audited support only | Entire organization | Operational organization data | Currently assigned leads and own private work |
| Create/import leads | Support workspace | Unassigned | Unassigned | Assigned to self; forged owner fields rejected |
| Assign/distribute | Support workspace | Yes | Yes | Own lead → active same-org manager only |
| Merge/delete leads | Support workspace | Yes | Yes | No |
| Team provisioning/roles/password reset/removal | Support workspace | Yes | No | No |
| Log in as a manager/telecaller | Through audited company support | Active same-company members; audited 30-minute session | No | No |
| Active-status operation | Support workspace | Yes | Telecallers only | No |
| Operational reports/audit | Support workspace | Yes | Yes, with sensitive audit categories excluded | Own reports; no audit |
| Personal geofenced attendance | Not an org member | Yes | Yes | Yes |
| Manual time/leave submission | Support employee operations | For employees, review-only for own manual requests | Own | Own |
| Review time/leave | Support workspace | Team; cannot self-review | Telecallers/field executives; cannot self-review | No |
| Payroll/rates/snapshots/settings/credentials | Support workspace | Yes | No | No |
| Integration status | Support workspace | Yes | Masked status and runs | No |
| Device calls | Support workspace | Organization | Organization | Own calls on currently assigned leads |
| Delete recordings/audio attachments | Support workspace | Company recordings | Own uploads only, with current access | No, including own uploads |

Support is a separate 30-minute session, never implicit owner membership. It has a persistent banner and a cookie-authenticated exit that still works after support access expires. Active support sessions are revoked on organization suspension. Last active administrators cannot be removed, deactivated or demoted; the organization lock prevents concurrent removal of both remaining admins. Organization deletion is a confirmed archive with immediate access revocation; purge/recovery remain operator actions. Member removal is an archive and requires another active same-organization manager when active leads are owned.

Super-admin company-admin mutations recheck current owner authority and lock the
target company. They accept only administrator creation or allowed account fields;
cross-company IDs and other roles are rejected. Login phones remain globally
unique. Creation/reactivation respects active seat limits, and last-admin checks
count the target company. Actual phone/status changes and password resets revoke
the target's sessions, including acting-as sessions; name-only changes do not.
Passwords/authenticator secrets are never returned or audited. Logo replacement
validates image bytes before changing the profile; removal retains other settings
and private attachment history.

Subscription payments snapshot plan terms, amount and method. `upi` remains the
default for existing clients and migration 0007 backfills old rows as UPI without
altering their references. UPI references remain unique; `cod` records have NULL
references enforced by database constraints. Both methods share the single-pending
company guard and request idempotency; method/amount conflicts cannot reuse an
acknowledged request ID. Exact acknowledged retries remain readable after disabling
a method. Cash-only configuration requires no QR. Cash approval requires an
explicit `cash_received=true` owner acknowledgement; rejected/unreceived requests
never activate plans. Organization locking serializes reviews and subscription
updates, so concurrent approvals extend once. These are human receipt decisions,
not automatic bank reconciliation or proof that physical cash was collected.

Administrator member login creates a separate session linked to the existing
administrator session. Its effective user/role is the selected active manager or
telecaller, with the normal assignment and company permission checks. It never
reveals or replaces the member's password or authenticator secret. Account-security
mutations are blocked in this mode. A persistent banner identifies the member,
administrator and deadline, with a cookie-authenticated return to the original
account. It cannot nest, impersonate another admin, extend the original session,
outlive 30 minutes, or continue after the original administrator loses authority.
An expired member window returns to the still-valid administrator on refresh;
expired company support returns its super admin to the platform. Returning revokes
the member session and rotates the original refresh credential. Signing out also
revokes its parent session. Work belongs to the effective member, while audit events
identify the actual administrator and include `acting_as_user_id`. Start/return are
audited. Password/role/active-state changes revoke affected member access. Independent
member sessions remain separate from an administrator's inspection session.

## Data model

`models.py` defines Organization, User, AuthSession, LoginGuard, Lead, Assignment, Note, ManualCall, PhoneCall, Attachment, Task, Definition, SavedView, Audit, Automation, AutomationRun, Job, Attendance, TimeEntry, Leave, PayProfile, ScheduleException, Integration, SyncRun, Provenance, ImportRun, Backup and WorkerHeartbeat.

Categories, custom fields and stages use organization-scoped `Definition` rows with `(org_id, kind, key)` uniqueness. The work schedule/geofence are versioned by audit in organization settings; each check-in stores its own fixed midnight cutoff. The distribution cursor lives on the locked organization. Time/leave records store the employee, submitter and reviewer separately. Manual outcomes, actual device calls, business status, custom pipeline stage and the approved payroll ledger are distinct records.

Foreign keys preserve identity and history. Every application lookup includes organization scope; caller reads additionally require ownership. Merge reparents notes, files, manual and device calls, tasks, assignments, provider provenance, automation executions, audit references and pending event payloads. Primary identity wins; nonconflicting custom/qualification details and interests are combined. The source is archived for recovery and audit instead of cascade-deleting its history.

## Business rules and metric definitions

- Phone normalization uses libphonenumber and E.164. Numbers without `+` are interpreted in region IN, including valid Indian landlines; international numbers must include their country code. Arbitrary foreign identifiers are never truncated to ten digits.
- Telecaller queues: overdue callbacks, never-contacted leads oldest first, then other records. Admin/manager queues: unassigned first, newest within each group. Assignment is explicit; ingestion does not auto-distribute. Round robin skips inactive/deleted callers and never overwrites an existing owner.
- Imports: 10 MiB compressed input, 50 MiB expanded XLSX, 10,000 rows and 100 columns. UTF-8 BOM and aliases are recognized. Empty rows are counted separately. Duplicate phones within a file or organization are skipped. Exact completed file retry is keyed by organization, user and SHA-256 digest. A corrected file has a new digest. No arbitrary assignee or org columns are accepted. CSV exports prefix spreadsheet formulas, including leading `+`, with an apostrophe.
- Outcomes require an idempotency key. Follow-up requires a future timestamp; other outcomes clear callback state. Lost requires a reason and active-manager handoff. DND blocks manual contact actions in the UI and API; notes and received device metadata remain recordable.
- Score: valid contact 20, city 10, recorded interests 15, first contact 15, next step 15, qualified stage 10 or proposal/won/converted 25. Hot ≥75, warm ≥45, otherwise cool. The factor is labeled "Interests recorded". Any nonblank interests award 15 points once; clearing them removes those points. This is recorded qualification/progress, not a prediction of purchase.
- Products/services of interest: the existing `Lead.interests` JSON list is now a general field available in every create/edit form and in a focused score-card editor. Existing category-key entries are retained. Interests are customer information entered by the team, independent of the optional pharma fields. Entries are trimmed, deduplicated case-insensitively, bounded to 30 items/160 characters per item, and reject internal control characters or the import separator `|`. `category` remains validated against the organization taxonomy. CSV/XLSX imports and CSV exports use `|` between interests. Merge combines interest lists and refuses a result over 30 before moving any history; neither record is altered on refusal.
- Stale means created more than 48 hours ago with no first contact. Callback attention counts use all currently visible leads. Notification targets preserve current permission checks.
- Dates are stored in UTC. Attendance boundaries and report hourly buckets use the workplace IANA timezone (default Asia/Kolkata). User-entered date/time inputs use the browser timezone and are sent with an explicit UTC offset. Tables display browser-local date/time; the reports identify the bucket timezone. Date ranges are `[from, to)`; end is exclusive.
- Login does not mark attendance. Check-in validates coordinates, accuracy and distance on the server. Accuracy must be ≤100m and ≤radius. Accepted radius is 25–5000m. Location is evidence supplied by the device, not tamper-proof GPS. Check-out before check-in and a second same-day check-in are conflicts.
- Midnight cutoff is saved at check-in. Manual and worker closures use the same locked function. A worker recovering at 02:00 records the saved midnight cutoff. Sessions shorter than 60 seconds create no work-time entry; longer sessions create one pending entry with a unique attendance source ID.
- Payroll has two per-employee methods. Existing `work` profiles keep per-day
  eligible hours `min(24, max(approved manual hours, approved attendance hours))`
  multiplied by the original hourly rate. Migration 0006 preserves all existing
  profiles/rates and adds optional `office_calls` with a separate calling rate.
  Office + calling pays `(approved office seconds - call overlap) / 3600 × office
  rate + unique answered-call seconds / 3600 × calling rate`. The separate-rate
  office source is closed Attendance with its matching approved TimeEntry; manual
  ledger hours are not substituted for office intervals. Open/pending/rejected
  attendance is visible but unpaid. Calls outside attendance remain eligible at
  the calling rate. Positive answered device-call intervals are merged per employee;
  manual conversations, including linked outcomes, never add calling pay. Historic
  calls stay attributed to their employee after customer reassignment/archival.
  Intervals are clipped at workplace-local month/day boundaries and the captured
  calculation time; future duration is excluded, DST uses actual elapsed time.
  Call placement uses device start + duration and is approximate at office edges
  because the sync contract has no connected-at timestamp. Each pay component uses
  Decimal half-up to a paisa once, then sums; team totals also use Decimal. Daily
  targets/leave do not generate paid hours. Estimates stay live and rates apply
  across months. Admin-only list/export/profile permissions and sensitive audit
  restrictions remain in force; omitted new fields preserve legacy API updates.
- Workday targets follow weekdays and dated exceptions; approved leave reduces the target only for working days in the selected month. Leave contributes no paid hours by itself. Overlapping pending/approved leave is rejected transactionally; holidays/weekends and cross-month ranges are intersected explicitly. Inactive employees cannot receive newly approved submissions until reactivated; historical records remain intact.
- Analytics leads, sources and statuses use lead creation within the selected range. A prior range of identical duration supplies the comparison. Calls use interaction/device start time. A manual outcome linked to a device call adds business outcome/order value but no duplicate count or duration. Observed and declared seconds are displayed separately. Average order value uses positive entered order amounts. Exports use the same service functions as cards/charts.
- Device idempotency: organization + user + installation ID + device-call ID. Only exact unambiguous currently assigned lead numbers are accepted. Personal/unassigned calls are excluded. Initial synchronization is limited to 30 days and five minutes of future clock skew. Later duration updates are monotonic; identity conflicts are reported. Recordings cannot reuse the same content hash on unrelated calls.
- Definitions validate required custom fields and types server-side. Default status mapping stages are protected. A stage in use must migrate its leads before removal/deactivation. Field/category definitions are archived so historical values remain understandable.
- Real estate onboarding uses property category defaults. Conversion retires only
  unchanged healthcare seed categories; custom keys and renamed definitions are
  preserved. Migration 0005 backfills that retirement for already-converted
  companies and disables their pharma qualification flag. It changes no customer,
  call, attachment or property data. The data correction remains on schema downgrade.
  Category selection uses active definitions; an existing selected inactive value
  remains readable as a previous category. Lead create/edit, summary, filtering
  and export use the same saved primary category. Settings saves cannot enable
  pharma qualification in a real estate company.

## Field-executive permission and handoff contract

`field_executive` is a dedicated organization role, created through the existing
admin team routes and counted by the existing subscription seat ledger. It uses
the responsive web CRM. Android authentication/call ingestion allowlists remain
`manager`/`telecaller`; no Android source, binary or sync-contract change is made.

The caller remains primary Lead.owner_id for coordination and existing recording
sync. FieldHandoff grants the current executive access to that lead's full client
notes/call history/recordings/requirements, with tasks limited to their own. Field
executives see their current assigned leads and self-created leads, own tasks,
attendance/time/leave and personal analytics. They can read company inventory and
manage their own accessible visits, but cannot read team payroll/audit/integrations,
create bookings, administer people or delete any recordings. Company admins can
use the existing audited 30-minute member-login flow for a field executive.

The handoff keeps its brief, meeting point, current visit, optional follow-up task,
status, actor, timestamps, request digest and version. A partial unique index
enforces one current handoff per organization/lead. All mutations lock the company
and recheck live account/session state. Creation requires current lead access,
client confirmation, real-estate setup, available inventory and an active same-org
executive; visit overlap checks are shared with ordinary site visits. Pending
handoffs require the assigned executive's acceptance. Caller access follows normal
lead ownership; unrelated callers/executives have no handoff or file access.

Visit outcome and next step commit atomically with notes/audit and the linked task.
Future visit completion, no-show-to-booking and undated follow-ups are rejected.
Updates require the current version, so concurrent accepts/outcomes create one
result/task. Original request retries remain idempotent after cancellation; changed
payloads conflict. Generic visit/task mutations redirect users to field work for
linked records. Cancellation clears the pending visit/task together. Rescheduling
a finished visit retains it and creates the next one. A matching ready handoff is
closed when its booking is confirmed. No automatic lead win/loss is inferred.

Reassignment updates visit/task responsibility and requires fresh acceptance.
The former executive immediately loses query/history/download access. A previous
closed handoff becomes non-current on a new handoff; it grants no lingering access.
Active work blocks employee deactivation/role changes/removal and lead archival or
closed outcomes until resolved. Generic merge refuses leads with handoff history
rather than violating assignment uniqueness or losing history. Revision 0008 is
additive; rollback refuses if any field work or field-executive account exists.

| Field role action | Scope |
| --- | --- |
| Read/edit lead, notes and buyer requirements | Current handoff or self-owned lead |
| Read call/recording history and files | Accessible client; authenticated private downloads |
| Delete recordings, including own | Never |
| Task ownership, time/leave, attendance | Own only |
| Visit outcome/follow-up | Current accepted handoff; version and transition checks |
| Accept assignment | Assigned executive only |
| Create/reassign handoff | Caller on own client creates; admin/manager reassigns |
| Booking/team/payroll/audit/billing administration | Denied |

## Live reminder inbox

`GET /api/notifications/inbox` is a read-only, permission-scoped union of overdue
lead callbacks, the current user's open tasks due within 24 hours, relevant field
handoffs and first-contact reminders. Callback eligibility excludes deleted,
DND, lost/converted and all closed stages, including inactive custom stages.
Future callbacks do not also create stale first-contact reminders. Current lead
and handoff access is re-evaluated on every request; tasks are never shared merely
because an administrator can read their client. Callback tasks use Planner, or
Field work when managed by a current handoff. Resolving work uses the existing
mutation routes; reading the inbox never acknowledges or hides an action.

The endpoint accepts `category=all|callbacks`, `page >= 1` and `page_size=1..50`
(default 12). Counts aggregate the complete scoped result before SQL pagination.
Stable priority/due/id ordering puts callbacks first; pages clamp after work is
resolved. Due timestamps are canonical UTC and the response supplies the workplace
timezone for display. The shell refetches every 30 seconds while active and on
focus/open/manual refresh. Errors remain explicit even when cached empty data
exists. The existing `GET /api/notifications` array and native sync contract are
unchanged; no schema migration or workflow rule is required.

## Design system

Bright off-white surfaces, charcoal text, emerald primary actions, muted botanical secondary accents, fine borders and restrained radius. Manrope headings and DM Sans body are self-hosted through pinned font packages. Desktop tables retain clear type and row context; mobile contains table scrolling inside the panel rather than overflowing the page. Native dialogs trap focus and support Escape; form controls have explicit labels and visible focus. Loading skeletons, zero, setup, error/retry and permission states are distinct. Reduced motion is supported. Screenshots and automated accessibility results are recorded separately from business tests.


### Final QA data and recovery contracts

Lead history takes `page` and `size` (1–100, default 50), returns stable chronological pages plus per-section totals in `pagination`, and attaches authorized recordings directly to each paged phone call. Lead interest search is a case-insensitive literal substring of actual interest entries; list, saved view and export use the same filter. Date filters reject timezone-free timestamps and reversed/empty ranges. Attendance/time/leave use stable pages of up to 100 instead of silent lifetime cutoffs. Manager audit permissions apply before pagination; oversized audit exports are rejected with a narrowing instruction.

Lead filtering uses a shared web component for Leads and Lost deals. Common
controls update the URL immediately; advanced controls use draft/apply/cancel.
Applied chips, count, saved views and exports reflect the same normalized URL
values. Filter changes reset pagination and bulk selection. Lost deals always
forces status `lost`, including when applying another saved view. Legacy boolean
contact-preference values normalize to strings without dropping `false`.
Calendar-day ranges become timezone-aware local-midnight `[start, next-day)`
boundaries, including daylight-saving transitions. Existing precise timestamp
ranges are retained until explicitly edited. Legacy date-only saved endpoints
normalize to local midnight while retaining their exclusive-end semantics. City
and state use case-insensitive trimmed full-name equality. Status, source and
follow-up queue IDs validate identically on list and export. Owner filter choices
include inactive members from the role-scoped team API; assignment controls still
use the active directory.

A provider batch above 10,000 records is rejected without advancing its cursor. External IDs longer than 120 characters are represented by a SHA-256 digest of the full ID. An unreadable stored credential isolates that provider in setup-required state and can be replaced or disconnected. PDF validation uses pypdf 6.21.1 to check document structure; unencrypted PDFs require 1–10,000 readable pages and encrypted documents retain their protected bytes. This does not imply content sanitization or transcription. [pypdf reader documentation](https://pypdf.readthedocs.io/en/stable/modules/PdfReader.html).

Database dependencies use FastAPI function scope throughout authentication and route handlers. Commit or rollback finishes before response headers are sent, so a commit failure produces a conflict response rather than a false success. Regression tests inspect durable rows at HTTP response start and inject a commit failure; private database details remain redacted.
