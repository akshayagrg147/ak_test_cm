package com.aven.calls;

import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.os.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** A bounded, user-started data transfer. Never a hidden or permanent call-recording service. */
public class SyncService extends Service {
  public static final AtomicBoolean active = new AtomicBoolean(false);
  private final ExecutorService executor = Executors.newSingleThreadExecutor();
  private Future<?> task;
  private final Handler handler = new Handler(Looper.getMainLooper());

  @Override
  public void onCreate() {
    super.onCreate();
    NotificationManager manager = getSystemService(NotificationManager.class);
    manager.createNotificationChannel(
        new NotificationChannel(
            "aven-sync", "Call sync progress", NotificationManager.IMPORTANCE_LOW));
  }

  @Override
  public int onStartCommand(Intent intent, int flags, int id) {
    if (!AvenApplication.get().enabled()) {
      stopSelf();
      return START_NOT_STICKY;
    }
    Notification notification =
        new Notification.Builder(this, "aven-sync")
            .setSmallIcon(R.drawable.ic_aven)
            .setContentTitle("Syncing work calls")
            .setContentText("Sending assigned-customer calls and available recordings to your CRM.")
            .setOngoing(true)
            .setContentIntent(
                PendingIntent.getActivity(
                    this,
                    0,
                    new Intent(this, MainActivity.class),
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE))
            .build();
    if (Build.VERSION.SDK_INT >= 29)
      startForeground(31, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
    else startForeground(31, notification);
    if (!active.compareAndSet(false, true)) return START_NOT_STICKY;
    handler.postDelayed(this::stopTransfer, 120_000);
    task =
        executor.submit(
            () -> {
              try {
                SyncEngine.sync(AvenApplication.get());
              } catch (Exception error) {
                AvenApplication.get()
                    .store
                    .meta(
                        "status",
                        error.getMessage() == null
                            ? "Sync interrupted; pending uploads are kept."
                            : error.getMessage());
                SyncScheduler.upload(this);
              } finally {
                active.set(false);
                stopForeground(STOP_FOREGROUND_REMOVE);
                stopSelf();
              }
            });
    return START_NOT_STICKY;
  }

  private void stopTransfer() {
    AvenApplication.get().api.cancelActive();
    if (task != null) task.cancel(true);
    active.set(false);
    SyncScheduler.upload(this);
    stopForeground(STOP_FOREGROUND_REMOVE);
    stopSelf();
  }

  @Override
  public void onTimeout(int startId, int foregroundServiceType) {
    stopTransfer();
  }

  @Override
  public void onDestroy() {
    handler.removeCallbacksAndMessages(null);
    if (task != null) task.cancel(true);
    executor.shutdownNow();
    active.set(false);
    super.onDestroy();
  }

  @Override
  public IBinder onBind(Intent intent) {
    return null;
  }
}
