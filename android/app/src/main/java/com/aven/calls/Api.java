package com.aven.calls;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import org.json.*;

public final class Api {
  public static final class Failure extends IOException {
    public final int status;
    public final String code;
    public final long retrySeconds;

    Failure(int status, String code, String message, String retry) {
      super(message);
      this.status = status;
      this.code = code;
      retrySeconds = SyncPolicy.retryAfterSeconds(retry);
    }
  }

  private final SecureSession session;
  private final java.util.concurrent.atomic.AtomicInteger cancellationEpoch =
      new java.util.concurrent.atomic.AtomicInteger();

  public Api(SecureSession session) {
    this.session = session;
  }

  private record Reply(JSONObject body, String cookie) {}

  private final okhttp3.OkHttpClient client =
      new okhttp3.OkHttpClient.Builder()
          .connectTimeout(15, java.util.concurrent.TimeUnit.SECONDS)
          .readTimeout(20, java.util.concurrent.TimeUnit.SECONDS)
          .writeTimeout(20, java.util.concurrent.TimeUnit.SECONDS)
          .callTimeout(75, java.util.concurrent.TimeUnit.SECONDS)
          .followRedirects(false)
          .followSslRedirects(false)
          .retryOnConnectionFailure(false)
          .build();

  public void cancelActive() {
    cancellationEpoch.incrementAndGet();
    client.dispatcher().cancelAll();
  }

  private Reply exchange(
      String base,
      String method,
      String path,
      JSONObject body,
      String access,
      String cookie,
      File file,
      String filename,
      String callId)
      throws Exception {
    okhttp3.RequestBody payload = null;
    if (file != null) {
      String safe = filename.replaceAll("[\\r\\n\\\"\\\\]", "_");
      if (safe.length() > 180) safe = safe.substring(safe.length() - 180);
      payload =
          new okhttp3.MultipartBody.Builder()
              .setType(okhttp3.MultipartBody.FORM)
              .addFormDataPart("phone_call_id", callId)
              .addFormDataPart(
                  "file",
                  safe,
                  okhttp3.RequestBody.create(
                      file, okhttp3.MediaType.get("application/octet-stream")))
              .build();
    } else if (body != null)
      payload =
          okhttp3.RequestBody.create(
              body.toString(), okhttp3.MediaType.get("application/json; charset=utf-8"));
    okhttp3.Request.Builder request =
        new okhttp3.Request.Builder()
            .url(base + "/api" + path)
            .method(method, payload)
            .header("X-Requested-With", "TalkoCRM")
            .header("Accept", "application/json");
    if (!access.isEmpty()) request.header("Authorization", "Bearer " + access);
    if (!cookie.isEmpty()) request.header("Cookie", "crm_refresh=" + cookie);
    try (okhttp3.Response response = client.newCall(request.build()).execute()) {
      int status = response.code();
      String text = "";
      if (response.body() != null)
        try (InputStream input = response.body().byteStream();
            ByteArrayOutputStream output = new ByteArrayOutputStream()) {
          byte[] bytes = new byte[8192];
          int count;
          while ((count = input.read(bytes)) != -1) {
            if (output.size() + count > 2 * 1024 * 1024)
              throw new IOException("Server response exceeds the expected size");
            output.write(bytes, 0, count);
          }
          text = new String(output.toByteArray(), StandardCharsets.UTF_8);
        }
      JSONObject data;
      try {
        data = text.isEmpty() ? new JSONObject() : new JSONObject(text);
      } catch (JSONException error) {
        throw new Failure(
            status, "invalid_response", "The server did not return valid CRM data.", "");
      }
      if (status < 200 || status >= 300) {
        JSONObject error = data.optJSONObject("error");
        throw new Failure(
            status,
            error == null ? "request_failed" : error.optString("code"),
            error == null
                ? "Request failed (" + status + "). Check the CRM address."
                : error.optString("message", "Request failed"),
            response.header("Retry-After"));
      }
      String refresh = "";
      for (String value : response.headers("Set-Cookie"))
        if (value.startsWith("crm_refresh=")) refresh = value.substring(12).split(";", 2)[0];
      return new Reply(data, refresh);
    }
  }

