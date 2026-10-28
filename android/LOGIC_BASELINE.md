# Android logic baseline — 25 October 2026

The owner tested and explicitly selected `aven-calls-android.zip` as the source
of truth for Android logic. Its SHA-256 is
`cbd6945b58960f0ffd2d441056ad82dc1d9e0badbdf6726666d217cf233e05e9`.
The eight changed source, test and wrapper files were imported; IDE settings,
assistant configuration, machine paths, caches and compiled artifacts were excluded.

## Behavior to preserve during UI work

- Match recording filenames by their supported date/time, without requiring a
  phone number in the filename. Contact-name filenames with a supported timestamp
  are eligible.
- Consider answered calls with positive duration when the filename timestamp is
  within 30 seconds before the call start through 30 seconds after its end.
  File modification time must be from 30 seconds before start through 10 minutes
  after end. The call list is restricted to cached CRM customer calls.
- Choose the eligible call whose start is closest to the filename timestamp.
  Equal distances retain the input order. This is a time-based heuristic, not
  independent proof of the recorded speaker's identity.
- Keep invalid dates, missing timestamps, timezone ambiguity, unsupported audio
  formats and calls outside the time windows ineligible for automatic matching.
- Recheck matched recording files that are still empty, in addition to growing
  files. Keep stable-file observations and manual attachment available.
- Expedite network-connected uploads with WorkManager and fall back to ordinary
  scheduled work when expedited quota is unavailable. Preserve foreground
  notification support, durable queue, retries, pause/resume and boot recovery.

The old requirement for a unique full-phone-number match is superseded by this
explicit user instruction. Backend call ownership, current assignments, upload
authorization and digest deduplication are unchanged.

## Integration compatibility fixes

The ZIP used Java charset overloads introduced in Android API 33 while the app
supports API 26. UTF-8 decoding and URL encoding use equivalent API-26-compatible
calls. WorkManager's `SystemForegroundService` is explicitly declared with the
`dataSync` type required by the new foreground information. These changes preserve
the imported matching and scheduling behavior. The Gradle wrapper remains at
the ZIP's version 8.14.5 with its checksum.

## Verification

`RecordingMatcherTest` specifies the intended new rules, including filenames
without a phone number, nearest-call and tied selection, exact timestamp and
modified-time boundaries, ineligible calls and phone timezones. Android
instrumentation exercises the foreground information and a real SAF provider
transitioning from an empty contact-name recording to downloadable CRM audio.

Executed results and limitations are recorded in
`artifacts/android/zip-logic-priority/verification.json` in the full repository.
The owner's physical-phone testing is separate from checks executed here.
The app uploads native Phone-app recordings; it does not create cellular audio.
