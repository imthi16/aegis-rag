#!/usr/bin/env node
/**
 * Capture the README screenshots + demo GIF from the REAL built frontend,
 * driven against a STUBBED API.
 *
 * Why this exists alongside capture_screenshots.mjs
 * -------------------------------------------------
 * `capture_screenshots.mjs` drives a real deployment: real Postgres, real
 * embeddings, real Qwen2.5 32B via Ollama. That is the authoritative capture,
 * but it needs ~20 GB of model weights and a 24 GB+ GPU, so it cannot run in
 * CI, on a laptop, or anywhere the models are not staged.
 *
 * This script renders the same shipped React build — real components, real CSS,
 * real routing and state — and answers its API calls from fixtures below. What
 * you see is genuinely the product's UI; the DATA is illustrative, not the
 * output of a live model. Anything published from this script must say so.
 *
 * It needs no backend, no database, no models, and no network.
 *
 * Usage:
 *   cd frontend && npm run build && cd ..
 *   npm i -D playwright        # or: NODE_PATH=/path/to/node_modules
 *   node infra/scripts/capture_demo.mjs
 *
 * Environment:
 *   AEGIS_OUT        output dir                (default docs/screenshots)
 *   AEGIS_DIST       built frontend to serve   (default frontend/dist)
 *   AEGIS_PORT       port for the static server(default 4178)
 *   AEGIS_CHROMIUM   chromium executable       (default: playwright's own)
 *   AEGIS_FFMPEG     ffmpeg for GIF encoding   (default: playwright's bundled)
 *   AEGIS_SKIP_GIF   set to skip the GIF pass
 */

import { createReadStream } from "node:fs";
import { mkdir, readdir, rm, stat } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, dirname, join, resolve } from "node:path";
import { execFile } from "node:child_process";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const run = promisify(execFile);
const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "../..");

const OUT = resolve(REPO, process.env.AEGIS_OUT ?? "docs/screenshots");
const DIST = resolve(REPO, process.env.AEGIS_DIST ?? "frontend/dist");
const PORT = Number(process.env.AEGIS_PORT ?? 4178);
const BASE = `http://127.0.0.1:${PORT}`;

const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 390, height: 844 };
const DEMO_QUERY = "What controls satisfy HIPAA audit requirements?";

// ── Fixtures ───────────────────────────────────────────────────────────────
// Field shapes mirror backend/app/schemas exactly (and frontend/src/types/api.ts).
// Values are ILLUSTRATIVE — they are not a real model's output.

const USER = { id: "9f2c1b7e-4d3a-4f58-9c21-6a0b8e7d5341", username: "admin", roles: ["admin"] };

const CHUNK_A = "7b20de55-9c14-4a0e-8f31-2d6b5a91c073";
const CHUNK_B = "c118a0b9-33ef-45d2-b6a7-90e14c8f52aa";
const CHUNK_C = "e5741dcb-27a8-4c19-9b03-8fa6d2e15b4c";
const DOC_A = "a3f91c04-7e52-4b18-9d6a-1c83f0b27e59";
const DOC_B = "b8412d67-05ca-4e93-a172-3f9d6c40e8b1";

const ANSWER_PARTS = [
  "HIPAA §164.312(b) requires audit controls — hardware, software, and procedural ",
  "mechanisms that record and examine activity in systems containing ePHI [1]. ",
  "Aegis satisfies this with an append-only, hash-chained `audit_log` covering ",
  "authentication, query, and document events, where each entry is HMAC-linked to ",
  "its predecessor so tampering is detectable and locatable [2].",
];

