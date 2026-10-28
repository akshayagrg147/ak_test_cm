package com.aven.calls;

import android.content.*;
import android.database.Cursor;
import android.database.sqlite.*;
import java.util.*;
import org.json.*;

/**
 * SQLite commits the outbox before a network request; only per-item server receipts acknowledge it.
 */
public final class CallStore extends SQLiteOpenHelper {
  public CallStore(Context context) {
    super(context, "aven-calls.db", null, 1);
    setWriteAheadLoggingEnabled(true);
  }

  @Override
  public void onCreate(SQLiteDatabase db) {
    db.execSQL(
        "CREATE TABLE contacts(id TEXT PRIMARY KEY,name TEXT NOT NULL,phone TEXT NOT NULL,dnd"
            + " INTEGER NOT NULL)");
    db.execSQL("CREATE INDEX contacts_phone ON contacts(phone)");
    db.execSQL(
        "CREATE TABLE calls(id TEXT PRIMARY KEY,phone TEXT NOT NULL,name TEXT NOT NULL,started"
            + " INTEGER NOT NULL,duration INTEGER NOT NULL,direction TEXT NOT NULL,result TEXT NOT"
            + " NULL,state TEXT NOT NULL DEFAULT 'pending',server_id TEXT NOT NULL DEFAULT"
            + " '',lead_id TEXT NOT NULL DEFAULT '',recording_state TEXT NOT NULL DEFAULT"
            + " 'waiting',recording_uri TEXT NOT NULL DEFAULT '',recording_name TEXT NOT NULL"
            + " DEFAULT '',error TEXT NOT NULL DEFAULT '',updated INTEGER NOT NULL)");
    db.execSQL(
        "CREATE TABLE files(uri TEXT PRIMARY KEY,size INTEGER NOT NULL,modified INTEGER NOT"
            + " NULL,observed INTEGER NOT NULL)");
    db.execSQL("CREATE TABLE meta(name TEXT PRIMARY KEY,value TEXT NOT NULL)");
  }

