# Real estate CRM and company subscriptions

The web CRM now supports real estate agencies and developers. Android source and
APK remain unchanged. Existing customers, files, calls and recordings stay in
their original company workspaces.

## Start from your dashboard

Open **Home → Overview**. Admins/managers see team activity and pipeline charts;
telecallers see their clients, own calls, talk time and next actions. Choose
**Today**, **Last 7 days** or **Last 30 days**. An admin can also choose a team
member. Use **Calls / Enquiries** to change the trend chart, or **View chart data**
to read exact counts. Chart dates follow the workplace timezone.

**Priority clients** links directly to a client needing follow-up or first contact.
Closed and do-not-contact clients are excluded. **Your next tasks** opens the
Planner or the relevant field-work client. Current tasks, visits and property
availability stay visible when you change the chart period. Activity refreshes
every 30 seconds; **Refresh** reloads the other dashboard sections too.

Super admin's **Companies** page shows subscription health and company team-size
charts above the directory. Trial/active status describes the saved subscription;
payment receipt still needs the super admin's normal verification.

In **Insights → Reports**, **Hourly call activity** shows the count for each
hour across the selected dates, in the workplace timezone. Counts appear above
the bars; a zero has no bar. Select an hour for its total or open **View hourly
data** for all 24 rows. On a narrow screen, scroll the chart sideways or use the
table. Phone calls use their start time, and standalone manual calls use their
saved time. Adding a result to a synced call does not count it twice.

## Super admin setup

Sign in with the platform owner account. The UI calls this **Super admin**; the
API role remains `owner`.

1. **Companies → Create company:** enter the business profile, brand, contact and
   address details, optional RERA/GST references, and first administrator's login.
   New companies get a five-seat trial and real estate pipeline/category defaults.
2. The company management panel opens after creation. Later, choose **Manage** on
   its company row. Upload, change or remove its PNG/JPEG/WebP logo; use **Edit
   profile** on the company row for its name, brand and business details. Logo
   removal keeps the profile and previous private attachment history. Company
   admins can also edit their profile/logo in **Studio → Workspace profile**.
3. **Company administrators & team → Add administrator** creates another admin
   login for that company. **Edit administrator** changes the name, login phone or
   optionally resets the password. Phone, password and active-status changes revoke
   that admin's existing sessions; name-only edits retain sessions. Authenticator
   settings remain intact. Deactivation/reactivation respects team seats, and one
   active administrator must remain. Other team roles are managed through the
   audited company support workspace. **Manage subscription** sets dates/plan/seats.
4. **Plans & payments:** create your own monthly/yearly prices in INR and active
   team seat limits. No paid prices are invented or published automatically.
   Inactive plans are hidden from checkout. Existing payment claims retain their
   original price/name/seat snapshots.
5. Open **Payment methods & instructions**. Enable **UPI / QR**, **Cash collection
   (COD)**, or both. UPI needs the receiving account/payee name and an actual QR
   image; the UPI ID is optional. Verify the QR yourself before sharing it. The
   software validates image content, not the encoded receiving account. Cash needs
   no QR or UPI account: enter instructions explaining how to arrange collection.
   Disable both methods to pause new submissions. Existing UPI settings remain
   enabled after upgrade; cash starts disabled until you enable it.

Suspension revokes company and support sessions immediately. Archiving retains
records and requires resolving pending payments first. Support remains a separate,
audited 30-minute session. Super admin does not silently join company workspaces.

## Company payment flow

In **Studio → Subscription**, a company admin selects a monthly/yearly plan and
chooses **Pay using QR** or **Pay cash (COD)**, according to the enabled methods.
For UPI, they pay through their own bank/UPI app, confirm the
payee and amount there, and submit the transaction reference/UTR. An optional
PNG/JPEG/WebP/PDF receipt can be up to 5 MB.

**COD means cash collected in person.** The company requests collection and
follows your instructions. Cash requests have no invented UTR or uploaded receipt;
they do not activate a subscription. Only one pending request is allowed per
company, across both methods.

Both methods remain **pending**. In **Payment verification**, filter by method and
open the request. For UPI, check the actual receiving bank/UPI account. For cash,
collect the full displayed amount first, then explicitly confirm cash received
before approval. The server requires this confirmation. You can reject either
method with a note without claiming cash receipt. Approval activates or extends
the subscription exactly once. Rejection permits a new submission. Duplicate UPI
references, conflicting retries and changed quoted prices are rejected. Receipts
are private and retained with payment history.

Renewals extend an active paid period; trial/expired periods start from approval.
Dates use the India calendar; end dates are inclusive. Active admins, managers
and telecallers all consume seats. Creating/reactivating a member beyond the limit,
or reducing seats below the active member count, is blocked.

