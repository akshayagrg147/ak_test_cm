# ViaCRM: design and client presentation

## Direction

The requested redesign replaces the previous flat, sixteen-link feature sidebar and sage palette with a compact graphite work-area rail and a horizontal contextual navigation layer. The owner selected **ViaCRM** on 25 October 2026. Its connected V symbol uses cobalt `#264EDB`, mint `#91ECD3` and deep ink `#162B49`. A rounded V with a highlighted terminal suggests a clear route from enquiry to the next action. The tagline is **Every lead. A way forward.** Public pages, login and authenticated screens share this identity, neutral surfaces and restrained borders. No competitor assets or source code were introduced.

The logo has full-color, dark-background and single-color SVG masters, with
outlined Manrope lettering that requires no installed font. Transparent PNG
exports, an icon, favicon and a presentation sheet are included. Sources are in
`web/public/brand/`; downloads and usage notes are in `artifacts/viacrm-brand/`.
`cd web && node scripts/export-brand.mjs` recreates the PNG exports using the
existing Playwright Chromium installation. Company branding remains independent;
the Android name, package, source, signing identity and APK are unchanged.

The dashboard combines a daily action hub, actual API metrics, follow-up attention, pipeline/source views and recent opportunities. These figures remain calculated from persisted records. The public preview is explicitly illustrative.

## Role-focused dashboards — 25 October 2026

The company overview uses a compact period selector (Today, Last 7 days, Last 30
days), an optional team-member selector and a visible refresh action. Admins and
managers see new enquiries, calls, converted leads, priority follow-ups, a trend
chart, enquiry sources, stage distribution and team calling activity. Telecallers
see their assigned clients, own calls/talk time, call outcomes, private tasks and
direct links to clients/calls/visits. The super-admin overview adds company
subscription health and team-size charts while keeping company management intact.

Numbers come from permission-filtered persisted data. The additive read-only
`/api/dashboard` groups calls and enquiries using workplace dates. Linked call
remarks do not add another call; manual calls remain distinguishable from device
results. Current priority work excludes closed, archived and do-not-contact clients.
Chart periods do not filter current tasks/visits or live portfolio figures; this
distinction is visible on the page. No growth estimate or sample chart is inserted
when a workspace has no activity.

Charts share consistent color legends, an exact-value HTML table, keyboard
controls and empty/loading/retry states. Counts remain available as text. The
layout stacks on phones, retains the established readable text scale, uses ViaCRM
colors and respects reduced motion. Android and its call-sync contract are unchanged.

## Navigation

| Work area | Pages |
| --- | --- |
| Home | Overview, Planner, Conversations |
| Sales | Leads, Closed opportunities |
| People | Attendance, Requests & approvals, Team directory, Payroll estimates |
| Insights | Reports |
| Studio | Workflows, Connections, Audit log, Data snapshots, Workspace profile, Account & security |

Pages retain their established URLs and server permissions. Unavailable pages are filtered by role. Deep links select the right work area automatically. The platform owner retains a separate organization-management workspace and explicit support banner.

On small screens the work-area rail opens from the menu. It supports keyboard navigation, Escape, backdrop dismissal, focus restoration, route dismissal and a clean transition to desktop. Background content becomes inert while the rail is open. Section navigation scrolls within its container; tables retain contained horizontal scrolling. Long client brands truncate in the header with their full text available in the title. Numeric cards fit values to the available width, preserving the full value in their title.

## Comfortable reading — 18 October 2026

After feedback that the first larger-text pass felt oversized, the default reading size is **16px**, with **14px minimum secondary text** at the standard browser font setting. Form labels, entered values, primary buttons and customer names use 16px. CRM page headings use 28–30px, and section headings use 20px. DM Sans remains the body font, with Manrope headings; reduced negative letter spacing and a 1.55 body line height keep the text clear. Secondary text retains its darker slate color.

Typography uses shared `rem` tokens so browser font preferences can enlarge it further. Primary buttons and standard inputs are at least 44px tall; checkboxes are 20px, and inline actions and task completion controls are 44px. The navigation rail is 104px wide and dialogs are up to 700px wide. Mobile cards and filters stack to keep their text readable. The header wraps when larger text needs another row. Tables and tab lists retain their contained scrolling.

The readability browser suite measures rendered text sizes across all sixteen admin pages at 360, 768 and 1440px, checks login at 320–1440px, verifies the lead editor, and exercises navigation and form entry with a doubled browser default font. See ACCEPTANCE.md for executed results and screenshots. These checks do not claim a usability study with older adults.

## Presentation workspace

Run `bash scripts/dev.sh`, then open http://localhost:5173/login and sign in with `+919900000007` / `LocalCRM!2026`. This opens **Meridian Studio**, a separate development organization with 24 fictional customer records, four users, conversation outcomes, notes and six tasks. All data is persisted through the same database/model layer as the application. Existing workspaces are preserved, and repeated seeding changes nothing. The seed refuses non-development environments or conflicting account phones.

Suggested walkthrough: Overview → Sales/Leads → a customer detail → Home/Planner → Insights/Reports → People → Studio. Configure a real contact email/phone before using public contact actions. Rename/rebrand through Studio/Workspace profile for each client.

The demo companies, phone numbers, orders and performance are fictional development fixtures. They are not testimonials, actual customer results or live provider delivery. Do not call the fixture phone numbers.

## Verification

See ACCEPTANCE.md for executed checks. Browser assertions exercise every permitted navigation destination for admin, manager and caller, active state on a reloaded lead deep link, mobile focus/dismissal/resize, long client branding from 320 to 1440px, real business workflows and automated accessibility scans. Screenshot capture visits all sixteen CRM pages at 1440 and 360px using the separate presentation account.

## Interest-entry correction

Products/services of interest is a visible, optional field for every business type. The lead score panel offers a focused Add/Edit interests action, and its description explains that the team records customer-confirmed interests. The field uses one item per line instead of category keys. Saved interests add 15 points once; removing them removes those points. The optional pharma mode still controls primary category and industry-specific qualification fields.

## Saved filters

The lead list labels named filter combinations **Saved filters**. The **Save filters** form explains their purpose and asks for a readable **Filter name**. Removing a saved filter removes only the shortcut. Browser tests create their saved entries in a temporary organization, remove those entries, and archive the test organization afterward. Test-generated timestamp names are not demo content.
