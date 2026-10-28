package com.aven.calls;

/** Conservative normalization. International numbers are never matched by suffix alone. */
public final class PhoneNumbers {
  private PhoneNumbers() {}

  public static String normalize(String raw, String callingCode) {
    if (raw == null || raw.isBlank() || raw.contains("*") || raw.contains("#") || raw.contains("@"))
      return null;
    String text = raw.trim();
    if (!text.matches("[+0-9() .-]+")) return null;
    if (text.contains("+") && (text.indexOf('+') != 0 || text.lastIndexOf('+') != 0)) return null;
    String digits = text.replaceAll("[^0-9]", "");
    if (text.startsWith("00")) digits = digits.substring(2);
    else if (!text.startsWith("+")) {
      if (digits.length() == 11 && digits.startsWith("0")) digits = digits.substring(1);
      if (digits.length() == 10) digits = callingCode + digits;
    }
    if (digits.length() < 10 || digits.length() > 15 || digits.startsWith("0")) return null;
    return "+" + digits;
  }
}
