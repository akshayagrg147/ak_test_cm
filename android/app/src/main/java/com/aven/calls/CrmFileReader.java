package com.aven.calls;

import java.io.*;
import java.security.MessageDigest;
import java.util.concurrent.TimeUnit;
import org.json.JSONObject;

/** Authenticated, bounded downloads to private temporary storage; tokens never enter a URL. */
public final class CrmFileReader {
  private static final String PROCESS_PREFIX = "aven-preview-" + java.util.UUID.randomUUID() + "-";

  public CrmFileReader() { clearPreviousProcessPreviews(AvenApplication.get()); }

  public static synchronized void clearPreviousProcessPreviews(AvenApplication app) {
    File[] previous = app.getCacheDir().listFiles((folder, name) ->
        name.startsWith("aven-preview-") && !name.startsWith(PROCESS_PREFIX));
    if (previous != null) for (File file : previous) if (file.isFile()) file.delete();
  }

  private final okhttp3.OkHttpClient client = new okhttp3.OkHttpClient.Builder()
      .connectTimeout(15, TimeUnit.SECONDS).readTimeout(20, TimeUnit.SECONDS)
      .callTimeout(90, TimeUnit.SECONDS).followRedirects(false).followSslRedirects(false)
      .retryOnConnectionFailure(false).build();

  public void cancel() { client.dispatcher().cancelAll(); }

  public File download(AvenApplication app, JSONObject attachment) throws Exception {
    String id = attachment.getString("id"), owner = CrmHistory.identity(app);
    if (!id.matches("[A-Za-z0-9_-]{1,80}")) throw new IOException("Invalid file reference.");
    if (attachment.optLong("size") > SyncPolicy.DEFAULT_RECORDING_LIMIT)
      throw new IOException("This file exceeds the 64 MB playback limit.");
    CrmHistory.check(app, owner);
    app.api.json("GET", "/auth/me", null);
    CrmHistory.check(app, owner);
    for (int attempt = 0; attempt < 2; attempt++) {
      okhttp3.Request request = new okhttp3.Request.Builder()
          .url(app.session.get("server") + "/api/files/" + id)
          .header("Authorization", "Bearer " + app.session.get("access"))
          .header("X-Requested-With", "TalkoCRM").build();
      try (okhttp3.Response response = client.newCall(request).execute()) {
        if (response.code() == 401 && attempt == 0) {
          app.api.json("GET", "/auth/me", null);
          CrmHistory.check(app, owner);
          continue;
        }
        if (!response.isSuccessful())
          throw new Api.Failure(response.code(), "file_unavailable",
              response.code() == 404 || response.code() == 403
                  ? "This file is no longer available to your account. Refresh the lead."
                  : "Couldn't load this file. Check your connection and try again.", "");
        if (response.body() == null) throw new IOException("The CRM returned an empty file.");
        long limit = SyncPolicy.DEFAULT_RECORDING_LIMIT;
        if (response.body().contentLength() > limit) throw new IOException("This file exceeds the 64 MB playback limit.");
        File temp = File.createTempFile(PROCESS_PREFIX, ".tmp", app.getCacheDir());
        boolean complete = false;
        try {
          MessageDigest digest = MessageDigest.getInstance("SHA-256");
          long total = 0;
          try (InputStream input = response.body().byteStream(); OutputStream output = new FileOutputStream(temp)) {
            byte[] bytes = new byte[16384]; int n;
            while ((n = input.read(bytes)) != -1) {
              CrmHistory.check(app, owner);
              total += n;
              if (total > limit) throw new IOException("This file exceeds the 64 MB playback limit.");
              output.write(bytes, 0, n); digest.update(bytes, 0, n);
            }
          }
          if (total == 0 || (attachment.optLong("size") > 0 && total != attachment.optLong("size")))
            throw new IOException("The file was incomplete. Try again.");
          StringBuilder hex = new StringBuilder();
          for (byte b : digest.digest()) hex.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
          String expected = attachment.optString("digest");
          if (!expected.isEmpty() && !expected.equalsIgnoreCase(hex.toString()))
            throw new IOException("The file could not be verified. Try again.");
          CrmHistory.check(app, owner);
          complete = true;
          return temp;
        } finally {
          if (!complete) temp.delete();
        }
      }
    }
    throw new IOException("Sign in again to access this file.");
  }
}
