# Owner checklist: Search Console and Google Business Profile

For Akshay. These steps take about 30 minutes in total. Nothing here costs
money.

## A. Google Search Console

**Status (14 Nov 2026):** Claude added the property `https://viacrm.in/` in
your Chrome and deployed Google's verification file
`google1252a6f1e2519bd5.html`. Once you see "Ownership verified" there, only
the checks in step 4 below are left for you.

If you ever need to redo it:

1. Open https://search.google.com/search-console and sign in with the Google
   account that should own ViaCRM.
2. Click **Add property → URL prefix**, enter `https://viacrm.in/`, then click
   **Continue**.
3. Choose **HTML file** and click **Verify**. The file is already live at
   `https://viacrm.in/google1252a6f1e2519bd5.html`. **Never delete that file**
   from `web/public/`, or you will lose verification.
4. Left menu **Sitemaps**: enter `sitemap.xml` and click **Submit**. The status
   should read "Success" within a day.
5. Paste each of these into the search bar at the top (**URL inspection**), then
   click **Request indexing**:
   - `https://viacrm.in/`
   - `https://viacrm.in/real-estate-crm/`
   - `https://viacrm.in/property-dealer-crm/`
   - `https://viacrm.in/real-estate-lead-management/`
   - `https://viacrm.in/call-recording-crm/`
6. Optional, 2 minutes: https://www.bing.com/webmasters → **Import from Google
   Search Console**. This covers Bing and DuckDuckGo.
7. Weekly, 5 minutes: open **Performance → Search results**. Check which
   queries show ViaCRM and which pages get clicks, and send the list to the
   SEO session for new page ideas.

The data starts to appear 2 to 4 days after verification. Rankings for new
pages usually take 4 to 12 weeks.

## B. Google Business Profile (GBP)

**Before you start, have these ready:**
- the sales phone number, the same one used everywhere else
- your city
- `https://viacrm.in/logo-512.png`
- 3 to 5 screenshots of Demo Realty (ViaCRM 1 is making these)

1. Open https://business.google.com/create and sign in with the same Google
   account.
2. **Business name:** `ViaCRM`. Use exactly this. Don't add keywords to the
   name, because Google suspends profiles for keyword stuffing.
3. **Category:** start typing "Software company" and pick it.
4. **"Do you want to add a location customers can visit?"** Choose **No**
   unless you have an office where customers visit. You will then be a
   service-area business, and your home address stays hidden.
5. **Service areas:** add the cities or states you sell in, for example your
   city plus nearby cities. All of India is too broad; pick up to about 20
   areas.
6. **Contact:** the sales phone number and website `https://viacrm.in/`.
7. **Verification:** Google will offer video, phone/SMS or a postcard. Video
   verification usually means recording your workspace, the ViaCRM app on your
   laptop and something that shows your city (signboard or street). Follow
   Google's on-screen steps. Approval can take a few days.
8. After verification, fill these in:
   - **Description:** paste the 750-character text from
     `docs/seo/backlinks.md` → #2.
   - **Services:** Real estate CRM setup · Lead import from Excel ·
     Telecaller training · Android call-sync setup.
   - **Logo:** `logo-512.png`. **Cover photo:** the `og-image.png` from the
     site, or a Demo Realty screenshot.
   - **Hours:** your WhatsApp reply hours.
   - **Products** (optional): one item "ViaCRM real estate CRM", price
     "Contact for pricing" until you confirm prices, linking to
     `https://viacrm.in/real-estate-crm/`.
9. **Weekly:** add a post with a Reel or carousel from Instagram and the link
   `https://viacrm.in/property-dealer-crm/`.
10. **Reviews:** ask only real trial users or customers. Never write reviews
    yourself, and never pay for them.

## C. Keep these identical everywhere

Use the same name, phone, website and city on GBP, Justdial, IndiaMART,
SoftwareSuggest, Techjockey and Instagram: **ViaCRM · [sales number] ·
https://viacrm.in/ · [city]**. Google trusts the business more when the
details match.