Payments use static QR or cash collection with human verification. They do not contact a bank,
debit accounts automatically, issue tax invoices, or verify money from screenshots.
Subscription expiry is displayed; workspace suspension is an explicit super-admin
action. The existing Android authentication/call-sync contract is preserved.

## Real estate workflow

### Telecaller → field executive → booking

1. **Company admin → People → Team directory → Add team member:** select the
   **Field executive** role and create their login. Field executives use the
   responsive web CRM on a phone or computer. They consume a normal active team
   seat. The existing Android APK and recording logic are unchanged.
2. The telecaller opens an assigned client and chooses **Visit & field executive
   → Arrange visit & hand off**, or **Property → Field work → Arrange visit & hand
   off**. Select the client, an available property and active field executive.
   Enter the agreed date/time, duration, meeting point and discussion brief;
   confirm that the client agreed before saving. Include the budget, questions
   and preparation needed. The client-confirmed Property brief remains available.
3. The executive signs in and lands on **Your field work**. The card shows the
   caller/coordinator, property, meeting point, brief, visit and next action.
   Choose **Accept handoff**, then **Open client history** to review notes, calls,
   permitted recordings/files and property requirements. The telecaller keeps
   access and coordination; primary caller ownership and Android allowlists stay
   intact. Other executives do not gain access to the client.
4. Use **Record visit outcome**: **Client attended** or **Client did not attend**.
   If the client attended before the scheduled time, check **Visit happened before
   the scheduled time** and enter the **Actual visit date & time**. It must be in
   the past and before the agreed schedule; both times remain in the visit history.
   A no-show still cannot be recorded before the scheduled visit starts.
   Record feedback and choose the next
   step. **Follow up with client** requires a clear next action and future date;
   it creates a task for that executive. Update that task through **Field work**
   or **Planner → Update field follow-up**, so the task and handoff stay consistent.
   A no-show requires follow-up or closure, rather than booking readiness.
5. **Reschedule / arrange another visit** updates a pending visit, or retains the
   completed/no-show visit and creates the next one. It clears/cancels the previous
   linked follow-up. Team clashes are checked; adjacent slots are allowed. Use
   **Cancel field work** with a reason when the client cancels. It cancels the
   pending visit/task together and retains history. **Close field work** retains
   the client; it does not mark the lead lost or delete it.
6. When the client is ready, choose **Ready for manager's booking review**.
   Admins/managers receive an in-app notification and see the ready queue. **Create
   booking** preselects the client, property and executive; enter the commercial
   terms and reference. Marking the matching booking **booked** closes the ready
   handoff. Only admins/managers create or change bookings; this records a deal,
   not bank verification. A cancelled reservation leaves the handoff available
   for another follow-up or closure.

**Field work** filters by client name/phone, status and overdue visits/follow-ups.
Counts are scoped to the viewer. Closed current work remains readable to the
assigned executive. Admins/managers can **Change executive** with a reason; the
replacement must accept again and the previous executive loses client/recording
access. Active field work must be reassigned or resolved before deactivating,
changing the role of, or removing its executive. Password resets remain available.

Only one current active handoff exists per client. Duplicate retries acknowledge
the original request; a changed request cannot reuse its identifier. Concurrent
updates use a version check: refresh a changed handoff before saving again. The
caller can coordinate dates/cancellation; the executive or admin/manager records
field outcomes. Resolve active field work before closing a lead outcome or
archiving it. A do-not-contact setting blocks new visit/follow-up contact actions;
cancellation remains available. Leads with field-work history cannot be merged
through the generic merge action; review the separate records to preserve their
assignment and visit history. Recording deletion is blocked for field executives
as well as telecallers, including their own audio uploads.

### Inventory, buyers and bookings

1. **Property → Inventory:** choose property type and sale/rent first. Apartments
   and villas show bedrooms/bathrooms; plots hide both; commercial/other types
   show optional washrooms. Changing type clears room counts that no longer apply.
   The API also normalizes irrelevant counts on create/edit. Plot area and handover,
   sale asking price, and rental monthly rent/available-from labels adapt to the
   selection. **Project / owner details (optional)** contains building, owner and
   RERA references; existing values are expanded when editing. These references
   are optional for all types, and saved entries remain when the section is closed.
   Add location, area, amenities and description. Upload private property
   photos, floor plans and PDF brochures. Search/filter by project/reference,
   type, city, sale/rent, availability and maximum price.
2. **Sales → Leads → Property brief:** save customer-confirmed intent, budget,
   preferred city/localities, types, bedrooms, timeline and financing. Matches
   apply all saved criteria to available inventory; customer interests are not
   inferred. Existing notes, tasks, calls, files and interests remain available.
