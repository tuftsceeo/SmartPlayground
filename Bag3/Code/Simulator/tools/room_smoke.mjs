#!/usr/bin/env node
/**
 * Browser smoke for <sim-room>: load goalrace with its display file, check
 * the display panel appears, shows the ready icon, and reacts to the wand's
 * `goal` broadcast (whale icon for blue, `winner` sent back over the bus).
 *
 * Run from anywhere:  node Bag3/Code/Simulator/tools/room_smoke.mjs
 *
 * Serves Bag3/Code with `python3 -m http.server`. Pyodide normally loads from
 * cdn.jsdelivr.net; this script answers those requests from a local copy of
 * the same version's npm package instead, so it runs without access to that
 * CDN. Set PYODIDE_DIR to an unpacked `pyodide` package directory, or leave
 * it unset to fetch the package once with `npm pack` into the OS temp dir.
 * Chromium comes from PLAYWRIGHT_BROWSERS_PATH (default /opt/pw-browsers).
 */

import { spawn, execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve, extname } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";

const HERE = dirname(fileURLToPath(import.meta.url));
const SIM = resolve(HERE, "..");
const CODE = resolve(SIM, "..");
process.env.PLAYWRIGHT_BROWSERS_PATH ||= "/opt/pw-browsers";

function loadPlaywright() {
  for (const base of [import.meta.url, "file:///opt/node-tools/"]) {
    try {
      return createRequire(base)("playwright");
    } catch (err) {
      if (err.code !== "MODULE_NOT_FOUND") throw err;
    }
  }
  throw new Error("playwright not found (looked next to this script and in /opt/node-tools)");
}
const { chromium } = loadPlaywright();

const wandSrc = readFileSync(join(SIM, "wand-sim.js"), "utf8");
const PYODIDE_VERSION = /PYODIDE_VERSION = "([^"]+)"/.exec(wandSrc)[1];

function pyodideDir() {
  if (process.env.PYODIDE_DIR) return process.env.PYODIDE_DIR;
  const dir = join(tmpdir(), `pyodide-npm-${PYODIDE_VERSION}`);
  const pkg = join(dir, "package");
  if (!existsSync(join(pkg, "pyodide.asm.wasm"))) {
    mkdirSync(dir, { recursive: true });
    execFileSync("npm", ["pack", `pyodide@${PYODIDE_VERSION}`, "--silent"], { cwd: dir, stdio: "inherit" });
    execFileSync("tar", ["xzf", `pyodide-${PYODIDE_VERSION}.tgz`], { cwd: dir, stdio: "inherit" });
  }
  return pkg;
}

/** icon_store's parse of an icon file, as a hex string of 768 bytes. */
function iconHex(path) {
  const vals = [];
  for (const line of readFileSync(path, "utf8").split("\n")) {
    const t = line.trim();
    if (!t.startsWith("(")) continue;
    for (const m of t.matchAll(/\((\d+),\s*(\d+),\s*(\d+)\)/g)) vals.push(+m[1], +m[2], +m[3]);
  }
  assert.equal(vals.length, 768, `${path}: expected 768 values`);
  return vals.map((v) => v.toString(16).padStart(2, "0")).join("");
}

const ICONS = join(SIM, "vendor", "display", "games", "goalrace_icons");
const READY = iconHex(join(ICONS, "ready.py"));
const WHALE = iconHex(join(ICONS, "whale.py"));

const MIME = { ".js": "text/javascript", ".mjs": "text/javascript", ".wasm": "application/wasm",
  ".json": "application/json", ".zip": "application/zip" };

async function startServer() {
  const port = 8800 + Math.floor(Math.random() * 900);
  const proc = spawn("python3", ["-m", "http.server", String(port), "--bind", "127.0.0.1"],
    { cwd: CODE, stdio: ["ignore", "ignore", "pipe"] });
  const origin = `http://127.0.0.1:${port}`;
  for (let i = 0; i < 50; i++) {
    try {
      const r = await fetch(`${origin}/Simulator/index.html`);
      if (r.ok) return { proc, origin };
    } catch { /* not listening yet */ }
    await new Promise((r) => setTimeout(r, 100));
  }
  proc.kill();
  throw new Error("http.server did not start");
}

