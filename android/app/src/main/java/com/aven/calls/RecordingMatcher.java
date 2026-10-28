package com.aven.calls;

import java.text.SimpleDateFormat;
import java.time.*;
import java.time.format.*;
import java.util.*;
import java.util.regex.*;

/**
 * Matches a recording file to a CRM-verified call using timestamp only.
 * The calls list is already filtered to CRM customers, so number check in filename is unnecessary.
 */
public final class RecordingMatcher {
  private static final Pattern TIME =
      Pattern.compile("(?<!\\d)(20\\d{6}|\\d{6})[_ -](\\d{6})(?!\\d)");
  private static final Pattern NUMBER =
      Pattern.compile("(?<![0-9])\\+?[0-9][0-9 ()-]{8,20}[0-9](?![0-9])");

  private static final long WINDOW_MS = 30_000;

  public record CallRef(String key, String phone, long start, long duration, String result) {}

  public record Match(String key, String reason) {}

  private RecordingMatcher() {}

  public static Match match(
      String filename, long modified, List<CallRef> calls, String callingCode, ZoneId zone) {

    // Step 1: extract timestamp from filename (required)
    Matcher time = TIME.matcher(filename);
    if (!time.find())
      return new Match(null, "No timestamp found in filename.");
    long stamp;
    try {
      String date = time.group(1);
      if (date.length() == 6) date = "20" + date;
      LocalDateTime local =
          LocalDateTime.parse(
              date + time.group(2),
              DateTimeFormatter.ofPattern("uuuuMMddHHmmss")
                  .withResolverStyle(ResolverStyle.STRICT));
      List<ZoneOffset> offsets = zone.getRules().getValidOffsets(local);
      if (offsets.size() != 1)
        return new Match(null, "Ambiguous timezone; select manually.");
      stamp = local.toInstant(offsets.get(0)).toEpochMilli();
    } catch (Exception ignored) {
      return new Match(null, "Unrecognized date in filename.");
    }

    SimpleDateFormat fmt = new SimpleDateFormat("HH:mm:ss", Locale.US);
    String stampStr = fmt.format(new java.util.Date(stamp));

    // Step 2: match by timestamp against CRM-verified calls in DB
    // stamp must fall within [call.start - WINDOW, call.end + WINDOW]
    List<CallRef> candidates = new ArrayList<>();
    for (CallRef call : calls) {
      long end = call.start + call.duration * 1000;
      if ("answered".equals(call.result)
          && call.duration > 0
          && stamp >= call.start - WINDOW_MS
          && stamp <= end + WINDOW_MS
          && modified >= call.start - WINDOW_MS
          && modified <= end + 600_000)
        candidates.add(call);
    }

    if (candidates.isEmpty()) {
      String nearest = "";
      if (!calls.isEmpty()) {
        CallRef n = calls.stream()
            .min(Comparator.comparingLong(c -> Math.abs(c.start - stamp)))
            .orElse(null);
        if (n != null)
          nearest = " nearestCall=[" + fmt.format(new java.util.Date(n.start))
              + "-" + fmt.format(new java.util.Date(n.start + n.duration * 1000))
              + " result=" + n.result + " dur=" + n.duration + "s]";
      }
      return new Match(null, "No matching CRM call. stamp=" + stampStr + nearest);
    }

    // Step 3: if multiple candidates, pick the one closest to stamp
    candidates.sort(Comparator.comparingLong(c -> Math.abs(c.start - stamp)));
    CallRef best = candidates.get(0);
    String reason = "matched stamp=" + stampStr
        + " candidates=" + candidates.size()
        + " picked=" + fmt.format(new java.util.Date(best.start));
    return new Match(best.key, reason);
  }

  public static boolean supported(String name) {
    return name != null && name.toLowerCase(Locale.ROOT).matches(".*\\.(m4a|mp3|wav|ogg|flac)$");
  }
}
