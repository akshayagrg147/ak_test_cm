package com.aven.calls;

import android.content.*;

public class BootReceiver extends BroadcastReceiver {
  @Override
  public void onReceive(Context context, Intent intent) {
    String action = intent.getAction();
    if (Intent.ACTION_BOOT_COMPLETED.equals(action)
        || Intent.ACTION_MY_PACKAGE_REPLACED.equals(action)) {
      SyncScheduler.restore(context);
      SyncScheduler.capture(context, 5);
    }
  }
}