const pyDir = pyodideDir();
const { proc, origin } = await startServer();
const browser = await chromium.launch();
let failed = false;
const errors = [];
const consoleLines = [];
try {
  const page = await browser.newPage();
  page.on("console", (m) => consoleLines.push(`[${m.type()}] ${m.text()}`));
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.route(`https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/**`, (route) => {
    const name = new URL(route.request().url()).pathname.split("/").pop();
    const file = join(pyDir, name);
    if (!existsSync(file)) return route.fulfill({ status: 404, body: `not in local pyodide: ${name}` });
    return route.fulfill({ status: 200, body: readFileSync(file),
      headers: { "content-type": MIME[extname(name)] || "application/octet-stream" } });
  });

  await page.goto(`${origin}/Simulator/index.html?game=goalrace`);

  // 1. The display panel appears and draws the ready icon.
  await page.waitForFunction(() => {
    const room = document.querySelector("sim-room");
    const box = room?.shadowRoot.querySelector('[data-panel="display"]');
    return box && !box.hidden && room.panel("display")?.ready;
  }, null, { timeout: 120000 });
  const caps = await page.evaluate(() => document.querySelector("sim-room").capabilities);
  assert.equal(caps.has_display_file, true);
  assert.equal(caps.uses_display, true);
  assert.equal(caps.party, false);
  await page.waitForFunction((hex) =>
    document.querySelector("sim-room").panel("display").lastFrameHex === hex, READY, { timeout: 30000 });
  const canvasShown = await page.evaluate(() => {
    const c = document.querySelector("sim-room").shadowRoot.querySelector('[data-el="display-canvas"]');
    return !c.hidden && c.width > 0;
  });
  assert.ok(canvasShown, "display canvas should be drawn");
  console.log("ok  display panel shown with the ready icon");

  // 2. Join blue and tap the goal on the wand.
  await page.evaluate(() => {
    const room = document.querySelector("sim-room");
    room.wand.pyodide.pyimport("sim_state").tap_nfc("teamblue");
  });
  await page.waitForTimeout(1500);
  await page.evaluate(() => {
    const room = document.querySelector("sim-room");
    room.wand.pyodide.pyimport("sim_state").tap_nfc("goal");
  });

  // 3. The display shows the whale and answers with `winner`.
  await page.waitForFunction((hex) =>
    document.querySelector("sim-room").panel("display").lastFrameHex === hex, WHALE, { timeout: 30000 });
  console.log("ok  display reacted to goal (whale icon)");
  const log = await page.evaluate(() => {
    const room = document.querySelector("sim-room");
    const dec = new TextDecoder();
    return room.bus.log.filter((e) => e.event === "send")
      .map((e) => ({ src: e.src, dst: e.dst, text: dec.decode(e.payload) }));
  });
  const goal = log.find((e) => e.src === "02:00:00:00:0a:01" && /"goal"/.test(e.text));
  const winner = log.find((e) => e.src === "02:00:00:00:0d:01" && /"winner"/.test(e.text));
  assert.ok(goal, "bus log has the wand's goal broadcast");
  assert.deepEqual(JSON.parse(goal.text), { type: "goal", team: "blue" });
  assert.ok(winner, "bus log has the display's winner broadcast");
  assert.deepEqual(JSON.parse(winner.text), { type: "winner", team: "blue" });
  const feed = await page.evaluate(() =>
    document.querySelector("sim-room").shadowRoot.querySelector('[data-el="display-feed"]').textContent);
  assert.match(feed, /"goal"/, "feed lists the wand's goal message");
  console.log("ok  bus log: goal from wand, winner from display");

  assert.ok(!consoleLines.some((l) => /renderPreview unavailable/.test(l)),
    "display should draw with iconmaker's renderPreview");
  const realErrors = errors.filter((e) => !/favicon/.test(e));
  assert.deepEqual(realErrors, [], `page errors:\n${realErrors.join("\n")}`);
  console.log("PASS room_smoke");
} catch (err) {
  failed = true;
  console.error("FAIL room_smoke:", err.message || err);
  console.error("page console (last 40 lines):\n" + consoleLines.slice(-40).join("\n"));
} finally {
  await browser.close();
  proc.kill();
}
process.exit(failed ? 1 : 0);
