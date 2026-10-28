package com.aven.calls;

import static org.junit.Assert.*;

import java.time.*;
import java.util.*;
import org.junit.Test;

public class RecordingMatcherTest {
  private final long start = Instant.parse("2026-10-18T10:00:00Z").toEpochMilli();

  private RecordingMatcher.CallRef call(String key, String number, long offset, String result) {
    return new RecordingMatcher.CallRef(key, number, start + offset, 60, result);
  }

  @Test
  public void matchesNativePhoneAndDate() {
    assertEquals(
        "a",
        RecordingMatcher.match(
                "Call recording +919810060001_261018_100005.m4a",
                start + 60000,
                List.of(call("a", "+919810060001", 0, "answered")),
                "91",
                ZoneId.of("UTC"))
            .key());
    assertEquals(
        "a",
        RecordingMatcher.match(
                "Call 9810060001_20261018_100005.wav",
                start + 60000,
                List.of(call("a", "+919810060001", 0, "answered")),
                "91",
                ZoneId.of("UTC"))
            .key());
  }

  @Test
  public void matchesTimestampWithoutRequiringThePhoneInTheFilename() {
    // The user-tested ZIP intentionally accepts native contact-name recordings.
    for (String name :
        new String[] {
          "Call +919810060002_261018_100005.m4a",
          "Call customer_261018_100005.m4a",
          "261018_100005.m4a"
        })
      assertEquals(
          name,
          "a",
          RecordingMatcher.match(
                  name,
                  start + 60000,
                  List.of(call("a", "+919810060001", 0, "answered")),
                  "91",
                  ZoneId.of("UTC"))
              .key());
  }

  @Test
  public void refusesOldMissingAndInvalidTimestamps() {
    for (String name :
        new String[] {
          "Call +919810060001_261017_100005.m4a",
          "Call +919810060001.m4a",
          "Call +919810060001_261332_100005.m4a"
        })
      assertNull(
          name,
          RecordingMatcher.match(
                  name,
                  start + 60000,
                  List.of(call("a", "+919810060001", 0, "answered")),
                  "91",
                  ZoneId.of("UTC"))
              .key());
  }

  @Test
  public void choosesTheClosestStartAmongEligibleCalls() {
    assertEquals(
        "a",
        RecordingMatcher.match(
                "Call +919810060001_261018_100005.m4a",
                start + 60000,
                List.of(
                    call("a", "+919810060001", 0, "answered"),
                    call("b", "+919810060001", 30000, "answered")),
                "91",
                ZoneId.of("UTC"))
            .key());
    assertEquals(
        "b",
        RecordingMatcher.match(
                "Call customer_261018_100025.m4a",
                start + 60000,
                List.of(
                    call("a", "+919810060001", 0, "answered"),
                    call("b", "+919810060002", 30000, "answered")),
                "91",
                ZoneId.of("UTC"))
            .key());
  }

  @Test
  public void equalDistancesRetainTheInputOrderFromTheZip() {
    var first = call("a", "+919810060001", 0, "answered");
    var second = call("b", "+919810060002", 30000, "answered");
    assertEquals("a", match("261018_100015.wav", start + 60000, List.of(first, second)));
    assertEquals("b", match("261018_100015.wav", start + 60000, List.of(second, first)));
  }

  @Test
  public void timestampWindowIncludesThirtySecondsBeforeAndAfterTheCall() {
    var calls = List.of(call("a", "+919810060001", 0, "answered"));
    assertEquals("a", match("261018_095930.wav", start + 60000, calls));
    assertEquals("a", match("261018_100130.wav", start + 60000, calls));
    assertNull(match("261018_095929.wav", start + 60000, calls));
    assertNull(match("261018_100131.wav", start + 60000, calls));
  }

