package com.aven.calls;

import static org.junit.Assert.*;

import org.junit.Test;

public class PhoneNumbersTest {
  @org.junit.Test
  public void rejectsMisplacedPlusSigns() {
    org.junit.Assert.assertNull(PhoneNumbers.normalize("++919810001234", "91"));
    org.junit.Assert.assertNull(PhoneNumbers.normalize("9198+10001234", "91"));
  }

  @Test
  public void localAndInternationalForms() {
    for (String phone :
        new String[] {
          "9810060001", "09810060001", "+91 98100 60001", "0091-9810060001", "919810060001"
        }) assertEquals("+919810060001", PhoneNumbers.normalize(phone, "91"));
  }

  @Test
  public void explicitCountriesNeverUseSuffixMatching() {
    assertEquals("+14155552671", PhoneNumbers.normalize("+1 (415) 555-2671", "91"));
    assertNotEquals(
        PhoneNumbers.normalize("+14155552671", "91"), PhoneNumbers.normalize("4155552671", "91"));
  }

  @Test
  public void rejectsUnknownPrivateAndServiceCodes() {
    for (String phone :
        new String[] {
          "",
          "Unknown",
          "private",
          "-1",
          "123",
          "*123#",
          "user@phone.test",
          "+012345678901",
          "1234567890123456"
        }) assertNull(phone, PhoneNumbers.normalize(phone, "91"));
    assertNull(PhoneNumbers.normalize(null, "91"));
  }
}
