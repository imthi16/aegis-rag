#!/usr/bin/env node
/**
 * Capture the README screenshots from a running Aegis stack.
 *
 * This is a documentation tool, not part of the build or the air-gapped runtime.
 * It drives a real browser against a real deployment, so what lands in
 * docs/screenshots is the actual product — never a mockup.
 *
 * Usage (with the stack already up and an admin seeded):
 *
 *   npx playwright@1.48.2 install chromium      # one-time, online
 *   AEGIS_USER=admin AEGIS_PASSWORD='…' \
 *     node infra/scripts/capture_screenshots.mjs
 *
 * Options via environment:
 *   AEGIS_URL       base URL of the frontend      (default http://localhost:8080)
 *   AEGIS_USER      operator username             (required)
 *   AEGIS_PASSWORD  operator passphrase           (required)
 *   AEGIS_QUERY     question to ask on the chat screen, so the evidence rail and
 *                   citation chips are populated rather than empty
 *   AEGIS_OUT       output directory              (default docs/screenshots)
 *
 * Screens that need a role you lack are skipped with a note, not failed: an
 * analyst capturing docs will not see the Ledger or Evaluation routes.
 */

import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "../..");

const BASE = process.env.AEGIS_URL ?? "http://localhost:8080";
const USER = process.env.AEGIS_USER;
const PASSWORD = process.env.AEGIS_PASSWORD;
const OUT = resolve(REPO, process.env.AEGIS_OUT ?? "docs/screenshots");
const DEMO_QUERY = process.env.AEGIS_QUERY ?? "What controls satisfy HIPAA audit requirements?";

// Wide enough that the evidence rail is visible (it appears at lg = 1024px).
const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 390, height: 844 };

if (!USER || !PASSWORD) {
  console.error("AEGIS_USER and AEGIS_PASSWORD must be set.");
  process.exit(2);
}

let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch {
  console.error(
    "playwright is not installed. Run:\n" +
      "  npm i -D playwright@1.48.2 && npx playwright install chromium",
  );
  process.exit(2);
}

await mkdir(OUT, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: DESKTOP,
  deviceScaleFactor: 2, // retina — the UI is hairline-heavy and blurs at 1x
  colorScheme: "dark",
  reducedMotion: "reduce", // freeze pulses/sweeps so captures are deterministic
});
const page = await context.newPage();

const shot = async (name) => {
  const path = resolve(OUT, `${name}.png`);
  await page.screenshot({ path });
  console.log(`✓ ${name}.png`);
};

const goto = async (route) => {
  await page.goto(`${BASE}${route}`, { waitUntil: "networkidle" });
};

/**
 * Navigate by CLICKING the in-app nav — never goto() once signed in.
 *
 * The auth store is deliberately in-memory only (no localStorage — see
 * store/authStore.ts and §6.18), so a full document navigation wipes the token
 * and <Protected> redirects to /login. Using goto() here captured the login
 * screen for every post-login shot. Client-side routing keeps the session.
 *
 * Returns false when the operator's roles don't expose that nav entry, so the
 * caller can skip the screen instead of failing the run.
 */
const ROUTES = {
  Interrogate: "/chat",
  Corpus: "/documents",
  Ledger: "/audit",
  Evaluation: "/eval",
};

const navigate = async (label) => {
  const route = ROUTES[label];
  if (page.url().endsWith(route)) return true;
  const link = page.getByRole("link", { name: new RegExp(label, "i") }).first();
  if ((await link.count()) === 0) return false;
  await link.click();
  await page.waitForURL(new RegExp(`${route}$`));
  await page.waitForLoadState("networkidle");
  return true;
};

// ── 1 · Login ──────────────────────────────────────────────────────────────
await goto("/login");
await page.waitForSelector("#username");
await shot("01-login");

// ── 2 · Sign in ────────────────────────────────────────────────────────────
await page.fill("#username", USER);
await page.fill("#password", PASSWORD);
await Promise.all([page.waitForURL(/\/(chat|documents)/), page.click('button[type="submit"]')]);

// ── 3 · Chat, empty state ──────────────────────────────────────────────────
await navigate("Interrogate");
await shot("02-interrogate-empty");

// ── 4 · Chat, answered — the signature screen ──────────────────────────────
// The graph runs retrieval → rerank → CRAG → generation → faithfulness before
// anything renders, so allow generously for a 32B model on CPU.
await page.fill('input[placeholder="Query the corpus…"]', DEMO_QUERY);
await page.click('form button[type="submit"]');
try {
  await page.waitForSelector("text=/Verified|Unverified|Insufficient/", { timeout: 600_000 });
  await page.waitForTimeout(500); // let the evidence rail settle
  await shot("03-interrogate-answered");
} catch {
  console.warn("! no answer within 10 min — skipping 03-interrogate-answered");
}

// ── 5 · Remaining routes ───────────────────────────────────────────────────
for (const [label, name] of [
  ["Corpus", "04-corpus"],
  ["Ledger", "05-ledger"],
  ["Evaluation", "06-evaluation"],
]) {
  // The nav only renders entries the operator's roles permit, so a missing
  // link means "not authorized" — skip that screen rather than fail.
  if (!(await navigate(label))) {
    console.warn(`! ${label} not permitted for ${USER} — skipping ${name}.png`);
    continue;
  }
  await shot(name);
}

// ── 6 · Mobile — the drawer and the evidence sheet ─────────────────────────
// Resize rather than re-navigate: the SPA stays mounted, so the in-memory
// session survives.
await navigate("Interrogate");
await page.setViewportSize(MOBILE);
await page.waitForTimeout(300);
await page.click('button[aria-label="Open navigation"]');
await page.waitForTimeout(300);
await shot("07-mobile-nav");

await browser.close();
console.log(`\nWrote screenshots to ${OUT}`);
