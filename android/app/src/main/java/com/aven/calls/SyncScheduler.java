package com.aven.calls;

import android.content.Context;
import androidx.work.*;
import java.util.concurrent.TimeUnit;

public final class SyncScheduler {
  private SyncScheduler() {}

  public static void restore(Context context) {
    if (AvenApplication.get() != null && AvenApplication.get().enabled()) {
      WorkManager.getInstance(context)
          .enqueueUniquePeriodicWork(
              "aven-periodic",
              ExistingPeriodicWorkPolicy.UPDATE,
              new PeriodicWorkRequest.Builder(SyncWorker.class, 15, TimeUnit.MINUTES)
                  .setInputData(new Data.Builder().putBoolean("capture_only", true).build())
                  .addTag("aven")
                  .build());
    }
  }

  public static void capture(Context context, long delay) {
    if (AvenApplication.get() != null && AvenApplication.get().enabled())
      WorkManager.getInstance(context)
          .enqueueUniqueWork(
              "aven-capture",
              ExistingWorkPolicy.APPEND_OR_REPLACE,
              new OneTimeWorkRequest.Builder(SyncWorker.class)
                  .setInitialDelay(delay, TimeUnit.SECONDS)
                  .setInputData(new Data.Builder().putBoolean("capture_only", true).build())
                  .addTag("aven")
                  .build());
  }

  public static void upload(Context context) {
    if (AvenApplication.get() != null && AvenApplication.get().enabled())
      WorkManager.getInstance(context)
          .enqueueUniqueWork(
              "aven-upload",
              ExistingWorkPolicy.APPEND_OR_REPLACE,
              new OneTimeWorkRequest.Builder(SyncWorker.class)
                  .setConstraints(
                      new Constraints.Builder()
                          .setRequiredNetworkType(NetworkType.CONNECTED)
                          .build())
                  .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                  .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
                  .addTag("aven")
                  .build());
  }

  public static void cancel(Context context) {
    WorkManager.getInstance(context).cancelAllWorkByTag("aven");
  }
}
