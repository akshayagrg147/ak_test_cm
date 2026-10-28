package com.aven.calls;

import static org.junit.Assert.*;

import org.junit.Test;

public class EndpointTest {
  @Test
  public void productionRequiresHttps() {
    assertEquals("https://crm.example.com", Endpoint.validate(" https://crm.example.com/ ", false));
    for (String address :
        new String[] {
          "http://crm.example.com",
          "http://10.0.2.2:8010",
          "ftp://crm.example.com",
          "https://user:pass@crm.example.com",
          "https://crm.example.com/api",
          "https://crm.example.com?token=1",
          "https://crm.example.com#token",
          "not-an-address"
        })
      try {
        Endpoint.validate(address, false);
        fail(address);
      } catch (IllegalArgumentException expected) {
      }
  }

  @Test
  public void debugHttpOnlyForLocalNetworks() {
    for (String address :
        new String[] {
          "http://10.0.2.2:8010",
          "http://127.0.0.1:8010",
          "http://localhost:8010",
          "http://192.168.1.8:8010",
          "http://172.16.0.1:8010"
        }) assertEquals(address, Endpoint.validate(address, true));
    for (String address :
        new String[] {
          "http://example.com",
          "http://192.168.1.1.evil.com",
          "http://172.32.0.1",
          "http://10.0.2.2@evil.com"
        })
      try {
        Endpoint.validate(address, true);
        fail(address);
      } catch (IllegalArgumentException expected) {
      }
  }
}
