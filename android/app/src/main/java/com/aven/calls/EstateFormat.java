package com.aven.calls;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Locale;

/** Presentation only: never used to decide call eligibility or recording matching. */
public final class EstateFormat {
  private EstateFormat() {}

  public static String money(String value, boolean rent) {
    try {
      BigDecimal amount = new BigDecimal(value);
      if (amount.signum() < 0) return "Price unavailable";
      String suffix = rent ? " / month" : "";
      if (amount.compareTo(new BigDecimal("10000000")) >= 0)
        return "₹" + amount.divide(new BigDecimal("10000000"), 2, RoundingMode.HALF_UP)
            .stripTrailingZeros().toPlainString() + " Cr" + suffix;
      if (amount.compareTo(new BigDecimal("100000")) >= 0)
        return "₹" + amount.divide(new BigDecimal("100000"), 2, RoundingMode.HALF_UP)
            .stripTrailingZeros().toPlainString() + " L" + suffix;
      return exactMoney(value) + suffix;
    } catch (RuntimeException ignored) { return "Price unavailable"; }
  }

  public static String exactMoney(String value) {
    try {
      BigDecimal amount = new BigDecimal(value);
      if (amount.signum() < 0) return "Price unavailable";
      String[] parts = amount.stripTrailingZeros().toPlainString().split("\\.");
      String digits = parts[0]; int start = Math.max(0, digits.length() - 3);
      StringBuilder grouped = new StringBuilder(digits.substring(start));
      for (int end = start; end > 0; end -= 2)
        grouped.insert(0, digits.substring(Math.max(0, end - 2), end) + ",");
      return "₹" + grouped + (parts.length == 2 ? "." + parts[1] : "");
    } catch (RuntimeException ignored) { return "Price unavailable"; }
  }

  public static String area(String value) {
    try {
      BigDecimal area = new BigDecimal(value);
      return area.signum() > 0 ? area.stripTrailingZeros().toPlainString() + " sq ft" : "Area not specified";
    } catch (RuntimeException ignored) { return "Area not specified"; }
  }

  public static String label(String value) {
    if (value == null || value.isBlank() || value.equals("null")) return "Not specified";
    String words = value.replace('_', ' ').replace('-', ' ');
    return Character.toUpperCase(words.charAt(0)) + words.substring(1);
  }

  public static String duration(String value) {
    try {
      long seconds = Math.max(0, Long.parseLong(value));
      return seconds >= 60 ? seconds / 60 + "m " + seconds % 60 + "s" : seconds + "s";
    } catch (RuntimeException ignored) { return "Duration unavailable"; }
  }
}
