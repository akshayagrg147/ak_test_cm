/* global console */
// Generates ViaCRM's static SEO pages, sitemap.xml and 404.html into
// web/public/ from web/seo/pages.mjs. Run from web/: `node scripts/seo-pages.mjs`.
// The output is committed so the Docker build needs no extra step.
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { SITE, pages } from "../seo/pages.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "public");
const today = "2026-11-14";

const esc = (s) =>
  String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
// JSON inside <script type="application/ld+json"> must not close the tag.
const ld = (o) =>
  `<script type="application/ld+json">${JSON.stringify(o).replace(/</g, "\\u003c")}</script>`;

const solutions = pages.filter((p) => !p.path.startsWith("/blog/"));
const posts = pages.filter((p) => p.type === "article");

const header = `
<a class="skip" href="#main">Skip to content</a>
<header class="site"><div class="wrap">
  <a class="brand" href="/"><img src="/brand/viacrm-logo.svg" alt="ViaCRM" width="150" height="34"></a>
  <nav aria-label="Main">
    <a href="/real-estate-crm/">Real estate CRM</a>
    <a href="/real-estate-lead-management/">Lead management</a>
    <a href="/call-recording-crm/">Call recording</a>
    <a href="/blog/">Blog</a>
    <a href="/login" rel="nofollow">Customer login</a>
  </nav>
</div></header>`;

const footer = `
<footer class="site"><div class="wrap cols">
  <div><strong>ViaCRM</strong><p>${esc(SITE.tagline)}<br>Real estate CRM for Indian brokers and agencies.</p></div>
  <div><strong>Solutions</strong><ul>
    <li><a href="/real-estate-crm/">Real estate CRM</a></li>
    <li><a href="/property-dealer-crm/">Property dealer CRM (Hinglish)</a></li>
    <li><a href="/real-estate-lead-management/">Lead management software</a></li>
    <li><a href="/call-recording-crm/">Telecaller CRM with call recording</a></li>
  </ul></div>
  <div><strong>Resources</strong><ul>
    <li><a href="/blog/">Blog</a></li>
    ${posts.map((p) => `<li><a href="${p.path}">${esc(p.h1)}</a></li>`).join("\n    ")}
  </ul></div>
  <div><strong>Company</strong><ul>
    <li><a href="/">Home</a></li>
    <li><a href="${SITE.instagram}" rel="noopener">Instagram @viacrm91</a></li>
    <li><a href="/login" rel="nofollow">Customer login</a></li>
  </ul></div>
</div><div class="wrap"><p>© 2026 ViaCRM</p></div></footer>`;

function crumbs(p) {
  const items = [{ name: "Home", url: "/" }];
  if (p.path.startsWith("/blog/") && p.path !== "/blog/")
    items.push({ name: "Blog", url: "/blog/" });
  items.push({ name: p.eyebrow.split(" · ")[0] === "Blog" ? "Blog" : p.h1, url: p.path });
  return items;
}

