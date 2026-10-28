# Aven Realty mobile — 1.1.4

Version 1.1.4 retries a failed history request when returning to the same screen,
without starting collection or touching pending calls. Only a structured CRM
not_found response is described as a missing/reassigned lead. An HTML tunnel
404 gets a connection/retry message, and company suspension has its own message.
Returning from the file picker does not restart a successfully loaded history
or cancel the export. See `artifacts/android/history-recovery/`.

Version 1.1.3 cleans up private playback files left by a terminated app process on the next launch. Process-specific preview names keep a second reader from deleting an active preview. This cleanup does not touch the call outbox, pending audio uploads or paused collection.

Version 1.1.2 adds **View history** to lead rows. The full lead screen reads the
existing `/leads/{id}` and paginated `/leads/{id}/history` APIs, the same APIs used
by the web CRM. Calls, manual outcomes/remarks, notes, activity, tasks and files
come from the server, even on a fresh emulator with an empty local call database.
Telecaller/company restrictions stay on the server. No chat or WhatsApp feature
is added; saved notes and call remarks appear in their actual sections.

Recordings play inside the app with pause, replay and seeking. Binary downloads
use authenticated requests without putting session tokens in URLs. Private
temporary files are size bounded and checked against the supplied size/digest;
playback stops and its temporary copy is removed on close, backgrounding or
session change. Audio focus loss pauses playback. Files can be saved through an
explicit Android file-picker action. History has loading, error/retry, confirmed
empty and pagination states; losing lead access removes previously shown history.
These reads do not import old CRM calls into this phone's upload outbox.
All five sections stay visible; larger system text uses two rows of section
buttons. The recording dialog scrolls when filenames or system text are long.

Version 1.1.1 fixes assignment loading after sign-in. Home/Leads fetch the complete
assigned-contact directory independently of call collection, phone permissions or
recording setup. Leads has a Refresh leads action above the list, a loading state,
an honest connection error with retry, and a confirmed-empty state only after a
successful response. Cached assignments remain usable after a failed refresh;
partial pages or responses for another account/company cannot replace them.
Foreground refreshes use a one-minute cache and failed automatic attempts are
throttled for 30 seconds; manual refresh always retries. Search text survives an
asynchronous refresh. Call upload consent remains a separate action on Home.

The Android app is a real-estate calling companion. The owner's tested ZIP remains
the source of truth for call capture, recording matching and transfer behavior.
The native interface uses a green and warm-neutral theme, property branding,
readable text, labelled controls and four navigation destinations.

- **Home:** assigned-lead count, today's locally saved calls, honest call-update
  status, permission/recording setup, Send updates and quick access to inventory.
- **Leads:** the existing assigned-customer allowlist, literal name/phone search,
  do-not-call handling, dial actions and recent conversation details.
- **Calls:** latest 30 local calls, All calls/Missed/Pending audio filters,
  separate call-details and recording states, and the existing manual attachment.
- **More:** company/account details, property catalogue, pause/resume, permission
  and battery help, recording-folder settings, country code and sign-out.
- **Property catalogue:** live company inventory using the existing `/properties`
  APIs, search by project/area/reference, property-type and sale/rent filters,
  24-item pages, full property information, actual price, location and area.
  Bedroom fields apply to apartments/villas; plots do not display bathrooms.
  Inventory editing stays in the web CRM. No fabricated inventory or photos are
  shown in the app.

The catalogue has loading, empty, filtered-empty, unavailable and retry states.
Its requests and in-memory results are scoped to the signed-in account/company;
the screen closes if that session expires or changes. Catalogue failures do not
clear the durable call queue. At larger system font sizes, filters stack vertically.

## Build and installation

Version code 8 updates the existing version-code-7 app with the same application
ID `com.aven.calls` and original signing key. This retains Android app data.
Debug remains a separate package. No database schema or call-sync API was changed.

Release builds take the current HTTPS workspace through Gradle's `avenServerUrl`:

```sh
./gradlew :app:assembleRelease -PavenServerUrl=https://your-crm.example.com
```

Without a configured default, sign-in shows the workspace-address field. Existing
installations retain their saved workspace. Temporary ngrok addresses require
the owner's Mac, backend and tunnel to stay online; use Connection settings at
sign-in when your manager supplies another address. Private signing material
belongs to the owner and is excluded from shareable source ZIPs.

## Verification

The full 25 October audit and 1.1.3 results are recorded in
`artifacts/full-audit-20261025/`. It includes API/browser regressions, Android 15
instrumentation and lifecycle checks, real web/mobile history parity, and a
force-stop/cold-start check that preserves a pending call while removing the old
playback preview. All 14 core calling/auth/storage classes retain their hashes.


For 1.1.2, see `artifacts/android/crm-history-fix/verification.json`, including
normal/larger-text HTTP/Android integration checks and actual signed HTTPS
history/playback of an existing CRM lead. Earlier directories below record their
respective releases; they are not additional handset runs for this update.

For the 1.1.1 assignment-loading fix, see
`artifacts/android/lead-loading-fix/verification.json`: 8 Android 15 regression
tests, 32 JVM tests, lint/build checks, core-class fingerprint checks and a signed
in-place update showing Neha's 26 actual assignments while collection stayed off.
The following directory records the earlier 1.1.0 UI/lifecycle verification.

Current executed results, screenshots, initial failures/fixes and their limits are
in `artifacts/android/real-estate-ui/` in the full repository. The recording
matcher, sync engine, WorkManager scheduler/worker, service, local storage,
session/authentication and call receivers are checked against the pre-UI hashes.
The app still uploads recordings created by the built-in Phone app.
