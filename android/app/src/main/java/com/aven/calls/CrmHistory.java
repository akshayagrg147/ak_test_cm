package com.aven.calls;

import java.io.IOException;
import org.json.JSONObject;

/** Reads the same permission-filtered lead history used by the web CRM. */
public final class CrmHistory {
  private CrmHistory() {}
  public record Page(JSONObject lead, JSONObject history) {}

  public static String identity(AvenApplication app) {
    return app.session.get("server") + "\n" + app.session.get("org_id") + "\n"
        + app.session.get("user_id");
  }

  public static void check(AvenApplication app, String owner) throws IOException {
    if (Thread.currentThread().isInterrupted() || !app.session.authenticated()
        || !owner.equals(identity(app)))
      throw new IOException("Your account changed. Open the lead again after signing in.");
  }

  public static Page load(AvenApplication app, String id, int page) throws Exception {
    if (!id.matches("[A-Za-z0-9_-]{1,80}") || page < 1) throw new IOException("Invalid lead request.");
    String owner = identity(app);
    check(app, owner);
    JSONObject lead = app.api.json("GET", "/leads/" + id, null);
    check(app, owner);
    if (!id.equals(lead.getString("id"))
        || !app.session.get("org_id").equals(lead.getString("org_id")))
      throw new IOException("The CRM returned a different lead. Please try again.");
    JSONObject history = app.api.json("GET", "/leads/" + id + "/history?page=" + page + "&size=20", null);
    check(app, owner);
    for (String key : new String[] {"phone_calls", "manual_calls", "notes", "tasks", "files", "activity"}) {
      var records = history.getJSONArray(key);
      for (int i = 0; i < records.length(); i++) {
        JSONObject item = records.getJSONObject(i);
        if ((item.has("org_id") && !app.session.get("org_id").equals(item.getString("org_id")))
            || (item.has("lead_id") && !id.equals(item.optString("lead_id")))
            || (key.equals("activity") && item.has("entity_id") && !id.equals(item.optString("entity_id"))))
          throw new IOException("The CRM returned history for a different lead.");
      }
    }
    history.getJSONObject("pagination").getJSONObject("totals");
    return new Page(lead, history);
  }
}
