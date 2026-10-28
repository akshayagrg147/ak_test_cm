package com.aven.calls;

public final class SyncPolicy {
  public static final long MAX_AGE_MS = 30L * 24 * 60 * 60 * 1000;
  public static final long DEFAULT_RECORDING_LIMIT = 64L * 1024 * 1024;

  private SyncPolicy() {}

  public static boolean retryable(int code) {
    return code == 0 || code == 408 || code == 425 || code == 429 || code >= 500;
  }

  public static boolean inWindow(long start, long now) {
    return start >= now - MAX_AGE_MS && start <= now + 300_000;
  }

  public static String direction(int type) {
    return type == 2 ? "outgoing" : "incoming";
  }

  public static String result(int type, long seconds) {
    if (type == 3) return "missed";
    if (type == 5 || type == 6) return "rejected";
    if (type == 1 || (type == 2 && seconds > 0)) return "answered";
    return "unknown";
  }

  public static boolean supportedType(int type) {
    return type == 1 || type == 2 || type == 3 || type == 5 || type == 6 || type == 7;
  }

  public static String callKey(long row, long start) {
    return "log-" + row + "-" + start;
  }

  public static long retryAfterSeconds(String header) {
    try {
      return Math.max(10, Math.min(3600, Long.parseLong(header)));
    } catch (Exception ignored) {
      return 30;
    }
  }
}
