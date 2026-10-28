package com.aven.calls;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;
import android.content.pm.ServiceInfo;
import android.os.Build;
import androidx.annotation.NonNull;
import androidx.work.*;

public class SyncWorker extends Worker {
  public SyncWorker(@NonNull Context context, @NonNull WorkerParameters parameters) {
    super(context, parameters);
  }

  @NonNull
  @Override
  public ForegroundInfo getForegroundInfo() {
    Context context = getApplicationContext();
    NotificationManager manager = context.getSystemService(NotificationManager.class);
    manager.createNotificationChannel(
        new NotificationChannel("aven-sync", "Call sync progress", NotificationManager.IMPORTANCE_LOW));
    Notification notification =
        new Notification.Builder(context, "aven-sync")
            .setSmallIcon(R.drawable.ic_aven)
            .setContentTitle("Syncing call recording")
            .setContentText("Uploading recording to your CRM.")
            .setOngoing(true)
            .build();
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q)
      return new ForegroundInfo(32, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
    return new ForegroundInfo(32, notification);
  }

  @NonNull
  @Override
  public Result doWork() {
    AvenApplication app = AvenApplication.get();
    if (!app.enabled()) return Result.success();
    try {
      if (getInputData().getBoolean("capture_only", false)) {
        SyncEngine.capture(app);
        SyncScheduler.upload(getApplicationContext());
      } else SyncEngine.sync(app);
      return Result.success();
    } catch (Api.Failure error) {
      app.store.meta("status", error.getMessage());
      if (error.status == 401 || error.status == 403) return Result.failure();
      return SyncPolicy.retryable(error.status) ? Result.retry() : Result.failure();
    } catch (SecurityException error) {
      app.store.meta(
          "status",
          "Permission changed. Open Aven Calls to reconnect call-log or recording-folder access.");
      return Result.failure();
    } catch (Exception error) {
      if (BuildConfig.DEBUG) android.util.Log.w("AvenSync", "Sync deferred", error);
      app.store.meta(
          "status", "Sync interrupted. Work calls remain queued and will retry when possible.");
      return Result.retry();
    }
  }
}
