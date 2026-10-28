package com.aven.calls;

import static org.junit.Assert.*;

import android.app.Activity;
import android.content.Intent;
import android.text.method.PasswordTransformationMethod;
import android.widget.EditText;
import android.view.View;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class LoginPresentationTest {
  @Test
  public void passwordRemainsMaskedAfterSingleLineSetup() throws Exception {
    var instrumentation = InstrumentationRegistry.getInstrumentation();
    AvenApplication app =
        (AvenApplication) instrumentation.getTargetContext().getApplicationContext();
    app.api.cancelActive();
    SyncScheduler.cancel(app);
    SyncEngine.LOCK.lock();
    try {
      app.resetLocalData();
      app.session.clear();
    } finally {
      SyncEngine.LOCK.unlock();
    }
    Activity activity =
        instrumentation.startActivitySync(
            new Intent(app, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK));
    try {
      instrumentation.runOnMainSync(
          () -> {
            EditText password = activity.findViewById(R.id.login_password);
            EditText phone = activity.findViewById(R.id.login_phone);
            phone.setText("+919900000004");
            password.setText("Private-example-123!");
            assertFalse("Connection details should be hidden for everyday sign-in",
                activity.findViewById(R.id.server_address).isShown());
            View connection = activity.findViewById(R.id.connection_settings);
            connection.performClick();
            assertTrue(activity.findViewById(R.id.server_address).isShown());
            connection.performClick();
            assertFalse(activity.findViewById(R.id.server_address).isShown());
            assertEquals("+919900000004", phone.getText().toString());
            assertTrue(password.getTransformationMethod() instanceof PasswordTransformationMethod);
            assertTrue(password.createAccessibilityNodeInfo().isPassword());
            assertNotEquals(
                password.getText().toString(),
                password.getTransformationMethod().getTransformation(password.getText(), password)
                    .toString());
            assertEquals("Private-example-123!", password.getText().toString());
          });
    } finally {
      instrumentation.runOnMainSync(activity::finish);
    }
  }
}
