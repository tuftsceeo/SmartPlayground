// S6 browser check: serves Bag3/Code, drives Simulator/index.html, screenshots each case.
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
const CODE = new URL("../../", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
const PORT = 8765;
const srv = spawn("python", ["-m", "http.server", String(PORT), "--bind", "127.0.0.1"], { cwd: CODE, stdio: "ignore" });
await new Promise((r) => setTimeout(r, 1500));
mkdirSync("shots", { recursive: true });
const browser = await chromium.launch();
const results = [];

async function run(name, { game, source, settings, overlay, press, waitMs = 25000 }) {
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.goto(`http://127.0.0.1:${PORT}/Simulator/index.html?game=jump`);
  await page.waitForFunction(() => document.getElementById("log").textContent.length > 0, null, { timeout: 120000 });
  await page.evaluate(({ source, settings, game }) => {
    const sim = document.getElementById("sim");
    sim.settings = settings || null;      // applies at the next load, as ChatBroadcast does
    sim.setAttribute("autostart", "");
    if (source) sim.source = source; else sim.setAttribute("game", game);
  }, { source, settings, game });
  if (overlay) {
    await page.waitForTimeout(6000);
    const btn = page.getByRole("button", { name: /multiple device/i });
    if (await btn.count()) await btn.first().click(); else errors.push("no multi-device button");
  }
  await page.waitForTimeout(waitMs);
  if (press) {
    // Hold the button of the leader (plain lobby) or the Splat host wand.
    const pressed = await page.evaluate(async ({ who, ms }) => {
      const sim = document.getElementById("sim");
      const all = [...document.querySelectorAll("wand-sim")];
      const isHost = (w) => { try { return w.pyodide.pyimport("runtime").get_runtime()._role === "splat_host"; } catch { return false; } };
      const target = who === "host" ? all.find(isHost) : sim.wand;
      if (!target) return "no target";
      const st = target.pyodide.pyimport("sim_state");
      st.button_pressed = true;
      await new Promise((r) => setTimeout(r, ms));
      st.button_pressed = false;
      return "pressed " + who;
    }, press);
    console.log(name, pressed);
    if (pressed === "no target" && press.at) {
      // Hold the on-screen button of that wand with the mouse.
      await page.mouse.move(press.at[0], press.at[1]);
      await page.mouse.down();
      await page.waitForTimeout(press.ms);
      await page.mouse.up();
      console.log(name, "mouse hold at", press.at);
    }
    await page.waitForTimeout(8000);
  }
  await page.screenshot({ path: `shots/${name}.png`, fullPage: true });
  const log = await page.evaluate(() => document.getElementById("log").textContent);
  writeFileSync(`shots/${name}.log`, log);
  const keep = log.split("\n").filter((l) => !/pw_hb|pw_lobby|espnow broadcast|^enow/.test(l));
  results.push({ name, errors, log: keep.slice(-40).join("\n") });
  await page.close();
}

const only = process.argv[2];
const cases = {
  colorpads_2: { game: "colorpads", settings: { splats: 2 } },
  colorpads_1: { game: "colorpads", settings: { splats: 1 }, waitMs: 12000 },
  plainlobby: { source: readFileSync("plainlobby.py", "utf8"), settings: { wands: 2 }, overlay: true, press: { who: "leader", ms: 300 } },
  host_splattag: { game: "host_splattag", settings: { splat_host: 4, wands: 2 }, overlay: true, press: { who: "host", ms: 3500, at: [700, 397] }, waitMs: 40000 },
};
for (const [n, c] of Object.entries(cases)) if (!only || only === n) await run(n, c);
await browser.close(); srv.kill();
for (const r of results) console.log(`\n===== ${r.name}  errors: ${JSON.stringify(r.errors)}\n${r.log}`);
