// Content for ViaCRM's static, crawlable marketing pages.
// Run `node scripts/seo-pages.mjs` from web/ after editing; it writes
// web/public/<path>/index.html, web/public/sitemap.xml and web/public/404.html.
//
// Keep every claim true to the shipped product. WhatsApp is not a ViaCRM
// feature; do not add WhatsApp claims. Do not publish prices here unless the
// owner provides them.

export const SITE = {
  origin: "https://viacrm.in",
  name: "ViaCRM",
  tagline: "Every lead. A way forward.",
  instagram: "https://www.instagram.com/viacrm91/",
  // Fill these once the owner publishes them on the homepage too.
  phone: "",
  email: "",
};

const cta = `
<div class="cta">
  <a class="button" href="${SITE.instagram}" rel="noopener">Message us on Instagram</a>
  <a class="button ghost" href="/">See the full platform</a>
</div>`;

export const pages = [
  {
    path: "/real-estate-crm/",
    title: "Real Estate CRM Software for Indian Brokers & Agencies | ViaCRM",
    description:
      "Real estate CRM for Indian brokers, agencies and channel partners: lead capture, telecalling, site visits, property inventory and bookings in one workspace.",
    eyebrow: "Real estate CRM · India",
    h1: "Real estate CRM built for Indian brokers and agencies",
    lead: "Bring every property enquiry, call, site visit and booking into one workspace. ViaCRM gives your telecallers a clear queue, your field team a visit plan, and you a live view of the whole pipeline.",
    priority: "0.9",
    body: `
${cta}
<h2>Why brokers move from Excel and diaries to a real estate CRM</h2>
<p>Most agencies lose deals in the gaps: a call-back that nobody made, a site visit that was not confirmed, a buyer whose budget was written on paper. A real estate CRM closes those gaps by putting each lead, its owner and its next step in one place that the whole team can see.</p>
<div class="grid">
  <div class="card"><h3>Lead capture from your sources</h3><p>Website enquiry forms, Google Ads lead forms, IndiaMART and Justdial integrations, plus CSV import with duplicate checks.</p></div>
  <div class="card"><h3>Telecaller workflow</h3><p>Focused calling queues, call outcomes, follow-up dates and an automatic bell for overdue call-backs.</p></div>
  <div class="card"><h3>Call recordings from Android</h3><p>The ViaCRM Android app links calls and the phone's own recordings to the right lead, with folder access you control.</p></div>
  <div class="card"><h3>Property inventory</h3><p>Sale and rental listings, project details, photos and private brochures, matched against each buyer's budget and location.</p></div>
  <div class="card"><h3>Site visits and field executives</h3><p>Schedule visits, avoid agent clashes, hand over to a field executive and record feedback before the next conversation.</p></div>
  <div class="card"><h3>Bookings and commissions</h3><p>Track reservations, booking stages, agreed value and commission against the customer.</p></div>
</div>

<h2>Who ViaCRM is for</h2>
<ul>
  <li><strong>Property dealers and brokers</strong> who want every enquiry followed up on time.</li>
  <li><strong>Real estate agencies</strong> with telecalling teams and field executives.</li>
  <li><strong>Channel partners</strong> selling inventory for several developers.</li>
  <li><strong>Developers' sales teams</strong> managing site visits and bookings for a project.</li>
</ul>

<h2>How a lead moves through ViaCRM</h2>
<ol>
  <li><strong>Capture:</strong> the enquiry arrives from your form, ad or portal integration and is assigned to a team member.</li>
  <li><strong>Qualify:</strong> the telecaller records budget, preferred locations and property type, and sets the next follow-up.</li>
  <li><strong>Visit:</strong> a site visit is scheduled and, if needed, handed to a field executive who accepts it.</li>
  <li><strong>Close:</strong> the booking, agreed value and commission are recorded against the same customer history.</li>
</ol>

<h2>Built for teams, with the right access for each role</h2>
<p>Admins see the whole company. Telecallers see the leads assigned to them. Field executives see their current handoffs and their own work. Recordings cannot be deleted by callers or executives, and every company's data stays separate. Dashboards with charts show calls, follow-ups and pipeline by person and period.</p>

<h2>Your company, your brand</h2>
<p>Each company workspace carries its own logo and brand, its own lead stages, custom fields and roles. Attendance, leave approvals and payroll are available for teams that want HR basics in the same place.</p>

<div class="note">Data is hosted on AWS in Mumbai (ap-south-1). ViaCRM does not include WhatsApp messaging.</div>
`,
    faq: [
      [
        "What is a real estate CRM?",
        "A real estate CRM is software that stores every property enquiry with its source, owner, budget, preferred locations and next step, so brokers and agencies can follow up on time, schedule site visits and track bookings.",
      ],
      [
        "Does ViaCRM work for small brokers as well as agencies?",
        "Yes. A single broker can use it to keep follow-ups on time, and agencies can add telecallers and field executives with role-based access.",
      ],
      [
        "Which lead sources can ViaCRM capture?",
        "Website enquiry forms, Google Ads lead forms, IndiaMART and Justdial integrations, and CSV/Excel-exported files through the import tool.",
      ],
      [
        "Does ViaCRM record calls?",
        "The ViaCRM Android app uses the recordings your phone already makes with its built-in call recorder, after you give it access to that folder, and attaches them to the matching lead. Recording availability depends on the phone model and Android version.",
      ],
      [
        "Where is my data stored?",
        "ViaCRM runs on AWS in the Mumbai region, and each company's data is kept separate.",
      ],
    ],
  },
  {
    path: "/property-dealer-crm/",
    lang: "en-IN",
    title: "Property Dealer CRM — Leads, Calls & Site Visits Ek Jagah | ViaCRM",
    description:
      "Property dealer ke liye CRM: har enquiry, call, follow-up aur site visit ek jagah. ViaCRM se koi lead miss na ho. प्रॉपर्टी डीलर के लिए आसान CRM सॉफ्टवेयर।",
    eyebrow: "Property dealer CRM · Hinglish / हिंदी",
    h1: "Property dealer CRM: har lead, har follow-up ek jagah",
    lead: "Diary aur Excel mein leads kho jaati hain. ViaCRM mein har enquiry, call, site visit aur booking ek hi jagah hoti hai — aapki team ko pata rehta hai aaj kisko call karna hai.",
    priority: "0.8",
    body: `
${cta}
<h2>Property dealers ki sabse badi problem</h2>
<p>Lead aaya, call hua, "kal baat karte hain" bola — aur phir follow-up bhool gaye. Buyer ne kisi aur broker se property le li. ViaCRM har lead ke saath next follow-up ki date rakhta hai, aur time nikal jaane par bell se yaad dilata hai, jab tak result save na ho.</p>

<h2>ViaCRM mein kya milta hai</h2>
<div class="grid">
  <div class="card"><h3>Saari leads ek jagah</h3><p>Website form, Google Ads, IndiaMART, Justdial aur Excel/CSV import se leads seedha CRM mein.</p></div>
  <div class="card"><h3>Telecaller ke liye simple queue</h3><p>Aaj kisko call karna hai, pichli baat kya hui, next step kya hai — sab saamne.</p></div>
  <div class="card"><h3>Call recording Android app se</h3><p>Phone ki apni call recordings sahi lead ke saath jud jaati hain (phone model par depend karta hai).</p></div>
  <div class="card"><h3>Site visit planning</h3><p>Visit schedule karein, field executive ko handover karein, buyer ka feedback save karein.</p></div>
  <div class="card"><h3>Property inventory</h3><p>Sale aur rent properties, photos aur brochure — buyer ke budget aur location se match karein.</p></div>
  <div class="card"><h3>Booking aur commission</h3><p>Booking stage, final value aur commission customer ke record mein.</p></div>
</div>

<section lang="hi">
<h2>प्रॉपर्टी डीलर के लिए CRM क्यों?</h2>
<p>ViaCRM एक रियल एस्टेट CRM है जो भारतीय प्रॉपर्टी डीलर, ब्रोकर और एजेंसियों के लिए बना है। हर लीड का सोर्स, बजट, पसंदीदा लोकेशन और अगला फॉलो-अप एक जगह रहता है। टेलीकॉलर को अपनी लीड दिखती हैं, फील्ड एग्जीक्यूटिव को अपने साइट विज़िट, और मालिक को पूरी टीम का डैशबोर्ड।</p>
<ul>
  <li>लीड कैप्चर: वेबसाइट फॉर्म, Google Ads, IndiaMART, Justdial और CSV इम्पोर्ट</li>
  <li>फॉलो-अप रिमाइंडर: समय निकलने पर बेल अलर्ट</li>
  <li>साइट विज़िट और बुकिंग ट्रैकिंग</li>
  <li>Android ऐप से कॉल और रिकॉर्डिंग लीड के साथ</li>
</ul>
</section>

<h2>Kaun use kar sakta hai?</h2>
<p>Akela property dealer jo apne follow-ups time par karna chahta hai, ya badi agency jismein telecallers aur field executives hain — dono ke liye. Har role ko sirf utna access milta hai jitna zaroori hai.</p>

<div class="note">Data India mein (AWS Mumbai) host hota hai. ViaCRM mein WhatsApp messaging shaamil nahi hai.</div>
`,
    faq: [
      [
        "Property dealer CRM kya hota hai?",
        "Ye ek software hai jismein har property enquiry ka source, budget, location, kisne call kiya aur next follow-up kab hai — sab ek jagah save hota hai, taaki koi lead miss na ho.",
      ],
      [
        "Kya akela broker bhi ViaCRM use kar sakta hai?",
        "Haan. Akela broker apne follow-ups aur site visits manage kar sakta hai, aur team badhne par telecallers aur field executives add kar sakta hai.",
      ],
      [
        "Kya ViaCRM call record karta hai?",
        "ViaCRM ka Android app phone ke built-in call recorder ki recordings ko, folder access dene ke baad, sahi lead ke saath jodta hai. Ye phone model aur Android version par depend karta hai.",
      ],
      [
        "क्या ViaCRM हिंदी में समझाया जा सकता है?",
        "हाँ, हम आपकी टीम को हिंदी या हिंग्लिश में सेटअप और ट्रेनिंग समझा सकते हैं। Instagram पर @viacrm91 को मैसेज करें।",
      ],
    ],
  },
  {
    path: "/real-estate-lead-management/",
    title: "Real Estate Lead Management Software for India | ViaCRM",
    description:
      "Lead management software for real estate teams in India: capture leads from website forms, Google Ads, IndiaMART and Justdial, and never miss a follow-up.",
    eyebrow: "Lead management software",
    h1: "Real estate lead management software that keeps every follow-up on time",
    lead: "Capture enquiries from your website, ads and portals, assign each one to the right person, and see which leads are waiting for a call-back right now.",
    priority: "0.8",
    body: `
${cta}
<h2>Where your leads come from</h2>
<div class="table-scroll"><table>
  <thead><tr><th>Source</th><th>How it reaches ViaCRM</th></tr></thead>
  <tbody>
    <tr><td>Your website</td><td>A hosted enquiry form link, or your own form posting to your workspace's capture endpoint.</td></tr>
    <tr><td>Google Ads lead forms</td><td>Webhook delivery into your workspace.</td></tr>
    <tr><td>IndiaMART</td><td>Scheduled polling with your IndiaMART CRM key, plus manual sync.</td></tr>
    <tr><td>Justdial</td><td>Webhook delivery from Justdial.</td></tr>
    <tr><td>Old spreadsheets</td><td>CSV import with column mapping and duplicate detection.</td></tr>
    <tr><td>Walk-ins and calls</td><td>Add the lead by hand from the web app.</td></tr>
  </tbody>
</table></div>

<h2>What good lead management looks like</h2>
<h3>1. Every lead has an owner</h3>
<p>Assign leads to telecallers or agents. Each person sees their own queue; admins see everything.</p>
<h3>2. Every lead has a next step and a date</h3>
<p>Calls end with an outcome and a follow-up. Overdue call-backs show in a bell that stays until a result is saved or the call-back is rescheduled.</p>
<h3>3. Closed and DND leads stay out of the way</h3>
<p>Priority lists exclude closed, do-not-disturb and archived clients, so the team only works leads that can still convert.</p>
<h3>4. Managers see the funnel</h3>
<p>Admin and telecaller dashboards chart calls, follow-ups and pipeline by person and time period, with exportable reports.</p>

<h2>Built for real estate, not generic sales</h2>
<p>Leads carry budget, preferred locations and property type, and can be matched with available inventory. A lead can move into a site visit, a field executive handoff and finally a booking — without leaving its history behind.</p>
`,
    faq: [
      [
        "What is lead management software?",
        "Lead management software collects enquiries from all your sources, assigns each one to a person, and tracks every call and follow-up until the lead converts or closes.",
      ],
      [
        "Can ViaCRM import leads from IndiaMART and Justdial?",
        "Yes. IndiaMART leads are pulled on a schedule using your IndiaMART CRM key, and Justdial leads arrive by webhook.",
      ],
      [
        "Can I import my existing Excel leads?",
        "Yes. Save the sheet as CSV and use the import tool; it maps columns and reports duplicates before you confirm.",
      ],
    ],
  },
  {
    path: "/call-recording-crm/",
    title: "CRM with Call Recording for Telecallers (Android) | ViaCRM",
    description:
      "A telecaller CRM with an Android app that links calls and the phone's built-in call recordings to the right lead. Built for real estate calling teams in India.",
    eyebrow: "Telecaller CRM · Android",
    h1: "Telecaller CRM with call recordings linked to every lead",
    lead: "The ViaCRM Android app matches calls from your team's phones to the right lead and uploads the phone's own call recordings, so managers can review conversations without asking for screenshots.",
    priority: "0.8",
    body: `
${cta}
<h2>How call sync works</h2>
<ol>
  <li>Your telecaller signs in to the ViaCRM Android app with their CRM account.</li>
  <li>They see the leads assigned to them and call from the phone as usual.</li>
  <li>After they allow it, the app reads the call log for those calls and the recordings folder they choose.</li>
  <li>Each recording is matched to the closest eligible call by time and uploaded to the lead's history.</li>
</ol>

<div class="note">The app uses recordings made by your phone's built-in call recorder. It does not record calls itself, and availability depends on the phone brand, model and Android version. We will tell you honestly if a device does not support it.</div>

<h2>What managers get</h2>
<div class="grid">
  <div class="card"><h3>Call history per lead</h3><p>Every synced call and recording appears in the lead's timeline next to remarks and follow-ups.</p></div>
  <div class="card"><h3>Hourly call charts</h3><p>See when your team is calling and how many calls each person made in a period.</p></div>
  <div class="card"><h3>Recordings that stay</h3><p>Telecallers and field executives cannot delete recordings. Access follows the lead's permissions.</p></div>
</div>

<h2>What telecallers get</h2>
<p>A home screen with today's work, their assigned leads, call history and a read-only property catalogue to answer buyer questions during the call.</p>
`,
    faq: [
      [
        "Does ViaCRM record calls itself?",
        "No. It uses the recordings your phone's built-in call recorder already saves, after you give the app access to that folder.",
      ],
      [
        "Which phones are supported?",
        "Android phones whose built-in dialer can save call recordings. Support varies by brand, model and Android version, so test with your team's phones first.",
      ],
      [
        "Can a telecaller delete a recording?",
        "No. Telecallers and field executives have no recording-delete action.",
      ],
    ],
  },
  {
    path: "/blog/",
    title: "ViaCRM Blog — Real Estate Sales, Leads and Follow-ups",
    description:
      "Practical guides for Indian property dealers and real estate agencies on lead follow-up, telecalling and moving from Excel to a CRM.",
    eyebrow: "Blog",
    h1: "Guides for real estate sales teams",
    lead: "Short, practical articles for property dealers, brokers and agencies in India.",
    priority: "0.6",
    body: `
<div class="grid">
  <a class="card" href="/blog/real-estate-lead-follow-up/" style="text-decoration:none"><h3>How to follow up real estate leads so none go cold</h3><p>A simple follow-up routine for brokers and telecalling teams.</p></a>
  <a class="card" href="/blog/excel-vs-crm-for-property-dealers/" style="text-decoration:none"><h3>Excel vs CRM for property dealers</h3><p>When a spreadsheet stops being enough, and what to look for in a CRM.</p></a>
</div>
`,
  },
  {
    path: "/blog/real-estate-lead-follow-up/",
    type: "article",
    published: "2026-11-14",
    title: "How to Follow Up Real Estate Leads So None Go Cold | ViaCRM",
    description:
      "A practical follow-up routine for Indian property dealers and telecalling teams: response time, call scripts, follow-up dates and when to close a lead.",
    eyebrow: "Guide · Lead follow-up",
    h1: "How to follow up real estate leads so none go cold",
    lead: "Most property leads are not lost to a better offer. They are lost because nobody called back. Here is a simple routine any broker or agency can run.",
    priority: "0.6",
    body: `
<article class="prose">
<h2>1. Call new enquiries the same day</h2>
<p>A buyer who fills a form or calls from a portal listing is usually talking to several brokers. The first useful conversation wins attention. Set a rule: every new enquiry gets a call the same working day, and ideally within the hour.</p>

<h2>2. Ask the same five questions every time</h2>
<ul>
  <li>Buying or renting? For self-use or investment?</li>
  <li>Budget range, and is a home loan involved?</li>
  <li>Preferred locations or projects.</li>
  <li>Property type and size (2 BHK, plot, shop…).</li>
  <li>When do they want to move or decide?</li>
</ul>
<p>Write the answers in the lead record, not in a notebook. The next person who calls should not ask again.</p>

<h2>3. End every call with a date</h2>
<p>"I'll call you later" is not a follow-up. Agree a day and time, and save it. If the buyer is not ready, a follow-up in two weeks is still a follow-up.</p>

<h2>4. Move to a site visit quickly</h2>
<p>Once budget and location fit, offer two visit slots. Confirm the day before. After the visit, record feedback the same day: what they liked, objections and the next step.</p>

<h2>5. Review overdue follow-ups daily</h2>
<p>A manager should spend ten minutes each morning on overdue call-backs: who missed them and why. This is where a CRM helps most — ViaCRM shows overdue call-backs in a bell that stays until a result is saved.</p>

<h2>6. Close leads honestly</h2>
<p>Mark leads as closed, lost or do-not-disturb when that is the truth. A clean list means your team spends time on buyers who can still convert.</p>

<h2>A simple follow-up schedule</h2>
<div class="table-scroll"><table>
<thead><tr><th>When</th><th>Action</th></tr></thead>
<tbody>
<tr><td>Day 0</td><td>First call, qualify with the five questions, share 2–3 matching options.</td></tr>
<tr><td>Day 1–2</td><td>Follow-up call; offer site visit slots.</td></tr>
<tr><td>Day 3–7</td><td>Site visit; record feedback the same day.</td></tr>
<tr><td>Day 7–14</td><td>Negotiation or new options based on feedback.</td></tr>
<tr><td>Monthly</td><td>Nurture call for buyers who are not ready yet.</td></tr>
</tbody></table></div>

<p>Want this routine built into your team's daily queue? See <a href="/real-estate-lead-management/">ViaCRM's lead management</a>.</p>
</article>
`,
  },
  {
    path: "/blog/excel-vs-crm-for-property-dealers/",
    type: "article",
    published: "2026-11-14",
    title: "Excel vs CRM for Property Dealers: When to Switch | ViaCRM",
    description:
      "Excel works for a few leads. Here is when property dealers and real estate agencies outgrow spreadsheets, and what to look for in a real estate CRM.",
    eyebrow: "Guide · Choosing a CRM",
    h1: "Excel vs CRM for property dealers: when to switch",
    lead: "Spreadsheets are free and familiar. For a broker with a handful of buyers they are enough. Here is how to tell when they start costing you deals.",
    priority: "0.6",
    body: `
<article class="prose">
<h2>Signs you have outgrown Excel</h2>
<ul>
  <li>Two people called the same buyer, or nobody did.</li>
  <li>You cannot see which follow-ups were due yesterday.</li>
  <li>Leads arrive from IndiaMART, Justdial, ads and walk-ins, and someone copies them by hand.</li>
  <li>The sheet has many versions on different phones.</li>
  <li>You cannot tell which telecaller made how many calls this week.</li>
</ul>

<h2>Excel vs a real estate CRM</h2>
<div class="table-scroll"><table>
<thead><tr><th></th><th>Excel / Google Sheets</th><th>Real estate CRM</th></tr></thead>
<tbody>
<tr><td>Lead capture</td><td>Manual copy-paste</td><td>Forms, ads and portal integrations</td></tr>
<tr><td>Follow-up reminders</td><td>None, unless you build them</td><td>Automatic overdue alerts</td></tr>
<tr><td>Team access</td><td>Everyone sees everything</td><td>Role-based: each person sees their leads</td></tr>
<tr><td>Call history</td><td>A notes column</td><td>Timeline with calls, remarks and recordings</td></tr>
<tr><td>Site visits and bookings</td><td>Separate sheets</td><td>Linked to the same customer</td></tr>
<tr><td>Reports</td><td>Built by hand</td><td>Dashboards by person and period</td></tr>
</tbody></table></div>

<h2>What to look for in a CRM for property dealers</h2>
<ol>
  <li><strong>Real estate fields:</strong> budget, location, property type and inventory matching.</li>
  <li><strong>Your lead sources:</strong> check that the portals and ad forms you use are supported.</li>
  <li><strong>A telecaller workflow:</strong> queues, outcomes and follow-up dates, not just a contact list.</li>
  <li><strong>Mobile:</strong> an Android app for calling teams.</li>
  <li><strong>Data location and access control:</strong> who can see, export or delete what.</li>
  <li><strong>Easy import:</strong> bring your existing sheet in without retyping.</li>
</ol>

<h2>Moving your sheet into ViaCRM</h2>
<p>Export the sheet as CSV, map the columns in ViaCRM's import tool, review the duplicates it finds, and confirm. Then assign the leads to your team. Read more about <a href="/real-estate-crm/">ViaCRM for real estate</a>.</p>
</article>
`,
  },
];
