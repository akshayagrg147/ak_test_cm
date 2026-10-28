import { chromium } from "@playwright/test";
import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, URL } from "node:url";
import { log } from "node:console";

const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const assets = path.join(root, "web/public/brand");
const output = path.join(root, "artifacts/viacrm-brand");
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
try {
  for (const name of [
    "viacrm-logo",
    "viacrm-logo-on-dark",
    "viacrm-logo-monochrome",
    "viacrm-symbol",
  ]) {
    const svg = await readFile(path.join(assets, name + ".svg"), "utf8");
    const [, width, height] = svg.match(/viewBox="0 0 (\d+) (\d+)"/);
    const scale = name === "viacrm-symbol" ? 16 : 4;
    const page = await browser.newPage({
      viewport: {
        width: Number(width) * scale,
        height: Number(height) * scale,
      },
    });
    await page.setContent(
      `<style>html,body{margin:0;background:transparent}svg{display:block;width:100%;height:100%}</style>${svg}`,
    );
    await page.screenshot({
      path: path.join(output, name + ".png"),
      omitBackground: true,
    });
    await page.close();
  }
  const page = await browser.newPage({
    viewport: { width: 1120, height: 1140 },
    deviceScaleFactor: 1,
  });
  await page.goto(
    new URL("../public/brand/preview.html", import.meta.url).href,
  );
  await page.locator(".hero img").waitFor({ state: "visible" });
  await page.screenshot({
    path: path.join(output, "viacrm-brand-preview.png"),
    fullPage: true,
  });
} finally {
  await browser.close();
}
log("Exported four transparent PNG variants and the brand presentation.");