const QUERY_RESPONSE = {
  answer: ANSWER_PARTS.join(""),
  insufficient_evidence: false,
  faithful: true,
  faithfulness_score: 0.86,
  citations: [
    {
      marker: 1,
      document_id: DOC_A,
      chunk_id: CHUNK_A,
      page_number: 4,
      char_start: 1203,
      char_end: 1487,
      snippet:
        "§164.312(b) Audit controls. Implement hardware, software, and/or procedural mechanisms that record and examine activity in information systems that contain or use electronic protected health information.",
    },
    {
      marker: 2,
      document_id: DOC_B,
      chunk_id: CHUNK_C,
      page_number: 12,
      char_start: 604,
      char_end: 918,
      snippet:
        "Every sensitive action appends a record whose entry_hash is HMAC-SHA256 over the canonical payload plus the previous entry_hash, making the ledger tamper-evident and the first altered entry precisely identifiable.",
    },
  ],
  retrieved_chunks: [
    {
      chunk_id: CHUNK_A,
      document_id: DOC_A,
      score: 0.713,
      page_number: 4,
      content_preview:
        "§164.312(b) Audit controls. Implement hardware, software, and/or procedural mechanisms that record and examine activity in information systems that contain or use electronic protected health information.",
    },
    {
      chunk_id: CHUNK_C,
      document_id: DOC_B,
      score: 0.688,
      page_number: 12,
      content_preview:
        "Every sensitive action appends a record whose entry_hash is HMAC-SHA256 over the canonical payload plus the previous entry_hash, making the ledger tamper-evident.",
    },
    {
      chunk_id: CHUNK_B,
      document_id: DOC_A,
      score: 0.402,
      page_number: 7,
      content_preview:
        "Workforce security. Implement policies and procedures to ensure that all members of the workforce have appropriate access to electronic protected health information.",
    },
  ],
  doc_grades: [
    { chunk_id: CHUNK_A, relevant: true, score: 0.94 },
    { chunk_id: CHUNK_C, relevant: true, score: 0.88 },
    { chunk_id: CHUNK_B, relevant: false, score: 0.31 },
  ],
  correction_applied: false,
  latency_ms: 4210,
  request_id: "b7c1e93f-8a24-4d17-95c0-2e6b1f70a8d3",
};

const DOCUMENTS = {
  items: [
    {
      id: DOC_A,
      filename: "hipaa-security-rule-controls.pdf",
      classification: "confidential",
      allowed_roles: ["analyst", "compliance_auditor"],
      chunk_count: 184,
      status: "ready",
      created_at: "2026-07-21T09:14:22Z",
    },
    {
      id: DOC_B,
      filename: "aegis-audit-architecture.md",
      classification: "internal",
      allowed_roles: ["analyst", "viewer", "compliance_auditor"],
      chunk_count: 41,
      status: "ready",
      created_at: "2026-07-22T15:02:10Z",
    },
    {
      id: "d1f7a950-6b3c-4e08-8a52-71c4b9d0e6f2",
      filename: "incident-response-runbook.docx",
      classification: "restricted",
      allowed_roles: ["admin"],
      chunk_count: 96,
      status: "ready",
      created_at: "2026-07-23T11:48:35Z",
    },
    {
      id: "f409c2b8-1d76-4a53-b0e9-5c827fa3d914",
      filename: "data-retention-policy-v4.pdf",
      classification: "public",
      allowed_roles: ["analyst", "viewer"],
      chunk_count: 27,
      status: "ready",
      created_at: "2026-07-24T08:30:02Z",
    },
  ],
  total: 4,
  page: 1,
  size: 20,
};

const GENESIS = "0".repeat(64);
const hex = (seed) => {
  // Deterministic 64-hex that LOOKS like a digest without pretending to be one.
  // xorshift32, not an LCG: an LCG's low bits are barely random, so the output
  // came out full of zero runs ("798000...5180") and read as obviously fake.
  let x = (seed * 2654435761) >>> 0 || 1;
  let h = "";
  while (h.length < 64) {
    x ^= x << 13;
    x >>>= 0;
    x ^= x >>> 17;
    x ^= x << 5;
    x >>>= 0;
    h += x.toString(16).padStart(8, "0");
  }
  return h.slice(0, 64);
};

const AUDIT_ACTIONS = [
  ["auth.login", "user", "success", { username: "admin" }],
  ["document.ingested", "document", "success", { filename: "hipaa-security-rule-controls.pdf", chunks: 184 }],
  ["query.executed", "query", "success", { faithful: true, correction_applied: false }],
  ["auth.login_failed", "user", "denied", { username: "analyst", reason: "bad_credentials" }],
  ["auth.login", "user", "success", { username: "analyst" }],
  ["query.denied", "query", "denied", { reason: "no_accessible_documents" }],
  ["document.ingested", "document", "success", { filename: "incident-response-runbook.docx", chunks: 96 }],
  ["role.assigned", "user", "success", { add: ["compliance_auditor"] }],
  ["query.executed", "query", "success", { faithful: false, correction_applied: true }],
  ["audit.verified", "audit", "success", { ok: true, total: 1284 }],
];