function render(p) {
  const url = SITE.origin + p.path;
  const trail = crumbs(p);
  const graph = [
    {
      "@type": "BreadcrumbList",
      itemListElement: trail.map((c, i) => ({
        "@type": "ListItem",
        position: i + 1,
        name: c.name,
        item: SITE.origin + c.url,
      })),
    },
  ];
  if (p.type === "article")
    graph.push({
      "@type": "BlogPosting",
      headline: p.h1,
      description: p.description,
      datePublished: p.published,
      dateModified: p.published,
      mainEntityOfPage: url,
      inLanguage: p.lang || "en-IN",
      image: SITE.origin + "/og-image.png",
      author: { "@type": "Organization", name: SITE.name, url: SITE.origin + "/" },
      publisher: { "@id": SITE.origin + "/#organization" },
    });
  else
    graph.push({
      "@type": "WebPage",
      name: p.title,
      description: p.description,
      url,
      inLanguage: p.lang || "en-IN",
      about: { "@id": SITE.origin + "/#software" },
      publisher: { "@id": SITE.origin + "/#organization" },
    });
  if (p.faq?.length)
    graph.push({
      "@type": "FAQPage",
      mainEntity: p.faq.map(([q, a]) => ({
        "@type": "Question",
        name: q,
        acceptedAnswer: { "@type": "Answer", text: a },
      })),
    });
  const visibleCrumbs = trail
    .slice(0, -1)
    .map((c) => `<a href="${c.url}">${esc(c.name)}</a> › `)
    .join("");
  const faqHtml = p.faq?.length
    ? `<h2>Frequently asked questions</h2>\n${p.faq
        .map(([q, a]) => `<details><summary>${esc(q)}</summary><p>${esc(a)}</p></details>`)
        .join("\n")}`
    : "";
  const related = solutions
    .filter((s) => s.path !== p.path && s.path !== "/blog/")
    .map((s) => `<li><a href="${s.path}">${esc(s.h1)}</a></li>`)
    .join("\n");
  return `<!doctype html>
<html lang="${p.lang || "en-IN"}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(p.title)}</title>
<meta name="description" content="${esc(p.description)}">
<link rel="canonical" href="${url}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="theme-color" content="#264edb">
<link rel="icon" type="image/svg+xml" href="/favicon.svg?v=viacrm-1">
<link rel="stylesheet" href="/site/site.css?v=2">
<meta property="og:type" content="${p.type === "article" ? "article" : "website"}">
<meta property="og:site_name" content="ViaCRM">
<meta property="og:locale" content="en_IN">
<meta property="og:title" content="${esc(p.title)}">
<meta property="og:description" content="${esc(p.description)}">
<meta property="og:url" content="${url}">
<meta property="og:image" content="${SITE.origin}/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="ViaCRM — real estate CRM for Indian brokers and agencies">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="${esc(p.title)}">
<meta name="twitter:description" content="${esc(p.description)}">
<meta name="twitter:image" content="${SITE.origin}/og-image.png">
${p.type === "article" ? `<meta property="article:published_time" content="${p.published}">\n` : ""}${ld({ "@context": "https://schema.org", "@graph": graph })}
</head>
<body>
${header}
<main id="main"><div class="wrap">
<p class="crumbs">${visibleCrumbs}<span aria-current="page">${esc(trail[trail.length - 1].name)}</span></p>
<section class="hero">
<p class="eyebrow">${esc(p.eyebrow)}</p>
<h1>${esc(p.h1)}</h1>
<p class="lead">${esc(p.lead)}</p>
${p.type === "article" ? `<p class="crumbs">Published <time datetime="${p.published}">14 November 2026</time> · ViaCRM</p>` : ""}
</section>
${p.body.trim()}
${faqHtml}
<nav class="related" aria-label="Related pages"><h2>Explore ViaCRM</h2><ul>
${related}
<li><a href="/blog/">ViaCRM blog: guides for real estate sales teams</a></li>
</ul></nav>
</div></main>
${footer}
</body>
</html>
`;
}

for (const p of pages) {
  const dir = join(root, p.path);
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, "index.html"), render(p));
}

const urls = [{ path: "/", priority: "1.0" }, ...pages];
writeFileSync(
  join(root, "sitemap.xml"),
  `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls
  .map(
    (u) =>
      `  <url><loc>${SITE.origin}${u.path}</loc><lastmod>${u.published || today}</lastmod><priority>${u.priority || "0.5"}</priority></url>`,
  )
  .join("\n")}
</urlset>
`,
);

writeFileSync(
  join(root, "404.html"),
  `<!doctype html>
<html lang="en-IN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page not found | ViaCRM</title>
<meta name="robots" content="noindex">
<link rel="icon" type="image/svg+xml" href="/favicon.svg?v=viacrm-1">
<link rel="stylesheet" href="/site/site.css?v=2">
</head>
<body>
${header}
<main id="main"><div class="wrap"><section class="hero">
<p class="eyebrow">404</p>
<h1>This page does not exist</h1>
<p class="lead">The link may be old or mistyped. Try one of these instead.</p>
<div class="cta"><a class="button" href="/">ViaCRM home</a><a class="button ghost" href="/real-estate-crm/">Real estate CRM</a><a class="button ghost" href="/blog/">Blog</a></div>
</section></div></main>
${footer}
</body>
</html>
`,
);

console.log(`Wrote ${pages.length} pages, sitemap.xml (${urls.length} URLs) and 404.html`);
