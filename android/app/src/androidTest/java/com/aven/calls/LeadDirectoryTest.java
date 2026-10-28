package com.aven.calls;

import static org.junit.Assert.*;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.SystemClock;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.uiautomator.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;

/** Controlled HTTP integration tests; never writes to the working CRM database. */
@RunWith(AndroidJUnit4.class)
public class LeadDirectoryTest {
  private AvenApplication app;
  private Activity activity;
  private UiDevice device;
  private ServerSocket listener;
  private Thread server;
  private final BlockingQueue<String> replies = new LinkedBlockingQueue<>();
  private final List<String> paths = new CopyOnWriteArrayList<>();
  private String origin, pkg;

  @Before public void setup() throws Exception {
    var instrumentation = InstrumentationRegistry.getInstrumentation();
    app = (AvenApplication) instrumentation.getTargetContext().getApplicationContext();
    assertTrue("Tests must use the separate debug application", app.getPackageName().endsWith(".debug"));
    app.api.cancelActive(); SyncScheduler.cancel(app);
    SyncEngine.LOCK.lock();
    try { app.resetLocalData(); app.session.clear(); }
    finally { SyncEngine.LOCK.unlock(); }
    app.store.meta("enabled", "false");
    listener = new ServerSocket(0);
    origin = "http://127.0.0.1:" + listener.getLocalPort();
    pkg = app.getPackageName(); device = UiDevice.getInstance(instrumentation);
    server = new Thread(() -> {
      while (!listener.isClosed()) {
        try (Socket socket = listener.accept()) {
          socket.setSoTimeout(10000);
          BufferedReader input = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
          String request = input.readLine(); paths.add(request.split(" ")[1]);
          int length = 0; String line;
          while ((line = input.readLine()) != null && !line.isEmpty())
            if (line.toLowerCase(Locale.ROOT).startsWith("content-length:")) length = Integer.parseInt(line.substring(15).trim());
          while (length-- > 0) input.read();
          String reply = replies.poll(10, TimeUnit.SECONDS);
          if (reply != null) socket.getOutputStream().write(reply.getBytes(StandardCharsets.UTF_8));
        } catch (Exception ignored) { }
      }
    });
    server.start();
    authenticate();
  }

  @After public void cleanup() throws Exception {
    if (activity != null) InstrumentationRegistry.getInstrumentation().runOnMainSync(activity::finish);
    app.api.cancelActive(); listener.close(); server.join(12000);
    app.session.clear(); SyncScheduler.cancel(app);
  }

  private void authenticate() throws Exception {
    app.session.putAll(new JSONObject().put("server", origin).put("user_id", "caller")
        .put("org_id", "company").put("access", "test-access").put("refresh", "test-refresh")
        .put("name", "Test Caller").put("org_name", "Test company").put("role", "telecaller"));
  }

  private JSONObject lead(String id) throws Exception {
    return new JSONObject().put("id", id).put("name", "Property enquiry " + id)
        .put("phone", "+919810001234").put("dnd", false);
  }

  private JSONObject page(String id, String cursor) throws Exception {
    return new JSONObject().put("items", id == null ? new JSONArray() : new JSONArray().put(lead(id)))
        .put("user_id", "caller").put("organization_id", "company")
        .put("next_cursor", cursor == null ? JSONObject.NULL : cursor);
  }

  private void reply(int status, JSONObject body) {
    byte[] bytes = body.toString().getBytes(StandardCharsets.UTF_8);
    replies.add("HTTP/1.1 " + status + " Result\r\nContent-Type: application/json\r\nSet-Cookie: crm_refresh=test-refresh; HttpOnly\r\nContent-Length: "
        + bytes.length + "\r\nConnection: close\r\n\r\n" + body);
  }

  private void seedSavedLeadAndCall() throws Exception {
    app.store.contacts(new JSONArray().put(lead("saved")));
    app.store.meta("contacts_at", "123");
    app.store.capture("queued", "+919810001234", "Saved", System.currentTimeMillis(), 25, "incoming", "answered");
  }

  private void assertSaved() {
    assertEquals("saved", app.store.query("SELECT id FROM contacts").get(0).get("id"));
    assertEquals("123", app.store.meta("contacts_at"));
    assertEquals(1, app.store.query("SELECT id FROM calls WHERE id='queued'").size());
    assertFalse(app.enabled());
  }

