package com.aven.calls;

import static org.junit.Assert.*;
import org.junit.Test;

public class EstateFormatTest {
  @Test public void propertyPricesUseLakhCroreAndMonthlyRent() {
    assertEquals("₹75 L", EstateFormat.money("7500000.00", false));
    assertEquals("₹1.25 Cr", EstateFormat.money("12500000", false));
    assertEquals("₹25,000 / month", EstateFormat.money("25000", true));
    assertEquals("₹1 L", EstateFormat.money("100000", false));
    assertEquals("₹1 Cr", EstateFormat.money("10000000", false));
    assertEquals("₹99,999.99", EstateFormat.money("99999.99", false));
    assertEquals("₹1,25,00,000.5", EstateFormat.exactMoney("12500000.50"));
  }
  @Test public void missingOrInvalidAmountsAreNotInvented() {
    for (String value : new String[] {null, "", "null", "unknown", "-1"})
      assertEquals("Price unavailable", EstateFormat.money(value, false));
  }
  @Test public void areaPreservesTheRecordedPrecision() {
    assertEquals("1250.75 sq ft", EstateFormat.area("1250.7500"));
    assertEquals("1200 sq ft", EstateFormat.area("1200.00"));
    assertEquals("Area not specified", EstateFormat.area("0"));
    assertEquals("Area not specified", EstateFormat.area(null));
  }
  @Test public void callDurationRemainsReadableWithoutDroppingSeconds() {
    assertEquals("0s", EstateFormat.duration("0"));
    assertEquals("1m 21s", EstateFormat.duration("81"));
    assertEquals("60m 1s", EstateFormat.duration("3601"));
    assertEquals("Duration unavailable", EstateFormat.duration(null));
  }
  @Test public void optionalLabelsDoNotExposeNullOrRawEnumSeparators() {
    assertEquals("Off market", EstateFormat.label("off-market"));
    assertEquals("Not specified", EstateFormat.label("null"));
    assertEquals("Not specified", EstateFormat.label(""));
  }
}
