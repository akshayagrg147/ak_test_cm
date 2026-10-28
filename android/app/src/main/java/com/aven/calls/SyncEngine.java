package com.aven.calls;

import android.Manifest;
import android.content.*;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;
import android.provider.CallLog;
import androidx.documentfile.provider.DocumentFile;
import java.io.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.ReentrantLock;
import org.json.*;

public final class SyncEngine {
  public static final ReentrantLock LOCK = new ReentrantLock();

  private SyncEngine() {}

  private static void enter() throws Exception {
    if (!LOCK.tryLock(2, TimeUnit.SECONDS))
      throw new IOException("Another sync is running; this request remains queued.");
  }

  private static void check(AvenApplication app) throws InterruptedIOException {
    if (Thread.currentThread().isInterrupted() || !app.enabled())
      throw new InterruptedIOException("Sync paused; pending work is kept.");
  }

  public static void refreshContacts(AvenApplication app) throws Exception {
    JSONArray all = new JSONArray();
    String cursor = "";
    Set<String> seen = new HashSet<>();
    for (int page = 0; page < 250; page++) {
      check(app);
      JSONObject response =
          app.api.json(
              "GET",
              "/phone-calls/contacts?after=" + java.net.URLEncoder.encode(cursor, "UTF-8"),
              null);
      if (!response.getString("user_id").equals(app.session.get("user_id"))
          || !response.getString("organization_id").equals(app.session.get("org_id")))
        throw new IOException("Account changed during contact refresh. Sign in again.");
      JSONArray contacts = response.getJSONArray("items");
      for (int i = 0; i < contacts.length(); i++) all.put(contacts.getJSONObject(i));
      app.store.meta(
          "recording_limit",
          String.valueOf(
              response.optLong("max_recording_bytes", SyncPolicy.DEFAULT_RECORDING_LIMIT)));
      if (response.isNull("next_cursor") || response.optString("next_cursor").isEmpty()) {
        app.store.contacts(all);
        app.store.meta("contacts_at", String.valueOf(System.currentTimeMillis()));
        return;
      }
      cursor = response.getString("next_cursor");
      if (!seen.add(cursor))
        throw new IOException(
            "The contact list repeated a page; previous local contacts are preserved.");
    }
    throw new IOException(
        "The assigned-contact list is too large for one sync. Ask your administrator to review"
            + " assignments.");
  }

  public static void capture(AvenApplication app) throws Exception {
    enter();
    try {
      if (app.enabled()) {
        captureCalls(app);
        scanRecordings(app);
      }
    } finally {
      LOCK.unlock();
    }
  }

  public static void sync(AvenApplication app) throws Exception {
    enter();
    long deadline = System.currentTimeMillis() + 90_000;
    try {
      if (!app.enabled()) return;
      long retryAfter = 0;
      try {
        retryAfter = Long.parseLong(app.store.meta("retry_after_ms"));
      } catch (NumberFormatException ignored) {
      }
      if (retryAfter > System.currentTimeMillis())
        throw new IOException(
            "The server asked us to wait before retrying. Queued calls are safe.");
      app.store.meta("status", "Checking assigned customers and queued calls…");
      app.api.json("GET", "/auth/me", null);
      refreshContacts(app);
      captureCalls(app);
      scanRecordings(app);
      for (int batch = 0; batch < 100 && System.currentTimeMillis() < deadline; batch++) {
        check(app);
        List<Map<String, String>> calls =
            app.store.query(
                "SELECT * FROM calls WHERE state='pending' ORDER BY started,id LIMIT 100");
        if (calls.isEmpty()) break;
        JSONArray entries = new JSONArray();
        for (Map<String, String> call : calls)
          entries.put(
              new JSONObject()
                  .put("device_call_id", call.get("id"))
                  .put("phone", call.get("phone"))
                  .put("direction", call.get("direction"))
                  .put("result", call.get("result"))
                  .put(
                      "started_at",
                      Instant.ofEpochMilli(Long.parseLong(call.get("started"))).toString())
                  .put("duration", Long.parseLong(call.get("duration"))));
        JSONObject response =
            app.api.json(
                "POST",
                "/phone-calls/sync",
                new JSONObject()
                    .put("device_id", app.store.meta("installation"))
                    .put("calls", entries));
        JSONArray receipts = response.optJSONArray("entries");
        if (receipts == null)
          throw new IOException("Update the CRM server: per-call sync receipts are required.");
        Set<String> ack = new HashSet<>();
        for (int i = 0; i < receipts.length(); i++) {
          JSONObject receipt = receipts.getJSONObject(i);
          String id = receipt.getString("device_call_id"), status = receipt.getString("status");
          if (!calls.stream().anyMatch(c -> id.equals(c.get("id"))) || !ack.add(id))
            throw new IOException("Invalid call receipt. The remaining work stays queued.");
          if (status.equals("created") || status.equals("updated"))
            app.store.update(
                id,
                "state",
                "synced",
                "server_id",
                receipt.getString("call_id"),
                "lead_id",
                receipt.getString("lead_id"),
                "error",
                "");
          else if (status.equals("excluded") || status.equals("ambiguous"))
            app.store.update(
                id,
                "state",
                status,
                "error",
                status.equals("ambiguous")
                    ? "Multiple assigned leads use this number. Ask your manager to resolve it."
                    : "This customer is no longer assigned to you.");
          else if (status.equals("error"))
            app.store.update(
                id,
                "state",
                "error",
                "error",
                switch (receipt.optString("code")) {
                  case "outside_sync_window" ->
                      "The call time is outside the supported window. Check your phone's date and"
                          + " time.";
                  case "invalid_phone" ->
                      "The phone number is invalid. Check the customer's CRM number.";
                  case "identity_conflict" ->
                      "This call conflicts with a saved device entry. Ask your administrator to"
                          + " review it.";
                  default ->
                      "The CRM could not accept this call. Ask your administrator to review it.";
                });
          else throw new IOException("Unrecognized server receipt; pending work is preserved.");
        }
        if (ack.size() != calls.size())
          throw new IOException("Some calls were not acknowledged. They remain queued.");
      }
      scanRecordings(app);
      for (Map<String, String> call :
          app.store.query(
              "SELECT * FROM calls WHERE state='synced' AND recording_state='queued' ORDER BY"
                  + " started LIMIT 20")) {
        if (System.currentTimeMillis() > deadline) break;
        check(app);
        uploadRecording(app, call);
      }
      app.store.meta("last_sync", String.valueOf(System.currentTimeMillis()));
      int pending = app.store.pendingCount();
      int review = app.store.reviewCount();
      app.store.meta(
          "status",
          review > 0
              ? review + " work call(s) need review. Check Recent work calls."
              : pending == 0
                  ? "Work calls are up to date. Recordings upload when available and matched."
                  : pending + " item(s) remain queued; background sync will continue.");
      if (pending > 0) SyncScheduler.upload(app);
      app.store.prune(System.currentTimeMillis() - SyncPolicy.MAX_AGE_MS);
    } finally {
      LOCK.unlock();
    }
  }