  private void start() {
    activity = InstrumentationRegistry.getInstrumentation().startActivitySync(new Intent(app, MainActivity.class)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK));
  }

  private UiObject2 find(String id) {
    UiObject2 found = device.wait(Until.findObject(By.res(pkg, id)), 5000);
    assertNotNull(id, found); return found;
  }

  private void expect(String text) {
    assertTrue(text, device.wait(Until.hasObject(By.text(text)), 10000));
  }

  @Test public void freshLoginLoadsAssignmentsWithoutPhoneSetup() throws Exception {
    app.session.clear();
    reply(200, new JSONObject().put("access_token", "test-access").put("role", "telecaller")
        .put("user", new JSONObject().put("id", "caller").put("name", "Test Caller"))
        .put("organization", new JSONObject().put("id", "company").put("name", "Test company")));
    reply(200, page("fresh", null));
    start();
    find("connection_settings").click(); find("server_address").setText(origin);
    find("connection_settings").click();
    find("login_phone").setText("+919810009999"); find("login_password").setText("Test-secret!");
    find("login_submit").click();
    find("nav_customers").click(); expect("Property enquiry fresh");
    assertTrue(paths.contains("/api/auth/login"));
    assertTrue(paths.contains("/api/phone-calls/contacts?after="));
    assertFalse(app.enabled()); assertEquals("", app.store.meta("enabled_since"));
    assertEquals(PackageManager.PERMISSION_DENIED, app.checkSelfPermission(Manifest.permission.READ_CALL_LOG));
    assertEquals(0, app.store.query("SELECT * FROM calls").size());
  }

  @Test public void pausedDirectoryLoadsEveryPageAtomically() throws Exception {
    reply(200, page("one", "page two")); reply(200, page("two", null));
    LeadDirectory.refresh(app);
    assertEquals(2, app.store.query("SELECT * FROM contacts").size());
    assertTrue(paths.contains("/api/phone-calls/contacts?after=page+two"));
    assertFalse(app.enabled()); assertEquals("", app.store.meta("enabled_since"));
    assertFalse(app.store.meta("contacts_at").isEmpty());
  }

  @Test public void failedSecondPagePreservesSavedLeadsAndQueuedCalls() throws Exception {
    seedSavedLeadAndCall(); reply(200, page("partial", "next")); reply(503, new JSONObject());
    try { LeadDirectory.refresh(app); fail("Must reject incomplete list"); } catch (IOException expected) { }
    assertSaved();
  }

  @Test public void wrongCompanyResponseCannotReplaceSavedAssignments() throws Exception {
    seedSavedLeadAndCall(); reply(200, page("foreign", null).put("organization_id", "other-company"));
    try { LeadDirectory.refresh(app); fail("Must reject foreign company"); } catch (IOException expected) { }
    assertSaved();
  }

  @Test public void repeatedCursorCannotReplaceSavedAssignments() throws Exception {
    seedSavedLeadAndCall(); reply(200, page("partial", "repeat")); reply(200, page("other", "repeat"));
    try { LeadDirectory.refresh(app); fail("Must reject repeated pagination"); } catch (IOException expected) { }
    assertSaved();
  }

  @Test public void emptyIsShownOnlyAfterSuccessfulResponse() throws Exception {
    start(); find("nav_customers").click(); expect("Loading your leads…");
    assertFalse(device.hasObject(By.text("No leads assigned yet")));
    reply(200, page(null, null));
    expect("No leads assigned yet"); assertFalse(app.store.meta("contacts_at").isEmpty());
    assertFalse(app.enabled());
  }

  @Test public void expiredSessionReturnsToLoginWithoutErasingQueuedCalls() throws Exception {
    seedSavedLeadAndCall(); reply(401, new JSONObject()); reply(401, new JSONObject());
    start(); find("login_phone");
    assertFalse(app.session.authenticated());
    assertEquals(1, app.store.query("SELECT id FROM calls WHERE id='queued'").size());
    assertEquals("saved", app.store.query("SELECT id FROM contacts").get(0).get("id"));
  }

  @Test public void failedLoadOffersRetryAndRefreshKeepsSearchText() throws Exception {
    reply(503, new JSONObject()); start(); find("nav_customers").click();
    expect("Leads couldn't be refreshed");
    find("customer_search").setText("draft");
    reply(200, page("retry", null)); find("refresh_leads").click();
    expect("No matching leads"); assertEquals("draft", find("customer_search").getText());
    find("customer_search").setText(""); expect("Property enquiry retry");
    assertFalse(app.enabled());
  }
}
