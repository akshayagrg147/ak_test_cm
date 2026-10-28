package com.aven.calls;

import java.net.URI;

public final class Endpoint {
  private Endpoint() {}

  public static String validate(String value, boolean debug) {
    try {
      URI uri = new URI(value.trim());
      String host = uri.getHost();
      if (host == null
          || uri.getUserInfo() != null
          || uri.getQuery() != null
          || uri.getFragment() != null
          || (uri.getPath() != null && !uri.getPath().matches("/?")))
        throw new IllegalArgumentException();
      boolean local =
          host.equals("localhost")
              || host.equals("127.0.0.1")
              || host.equals("10.0.2.2")
              || host.matches("10\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}")
              || host.matches("192\\.168\\.\\d{1,3}\\.\\d{1,3}")
              || host.matches("172\\.(1[6-9]|2[0-9]|3[01])\\.\\d{1,3}\\.\\d{1,3}");
      if (!"https".equals(uri.getScheme()) && !(debug && local && "http".equals(uri.getScheme())))
        throw new IllegalArgumentException();
      return new URI(uri.getScheme(), null, host, uri.getPort(), null, null, null).toString();
    } catch (Exception ignored) {
      throw new IllegalArgumentException(
          "Enter an HTTPS CRM server address without a path. The test APK also accepts a local HTTP"
              + " server.");
    }
  }
}