3. **Property → Site visits:** schedule or reschedule an agent/property and record
   completion, no-show or cancellation with feedback. Overlapping visits for the
   same agent are blocked; adjacent visits are allowed. Future visits cannot be
   marked completed/no-show. Telecallers see their current assigned buyers and
   own visits.
4. **Property → Bookings:** admins/managers reserve an available unit, record agreed
   value, token and commission, then move to booked/closed or cancel. A unit can
   have one live booking. Cancellation releases inventory; closing marks it sold
   or leased. Closed/cancelled records cannot reopen. These amounts are commercial
   records, not bank verification. Booking stage and manual lead outcome are
   separate records.

Inventory edits are blocked while reserved/sold/leased. Resolve scheduled visits
and active bookings before archiving properties/customers. Customer merge moves
visits/bookings and retains an additional property brief in a note.

Existing companies can add the real estate defaults using
`POST /api/real-estate/setup` with a company admin session. This is repeatable and
preserves customer history. It retires the unchanged Pharmaceutical, Ayurvedic,
Homeopathic, Nutraceutical and Generic seed categories. Custom categories and
user-renamed definitions are kept. Migration 0005 applies the same retirement to
companies that were already converted. Retired definitions remain stored for
historical records; downgrading the schema does not reactivate them. Newly created
real estate companies start with property categories only.

**Add a lead / Edit details → Property category** records the lead's main category:
Apartment, Villa, Plot, Office, Retail, Warehouse or Other, plus active company
custom categories. The summary and lead filter use that same saved category.
The Property brief separately records detailed requirements and can include multiple
property types. Healthcare qualification fields remain disabled in real estate
companies, including after a workspace-settings save.

### Finding leads without losing track of filters

In **Sales → Leads**, start with **Find a lead**, **Lead status**, **Lead source**
or **Assigned to**. Search accepts part of a name, phone number or city. Lead status
describes the call outcome; **Sales stage** describes progress through your team's
pipeline. Inactive employees remain available in owner filters for historical work.

Use **More filters** for follow-up timing, contact preference, location, category,
recorded interests, sales stage or the date the lead was added. These selections
are a draft until **Apply filters**; **Cancel** discards the draft. The action bar
stays visible while scrolling. **Reset more filters** clears only the advanced
choices and keeps the search/status/source/owner. Apply to confirm that reset.

Category choices include active definitions. An older saved filter or existing lead
can retain an inactive category with a **(previous category)** label; it is not
offered when choosing a category for a new lead or a fresh filter. Existing records
can still be edited or found without silently rewriting their previous category.

Every applied choice appears above the results. Click a choice to remove it, or
use **Clear all filters** to start again. Results must match every selected choice.
The count and CSV export use the same filters. A blank result offers a clear reset
action, while a service failure keeps selections and provides a retry.

City and state filters match the full saved name, ignoring letter case and leading
or trailing spaces. Property/project interest searches part of the text actually
recorded on the lead. **Contact allowed** excludes customers marked Do not disturb;
it does not infer consent from a call. The “not contacted in 48 hours” queue means
no first contact recorded and a lead created more than 48 hours ago.

**Lead added** offers Today, Last 7 days, This month and Choose dates. Calendar
dates use the browser's timezone and include the whole last selected day. One end
may be left blank. Exact date/time filters retain an exclusive end timestamp.
Saved filters retain their selected dates rather than moving forward each day.
Existing precise timestamps and older date-only saved filters remain usable.

**Lost deals** uses the same controls and adds lost reason and the team member who
marked the lead lost. Clearing filters or applying a saved view keeps this page
within lost deals. Telecallers continue to see only their assigned leads.

### Automatic callback alerts

The **bell in the top bar** shows a red count when a callback is overdue. Click
it, then **Overdue callbacks**, to see the client, assigned person, scheduled time
and how long the callback has been waiting. Click an alert to open the client.
Admins and managers see the clients they are permitted to manage; telecallers see
their own clients, and field executives see their current accessible clients.
Private tasks stay with their assigned employee. Closed, DND and archived clients
do not create callback alerts.

Opening the bell does not clear unfinished work. For a client callback, save the
call result or set a new future callback time. A synced phone call alone does not
clear it: record the result and next step in the CRM. Complete a separate callback
task in **Planner**; update a managed field follow-up through **Field work** on the
client profile. A client callback and a separately created callback task are two
outstanding actions and can each appear in the count.

The bell checks every 30 seconds while the CRM tab is active, when you reopen it,
and when you click **Refresh alerts**. Times use the company's workplace timezone.
**All alerts** also includes upcoming tasks, first-contact reminders and relevant
field handoffs. Pages let you reach every reminder. An unavailable-service message
has a retry action and does not claim that all work is done. These are in-CRM
alerts; this feature does not send notifications when the browser is closed.

