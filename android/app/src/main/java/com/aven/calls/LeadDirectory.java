package com.aven.calls;

import java.io.IOException;
import java.io.InterruptedIOException;
import java.net.URLEncoder;
import java.util.HashSet;
import java.util.Set;
import org.json.JSONArray;
import org.json.JSONObject;

/** Reads assignments without enabling call collection or requesting phone permissions. */
public final class LeadDirectory {
  private LeadDirectory() {}

  private static String identity(AvenApplication app) throws InterruptedIOException {
    if (Thread.currentThread().isInterrupted() || !app.session.authenticated())
      throw new InterruptedIOException("Sign in again to load your leads.");
    return app.session.get("server") + "\n" + app.session.get("org_id") + "\n"
        + app.session.get("user_id");
  }

  public static void refresh(AvenApplication app) throws Exception {
    SyncEngine.LOCK.lockInterruptibly();
    try {
      String account = identity(app), cursor = "";
      JSONArray all = new JSONArray();
      Set<String> seen = new HashSet<>();
      for (int page = 0; page < 250; page++) {
        if (!account.equals(identity(app))) throw new IOException("Account changed. Reload your leads.");
        JSONObject response = app.api.json("GET", "/phone-calls/contacts?after="
            + URLEncoder.encode(cursor, "UTF-8"), null);
        if (!account.equals(identity(app))
            || !response.getString("user_id").equals(app.session.get("user_id"))
            || !response.getString("organization_id").equals(app.session.get("org_id")))
          throw new IOException("Account changed. Reload your leads.");
        JSONArray items = response.getJSONArray("items");
        for (int i = 0; i < items.length(); i++) all.put(items.getJSONObject(i));
        if (response.isNull("next_cursor") || response.optString("next_cursor").isEmpty()) {
          app.store.contacts(all);
          app.store.meta("contacts_at", String.valueOf(System.currentTimeMillis()));
          return;
        }
        cursor = response.getString("next_cursor");
        if (!seen.add(cursor)) throw new IOException("The server repeated a page. Your saved leads are kept.");
      }
      throw new IOException("The lead list is too large. Ask your manager to review assignments.");
    } finally {
      SyncEngine.LOCK.unlock();
    }
  }
}