  @Override
  public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
    throw new IllegalStateException(
        "Unsupported database upgrade; keep the existing data and update the app.");
  }

  public synchronized void clear() {
    SQLiteDatabase db = getWritableDatabase();
    db.beginTransaction();
    try {
      for (String table : List.of("calls", "contacts", "files", "meta"))
        db.delete(table, null, null);
      db.setTransactionSuccessful();
    } finally {
      db.endTransaction();
    }
  }

  public synchronized void meta(String name, String value) {
    ContentValues v = new ContentValues();
    v.put("name", name);
    v.put("value", value);
    getWritableDatabase().insertWithOnConflict("meta", null, v, SQLiteDatabase.CONFLICT_REPLACE);
  }

  public synchronized String meta(String name) {
    try (Cursor c =
        getReadableDatabase()
            .rawQuery("SELECT value FROM meta WHERE name=?", new String[] {name})) {
      return c.moveToFirst() ? c.getString(0) : "";
    }
  }

  public synchronized void contacts(JSONArray contacts) throws JSONException {
    SQLiteDatabase db = getWritableDatabase();
    db.beginTransaction();
    try {
      db.delete("contacts", null, null);
      for (int i = 0; i < contacts.length(); i++) {
        JSONObject item = contacts.getJSONObject(i);
        ContentValues v = new ContentValues();
        v.put("id", item.getString("id"));
        v.put("name", item.getString("name"));
        v.put("phone", item.getString("phone"));
        v.put("dnd", item.optBoolean("dnd") ? 1 : 0);
        db.insertOrThrow("contacts", null, v);
      }
      db.execSQL(
          "DELETE FROM calls WHERE phone NOT IN (SELECT phone FROM contacts) OR (lead_id!='' AND"
              + " lead_id NOT IN (SELECT id FROM contacts))");
      db.setTransactionSuccessful();
    } finally {
      db.endTransaction();
    }
  }

  public synchronized List<Map<String, String>> query(String sql, String... args) {
    List<Map<String, String>> rows = new ArrayList<>();
    try (Cursor c = getReadableDatabase().rawQuery(sql, args)) {
      while (c.moveToNext()) {
        Map<String, String> row = new LinkedHashMap<>();
        for (String col : c.getColumnNames())
          row.put(
              col,
              c.isNull(c.getColumnIndexOrThrow(col))
                  ? ""
                  : c.getString(c.getColumnIndexOrThrow(col)));
        rows.add(row);
      }
    }
    return rows;
  }

  public synchronized void capture(
      String id,
      String phone,
      String name,
      long start,
      long duration,
      String direction,
      String result) {
    SQLiteDatabase db = getWritableDatabase();
    db.beginTransaction();
    try {
      List<Map<String, String>> existing =
          query("SELECT duration,result,state,recording_state FROM calls WHERE id=?", id);
      if (existing.isEmpty()) {
        ContentValues v = new ContentValues();
        v.put("id", id);
        v.put("phone", phone);
        v.put("name", name);
        v.put("started", start);
        v.put("duration", duration);
        v.put("direction", direction);
        v.put("result", result);
        v.put(
            "recording_state",
            "answered".equals(result) && duration > 0 ? "waiting" : "unavailable");
        v.put("updated", System.currentTimeMillis());
        db.insertOrThrow("calls", null, v);
      } else {
        Map<String, String> old = existing.get(0);
        long previous = Long.parseLong(old.get("duration"));
        if (duration > previous
            || (!result.equals(old.get("result")) && !"unknown".equals(result))
            || Set.of("ambiguous", "excluded").contains(old.get("state"))) {
          ContentValues v = new ContentValues();
          v.put("duration", Math.max(previous, duration));
          v.put("result", "unknown".equals(result) ? old.get("result") : result);
          if ("answered".equals(result)
              && duration > 0
              && "unavailable".equals(old.get("recording_state")))
            v.put("recording_state", "waiting");
          v.put("state", "pending");
          v.put("updated", System.currentTimeMillis());
          db.update("calls", v, "id=?", new String[] {id});
        }
      }
      db.setTransactionSuccessful();
    } finally {
      db.endTransaction();
    }
  }

  public synchronized void update(String id, String... pairs) {
    ContentValues v = new ContentValues();
    for (int i = 0; i < pairs.length; i += 2) v.put(pairs[i], pairs[i + 1]);
    getWritableDatabase().update("calls", v, "id=?", new String[] {id});
  }

  public synchronized boolean stable(String uri, long size, long modified, long now) {
    List<Map<String, String>> existing = query("SELECT * FROM files WHERE uri=?", uri);
    if (!existing.isEmpty()
        && Long.parseLong(existing.get(0).get("size")) == size
        && Long.parseLong(existing.get(0).get("modified")) == modified)
      return now - Long.parseLong(existing.get(0).get("observed")) >= 3000;
    ContentValues v = new ContentValues();
    v.put("uri", uri);
    v.put("size", size);
    v.put("modified", modified);
    v.put("observed", now);
    getWritableDatabase().insertWithOnConflict("files", null, v, SQLiteDatabase.CONFLICT_REPLACE);
    return false;
  }

  public synchronized void prune(long before) {
    getWritableDatabase()
        .delete(
            "calls",
            "started<? AND state!='pending' AND NOT (state='synced' AND recording_state='queued')",
            new String[] {String.valueOf(before)});
  }

  /** Review/ambiguous rows must not create a self-scheduling upload loop. */
  public synchronized int pendingCount() {
    try (Cursor cursor =
        getReadableDatabase()
            .rawQuery(
                "SELECT count(*) FROM calls WHERE state='pending' OR (state='synced' AND"
                    + " recording_state='queued')",
                null)) {
      return cursor.moveToFirst() ? cursor.getInt(0) : 0;
    }
  }

  public synchronized int reviewCount() {
    try (Cursor cursor =
        getReadableDatabase()
            .rawQuery(
                "SELECT count(*) FROM calls WHERE state IN ('ambiguous','error') OR recording_state"
                    + " IN ('review','blocked','missing','too_large')",
                null)) {
      return cursor.moveToFirst() ? cursor.getInt(0) : 0;
    }
  }
}