  @Test
  public void fileModificationWindowIncludesItsExactBoundaries() {
    var calls = List.of(call("a", "+919810060001", 0, "answered"));
    assertEquals("a", match("261018_100005.wav", start - 30000, calls));
    assertEquals("a", match("261018_100005.wav", start + 660000, calls));
    assertNull(match("261018_100005.wav", start - 30001, calls));
    assertNull(match("261018_100005.wav", start + 660001, calls));
  }

  @Test
  public void onlyAnsweredCallsWithPositiveDurationAreCandidates() {
    for (String result : new String[] {"missed", "rejected", "blocked", "unknown", "answered_elsewhere"})
      assertNull(match("261018_100005.wav", start + 60000,
          List.of(call("a", "+919810060001", 0, result))));
    assertNull(match("261018_100005.wav", start + 60000,
        List.of(new RecordingMatcher.CallRef("a", "+919810060001", start, 0, "answered"))));
    assertNull(match("261018_100005.wav", start + 60000,
        List.of(new RecordingMatcher.CallRef("a", "+919810060001", start, -1, "answered"))));
    assertNull(match("261018_100005.wav", start + 60000, List.of()));
  }

  @Test
  public void anIneligibleCloserCallDoesNotHideAnEligibleCall() {
    assertEquals("answered", match("261018_100005.wav", start + 60000,
        List.of(call("missed", "+919810060001", 5000, "missed"),
            call("answered", "+919810060002", 0, "answered"))));
  }

  @Test
  public void interpretsFilenameInTheProvidedPhoneTimezone() {
    assertEquals("a", RecordingMatcher.match("Customer_261018_153005.wav", start + 60000,
        List.of(call("a", "+919810060001", 0, "answered")), "91",
        ZoneId.of("Asia/Kolkata")).key());
    assertNull(match("Customer_261018_153005.wav", start + 60000,
        List.of(call("a", "+919810060001", 0, "answered"))));
  }

  private String match(String filename, long modified, List<RecordingMatcher.CallRef> calls) {
    return RecordingMatcher.match(filename, modified, calls, "91", ZoneId.of("UTC")).key();
  }

  @Test
  public void doesNotAttachAudioToMissedCalls() {
    assertNull(
        RecordingMatcher.match(
                "Call +919810060001_261018_100005.m4a",
                start + 60000,
                List.of(call("a", "+919810060001", 0, "missed")),
                "91",
                ZoneId.of("UTC"))
            .key());
  }

  @Test
  public void modifiedTimeCrossChecksFilenameDate() {
    assertNull(
        RecordingMatcher.match(
                "Call +919810060001_261018_100005.m4a",
                start - 86400000,
                List.of(call("a", "+919810060001", 0, "answered")),
                "91",
                ZoneId.of("UTC"))
            .key());
  }

  @Test
  public void dstAmbiguityRequiresManualSelection() {
    long repeated = Instant.parse("2026-11-01T05:30:00Z").toEpochMilli();
    assertNull(
        RecordingMatcher.match(
                "Call +919810060001_261101_013000.m4a",
                repeated + 30000,
                List.of(new RecordingMatcher.CallRef("a", "+919810060001", repeated, 60, "answered")),
                "91",
                ZoneId.of("America/New_York"))
            .key());
  }

  @Test
  public void nonexistentLocalTimeRequiresManualSelection() {
    long gap = Instant.parse("2026-03-08T07:30:00Z").toEpochMilli();
    assertNull(RecordingMatcher.match("Customer_260308_023000.wav", gap + 30000,
        List.of(new RecordingMatcher.CallRef("a", "+919810060001", gap, 60, "answered")),
        "91", ZoneId.of("America/New_York")).key());
  }

  @Test
  public void formatSupport() {
    for (String file : new String[] {"call.M4A", "call.wav", "call.mp3", "call.ogg", "call.flac"})
      assertTrue(RecordingMatcher.supported(file));
    assertFalse(RecordingMatcher.supported("recording.txt"));
    assertFalse(RecordingMatcher.supported(null));
  }
}
