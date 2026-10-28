package com.aven.calls;

import android.database.Cursor;
import android.database.MatrixCursor;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.provider.DocumentsContract.Document;
import android.provider.DocumentsContract.Root;
import android.provider.DocumentsProvider;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/** A real DocumentsProvider/ContentResolver path with synthetic audio for emulator QA. */
public class RecordingDocuments extends DocumentsProvider {
  /** QA-only setup bridge; DocumentsProvider itself keeps Android's mandatory permission. */
  public static class Control extends android.content.ContentProvider {
    @Override
    public boolean onCreate() {
      return true;
    }

    @Override
    public Bundle call(String method, String arg, Bundle extras) {
      return getContext()
          .getContentResolver()
          .call(
              android.net.Uri.parse("content://com.aven.calls.qa.documents"), method, arg, extras);
    }

    @Override
    public Cursor query(android.net.Uri u, String[] p, String s, String[] a, String o) {
      return null;
    }

    @Override
    public String getType(android.net.Uri u) {
      return null;
    }

    @Override
    public android.net.Uri insert(android.net.Uri u, android.content.ContentValues v) {
      return null;
    }

    @Override
    public int delete(android.net.Uri u, String s, String[] a) {
      return 0;
    }

    @Override
    public int update(android.net.Uri u, android.content.ContentValues v, String s, String[] a) {
      return 0;
    }
  }

  private String name = "unmatched.wav";
  private long modified = 0;
  private File audio;

  @Override
  public boolean onCreate() {
    return true;
  }

  @Override
  public Bundle call(String method, String arg, Bundle extras) {
    if ("configure".equals(method)) {
      name = extras.getString("name");
      modified = extras.getLong("modified");
      try {
        audio = new File(getContext().getCacheDir(), "synthetic-call.wav");
        int size = extras.getInt("size", 16000);
        ByteBuffer wav = ByteBuffer.allocate(44 + size).order(ByteOrder.LITTLE_ENDIAN);
        wav.put("RIFF".getBytes())
            .putInt(36 + size)
            .put("WAVEfmt ".getBytes())
            .putInt(16)
            .putShort((short) 1)
            .putShort((short) 1)
            .putInt(8000)
            .putInt(16000)
            .putShort((short) 2)
            .putShort((short) 16)
            .put("data".getBytes())
            .putInt(size);
        byte[] pcm = new byte[size];
        new java.util.Random(modified).nextBytes(pcm);
        wav.put(pcm);
        try (FileOutputStream out = new FileOutputStream(audio)) {
          if (!extras.getBoolean("empty", false)) out.write(wav.array());
        }
      } catch (Exception error) {
        throw new IllegalStateException(error);
      }
      getContext()
          .grantUriPermission(
              extras.getString("package"),
              android.net.Uri.parse("content://com.aven.calls.qa.documents/tree/root"),
              android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION
                  | android.content.Intent.FLAG_GRANT_PREFIX_URI_PERMISSION
                  | android.content.Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
      return new Bundle();
    }
    return super.call(method, arg, extras);
  }

  private Cursor document(String id, String[] projection) {
    String[] columns =
        projection == null
            ? new String[] {
              Document.COLUMN_DOCUMENT_ID,
              Document.COLUMN_DISPLAY_NAME,
              Document.COLUMN_MIME_TYPE,
              Document.COLUMN_FLAGS,
              Document.COLUMN_SIZE,
              Document.COLUMN_LAST_MODIFIED
            }
            : projection;
    MatrixCursor cursor = new MatrixCursor(columns);
    MatrixCursor.RowBuilder row = cursor.newRow();
    for (String col : columns)
      row.add(
          switch (col) {
            case Document.COLUMN_DOCUMENT_ID -> id;
            case Document.COLUMN_DISPLAY_NAME -> "root".equals(id) ? "QA recordings" : name;
            case Document.COLUMN_MIME_TYPE ->
                "root".equals(id) ? Document.MIME_TYPE_DIR : "audio/wav";
            case Document.COLUMN_SIZE -> audio == null ? 0 : audio.length();
            case Document.COLUMN_LAST_MODIFIED -> modified;
            case Document.COLUMN_FLAGS -> 0;
            default -> null;
          });
    return cursor;
  }

  @Override
  public Cursor queryRoots(String[] projection) {
    return new MatrixCursor(new String[] {Root.COLUMN_ROOT_ID});
  }

  @Override
  public Cursor queryDocument(String id, String[] projection) {
    return document(id, projection);
  }

  @Override
  public Cursor queryChildDocuments(String id, String[] projection, String sort) {
    return document("audio", projection);
  }

  @Override
  public ParcelFileDescriptor openDocument(
      String id, String mode, android.os.CancellationSignal signal)
      throws java.io.FileNotFoundException {
    if (!"audio".equals(id)) throw new java.io.FileNotFoundException("QA document missing");
    return ParcelFileDescriptor.open(audio, ParcelFileDescriptor.MODE_READ_ONLY);
  }

  @Override
  public boolean isChildDocument(String parent, String child) {
    return "root".equals(parent) && "audio".equals(child);
  }
}
