package com.aven.calls;

import static org.junit.Assert.*;

import android.content.Intent;
import android.os.SystemClock;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.uiautomator.*;
import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.util.Locale;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class OtpUiTest {
  private void click(UiDevice device, String label) throws Exception {
    if (label.equals("Sign in") || label.equals("Verify and sign in")) {
      String id = "com.aven.calls.debug:id/login_submit";
      if (!device.hasObject(By.res(id)))
        new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView(new UiSelector().resourceId(id));
      device.findObject(By.res(id)).click();
      return;
    }
    if (!device.hasObject(By.text(label)))
      new UiScrollable(new UiSelector().scrollable(true))
          .scrollIntoView(new UiSelector().text(label));
    device.findObject(By.text(label)).click();
  }

  private String otp(String secret) throws Exception {
    ByteArrayOutputStream bytes = new ByteArrayOutputStream();
    int bits = 0, value = 0;
    for (char c : secret.toCharArray()) {
      value = (value << 5) | "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567".indexOf(c);
      bits += 5;
      if (bits >= 8) {
        bits -= 8;
        bytes.write((value >> bits) & 255);
      }
    }
    Mac mac = Mac.getInstance("HmacSHA1");
    mac.init(new SecretKeySpec(bytes.toByteArray(), "HmacSHA1"));
    byte[] hash =
        mac.doFinal(ByteBuffer.allocate(8).putLong(System.currentTimeMillis() / 30000).array());
    int truncated = ByteBuffer.wrap(hash).getInt(hash[hash.length - 1] & 15) & 0x7fffffff;
    return String.format(Locale.ROOT, "%06d", truncated % 1_000_000);
  }

  @Test
  public void authenticatorRejectsBadCodeCanRestartAndSignsIn() throws Exception {
    var instrumentation = InstrumentationRegistry.getInstrumentation();
    var args = InstrumentationRegistry.getArguments();
    AvenApplication app =
        (AvenApplication) instrumentation.getTargetContext().getApplicationContext();
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
    app.startActivity(
        new Intent(app, MainActivity.class)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK));
    UiDevice device = UiDevice.getInstance(instrumentation);
    String pkg = app.getPackageName();
    assertNotNull(device.wait(Until.findObject(By.res(pkg, "connection_settings")), 10000));
    device.findObject(By.res(pkg, "connection_settings")).click();
    assertNotNull(device.wait(Until.findObject(By.res(pkg, "server_address")), 10000));
    device.findObject(By.res(pkg, "server_address")).setText(args.getString("server"));
    device.findObject(By.res(pkg, "connection_settings")).click();
    device.findObject(By.res(pkg, "login_phone")).setText(args.getString("otp_phone"));
    device.findObject(By.res(pkg, "login_password")).setText(args.getString("password"));
    click(device, "Sign in");
    UiObject2 codeField = device.wait(Until.findObject(By.res(pkg, "login_code")), 10000);
    if (codeField == null)
      device.takeScreenshot(new java.io.File(app.getExternalFilesDir(null), "qa-otp-failure.png"));
    UiObject2 loginStatus = device.findObject(By.res(pkg, "sync_status"));
    assertNotNull("Verification code must be visible. Status: "
        + (loginStatus == null ? "not visible" : loginStatus.getText()), codeField);
    String bad = otp(args.getString("otp_secret")).equals("000000") ? "999999" : "000000";
    device.findObject(By.res(pkg, "login_code")).setText(bad);
    click(device, "Verify and sign in");
    assertTrue(device.wait(Until.hasObject(By.textContains("invalid or already used")), 10000));
    assertFalse(app.session.authenticated());
    click(device, "Restart sign-in");
    assertFalse(device.hasObject(By.res(pkg, "login_code")));
    device.findObject(By.res(pkg, "login_password")).setText(args.getString("password"));
    click(device, "Sign in");
    assertNotNull(device.wait(Until.findObject(By.res(pkg, "login_code")), 10000));
    long step = System.currentTimeMillis() / 30000;
    while (System.currentTimeMillis() / 30000 <= step) SystemClock.sleep(200);
    device.findObject(By.res(pkg, "login_code")).setText(otp(args.getString("otp_secret")));
    click(device, "Verify and sign in");
    long deadline = SystemClock.elapsedRealtime() + 10000;
    while (!app.session.authenticated() && SystemClock.elapsedRealtime() < deadline)
      SystemClock.sleep(100);
    assertTrue(app.session.authenticated());
    assertEquals("Emulator QA Authenticator", app.session.get("name"));
    assertFalse(app.enabled());
  }
}