  private static void captureCalls(AvenApplication app) throws Exception {
    if (app.checkSelfPermission(Manifest.permission.READ_CALL_LOG)
        != PackageManager.PERMISSION_GRANTED) {
      throw new SecurityException(
          "Call-log permission is needed. Open Permissions to enable work-call syncing.");
    }
    long now = System.currentTimeMillis(), since;
    try {
      since = Long.parseLong(app.store.meta("enabled_since"));
    } catch (Exception e) {
      return;
    }
    since = Math.max(since, now - SyncPolicy.MAX_AGE_MS);
    Map<String, List<Map<String, String>>> contacts = new HashMap<>();
    for (Map<String, String> c : app.store.query("SELECT * FROM contacts"))
      contacts.computeIfAbsent(c.get("phone"), ignored -> new ArrayList<>()).add(c);
    String[] projection = {
      CallLog.Calls._ID,
      CallLog.Calls.NUMBER,
      CallLog.Calls.TYPE,
      CallLog.Calls.DATE,
      CallLog.Calls.DURATION
    };
    android.database.sqlite.SQLiteDatabase db = app.store.getWritableDatabase();
    db.beginTransaction();
    try (Cursor rows =
        app.getContentResolver()
            .query(
                CallLog.Calls.CONTENT_URI,
                projection,
                CallLog.Calls.DATE + ">=?",
                new String[] {String.valueOf(since)},
                CallLog.Calls.DATE + " DESC, " + CallLog.Calls._ID + " DESC")) {
      if (rows == null)
        throw new IOException("The phone did not return a call log. Retry after unlocking it.");
      while (rows.moveToNext()) {
        check(app);
        int type = rows.getInt(2);
        long start = rows.getLong(3), duration = Math.max(0, rows.getLong(4));
        String number = PhoneNumbers.normalize(rows.getString(1), callingCode(app));
        if (!SyncPolicy.supportedType(type)
            || number == null
            || !contacts.containsKey(number)
            || !SyncPolicy.inWindow(start, now)) continue;
        List<Map<String, String>> matches = contacts.get(number);
        String name =
            matches.size() == 1 ? matches.get(0).get("name") : "Multiple customer matches";
        app.store.capture(
            SyncPolicy.callKey(rows.getLong(0), start),
            number,
            name,
            start,
            Math.min(86400, duration),
            SyncPolicy.direction(type),
            SyncPolicy.result(type, duration));
      }
      db.setTransactionSuccessful();
    } finally {
      db.endTransaction();
    }
  }

  private static String callingCode(AvenApplication app) {
    String code = app.store.meta("calling_code");
    return code.isEmpty() ? "91" : code;
  }

  private static List<RecordingMatcher.CallRef> callRefs(AvenApplication app) {
    List<RecordingMatcher.CallRef> refs = new ArrayList<>();
    for (Map<String, String> c : app.store.query("SELECT * FROM calls"))
      refs.add(
          new RecordingMatcher.CallRef(
              c.get("id"),
              c.get("phone"),
              Long.parseLong(c.get("started")),
              Long.parseLong(c.get("duration")),
              c.get("result")));
    return refs;
  }

