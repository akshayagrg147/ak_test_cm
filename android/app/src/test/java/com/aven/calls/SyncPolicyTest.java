package com.aven.calls;

import static org.junit.Assert.*;

import org.junit.Test;

public class SyncPolicyTest {
  @Test
  public void classificationDoesNotInventAnsweredOutgoingCalls() {
    assertEquals("unknown", SyncPolicy.result(2, 0));
    assertEquals("answered", SyncPolicy.result(2, 1));
    assertEquals("answered", SyncPolicy.result(1, 0));
    assertEquals("missed", SyncPolicy.result(3, 0));
    assertEquals("rejected", SyncPolicy.result(5, 0));
    assertEquals("rejected", SyncPolicy.result(6, 0));
    assertEquals("unknown", SyncPolicy.result(7, 0));
  }

  @Test
  public void voicemailIsNotAnOrdinaryCall() {
    assertFalse(SyncPolicy.supportedType(4));
    assertFalse(SyncPolicy.supportedType(0));
    for (int value : new int[] {1, 2, 3, 5, 6, 7}) assertTrue(SyncPolicy.supportedType(value));
  }

  @Test
  public void transientErrorsRetryButPermissionsAndValidationDoNot() {
    for (int code : new int[] {0, 408, 425, 429, 500, 503})
      assertTrue("" + code, SyncPolicy.retryable(code));
    for (int code : new int[] {200, 400, 401, 403, 404, 409, 413, 422})
      assertFalse("" + code, SyncPolicy.retryable(code));
  }

  @Test
  public void syncWindowBoundaries() {
    long now = 1_800_000_000_000L;
    assertTrue(SyncPolicy.inWindow(now - SyncPolicy.MAX_AGE_MS, now));
    assertFalse(SyncPolicy.inWindow(now - SyncPolicy.MAX_AGE_MS - 1, now));
    assertTrue(SyncPolicy.inWindow(now + 300_000, now));
    assertFalse(SyncPolicy.inWindow(now + 300_001, now));
  }

  @Test
  public void reusedCallLogRowHasNewIdentity() {
    assertNotEquals(SyncPolicy.callKey(5, 100), SyncPolicy.callKey(5, 200));
    assertNotEquals(SyncPolicy.callKey(5, 100), SyncPolicy.callKey(6, 100));
    assertEquals(SyncPolicy.callKey(5, 100), SyncPolicy.callKey(5, 100));
  }

  @Test
  public void retryAfterIsBounded() {
    assertEquals(10, SyncPolicy.retryAfterSeconds("-1"));
    assertEquals(3600, SyncPolicy.retryAfterSeconds("90000"));
    assertEquals(30, SyncPolicy.retryAfterSeconds(null));
    assertEquals(30, SyncPolicy.retryAfterSeconds("invalid"));
  }
}
