package com.aven.calls;

import static org.junit.Assert.*;

import android.Manifest;
import android.content.*;
import android.net.Uri;
import android.os.Bundle;
import android.provider.CallLog;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.util.*;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class DeviceIntegrationTest {
  private AvenApplication app;
  private Bundle args;

  @Before
  public void setup() throws Exception {
    app =
        (AvenApplication)
            InstrumentationRegistry.getInstrumentation().getTargetContext().getApplicationContext();
    args = InstrumentationRegistry.getArguments();
    app.store.meta("enabled", "false");
    SyncScheduler.cancel(app);
    SyncEngine.LOCK.lock();
    app.resetLocalData();
    app.session.clear();
    InstrumentationRegistry.getInstrumentation()
        .getUiAutomation()
        .adoptShellPermissionIdentity(
            Manifest.permission.WRITE_CALL_LOG,
            Manifest.permission.READ_CALL_LOG,
            "android.permission.MANAGE_DOCUMENTS");
    cleanNativeFixture();
  }

  private void cleanNativeFixture() {
    if (args.getString("customer_phone") != null)
      app.getContentResolver()
          .delete(
              CallLog.Calls.CONTENT_URI,
              CallLog.Calls.NUMBER + " IN (?,?)",
              new String[] {args.getString("customer_phone"), "+919810099999"});
  }

  @After
  public void teardown() {
    app.store.meta("enabled", "false");
    SyncScheduler.cancel(app);
    app.api.cancelActive();
    cleanNativeFixture();
    InstrumentationRegistry.getInstrumentation().getUiAutomation().dropShellPermissionIdentity();
    SyncEngine.LOCK.unlock();
  }

  @Test
  public void expeditedUploadHasForegroundNotificationAndServiceType() {
    SyncWorker worker =
        androidx.work.testing.TestListenableWorkerBuilder.from(app, SyncWorker.class).build();
    var info = worker.getForegroundInfo();
    assertEquals("aven-sync", info.getNotification().getChannelId());
    assertNotNull(app.getSystemService(android.app.NotificationManager.class)
        .getNotificationChannel("aven-sync"));
    if (android.os.Build.VERSION.SDK_INT >= 29)
      assertEquals(android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC,
          info.getForegroundServiceType());
  }

  @Test
  public void encryptedCredentialsAndDurableOutbox() throws Exception {
    app.session.putAll(
        new JSONObject()
            .put("refresh", "private-refresh-value")
            .put("user_id", "test-user")
            .put("access", "private-token"));
    String stored =
        app.getSharedPreferences("secure_session", Context.MODE_PRIVATE).getString("data", "");
    assertFalse(stored.contains("private-refresh-value"));
    assertFalse(stored.contains("private-token"));
    SecureSession restored = new SecureSession(app);
    assertTrue(restored.authenticated());
    assertEquals("private-token", restored.get("access"));
    restored.putAll(new JSONObject().put("access", "rotated").put("refresh", "rotated-cookie"));
    SecureSession rotated = new SecureSession(app);
    assertEquals("rotated", rotated.get("access"));
    assertEquals("rotated-cookie", rotated.get("refresh"));
    long now = System.currentTimeMillis();
    app.store.capture("one", "+919810001234", "Customer", now, 0, "outgoing", "unknown");
    app.store.capture("one", "+919810001234", "Customer", now, 25, "outgoing", "answered");
    app.store.update("one", "state", "synced");
    app.store.capture("one", "+919810001234", "Customer", now, 0, "outgoing", "unknown");
    try (CallStore reopened = new CallStore(app)) {
      var rows = reopened.query("SELECT * FROM calls");
      assertEquals(1, rows.size());
      assertEquals("25", rows.get(0).get("duration"));
      assertEquals("answered", rows.get(0).get("result"));
      assertEquals("waiting", rows.get(0).get("recording_state"));
      assertEquals("synced", rows.get(0).get("state"));
    }
    assertFalse(app.store.stable("uri", 100, now, now));
    assertFalse(app.store.stable("uri", 100, now, now + 2999));
    assertTrue(app.store.stable("uri", 100, now, now + 3000));
    assertFalse(app.store.stable("uri", 101, now + 1, now + 4000));
    app.store.contacts(new JSONArray());
    assertTrue(app.store.query("SELECT * FROM calls").isEmpty());
    app.store.contacts(
        new JSONArray()
            .put(
                new JSONObject()
                    .put("id", "lead-a")
                    .put("name", "Original")
                    .put("phone", "+919810001234")
                    .put("dnd", false)));
    app.store.capture("revoked", "+919810001234", "Original", now, 20, "incoming", "answered");
    app.store.update(
        "revoked", "state", "synced", "lead_id", "lead-a", "recording_state", "queued");
    app.store.contacts(
        new JSONArray()
            .put(
                new JSONObject()
                    .put("id", "lead-b")
                    .put("name", "Replacement")
                    .put("phone", "+919810001234")
                    .put("dnd", false)));
    assertTrue(
        "A shared number must not retain a revoked lead's cached call",
        app.store.query("SELECT * FROM calls").isEmpty());
    app.store.capture(
        "ambiguous", "+919810001234", "Needs lead review", now, 20, "incoming", "answered");
    app.store.update("ambiguous", "state", "ambiguous", "recording_state", "queued");
    app.store.capture(
        "rejected", "+919810001234", "Rejected metadata", now, 20, "incoming", "answered");
    app.store.update("rejected", "state", "error", "recording_state", "queued");
    assertEquals(
        "Rows needing review must not keep scheduling upload jobs", 0, app.store.pendingCount());
    app.store.capture(
        "metadata", "+919810001234", "Pending metadata", now, 20, "incoming", "answered");
    app.store.capture("audio", "+919810001234", "Pending audio", now, 20, "incoming", "answered");
    app.store.update("audio", "state", "synced", "recording_state", "queued");
    assertEquals(2, app.store.pendingCount());
    long old = now - SyncPolicy.MAX_AGE_MS - 1000;
    app.store.capture(
        "old-audio", "+919810001234", "Offline recording", old, 20, "incoming", "answered");
    app.store.update("old-audio", "state", "synced", "recording_state", "queued");
    app.store.capture("old-saved", "+919810001234", "Completed", old, 20, "incoming", "answered");
    app.store.update("old-saved", "state", "synced", "recording_state", "uploaded");
    app.store.prune(now - SyncPolicy.MAX_AGE_MS);
    assertEquals(
        "Retention must preserve an acknowledged call's pending audio",
        1,
        app.store.query("SELECT id FROM calls WHERE id='old-audio'").size());
    assertTrue(app.store.query("SELECT id FROM calls WHERE id='old-saved'").isEmpty());
    app.session.clear();
    assertFalse(new SecureSession(app).authenticated());
  }

  private void login(String phone) throws Exception {
    app.api.login(
        args.getString("server", "http://10.0.2.2:8010"),
        phone,
        args.getString("password"),
        "",
        "");
  }

  @Test
  public void cancelledReadDoesNotReconnectAfterPauseOrServiceTimeout() throws Exception {
    try (java.net.ServerSocket server = new java.net.ServerSocket(0)) {
      var first = new java.util.concurrent.CountDownLatch(1);
      var release = new java.util.concurrent.CountDownLatch(1);
      var connections = new java.util.concurrent.atomic.AtomicInteger();
      Thread listener =
          new Thread(
              () -> {
                try (java.net.Socket socket = server.accept()) {
                  connections.incrementAndGet();
                  first.countDown();
                  release.await(5, java.util.concurrent.TimeUnit.SECONDS);
                  server.setSoTimeout(1000);
                  try (java.net.Socket extra = server.accept()) {
                    connections.incrementAndGet();
                  } catch (java.net.SocketTimeoutException expected) {
                  }
                } catch (Exception error) {
                  if (!server.isClosed()) throw new RuntimeException(error);
                }
              });
      listener.setDaemon(true);
      listener.start();
      app.session.putAll(
          new JSONObject()
              .put("server", "http://127.0.0.1:" + server.getLocalPort())
              .put("user_id", "test-user")
              .put("access", "test-token")
              .put("refresh", "test-cookie"));
      var executor = java.util.concurrent.Executors.newSingleThreadExecutor();
      var request = executor.submit(() -> app.api.json("GET", "/auth/me", null));
      try {
        assertTrue(first.await(5, java.util.concurrent.TimeUnit.SECONDS));
        app.api.cancelActive();
        release.countDown();
        try {
          request.get(3, java.util.concurrent.TimeUnit.SECONDS);
          fail("Cancelled read succeeded");
        } catch (java.util.concurrent.ExecutionException expected) {
          assertTrue(expected.getCause() instanceof java.io.IOException);
        }
        listener.join(2000);
        assertEquals(
            "Intentional cancellation must not create another HTTP request", 1, connections.get());
      } finally {
        release.countDown();
        app.api.cancelActive();
        request.cancel(true);
        executor.shutdownNow();
      }
    }
  }

  @Test
  public void revokedRefreshStopsWorkerAndPreservesQueuedCalls() throws Exception {
    login(args.getString("phone"));
    app.store.meta("enabled", "true");
    app.store.capture(
        "queued-before-expiry",
        args.getString("customer_phone"),
        "QA customer",
        System.currentTimeMillis(),
        15,
        "outgoing",
        "answered");
    app.api.logout();
    app.session.put("access", "expired-token");
    SyncWorker worker =
        androidx.work.testing.TestListenableWorkerBuilder.from(app, SyncWorker.class).build();
    assertEquals(
        androidx.work.ListenableWorker.Result.failure().getClass(), worker.doWork().getClass());
    assertFalse(app.session.authenticated());
    assertEquals(1, app.store.query("SELECT id FROM calls WHERE state='pending'").size());
  }

  private long nativeCall(String number, long start, int type, int duration) {
    ContentValues value = new ContentValues();
    value.put(CallLog.Calls.NUMBER, number);
    value.put(CallLog.Calls.DATE, start);
    value.put(CallLog.Calls.TYPE, type);
    value.put(CallLog.Calls.DURATION, duration);
    value.put(CallLog.Calls.NEW, 0);
    return ContentUris.parseId(app.getContentResolver().insert(CallLog.Calls.CONTENT_URI, value));
  }

  @Test
  public void ambiguousRecordingWaitsForLeadReviewWithoutSchedulingAnotherUpload()
      throws Exception {
    login(args.getString("phone"));
    app.store.meta("enabled", "true");
    long start = System.currentTimeMillis() - 5000;
    app.store.meta("enabled_since", String.valueOf(start - 1000));
    JSONObject duplicate =
        app.api.json(
            "POST",
            "/leads",
            new JSONObject()
                .put("name", "QADuplicate")
                .put("phone", args.getString("customer_phone"))
                .put("allow_duplicate", true));
    long row = nativeCall(args.getString("customer_phone"), start, CallLog.Calls.INCOMING_TYPE, 2);
    String key = SyncPolicy.callKey(row, start);
    try {
      app.store.capture(
          key, args.getString("customer_phone"), "QA customer", start, 2, "incoming", "answered");
      app.store.update(
          key,
          "recording_state",
          "queued",
          "recording_uri",
          "content://unavailable-qa-recording/document/test");
      SyncEngine.sync(app);
      var call = app.store.query("SELECT * FROM calls WHERE id=?", key).get(0);
      assertEquals("ambiguous", call.get("state"));
      assertEquals(
          "The unresolved file must not be opened or uploaded",
          "queued",
          call.get("recording_state"));
      assertEquals(0, app.store.pendingCount());
      assertEquals(1, app.store.reviewCount());
      assertTrue(app.store.meta("status").contains("need review"));
      var jobs =
          androidx.work.WorkManager.getInstance(app).getWorkInfosForUniqueWork("aven-upload").get();
      assertTrue(
          "Review rows must not enqueue a follow-up transfer",
          jobs.stream().allMatch(job -> job.getState().isFinished()));
    } finally {
      // QA-only administrator cleanup; the production APK never receives this credential.
      okhttp3.Request request =
          new okhttp3.Request.Builder()
              .url(
                  args.getString("server")
                      + "/api/leads/"
                      + duplicate.getString("id")
                      + "?confirmation=QADuplicate")
              .header("Authorization", "Bearer " + args.getString("admin_token"))
              .header("X-Requested-With", "TalkoCRM")
              .delete()
              .build();
      try (okhttp3.Response response = new okhttp3.OkHttpClient().newCall(request).execute()) {
        assertTrue("Isolated duplicate lead cleanup failed", response.isSuccessful());
      }
      app.getContentResolver()
          .delete(
              CallLog.Calls.CONTENT_URI,
              CallLog.Calls._ID + "=?",
              new String[] {String.valueOf(row)});
    }
  }

  @Test
  public void actualApiNativeCallLogSafAudioRetryAndAccountIsolation() throws Exception {
    assertNotNull(
        "Pass the isolated QA fixture, never a real caller account", args.getString("phone"));
    try {
      app.api.login(args.getString("server"), args.getString("phone"), "wrong-password", "", "");
      fail("Bad password accepted");
    } catch (Api.Failure expected) {
      assertEquals(401, expected.status);
    }
    try {
      login(args.getString("admin_phone"));
      fail("Admin may not enable device sync");
    } catch (Api.Failure expected) {
      assertEquals(403, expected.status);
    }
    login(args.getString("phone"));
    app.store.meta("enabled", "true");
    long start = System.currentTimeMillis() - 120_000;
    app.store.meta("enabled_since", String.valueOf(start - 60_000));
    app.store.meta("calling_code", "91");
    SyncEngine.refreshContacts(app);
    assertEquals(1, app.store.query("SELECT * FROM contacts").size());
    long row = nativeCall(args.getString("customer_phone"), start, CallLog.Calls.INCOMING_TYPE, 20);
    long missed =
        nativeCall(args.getString("customer_phone"), start + 30_000, CallLog.Calls.MISSED_TYPE, 0);
    long personal = nativeCall("+919810099999", start, CallLog.Calls.OUTGOING_TYPE, 30);
    try {
      SyncEngine.capture(app);
      assertEquals(2, app.store.query("SELECT * FROM calls").size());
      assertEquals(
          "unavailable",
          app.store
              .query("SELECT recording_state FROM calls WHERE result='missed'")
              .get(0)
              .get("recording_state"));
      String id = SyncPolicy.callKey(row, start);
      var answered = app.store.query("SELECT * FROM calls WHERE id=?", id).get(0);
      assertEquals("pending", answered.get("state"));
      // Unreachable local endpoint must leave the committed queue intact.
      app.session.put("server", "http://127.0.0.1:1");
      try {
        SyncEngine.sync(app);
        fail("Unavailable server accepted");
      } catch (java.io.IOException expected) {
      }
      assertEquals(2, app.store.query("SELECT * FROM calls WHERE state='pending'").size());
      app.session.put("server", args.getString("server"));
      // An expired access token rotates the real refresh cookie and resumes the same account.
      String previous = app.session.get("refresh");
      app.session.put("access", "expired-token");
      SyncEngine.sync(app);
      assertNotEquals(previous, app.session.get("refresh"));
      assertEquals(2, app.store.query("SELECT * FROM calls WHERE state='synced'").size());
      String callId =
          app.store.query("SELECT server_id FROM calls WHERE id=?", id).get(0).get("server_id");
      SyncEngine.sync(app);
      assertEquals(
          callId,
          app.store.query("SELECT server_id FROM calls WHERE id=?", id).get(0).get("server_id"));
      android.os.SystemClock.sleep(6000);
      assertEquals(
          app.session.get("user_id"),
          app.api.json("GET", "/auth/me", null).getJSONObject("user").getString("id"));
      // Exercise a real SAF provider and streamed multipart upload using synthetic WAV audio.
      Context test = InstrumentationRegistry.getInstrumentation().getContext();
      Uri tree = Uri.parse("content://com.aven.calls.qa.documents/tree/root");
      Bundle options = new Bundle();
      options.putString(
          "name",
          "Customer_"
              + DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss")
                  .format(Instant.ofEpochMilli(start).atZone(ZoneId.systemDefault()))
              + ".wav");
      options.putLong("modified", start + 20_000);
      options.putString("package", app.getPackageName());
      options.putBoolean("empty", true);
      test.getContentResolver()
          .call(Uri.parse("content://com.aven.calls.qa.control"), "configure", null, options);
      app.getContentResolver()
          .takePersistableUriPermission(tree, Intent.FLAG_GRANT_READ_URI_PERMISSION);
      app.store.meta("recording_tree", tree.toString());
      SyncEngine.capture(app);
      assertEquals("waiting", app.store.query("SELECT recording_state FROM calls WHERE id=?", id)
          .get(0).get("recording_state"));
      var rechecks = androidx.work.WorkManager.getInstance(app)
          .getWorkInfosForUniqueWork("aven-capture").get();
      assertTrue("An empty recording must schedule another capture", rechecks.stream()
          .anyMatch(job -> !job.getState().isFinished()));
      options.putBoolean("empty", false);
      test.getContentResolver()
          .call(Uri.parse("content://com.aven.calls.qa.control"), "configure", null, options);
      SyncEngine.capture(app);
      assertEquals(
          "waiting",
          app.store
              .query("SELECT recording_state FROM calls WHERE id=?", id)
              .get(0)
              .get("recording_state"));
      android.os.SystemClock.sleep(3100);
      SyncEngine.sync(app);
      assertEquals(
          "uploaded",
          app.store
              .query("SELECT recording_state FROM calls WHERE id=?", id)
              .get(0)
              .get("recording_state"));
      // Repeating a lost upload acknowledgement reuses the existing server attachment.
      app.store.update(id, "recording_state", "queued");
      SyncEngine.sync(app);
      assertEquals(
          "uploaded",
          app.store
              .query("SELECT recording_state FROM calls WHERE id=?", id)
              .get(0)
              .get("recording_state"));
      app.store.meta("recording_tree", "");
      app.store.update(
          id,
          "recording_state",
          "queued",
          "recording_uri",
          "content://com.aven.calls.qa.documents/document/missing");
      SyncEngine.sync(app);
      assertEquals(
          "missing",
          app.store
              .query("SELECT recording_state FROM calls WHERE id=?", id)
              .get(0)
              .get("recording_state"));
      app.store.meta("enabled", "false");
      nativeCall(args.getString("customer_phone"), start + 60_000, CallLog.Calls.REJECTED_TYPE, 0);
      SyncEngine.capture(app);
      assertEquals(2, app.store.query("SELECT * FROM calls").size());
      login(args.getString("second_phone"));
      assertTrue(app.store.query("SELECT * FROM calls").isEmpty());
      assertTrue(app.store.query("SELECT * FROM contacts").isEmpty());
      assertFalse(app.enabled());
    } finally {
      for (long nativeId : new long[] {row, missed, personal})
        app.getContentResolver()
            .delete(
                CallLog.Calls.CONTENT_URI,
                CallLog.Calls._ID + "=?",
                new String[] {String.valueOf(nativeId)});
    }
  }
}
