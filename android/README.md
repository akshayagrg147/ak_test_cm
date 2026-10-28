# Aven Realty for Android

## Current real-estate interface — 1.1.4

See [REAL_ESTATE_UI.md](REAL_ESTATE_UI.md) for the Home, Leads, Calls and More
screens and the live property catalogue. The deliverable is
`artifacts/android/aven-realty-1.1.4.apk`. Use **View history** on a lead to see
permission-filtered CRM Calls, Notes, Activity, Tasks and Files, including calls
uploaded by another phone using the same account. Recordings play inside the app;
Files also offers Save file to a location you choose. Version 1.1.4 retries a failed history screen when returning to the app and distinguishes a structured CRM access denial from a tunnel/proxy response. Version 1.1.3 removes private playback previews left by an earlier crashed process on the next app launch; it preserves queued uploads and the paused setting. The Calls navigation still
shows this phone's local upload queue. Assigned leads load immediately after
sign-in even while call collection is paused or not configured. Use Refresh leads
on Leads to check for assignment changes. Evidence for this fix is under
`artifacts/android/lead-loading-fix/`. The owner's tested recording/sync logic
is preserved. Builds and actual verification are recorded separately under
`artifacts/android/real-estate-ui/`; older APKs and evidence below are historical.

The Android logic baseline is the owner's tested ZIP selected on 25 October 2026.
See [LOGIC_BASELINE.md](LOGIC_BASELINE.md) before changing the UI or recording/sync
behavior. Older APK and QA records below describe their respective delivery dates.
The 1.1.0 release uses the owner's original signing key and application ID, with a
higher version code for an in-place update. Keep the private signing key separate.

Native Android companion for the Aven web CRM. Reads the system call log, queues eligible assigned-customer calls privately, and uploads recordings produced by the phone's built-in recorder. It opens the existing Phone app for outgoing calls. WhatsApp is excluded.

The app does **not** create cellular recordings. A normal third-party APK cannot use Android's privileged `VOICE_CALL` audio source. A foreground service and WorkManager do not change that restriction. See [Android audio-source documentation](https://developer.android.com/reference/android/media/MediaRecorder.AudioSource#VOICE_CALL).

## Phone recommendation and installation

### Historical phone interface — version 1.0.2

Previous delivery: `artifacts/android/aven-calls-1.0.2-simple-ui.apk`. That signed app updates
1.0.0/1.0.1 without removing the saved account or pending calls. The current ngrok
workspace address remains prefilled; **Connection settings** on sign-in lets a manager
change it without cluttering the normal login form.

- **Home:** follow the two setup steps, then see waiting uploads and recent calls.
  **Send updates** checks now. Each call shows separate **Call details** and **Recording** results.
- **Customers:** search assigned customers by name or number and open the Phone app to call them.
- **Settings:** choose/change the recording folder, pause uploads, review phone permissions,
  change the default country code, get setup help or sign out.

For first use, sign in, confirm authorization, tap **Allow & continue**, then
**Choose recording folder**. **Set up recordings later** enables a call-details-only
workflow and keeps the missing audio setup visible. The country code defaults to 91;
change it under Settings if needed. Recording help explains the phone's built-in
recorder and folder selection. A connected folder does not prove the Phone app is
recording calls; the actual handset still needs a real recording/playback test.

### Shareable ngrok test build — 18 October 2026

`artifacts/android/aven-calls-1.0.1-ngrok-test.apk` is a signed, non-debuggable release
with `https://1dd2-111-223-3-131.ngrok-free.app` prefilled for a fresh installation.
The server field remains editable. Existing installations retain their saved server.
It uses the same signing key and app ID as version 1.0.0, with version code 2 for updates.
No account credentials are embedded. A telecaller/manager test account and assigned
customer are required. Keep this Mac, the local API on port 8010, and ngrok running
throughout the test. If the tunnel address changes, enter the new HTTPS origin at sign-in.
Native recording availability, file format and folder access still need physical-phone testing.
For a different release default, build with `-PavenServerUrl=https://your-crm.example.com`.
The debug build continues to default to the local emulator API.