  public JSONObject login(
      String server, String phone, String password, String challenge, String code)
      throws Exception {
    // Start an explicit sign-in on a fresh connection; never replay the login POST.
    client.connectionPool().evictAll();
    JSONObject body = new JSONObject().put("phone", phone).put("password", password);
    if (!challenge.isEmpty()) body.put("challenge", challenge).put("code", code);
    Reply reply = exchange(server, "POST", "/auth/login", body, "", "", null, "", "");
    if (reply.body.optBoolean("challenge_required")) return reply.body;
    String role = reply.body.optString("role");
    if (!role.equals("manager") && !role.equals("telecaller")) {
      try {
        exchange(server, "POST", "/auth/logout", new JSONObject(), "", reply.cookie, null, "", "");
      } catch (Exception ignored) {
      }
      throw new Failure(
          403,
          "unsupported_role",
          "Sign in with a telecaller or manager account to sync assigned customer calls.",
          "");
    }
    JSONObject user = reply.body.getJSONObject("user"),
        org = reply.body.getJSONObject("organization");
    if (reply.cookie.isEmpty())
      throw new IOException("The server did not issue a refresh session.");
    boolean changed =
        !user.getString("id").equals(session.get("user_id"))
            || !org.getString("id").equals(session.get("org_id"))
            || !server.equals(session.get("server"));
    if (changed) AvenApplication.get().resetLocalData();
    session.putAll(
        new JSONObject()
            .put("server", server)
            .put("user_id", user.getString("id"))
            .put("org_id", org.getString("id"))
            .put("name", user.getString("name"))
            .put("org_name", org.getString("name"))
            .put("role", role)
            .put("access", reply.body.getString("access_token"))
            .put("refresh", reply.cookie));
    return reply.body;
  }

  private synchronized void refresh() throws Exception {
    try {
      Reply reply =
          exchange(
              session.get("server"),
              "POST",
              "/auth/refresh",
              new JSONObject(),
              "",
              session.get("refresh"),
              null,
              "",
              "");
      if (reply.cookie.isEmpty()) throw new IOException("The refresh session was not rotated");
      if (!reply.body.getJSONObject("user").getString("id").equals(session.get("user_id"))
          || !reply
              .body
              .getJSONObject("organization")
              .getString("id")
              .equals(session.get("org_id"))) {
        session.invalidate();
        throw new Failure(
            401, "identity_changed", "The server session changed accounts. Sign in again.", "");
      }
      session.putAll(
          new JSONObject()
              .put("access", reply.body.getString("access_token"))
              .put("refresh", reply.cookie));
    } catch (Failure e) {
      if (e.status == 401) {
        session.invalidate();
        AvenApplication.get().store.meta("status", "Sign in again to resume queued uploads.");
      }
      throw e;
    }
  }

  public JSONObject json(String method, String path, JSONObject body) throws Exception {
    return authorized(method, path, body, null, "", "", true, true);
  }

  public JSONObject upload(String lead, String call, File file, String name) throws Exception {
    return authorized("POST", "/leads/" + lead + "/files", null, file, name, call, true, false);
  }

  private JSONObject authorized(
      String method,
      String path,
      JSONObject body,
      File file,
      String name,
      String call,
      boolean retry,
      boolean reconnect)
      throws Exception {
    int startedEpoch = cancellationEpoch.get();
    if (!session.authenticated())
      throw new Failure(401, "sign_in_required", "Sign in again to resume syncing.", "");
    try {
      return exchange(
              session.get("server"),
              method,
              path,
              body,
              session.get("access"),
              session.get("refresh"),
              file,
              name,
              call)
          .body;
    } catch (Failure failure) {
      if (failure.status == 429)
        AvenApplication.get()
            .store
            .meta(
                "retry_after_ms",
                String.valueOf(System.currentTimeMillis() + failure.retrySeconds * 1000));
      if (failure.status == 401 && retry) {
        refresh();
        return authorized(method, path, body, file, name, call, false, reconnect);
      }
      throw failure;
    } catch (IOException disconnected) {
      // A server may close an idle keep-alive socket between calls. Only replay a read,
      // on a fresh connection; mutations and rotating refresh cookies keep explicit retries.
      if (reconnect
          && "GET".equals(method)
          && !Thread.currentThread().isInterrupted()
          && startedEpoch == cancellationEpoch.get()) {
        client.connectionPool().evictAll();
        return authorized(method, path, body, file, name, call, retry, false);
      }
      throw disconnected;
    }
  }

  public void logout() throws Exception {
    if (session.authenticated())
      exchange(
          session.get("server"),
          "POST",
          "/auth/logout",
          new JSONObject(),
          "",
          session.get("refresh"),
          null,
          "",
          "");
  }
}