  private static void scanRecordings(AvenApplication app) throws Exception {
    String tree = app.store.meta("recording_tree");
    if (tree.isEmpty()) return;
    DocumentFile folder = DocumentFile.fromTreeUri(app, Uri.parse(tree));
    if (folder == null || !folder.canRead()) {
      app.store.meta(
          "folder_status", "Folder access was removed. Choose the recording folder again.");
      return;
    }
    List<RecordingMatcher.CallRef> refs = callRefs(app);
    long now = System.currentTimeMillis();
    boolean settling = false;
    for (DocumentFile file : folder.listFiles()) {
      check(app);
      if (!file.isFile() || !RecordingMatcher.supported(file.getName())) continue;
      RecordingMatcher.Match match =
          RecordingMatcher.match(
              file.getName(), file.lastModified(), refs, callingCode(app), ZoneId.systemDefault());
      if (match.key() == null) continue;
      List<Map<String, String>> stored =
          app.store.query("SELECT * FROM calls WHERE id=?", match.key());
      if (stored.isEmpty()) continue;
      Map<String, String> call = stored.get(0);
      if (!Set.of("pending", "synced").contains(call.get("state"))) continue;
      if (Set.of("uploaded", "queued").contains(call.get("recording_state"))) continue;
      if (file.length() <= 0) {
        app.store.update(
            match.key(),
            "recording_state",
            "waiting",
            "error",
            "Recording is empty or still being written.");
        settling = true;
        continue;
      }
      if (file.length() > recordingLimit(app)) {
        app.store.update(
            match.key(),
            "recording_state",
            "too_large",
            "error",
            "Recording exceeds the server upload limit.");
        continue;
      }
      if (!app.store.stable(file.getUri().toString(), file.length(), file.lastModified(), now)) {
        settling = true;
        continue;
      }
      app.store.update(
          match.key(),
          "recording_state",
          "queued",
          "recording_uri",
          file.getUri().toString(),
          "recording_name",
          file.getName(),
          "error",
          "");
    }
    app.store.meta(
        "folder_status",
        "Recording folder connected. Only confidently matched work-call files upload"
            + " automatically.");
    if (settling) SyncScheduler.capture(app, 10);
  }

  public static long recordingLimit(AvenApplication app) {
    try {
      return Math.max(1, Long.parseLong(app.store.meta("recording_limit")));
    } catch (Exception ignored) {
      return SyncPolicy.DEFAULT_RECORDING_LIMIT;
    }
  }

  public static void attachSelected(AvenApplication app, String key, Uri uri, String name)
      throws Exception {
    enter();
    try {
      if (!app.enabled())
        throw new IOException("Enable work-call sync before attaching a recording.");
      List<Map<String, String>> rows =
          app.store.query(
              "SELECT id FROM calls WHERE id=? AND state NOT IN ('excluded','ambiguous','error')",
              key);
      if (rows.isEmpty()) throw new IOException("This work call is unavailable.");
      app.store.update(
          key,
          "recording_state",
          "queued",
          "recording_uri",
          uri.toString(),
          "recording_name",
          name,
          "error",
          "");
      SyncScheduler.upload(app);
    } finally {
      LOCK.unlock();
    }
  }

  private static void uploadRecording(AvenApplication app, Map<String, String> call)
      throws Exception {
    File snapshot = File.createTempFile("aven-upload-", ".audio", app.getCacheDir());
    try {
      Uri uri = Uri.parse(call.get("recording_uri"));
      long limit = recordingLimit(app), total = 0;
      try (InputStream source = app.getContentResolver().openInputStream(uri);
          OutputStream out = new FileOutputStream(snapshot)) {
        if (source == null) throw new FileNotFoundException();
        byte[] data = new byte[32768];
        int n;
        while ((n = source.read(data)) != -1) {
          check(app);
          total += n;
          if (total > limit) {
            app.store.update(
                call.get("id"),
                "recording_state",
                "too_large",
                "error",
                "Recording exceeds the server limit of " + (limit / 1024 / 1024) + " MiB.");
            return;
          }
          out.write(data, 0, n);
        }
      }
      if (total == 0) {
        app.store.update(
            call.get("id"),
            "recording_state",
            "missing",
            "error",
            "The recording is empty. Select a completed file.");
        return;
      }
      app.api.upload(
          call.get("lead_id"), call.get("server_id"), snapshot, call.get("recording_name"));
      app.store.update(call.get("id"), "recording_state", "uploaded", "error", "");
    } catch (FileNotFoundException | SecurityException e) {
      app.store.update(
          call.get("id"),
          "recording_state",
          "missing",
          "error",
          "Recording missing or access revoked. Select the file again.");
    } catch (Api.Failure e) {
      if (e.status == 404 || e.status == 403) {
        app.store.update(
            call.get("id"),
            "recording_state",
            "blocked",
            "error",
            "Call access changed. The recording was not uploaded.");
      } else if (!SyncPolicy.retryable(e.status) && e.status != 401) {
        app.store.update(call.get("id"), "recording_state", "review", "error", e.getMessage());
      } else throw e;
    } finally {
      snapshot.delete();
    }
  }
}
