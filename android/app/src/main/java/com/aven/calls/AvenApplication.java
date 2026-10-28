package com.aven.calls;

import android.app.Application;
import android.content.*;
import java.io.File;
import java.util.UUID;

public class AvenApplication extends Application {
  private static AvenApplication instance;
  public SecureSession session;
  public CallStore store;
  public Api api;

  @Override
  public void onCreate() {
    super.onCreate();
    instance = this;
    session = new SecureSession(this);
    store = new CallStore(this);
    api = new Api(session);
    if (store.meta("installation").isEmpty())
      store.meta("installation", UUID.randomUUID().toString());
    File[] leftovers = getCacheDir().listFiles((dir, name) -> name.startsWith("aven-upload-"));
    if (leftovers != null)
      for (File file : leftovers)
        if (System.currentTimeMillis() - file.lastModified() > 3600000) file.delete();
    SyncScheduler.restore(this);
  }

  public static AvenApplication get() {
    return instance;
  }

  public void resetLocalData() {
    SyncScheduler.cancel(this);
    for (android.content.UriPermission permission :
        getContentResolver().getPersistedUriPermissions())
      try {
        getContentResolver()
            .releasePersistableUriPermission(
                permission.getUri(), Intent.FLAG_GRANT_READ_URI_PERMISSION);
      } catch (SecurityException ignored) {
      }
    store.clear();
    store.meta("installation", UUID.randomUUID().toString());
  }

  public boolean enabled() {
    return "true".equals(store.meta("enabled")) && session.authenticated();
  }
}
