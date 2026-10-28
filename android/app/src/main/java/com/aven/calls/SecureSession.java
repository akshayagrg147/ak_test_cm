package com.aven.calls;

import android.content.*;
import android.security.keystore.*;
import android.util.Base64;
import java.security.KeyStore;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;
import org.json.JSONObject;

/** Tokens and the rotating refresh cookie remain in Keystore-encrypted app-private storage. */
public final class SecureSession {
  private final Context context;
  private JSONObject values;

  public SecureSession(Context context) {
    this.context = context.getApplicationContext();
  }

  private SecretKey key() throws Exception {
    KeyStore store = KeyStore.getInstance("AndroidKeyStore");
    store.load(null);
    String alias = "aven-session-v1";
    if (!store.containsAlias(alias)) {
      KeyGenerator generator =
          KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
      generator.init(
          new KeyGenParameterSpec.Builder(
                  alias, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
              .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
              .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
              .build());
      generator.generateKey();
    }
    return (SecretKey) store.getKey(alias, null);
  }

  private synchronized JSONObject data() {
    if (values != null) return values;
    try {
      String stored =
          context
              .getSharedPreferences("secure_session", Context.MODE_PRIVATE)
              .getString("data", "");
      if (stored.isEmpty()) return values = new JSONObject();
      String[] parts = stored.split(":");
      Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
      cipher.init(
          Cipher.DECRYPT_MODE,
          key(),
          new GCMParameterSpec(128, Base64.decode(parts[0], Base64.NO_WRAP)));
      return values =
          new JSONObject(
              new String(
                  cipher.doFinal(Base64.decode(parts[1], Base64.NO_WRAP)),
                  java.nio.charset.StandardCharsets.UTF_8));
    } catch (Exception error) {
      context.getSharedPreferences("secure_session", Context.MODE_PRIVATE).edit().clear().commit();
      return values = new JSONObject();
    }
  }

  public synchronized String get(String name) {
    return data().optString(name, "");
  }

  public synchronized boolean authenticated() {
    return !get("refresh").isEmpty() && !get("user_id").isEmpty();
  }

  public synchronized void put(String name, Object value) {
    try {
      putAll(new JSONObject().put(name, value));
    } catch (org.json.JSONException error) {
      throw new IllegalStateException(error);
    }
  }

  public synchronized void putAll(JSONObject changes) {
    try {
      JSONObject next = new JSONObject(data().toString());
      java.util.Iterator<String> keys = changes.keys();
      while (keys.hasNext()) {
        String key = keys.next();
        next.put(key, changes.get(key));
      }
      Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
      cipher.init(Cipher.ENCRYPT_MODE, key());
      String encoded =
          Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP)
              + ":"
              + Base64.encodeToString(
                  cipher.doFinal(next.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8)),
                  Base64.NO_WRAP);
      if (!context
          .getSharedPreferences("secure_session", Context.MODE_PRIVATE)
          .edit()
          .putString("data", encoded)
          .commit()) throw new IllegalStateException("Could not save sign-in securely");
      values = next;
    } catch (Exception error) {
      throw new IllegalStateException("Secure storage is unavailable. Sign in again.", error);
    }
  }

  public synchronized void invalidate() {
    try {
      putAll(new JSONObject().put("access", "").put("refresh", ""));
    } catch (org.json.JSONException impossible) {
      throw new IllegalStateException(impossible);
    }
  }

  public synchronized void clear() {
    if (!context
        .getSharedPreferences("secure_session", Context.MODE_PRIVATE)
        .edit()
        .clear()
        .commit())
      throw new IllegalStateException(
          "Could not remove local credentials. Free device storage and sign out again.");
    values = new JSONObject();
  }
}
