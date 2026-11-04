#!/usr/bin/env node
/**
 * Run a lobby game headless: the simulated wand in Pyodide under Node, with
 * virtual peer wands and Splats (js/headless.js). No browser.
 *
 *   node Bag3/Code/Simulator/tools/sim_run.mjs --game lobbytest [--seconds 20] [--seed 1] [--scale 4]
 *   node Bag3/Code/Simulator/tools/sim_run.mjs --file my_game.py
 *   --verbose also prints everything the wand printed.
 *
 * Prints a JSON report and exits 1 when the game raised, or when play() did
 * not return after the leader ended the game or went silent.
 *
 * Imported, it exports simRun({ code | game, seconds, seed, scale }) for
 * BroadcastCode/ChatBroadcast/tools/prompt_eval.mjs; each call boots its own
 * Pyodide.
 *
 * Pyodide comes from its npm package, not the CDN the browser uses: set
 * PYODIDE_DIR to an unpacked `pyodide` package directory, or leave it unset
 * to fetch it once with `npm pack` into the OS temp dir (the same place
 * tools/room_smoke.mjs looks).
 */

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { createHeadlessRoom, simRunWith } from "../js/headless.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const SIM = resolve(HERE, "..");
const PYODIDE_VERSION = /PYODIDE_VERSION = "([^"]+)"/.exec(readFileSync(join(SIM, "wand-sim.js"), "utf8"))[1];

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

async function bootPyodide() {
  const dir = pyodideDir();
  const { loadPyodide } = await import(pathToFileURL(join(dir, "pyodide.mjs")).href);
  return loadPyodide({ indexURL: dir + "/", stdout: () => {}, stderr: () => {} });
}

/** Run one lobby game headless; see js/headless.js simRunWith for the result. */
export async function simRun({ code = null, game = null, seconds = 20, seed = 1, scale = 4 } = {}) {
  const pyodide = await bootPyodide();
  const room = await createHeadlessRoom({
    pyodide, scale, readText: (rel) => readFile(join(SIM, rel), "utf8"),
  });
  try {
    return await simRunWith(room, { code, game, seconds, seed });
  } finally {
    await room.stop();
    room.dispose();
  }
}

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : fallback;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const file = arg("file", null);
  const opts = {
    game: file ? null : arg("game", "lobbytest"),
    code: file ? readFileSync(file, "utf8") : null,
    seconds: Number(arg("seconds", 20)),
    seed: Number(arg("seed", 1)),
    scale: Number(arg("scale", 4)),
  };
  const t0 = Date.now();
  const r = await simRun(opts);
  const { prints, ...report } = r;
  console.log(JSON.stringify({ ...report, realSeconds: (Date.now() - t0) / 1000 }, null, 2));
  if (process.argv.includes("--verbose")) console.log(`\nwand output:\n${prints.join("\n")}`);
  else if (!r.ok) console.log(`\nlast wand output:\n${prints.slice(-60).join("\n")}`);
  process.exit(r.ok ? 0 : 1);
}
