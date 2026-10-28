package com.aven.calls;

import static org.junit.Assert.*;
import android.app.Activity;
import android.content.Intent;
import android.graphics.Rect;
import android.os.SystemClock;
import android.view.*;
import android.widget.*;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.uiautomator.*;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class EstateUiTest {
  private AvenApplication app;
  private UiDevice device;
  private String pkg, server;
  private Activity activity;

  @Before public void setup() throws Exception {
    var instrumentation = InstrumentationRegistry.getInstrumentation();
    app = (AvenApplication) instrumentation.getTargetContext().getApplicationContext();
    app.store.meta("enabled", "false"); SyncScheduler.cancel(app); app.api.cancelActive();
    SyncEngine.LOCK.lock();
    try { app.resetLocalData(); app.session.clear(); }
    finally { SyncEngine.LOCK.unlock(); }
    var args = InstrumentationRegistry.getArguments(); server = args.getString("server");
    app.api.login(server, args.getString("phone"), args.getString("password"), "", "");
    device = UiDevice.getInstance(instrumentation); pkg = app.getPackageName();
  }

  @After public void cleanup() {
    app.store.meta("enabled", "false"); SyncScheduler.cancel(app);
    app.session.put("server", server);
    if (activity != null) InstrumentationRegistry.getInstrumentation().runOnMainSync(activity::finish);
  }

  private void start(Class<? extends Activity> target) {
    activity = InstrumentationRegistry.getInstrumentation().startActivitySync(new Intent(app, target)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK));
  }

  private UiObject2 find(String id) throws Exception {
    UiObject2 found = device.wait(Until.findObject(By.res(pkg, id)), 1000);
    if (found == null) {
      new UiScrollable(new UiSelector().scrollable(true)).setMaxSearchSwipes(50)
          .scrollIntoView(new UiSelector().resourceId(pkg + ":id/" + id));
      found = device.wait(Until.findObject(By.res(pkg, id)), 5000);
    }
    assertNotNull(id, found); return found;
  }

  private UiObject2 showText(String label) throws Exception {
    UiObject2 found = device.wait(Until.findObject(By.text(label)), 1500);
    if (found == null) {
      assertTrue("Scrollable content must be ready before searching for " + label,
          device.wait(Until.hasObject(By.scrollable(true)), 5000));
      new UiScrollable(new UiSelector().scrollable(true)).setMaxSearchSwipes(50)
          .scrollIntoView(new UiSelector().text(label));
      found = device.wait(Until.findObject(By.text(label)), 5000);
    }
    assertNotNull(label, found); return found;
  }

  private void clickText(String label) throws Exception { showText(label).click(); }
  private void expectText(String label) throws Exception { assertNotNull(showText(label)); }

  @Test public void assignedLeadsDndAndCallFiltersShowSeparateStates() throws Exception {
    String phone = InstrumentationRegistry.getArguments().getString("customer_phone");
    app.store.contacts(new JSONArray()
        .put(new JSONObject().put("id", "lead-a").put("name", "Panipat buyer").put("phone", phone))
        .put(new JSONObject().put("id", "dnd-lead").put("name", "Do not call lead").put("phone", "+919810077700").put("dnd", true)));
    app.store.meta("contacts_at", String.valueOf(System.currentTimeMillis()));
    app.store.capture("answered", phone, "Panipat buyer", System.currentTimeMillis(), 81, "outgoing", "answered");
    app.store.update("answered", "state", "synced", "recording_state", "waiting");
    app.store.capture("missed", phone, "Missed enquiry", System.currentTimeMillis()-1000, 0, "incoming", "missed");
    start(MainActivity.class);
    find("nav_customers").click();
    find("customer_search").setText("Do not call lead");
    expectText("Do not call");
    assertFalse(device.hasObject(By.text("Call lead")));
    find("customer_search").setText("Panipat buyer");
    expectText("Call lead");
    find("nav_calls").click(); find("calls_missed").click();
    assertTrue(find("calls_missed").isSelected());
    assertNotNull(find("calls_list"));
    expectText("Missed enquiry");
    find("calls_audio").click();
    expectText("Panipat buyer");
    assertNotNull(find("calls_list"));
    clickText("Resume uploads to add a recording.");
    assertFalse(device.hasObject(By.text("Missed enquiry")));
    assertEquals("waiting", app.store.query("SELECT recording_state FROM calls WHERE id='answered'").get(0).get("recording_state"));
    find("nav_settings").click(); assertNotNull(find("property_catalogue"));
    find("nav_home").click(); assertTrue(find("nav_home").isSelected());
  }

  @Test public void inventoryUsesActualApiSearchTypeRentAndPagination() throws Exception {
    start(PropertyActivity.class);
    expectText("25 properties · Page 1");
    device.takeScreenshot(new java.io.File(app.getExternalFilesDir(null), "qa-properties.png"));
    find("property_search").setText("no-such-property-xyz"); find("property_submit").click();
    expectText("No properties found");
    find("property_refresh").click();
    expectText("25 properties · Page 1");
    find("property_type").click(); clickText("Plot");
    expectText("1 property · Page 1");
    clickText("View property");
    expectText("Property details");
    expectText("QA Panipat Plot 0");
    device.takeScreenshot(new java.io.File(app.getExternalFilesDir(null), "qa-plot-detail.png"));
    // Plots must never display irrelevant bedroom/bathroom fields.
    InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
      assertFalse(hasText(activity.getWindow().getDecorView(), "Bedrooms"));
      assertFalse(hasText(activity.getWindow().getDecorView(), "Bathrooms"));
      checkLayout(activity.getWindow().getDecorView());
    });
    find("property_back").click();
    expectText("1 property · Page 1");
    assertEquals("Plot", find("property_type").getText());
    find("property_type").click(); clickText("All property types");
    expectText("25 properties · Page 1");
    find("property_next").click();
    expectText("25 properties · Page 2");
    assertNotNull(find("property_previous"));
    find("property_previous").click();
    expectText("25 properties · Page 1");
    find("property_listing").click(); clickText("For rent");
    expectText("1 property · Page 1");
    clickText("View property");
    expectText("₹25,000 / month");
  }

  @Test public void unreachableInventoryShowsRetryWithoutRemovingQueuedCalls() throws Exception {
    app.store.capture("offline-safe", "+919810001234", "Queued enquiry", System.currentTimeMillis(), 10, "outgoing", "answered");
    app.session.put("server", "http://127.0.0.1:1");
    start(PropertyActivity.class);
    expectText("Properties couldn't be loaded");
    find("property_retry").click();
    expectText("Properties couldn't be loaded");
    assertEquals(1, app.store.query("SELECT id FROM calls WHERE id='offline-safe'").size());
    find("property_back").click();
    long deadline = SystemClock.elapsedRealtime() + 2000;
    while (!activity.isFinishing() && !activity.isDestroyed() && SystemClock.elapsedRealtime() < deadline)
      SystemClock.sleep(50);
    assertTrue(activity.isFinishing() || activity.isDestroyed());
  }

  @Test public void visibleControlsRespectTouchSizeAndTextLayout() throws Exception {
    start(MainActivity.class);
    InstrumentationRegistry.getInstrumentation().waitForIdleSync();
    device.waitForIdle();
    device.takeScreenshot(new java.io.File(app.getExternalFilesDir(null), "qa-home-layout.png"));
    InstrumentationRegistry.getInstrumentation().waitForIdleSync();
    InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> checkLayout(activity.getWindow().getDecorView()));
    find("nav_customers").click(); find("customer_search").setText("Search survives navigation");
    find("nav_calls").click(); find("nav_customers").click();
    assertEquals("Search survives navigation", find("customer_search").getText());
    device.takeScreenshot(new java.io.File(app.getExternalFilesDir(null), "qa-leads-layout.png"));
    InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> checkLayout(activity.getWindow().getDecorView()));
  }

  @Test public void inventoryClosesWhenTheSessionExpiresWithoutClearingSavedCalls() throws Exception {
    app.store.capture("session-safe", "+919810001234", "Queued enquiry", System.currentTimeMillis(), 10, "outgoing", "answered");
    start(PropertyActivity.class);
    expectText("25 properties · Page 1");
    app.session.invalidate();
    long deadline = SystemClock.elapsedRealtime() + 6000;
    while (!activity.isFinishing() && !activity.isDestroyed() && SystemClock.elapsedRealtime() < deadline)
      SystemClock.sleep(100);
    assertTrue("Inventory must close when authentication expires", activity.isFinishing() || activity.isDestroyed());
    assertEquals(1, app.store.query("SELECT id FROM calls WHERE id='session-safe'").size());
  }

  @Test public void loadingResponseDoesNotEraseADraftSearch() throws Exception {
    try (var listener = new java.net.ServerSocket(0)) {
      var received = new java.util.concurrent.CountDownLatch(1);
      var release = new java.util.concurrent.CountDownLatch(1);
      Thread response = new Thread(() -> {
        try (var socket = listener.accept()) {
          var input = new java.io.BufferedReader(new java.io.InputStreamReader(socket.getInputStream()));
          String line;
          while ((line = input.readLine()) != null && !line.isEmpty()) {}
          received.countDown();
          assertTrue(release.await(10, java.util.concurrent.TimeUnit.SECONDS));
          byte[] body = "{\"items\":[],\"total\":0,\"page\":1}".getBytes(java.nio.charset.StandardCharsets.UTF_8);
          socket.getOutputStream().write(("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
              + body.length + "\r\nConnection: close\r\n\r\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
          socket.getOutputStream().write(body);
        } catch (Exception failure) { throw new RuntimeException(failure); }
      });
      response.start();
      try {
        app.session.put("server", "http://127.0.0.1:" + listener.getLocalPort());
        start(PropertyActivity.class);
        assertTrue(received.await(5, java.util.concurrent.TimeUnit.SECONDS));
        find("property_search").setText("Sector 18 draft");
        release.countDown();
        expectText("0 properties · Page 1");
        assertEquals("Sector 18 draft", find("property_search").getText());
      } finally { release.countDown(); response.join(12000); }
    }
  }

  private boolean hasText(View view, String value) {
    if (view instanceof TextView text && text.getText().toString().equals(value)) return true;
    if (view instanceof ViewGroup group)
      for (int i = 0; i < group.getChildCount(); i++) if (hasText(group.getChildAt(i), value)) return true;
    return false;
  }

  private void checkLayout(View view) {
    if (view.isShown() && view.getGlobalVisibleRect(new Rect()) && view instanceof TextView text) {
      if (view instanceof Button || view instanceof EditText)
        assertTrue("Touch target: " + text.getText(), view.getHeight() >= 48 * view.getResources().getDisplayMetrics().density - 1);
      if (text.getLayout() != null)
        for (int i = 0; i < text.getLayout().getLineCount(); i++)
          assertEquals("Truncated text: " + text.getText(), 0, text.getLayout().getEllipsisCount(i));
    }
    if (view instanceof ViewGroup group)
      for (int i = 0; i < group.getChildCount(); i++) checkLayout(group.getChildAt(i));
  }
}
