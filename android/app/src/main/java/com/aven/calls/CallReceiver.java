package com.aven.calls;

import android.content.*;
import android.telephony.TelephonyManager;

public class CallReceiver extends BroadcastReceiver {
  @Override
  public void onReceive(Context context, Intent intent) {
    if (TelephonyManager.ACTION_PHONE_STATE_CHANGED.equals(intent.getAction())
        && TelephonyManager.EXTRA_STATE_IDLE.equals(
            intent.getStringExtra(TelephonyManager.EXTRA_STATE))) {
      SyncScheduler.capture(context, 3);
      SyncScheduler.capture(context, 20);
    }
  }
}