Start with **one India-region Samsung Galaxy running Samsung Phone**, purchased only after the seller demonstrates **Phone → Settings → Record calls → Auto record calls** on that exact unit. Samsung documents automatic recording, but availability varies by region, model and software. Confirm the saved audio can be selected through Android's folder picker. Prefer a company-managed device for telecalling. This is a pilot recommendation, not a certification of an untested model. [Samsung's recording guide](https://www.samsung.com/in/support/mobile-devices/how-to-record-play-back-and-share-voice-recordings-on-your-samsung-galaxy-phone/).

1. Install the signed `aven-calls-1.0.2-simple-ui.apk` on Android 8 or later. The current test workspace address is prefilled. To change it, expand **Connection settings** and enter the **HTTPS origin** of your CRM, without `/api` or another path. A server running at `localhost` on the Mac is not an Internet service.
2. Sign in as a telecaller or manager. The same account must own the CRM leads whose calls should sync. Organization administrators manage leads in the web CRM; they do not enable this device collector with an administrator login.
3. On Home, confirm authorization and tap **Allow & continue**. Allow **Phone** and **Call logs**. Notifications are recommended for upload progress. The country code is 91 by default and can be changed under Settings.
4. In Samsung Phone, enable native automatic recording. In Aven choose **Choose recording folder**, navigate to the actual recording directory, and grant access. The app reads that folder directly; it does not crawl the phone's storage. Connect the directory containing the recordings, not its parent.
5. Make one incoming and one outgoing test call. Check metadata and playback in the web CRM's call history. Validate both speakers, speakerphone, Bluetooth and SIM variants before fleet use.

`READ_CALL_LOG` is a hard-restricted Android permission. An installer or device-management policy may need to allowlist it. The APK cannot grant itself restricted permissions. Installation via an approved enterprise method must be validated on the target phone. [Android permission reference](https://developer.android.com/reference/android/Manifest.permission#READ_CALL_LOG).

The separate `aven-calls-1.0.0-local-test.apk` is a debuggable QA build with a different app ID. It also accepts private/local HTTP addresses for development. For a USB-connected **test phone**, use `adb -s YOUR_DEVICE reverse tcp:8010 tcp:8010`, then `http://127.0.0.1:8010`. The emulator uses `http://10.0.2.2:8010`. The release build requires HTTPS; production deployment was not requested or performed.

## What happens in difficult situations

| Situation | Behavior |
|---|---|
| Incoming, outgoing, missed, rejected or blocked work calls | Reads the system history after the call. Zero-duration outgoing calls remain unknown rather than being invented as answered. |
| Personal, private or invalid numbers | Never enter the upload queue unless the normalized number is a currently assigned CRM customer. No suffix-only phone matching. |
| Two assigned leads share a phone number | Server returns an ambiguous receipt; the manager must resolve the duplicate. |
| Internet/server unavailable | SQLite keeps calls; network-constrained WorkManager retries with backoff. Each server receipt acknowledges one call. |
| Process killed or phone restarted | Durable queue and encrypted session survive. WorkManager and the boot receiver restore reconciliation after unlock. |
| App force-stopped | Android blocks execution until the user opens the app. Reopening reconciles calls since enablement, capped at 30 days. |
| Battery saving, Doze or OEM sleeping apps | Android can delay work. Periodic reconciliation has a minimum 15-minute interval and no exact-time guarantee. Check Samsung Sleeping apps settings. |
| Manual Send updates | Starts a visible, bounded data-transfer foreground service. It stops after completion, interruption or a 120-second timeout. No boot-time or permanent recording service. |
| Call-log access removed | Visible permission failure; existing queue is retained. Regrant permission and open the app to reconcile. |
| Notifications denied | Background queue processing remains possible; notification visibility is controlled by Android. |
| Recording absent, still growing, inaccessible or too large | No fabricated audio. Empty/changing files wait, access failures request reselection, oversized files show an error. Default maximum is 64 MiB per recording. |
| Recording filename contains a supported date/time, with or without a phone number | Uses the owner's ZIP logic: select the answered CRM call with positive duration and the closest start within the timestamp and modified-time windows. Ties retain input order. The file must be stable across observations at least 3 seconds apart. |
| Missing or invalid recording timestamp | Use **Add recording** on the relevant recent call and confirm the customer/call explicitly. Contact-name files with a valid timestamp can match automatically. |
| Repeated upload after lost acknowledgement | Backend deduplicates the recording digest for that call. The same audio cannot silently attach to unrelated calls. |
| Lead reassigned or deleted | Refresh removes the local lead and its queued calls. Server also checks current assignment before metadata or audio mutations. |
| Pause | Stops collection and scheduled work; pending local calls remain. Re-enabling starts collection from that moment, retaining previously queued entries. |
| Sign out/account or server switch | Clears private queue, cached customers and recording grants. Already uploaded CRM data remains. Offline sign-out clears this phone; an unreachable server session expires or can be revoked in web administration. |

Only the newest 30 local work calls and first 100 matching customers are rendered at once.
Customer search queries the entire cached assignment list. Capture/sync uses the complete
paginated assignment list, up to 50,000 records. Server responses and batch sizes are bounded.
There is no call recording for WhatsApp/VoIP apps.

## Build

Java 17, Android SDK 36, AGP 8.13.2, Gradle wrapper 8.14.5, target SDK 36, minimum SDK 26. Libraries are pinned and Gradle dependency locks are checked in.

```sh
cd android
printf 'sdk.dir=%s\n' "$ANDROID_HOME" > local.properties
./gradlew :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
```

For a signed release, set `AVEN_SIGNING_STORE` to your PKCS12 signing store and `AVEN_SIGNING_PASSWORD` to its password. The alias is `aven-calls`, then run `./gradlew :app:lintRelease :app:assembleRelease`. Without those variables the release task produces an unsigned developer artifact. No signing secret is in the repository, ZIP or APK.

The signing material generated for this local delivery is private in `.local/android-signing/` at the repository root. **Back up that directory securely** before moving or cleaning the project. Future updates of this APK must use the same key. Do not put it in source control or send it with the APK.

## Verification

See [the executed QA matrix](QA_MATRIX.md) and the root [acceptance record](../docs/ACCEPTANCE.md). Instrumentation uses an isolated temporary CRM workspace and a separate QA APK. Its document provider generates synthetic WAV audio; it is never included in the delivered app.

```sh
# API + web services must already be running; owner credentials come from the environment.
QA_OWNER_PHONE=... QA_OWNER_PASSWORD=... ../.venv/bin/python tools/qa_fixture.py create
QA_OWNER_PHONE=... QA_OWNER_PASSWORD=... ../.venv/bin/python tools/qa_fixture.py otp
./gradlew :app:assembleDebug :app:assembleDebugAndroidTest
adb -s emulator-5580 install -r -g app/build/outputs/apk/debug/app-debug.apk
adb -s emulator-5580 install -r app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
../.venv/bin/python tools/run_device_tests.py
../.venv/bin/python tools/lifecycle_qa.py
QA_OWNER_PHONE=... QA_OWNER_PASSWORD=... ../.venv/bin/python tools/qa_fixture.py archive
```

The host QA scripts deliberately target only the dedicated `emulator-5580` (Android 15) or `emulator-5582` (Android 16, selected using `AVEN_QA_SERIAL`). They neither detect nor operate a physical phone. Credentials are written only under ignored `.local/` with private file permissions. Do not install the separate instrumentation APK on employee phones.