const AUDIT = {
  items: AUDIT_ACTIONS.map(([action, resource_type, outcome, details], i) => {
    const id = 1284 - i;
    return {
      id,
      ts: new Date(Date.UTC(2026, 6, 24, 14, 20 - i * 3, 41)).toISOString(),
      actor_id: outcome === "denied" && action === "auth.login_failed" ? null : USER.id,
      actor_roles: action.startsWith("auth.login_failed") ? [] : ["admin"],
      action,
      resource_type,
      resource_id: resource_type === "document" ? DOC_A : null,
      outcome,
      ip_address: "172.19.0.4",
      request_id: `3f9a${(1000 + i).toString(16)}-2c41-4b8d-9e07-6a15c8b0d${(20 + i).toString(16)}f`,
      details,
      prev_hash: id === 1 ? GENESIS : hex(id - 1),
      entry_hash: hex(id),
    };
  }),
  total: 1284,
  page: 1,
  size: 50,
};

const CHAIN_OK = { ok: true, total: 1284, first_broken_id: null, broken_field: null };

let evalRuns = [
  {
    id: "5c1e8a37-90fd-4b26-a814-7e0c39b5d2f1",
    suite: "both",
    dataset: "eval/datasets/golden_qa.jsonl",
    status: "completed",
    passed: true,
    faithfulness_avg: 0.86,
    hallucination_rate: 0.08,
    created_at: "2026-07-24T13:05:44Z",
  },
  {
    id: "8b03d5f1-27ac-4e69-b0d8-41f96c7a2e5b",
    suite: "ragas",
    dataset: "eval/datasets/golden_qa.jsonl",
    status: "completed",
    passed: false,
    faithfulness_avg: 0.62,
    hallucination_rate: 0.24,
    created_at: "2026-07-23T17:41:09Z",
  },
];

// ── Static server for the built SPA ────────────────────────────────────────

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".woff2": "font/woff2",
  ".json": "application/json; charset=utf-8",
  ".ico": "image/x-icon",
};

async function serveDist() {
  try {
    await stat(join(DIST, "index.html"));
  } catch {
    console.error(`No build at ${DIST}. Run: cd frontend && npm run build`);
    process.exit(2);
  }

  const server = createServer((req, res) => {
    const url = new URL(req.url, BASE);
    let file = join(DIST, decodeURIComponent(url.pathname));
    // SPA fallback: any path without a file extension is a client route.
    if (!extname(url.pathname)) file = join(DIST, "index.html");
    createReadStream(file)
      .on("open", () => res.writeHead(200, { "content-type": MIME[extname(file)] ?? "application/octet-stream" }))
      .on("error", () => {
        res.writeHead(404).end("not found");
      })
      .pipe(res);
  });

  await new Promise((r) => server.listen(PORT, "127.0.0.1", r));
  return server;
}

// ── API stub ───────────────────────────────────────────────────────────────

const json = (route, body, status = 200) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

/** Build the SSE body exactly as /query/stream emits it (see useQueryStream). */
function sseBody(response) {
  // Token frames concatenate with no separator, so each part carries its own
  // spacing. The final frame is `event: done` + the full QueryResponse.
  const frames = response.answer
    ? ANSWER_PARTS.map((part) => `data: ${part}\n\n`)
    : [];
  frames.push(`event: done\ndata: ${JSON.stringify(response)}\n\n`);
  return frames.join("");
}

async function installStubs(context) {
  await context.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname.replace(/^.*\/api\/v1/, "");
    const method = req.method();

    if (path === "/auth/login" && method === "POST") {
      return json(route, {
        access_token: "demo.access.token",
        refresh_token: "demo.refresh.token",
        token_type: "bearer",
        user: USER,
      });
    }
    if (path === "/auth/me") return json(route, { ...USER, email: "admin@example.internal", is_active: true });
    if (path === "/auth/logout") return json(route, { status: "ok" });

    if (path === "/query/stream" && method === "POST") {
      // Hold briefly so the "Retrieving evidence…" state is visible in the GIF —
      // the real graph runs retrieval → rerank → CRAG → generation → grading
      // before anything renders.
      await new Promise((r) => setTimeout(r, 1500));
      return route.fulfill({
        status: 200,
        headers: { "content-type": "text/event-stream; charset=utf-8", "cache-control": "no-cache" },
        body: sseBody(QUERY_RESPONSE),
      });
    }
    if (path === "/query" && method === "POST") return json(route, QUERY_RESPONSE);

    if (path.startsWith("/documents")) return json(route, DOCUMENTS);
    if (path.startsWith("/audit/verify")) return json(route, CHAIN_OK);
    if (path.startsWith("/audit")) return json(route, AUDIT);

    if (path === "/eval/run" && method === "POST") {
      evalRuns = [
        {
          id: "0a7f4e21-6c93-4d58-8b1e-25f0a9c7d3e6",
          suite: "both",
          dataset: "eval/datasets/golden_qa.jsonl",
          status: "running",
          passed: false,
          faithfulness_avg: null,
          hallucination_rate: null,
          created_at: new Date(Date.UTC(2026, 6, 24, 14, 22, 3)).toISOString(),
        },
        ...evalRuns,
      ];
      return json(route, { run_id: evalRuns[0].id }, 202);
    }
    if (path.startsWith("/eval/runs")) return json(route, { items: evalRuns, total: evalRuns.length });

    return json(route, { error: { code: "not_stubbed", message: path, request_id: "demo" } }, 404);
  });
}