No **Studio → Workflows** rule is required. Workflows remain optional for extra
actions such as automatically creating a task or assigning a manager.

### Salary from office and calling time

As company admin, open **People → Payroll estimates**, find the employee and choose
**Edit rate → Office + calling — separate rates**. Enter an office hourly rate,
a calling hourly rate greater than zero, and the daily work target. Save. Existing
employees retain the original Approved work hours method until you select this
new method; no existing rate is changed automatically.

The separate-rate calculation follows the requested **6 + 2** policy:

- Eight approved office hours containing two call hours become six non-call office
  hours at the office rate, plus two call hours at the calling rate.
- For example, ₹100/hour for office work and ₹150/hour for calling gives
  **6 × ₹100 + 2 × ₹150 = ₹900**.
- Calls outside approved office attendance also use the calling rate. They do not
  reduce unrelated office hours.

Employees record office attendance by checking in/out in the web CRM. Closed
attendance creates time for review under **Requests & approvals**. Only approved
office attendance contributes office pay. Open, pending and rejected attendance
remains unpaid. Manually submitted work hours do not create office-presence time
under the separate-rate method. The original Approved work hours method continues
to support the existing attendance/manual-work ledger and source-overlap rules.

Calling time comes from synced answered phone calls with positive durations;
missed, rejected and unknown results are excluded. Audio upload is not required.
Manual conversation durations are shown for reference and excluded from calling
pay. Overlapping call intervals, including duplicates from different installations,
count once. Payroll retains the employee's historical call time after a lead is
reassigned or archived. Android and its sync API contract remain unchanged.

**View breakdown** shows recorded/approved/pending office time, calls inside and
outside approved office time, both pay components and the daily time breakdown.
**Export estimate** includes the same month, rates, paid hours and pay components.
Monthly/day boundaries use the company's workplace timezone and actual elapsed
time, including daylight-saving changes. Each component rounds once to a paisa;
the total is their sum. Daily target and approved leave affect target tracking,
not paid hours.

Call placement uses the phone-reported start plus duration. The current phone
metadata does not provide a separate connected-at timestamp, so placement around
office boundaries is approximate. Check-in/out attendance is a recorded session,
not continuous location monitoring. Rates apply to every month; late syncing,
approvals and rate changes update these live estimates. Finalized payroll locks,
payments, tax/statutory deductions and commissions are not part of this estimate.

### Recording permissions

Telecallers can upload, play and download recordings on calls/leads they can
currently access. They cannot delete recordings, including their own phone-sync
uploads or audio added through Files. The Remove action is hidden and the server
rejects direct deletion requests. Audio is identified by its validated content,
so renaming a recording as a document does not bypass the rule. This restriction
also applies when an administrator uses **Log in as member** for a telecaller.
Return to the administrator account to remove a company recording. Permissions
for ordinary non-audio documents remain unchanged. This policy applies to the
CRM's stored attachments; the Android source/APK was not changed.

## Local access

### Log in as a team member

Company admins can open **People → Team**, then click an active telecaller or
manager's name or **Log in as member**. This opens that person's actual web
workspace, including their own lead access, calls, tasks, reports and permitted
create/edit actions. No member password is needed or exposed. Other admins and
inactive accounts cannot be selected. Managers and telecallers do not get this
administrator action. Super admins first enter the company's audited support
workspace.

The banner says **Signed in as [member]**, identifies the administrator, and shows
the 30-minute deadline. Use **Return to my account** to go back to Team with your
administrator permissions. Existing project/member work is not changed just by
opening the account. Changes you choose to make are stored for that member and
audited with your administrator identity. Password/authenticator changes require
the member's own sign-in and are disabled here.

Reload keeps the member context. Expiry returns to a still-valid administrator
session on refresh; lost administrator authority requires signing in again. Signing
out ends both this member-access session and its source administrator session.
The member's separately signed-in browser/Android sessions are not logged out by
entering or returning from this mode. Android source and APK remain unchanged.

### Development URLs and accounts

- CRM: http://localhost:5173
- Super admin: http://localhost:5173/app/platform
- Plans/QR: http://localhost:5173/app/platform/billing
- Payment review: http://localhost:5173/app/platform/payments
- Company subscription: http://localhost:5173/app/billing
- API docs: http://localhost:8010/api/docs

Existing development owner: `+919900000001`; company admin: `+919900000002`.
Both use the documented development password `LocalCRM!2026`. Provision separate
credentials and infrastructure for deployment. No deployment or real bank transfer
is performed by development/testing.

Isolated browser QA uses `talkocrm_browser_test`, API port 8011 and web port 5174.
Its receipt/QR fixtures are synthetic test images, not payment credentials.
