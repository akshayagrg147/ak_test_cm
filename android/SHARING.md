# Sharing the Android source

This folder is the Aven Realty Android app, version 1.1.4. It is source code for a developer; someone who only wants to use the app should receive the signed APK instead.

The owner selected their tested ZIP as the Android logic baseline on 25 October
2026. Read `LOGIC_BASELINE.md` before UI changes; its recording matching and
background-sync rules take precedence over older QA descriptions.

## Open and build

1. Extract the source ZIP and open its `android` folder in Android Studio.
2. Use JDK 17 and install Android SDK 36. Android Studio creates the machine-specific `local.properties`; it is deliberately excluded from the ZIP.
3. From the `android` folder run:

```sh
./gradlew :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
```

The debug APK is produced at `app/build/outputs/apk/debug/app-debug.apk`. On Windows use `gradlew.bat`. The checked-in Gradle wrapper and dependency lockfile are included. The first build needs Internet access to download the SDK and dependencies.

## Connect to the CRM

This is a native companion app and needs the running Aven CRM backend, an authorized telecaller/manager account, and assigned customers. The backend and web CRM are in the separate full-project source ZIP.

The debug build defaults to `http://10.0.2.2:8010` for the Android emulator. Change the address in **Connection settings** on the sign-in screen for another server. Use an HTTPS address for release builds. The release source has no hardcoded server; supply `avenServerUrl` when building or enter the workspace on first sign-in. The delivered APK is configured with the owner's current HTTPS tunnel, which requires their local server and tunnel to remain online.

To change the release default when building:

```sh
./gradlew :app:assembleRelease -PavenServerUrl=https://your-crm.example.com
```

Without signing environment variables this produces an unsigned release artifact. See `README.md` for signing configuration. Keep the existing app's private signing key with its owner: it is not included here. Updates to the already-distributed release require that same key. A developer can build and install the separate debug app without receiving it.

## Scope and verification

The app reads eligible assigned-customer calls and uploads recordings created by the phone's built-in Phone app after the user grants access to their recording folder. It does not create cellular call recordings. Exact OPPO model, native recording availability, recording-file access and installation permissions still need testing on the physical handset.

See `QA_MATRIX.md` for previous executed checks and their limits. The included `tools/` QA automation, historical artifact links and repository-wide acceptance record refer to the full CRM repository; those scripts need its backend, private local fixtures and Python environment. Normal Gradle builds and JVM unit tests do not require the full repository layout.

## What is excluded

The source ZIP excludes account sessions, local databases, environment files, SDK paths, build caches, compiled APKs and private signing material. `SOURCE_MANIFEST.json` at the archive root records each included file's SHA-256 hash.