// ── Capture ────────────────────────────────────────────────────────────────

// ESM resolves bare specifiers from this file's directory upward, ignoring
// NODE_PATH — so when playwright lives outside the repo, point AEGIS_PLAYWRIGHT
// at its directory (an absolute path import always resolves).
let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch {
  const external = process.env.AEGIS_PLAYWRIGHT;
  if (!external) {
    console.error(
      "playwright is not installed. Either:\n" +
        "  npm i -D playwright\n" +
        "or point at an existing install:\n" +
        "  AEGIS_PLAYWRIGHT=/path/to/node_modules/playwright node infra/scripts/capture_demo.mjs",
    );
    process.exit(2);
  }
  ({ chromium } = await import(resolve(external, "index.mjs")).catch(() => import(external)));
}

const server = await serveDist();
await mkdir(OUT, { recursive: true });

const launchOpts = {};
if (process.env.AEGIS_CHROMIUM) launchOpts.executablePath = process.env.AEGIS_CHROMIUM;
const browser = await chromium.launch(launchOpts);

const baseContext = {
  deviceScaleFactor: 2, // the UI is hairline-heavy and blurs at 1x
  colorScheme: "dark",
  reducedMotion: "reduce", // freeze pulses so stills are deterministic
};

async function signIn(page) {
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await page.waitForSelector("#username");
  await page.fill("#username", "admin");
  await page.fill("#password", "demo-passphrase");
  await Promise.all([page.waitForURL(/\/(chat|documents)/), page.click('button[type="submit"]')]);
}

/**
 * Navigate by CLICKING the in-app nav, never page.goto().
 *
 * The auth store is deliberately in-memory only (no localStorage — see
 * store/authStore.ts and §6.18). A full document navigation therefore wipes the
 * token and <Protected> bounces straight back to /login, so every post-login
 * goto() silently captures the login screen instead of the intended route.
 * Client-side routing keeps the store alive.
 */
const ROUTES = {
  Interrogate: "/chat",
  Corpus: "/documents",
  Ledger: "/audit",
  Evaluation: "/eval",
};

async function navigate(page, label) {
  const route = ROUTES[label];
  if (page.url().endsWith(route)) return;
  await page.getByRole("link", { name: new RegExp(label, "i") }).first().click();
  await page.waitForURL(new RegExp(`${route}$`));
  await page.waitForLoadState("networkidle");
}

// ── Pass 1 · stills ────────────────────────────────────────────────────────

{
  const context = await browser.newContext({ ...baseContext, viewport: DESKTOP });
  await installStubs(context);
  const page = await context.newPage();
  const shot = async (name) => {
    await page.screenshot({ path: resolve(OUT, `${name}.png`) });
    console.log(`✓ ${name}.png`);
  };

  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await page.waitForSelector("#username");
  await shot("01-login");

  await signIn(page);
  await navigate(page, "Interrogate");
  await page.waitForTimeout(400);
  await shot("02-interrogate-empty");

  await page.fill('input[placeholder="Query the corpus…"]', DEMO_QUERY);
  await page.click('form button[type="submit"]');
  await page.waitForSelector("text=/verified|unverified/i", { timeout: 30_000 });
  await page.waitForTimeout(900); // let the gauge finish its width transition
  await shot("03-interrogate-answered");

  for (const [label, name] of [
    ["Corpus", "04-corpus"],
    ["Ledger", "05-ledger"],
    ["Evaluation", "06-evaluation"],
  ]) {
    await navigate(page, label);
    await page.waitForTimeout(600);
    await shot(name);
  }

  // Back to chat at desktop width (the rail is still visible), then shrink —
  // resizing keeps the SPA mounted, so the session survives.
  await navigate(page, "Interrogate");
  await page.setViewportSize(MOBILE);
  await page.waitForTimeout(400);
  await page.click('button[aria-label="Open navigation"]');
  await page.waitForTimeout(400);
  await shot("07-mobile-nav");

  await context.close();
}

