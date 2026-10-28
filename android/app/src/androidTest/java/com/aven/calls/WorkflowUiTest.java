package com.aven.calls;

import static org.junit.Assert.*;

import android.content.Intent;
import android.os.Bundle;
import android.os.SystemClock;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.uiautomator.*;
import org.junit.Test;
import org.junit.runner.RunWith;

/**
 * Real sign-in/consent/foreground-service controls. Leaves only the isolated QA account enabled.
 */
@RunWith(AndroidJUnit4.class)
public class WorkflowUiTest {
  private UiObject2 find(UiDevice device, String pkg, String id) throws Exception {
    if (device.wait(Until.findObject(By.res(pkg, id)), 500) == null) {
      assertTrue(
          "Dashboard must finish rendering before scrolling",
          device.wait(Until.hasObject(By.scrollable(true)), 5000));
      new UiScrollable(new UiSelector().scrollable(true))
          .scrollIntoView(new UiSelector().resourceId(pkg + ":id/" + id));
    }
    return device.wait(Until.findObject(By.res(pkg, id)), 5000);
  }

  @Test
  public void loginConsentForegroundSyncAndPauseControls() throws Exception {
    var instrumentation = InstrumentationRegistry.getInstrumentation();
    AvenApplication app =
        (AvenApplication) instrumentation.getTargetContext().getApplicationContext();
    Bundle args = InstrumentationRegistry.getArguments();
    app.store.meta("enabled", "false");
    SyncScheduler.cancel(app);
    app.api.cancelActive();
    SyncEngine.LOCK.lock();
    try {
      app.resetLocalData();
      app.session.clear();
    } finally {
      SyncEngine.LOCK.unlock();
    }
    UiDevice device = UiDevice.getInstance(instrumentation);
    app.startActivity(
        new Intent(app, MainActivity.class)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK));
    String pkg = app.getPackageName();
    assertNotNull(device.wait(Until.findObject(By.res(pkg, "connection_settings")), 10000));
    device.findObject(By.res(pkg, "connection_settings")).click();
    UiObject2 address = device.wait(Until.findObject(By.res(pkg, "server_address")), 10000);
    assertNotNull(address);
    address.setText(args.getString("server"));
    device.findObject(By.res(pkg, "connection_settings")).click();
    device.findObject(By.res(pkg, "login_phone")).setText(args.getString("phone"));
    device.findObject(By.res(pkg, "login_password")).setText(args.getString("password"));
    if (!device.hasObject(By.res(pkg, "login_submit")))
      new UiScrollable(new UiSelector().scrollable(true))
          .scrollIntoView(new UiSelector().resourceId(pkg + ":id/login_submit"));
    device.findObject(By.res(pkg, "login_submit")).click();
    long loginDeadline = SystemClock.elapsedRealtime() + 15000;
    while (!app.session.authenticated() && SystemClock.elapsedRealtime() < loginDeadline)
      SystemClock.sleep(200);
    assertTrue("UI login must establish a real session", app.session.authenticated());
    assertNotNull(find(device, pkg, "enable_sync"));
    device.findObject(By.res(pkg, "enable_sync")).click();
    assertFalse(app.enabled());
    device.findObject(By.res(pkg, "sync_consent")).click();
    device.findObject(By.res(pkg, "enable_sync")).click();
    long permissionDeadline = SystemClock.elapsedRealtime() + 10000;
    while (!app.enabled() && SystemClock.elapsedRealtime() < permissionDeadline) {
      UiObject2 allow =
          device.findObject(By.res("com.android.permissioncontroller", "permission_allow_button"));
      if (allow != null) allow.click();
      SystemClock.sleep(200);
    }
    assertNotNull(find(device, pkg, "sync_now"));
    assertTrue(app.enabled());
    long deadline = SystemClock.elapsedRealtime() + 15000;
    while (app.store.query("SELECT * FROM contacts").isEmpty()
        && SystemClock.elapsedRealtime() < deadline) SystemClock.sleep(200);
    assertEquals(1, app.store.query("SELECT * FROM contacts").size());
    SyncEngine.LOCK.lock();
    try {
      device.findObject(By.res(pkg, "sync_now")).click();
      long serviceDeadline = SystemClock.elapsedRealtime() + 1500;
      while (!SyncService.active.get() && SystemClock.elapsedRealtime() < serviceDeadline)
        SystemClock.sleep(50);
      assertTrue(
          "Sync now must start the data-transfer foreground service", SyncService.active.get());
    } finally {
      SyncEngine.LOCK.unlock();
    }
    deadline = SystemClock.elapsedRealtime() + 15000;
    while (app.store.meta("last_sync").isEmpty() && SystemClock.elapsedRealtime() < deadline)
      SystemClock.sleep(200);
    assertFalse(app.store.meta("last_sync").isEmpty());
    assertNotNull(find(device, pkg, "recording_status"));
    assertEquals("No recording folder selected", device.findObject(By.res(pkg, "recording_status")).getText());
    assertNotNull(find(device, pkg, "skip_recordings"));
    device.findObject(By.res(pkg, "skip_recordings")).click();
    assertTrue("Skipping recordings must not invent a folder grant", app.store.meta("recording_tree").isEmpty());
    device.findObject(By.res(pkg, "nav_customers")).click();
    assertTrue(device.findObject(By.res(pkg, "nav_customers")).isSelected());
    UiObject2 search = device.wait(Until.findObject(By.res(pkg, "customer_search")), 5000);
    assertNotNull(search);
    search.setText("no-such-customer-xyz");
    assertTrue(device.wait(Until.hasObject(By.text("No matching leads")), 5000));
    search.setText("%_");
    assertTrue(device.wait(Until.hasObject(By.text("No matching leads")), 5000));
    search.setText(args.getString("customer_phone"));
    assertTrue(device.wait(Until.hasObject(By.text("Call lead")), 5000));
    search.setText("");
    device.findObject(By.res(pkg, "nav_settings")).click();
    assertNotNull(find(device, pkg, "pause_sync"));
    device.findObject(By.res(pkg, "pause_sync")).click();
    assertNotNull(find(device, pkg, "enable_sync"));
    assertFalse(app.enabled());
    device.findObject(By.res(pkg, "enable_sync")).click();
    assertNotNull(find(device, pkg, "sync_now"));
    SyncEngine.LOCK.lock();
    try {
      app.store.capture(
          "session-recovery",
          args.getString("customer_phone"),
          "QA customer",
          System.currentTimeMillis(),
          5,
          "outgoing",
          "answered");
      app.session.invalidate();
    } finally {
      SyncEngine.LOCK.unlock();
    }
    assertNotNull(
        "Expired sessions must return to sign-in without a manual sign-out",
        device.wait(Until.findObject(By.res(pkg, "login_phone")), 10000));
    assertEquals(1, app.store.query("SELECT id FROM calls WHERE id='session-recovery'").size());
    device.findObject(By.res(pkg, "login_phone")).setText(args.getString("phone"));
    device.findObject(By.res(pkg, "login_password")).setText(args.getString("password"));
    if (!device.hasObject(By.res(pkg, "login_submit")))
      new UiScrollable(new UiSelector().scrollable(true))
          .scrollIntoView(new UiSelector().resourceId(pkg + ":id/login_submit"));
    device.findObject(By.res(pkg, "login_submit")).click();
    long authDeadline = SystemClock.elapsedRealtime() + 15000;
    while (!app.session.authenticated() && SystemClock.elapsedRealtime() < authDeadline)
      SystemClock.sleep(100);
    assertTrue(app.session.authenticated());
    assertNotNull(find(device, pkg, "sync_now"));
    assertEquals(
        "Signing back into the same account must keep queued work",
        1,
        app.store.query("SELECT id FROM calls WHERE id='session-recovery'").size());
    device.takeScreenshot(new java.io.File(app.getExternalFilesDir(null), "qa-dashboard.png"));
    device.pressHome();
  }
}