// ── Pass 2 · demo GIF ──────────────────────────────────────────────────────

async function findFfmpeg() {
  if (process.env.AEGIS_FFMPEG) return process.env.AEGIS_FFMPEG;
  const cache = join(process.env.HOME ?? "", ".cache/ms-playwright");
  try {
    for (const dir of await readdir(cache)) {
      if (!dir.startsWith("ffmpeg")) continue;
      for (const f of await readdir(join(cache, dir))) {
        if (f.startsWith("ffmpeg")) return join(cache, dir, f);
      }
    }
  } catch {
    /* no cache */
  }
  return "ffmpeg";
}

if (!process.env.AEGIS_SKIP_GIF) {
  const videoDir = resolve(OUT, ".video");
  await rm(videoDir, { recursive: true, force: true });

  const context = await browser.newContext({
    ...baseContext,
    deviceScaleFactor: 1, // video is downscaled anyway; 2x just wastes frames
    viewport: { width: 1280, height: 800 },
    recordVideo: { dir: videoDir, size: { width: 1280, height: 800 } },
  });
  await installStubs(context);
  const page = await context.newPage();

  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await page.waitForSelector("#username");
  await page.waitForTimeout(900);
  await page.type("#username", "admin", { delay: 90 });
  await page.type("#password", "demo-passphrase", { delay: 55 });
  await page.waitForTimeout(400);
  await Promise.all([page.waitForURL(/\/(chat|documents)/), page.click('button[type="submit"]')]);
  await navigate(page, "Interrogate");
  await page.waitForTimeout(800);

  await page.type('input[placeholder="Query the corpus…"]', DEMO_QUERY, { delay: 42 });
  await page.waitForTimeout(300);
  await page.click('form button[type="submit"]');
  await page.waitForSelector("text=/verified|unverified/i", { timeout: 30_000 });
  await page.waitForTimeout(2600); // dwell on the answer + evidence rail

  await navigate(page, "Corpus");
  await page.waitForTimeout(1800);

  await navigate(page, "Ledger");
  await page.waitForTimeout(700);
  try {
    await page.getByRole("button", { name: /verify/i }).first().click({ timeout: 3000 });
    await page.waitForTimeout(1900);
  } catch {
    console.warn("! no Verify button matched — continuing");
    await page.waitForTimeout(900);
  }

  await navigate(page, "Evaluation");
  await page.waitForTimeout(700);
  try {
    await page.getByRole("button", { name: /run eval/i }).click({ timeout: 3000 });
    await page.waitForTimeout(2200); // the new run appears as "Running"
  } catch {
    await page.waitForTimeout(1400);
  }

  const video = page.video();
  await context.close(); // flushes the video file
  const webm = video ? await video.path() : null;

  if (webm) {
    const ffmpeg = await findFfmpeg();
    const gif = resolve(OUT, "demo.gif");
    const filters =
      "fps=11,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=3";
    try {
      await run(ffmpeg, ["-y", "-i", webm, "-filter_complex", filters, "-loop", "0", gif], {
        maxBuffer: 1 << 28,
      });
      const { size } = await stat(gif);
      console.log(`✓ demo.gif (${(size / 1e6).toFixed(2)} MB)`);
      // Only discard the source once the GIF actually exists.
      await rm(videoDir, { recursive: true, force: true }).catch(() => {});
    } catch (err) {
      // Playwright's bundled ffmpeg is a minimal VP8 build with no GIF encoder
      // or palette filters. Keep the webm so it can be converted by hand, and
      // print ffmpeg's own diagnostics rather than just the exec message.
      const detail = (err.stderr ?? err.message ?? "").toString().trim().split("\n").slice(-4).join("\n");
      console.warn(`! GIF encode failed using ${ffmpeg}:\n${detail}\n  video kept: ${webm}`);
      console.warn("  Install a full ffmpeg (e.g. npm i ffmpeg-static) and set AEGIS_FFMPEG.");
    }
  }
}

await browser.close();
server.close();
console.log(`\nWrote to ${OUT}`);
