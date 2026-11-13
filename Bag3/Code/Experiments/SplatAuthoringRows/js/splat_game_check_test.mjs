/**
 * splat_game_check_test.mjs -- send-time checks for wand Splat games in the
 * SplatAuthoringRows experiment: splatGameCheck.js (declarations, net and
 * splats use) and splatActionCheck.js (action names, including
 * splats.unit(i).play/color/note/sound).
 *
 * The send-time gate is the wand branch of ChatBroadcast js/upload.js
 * validateGameCode: the problems from splatGameProblems, then the unknown
 * action names. upload.js is not copied here, so that gate is mirrored in
 * sendCheck() below.
 *
 * Also runs the host games in SplatAuthoringRows/wand/games/ through the check.
 *
 * Usage, from SplatAuthoringRows/: node js/splat_game_check_test.mjs
 */
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { splatGameProblems } from "./splatGameCheck.js";
import { unknownSplatActionsIn } from "./splatActionCheck.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXPERIMENT = resolve(HERE, "..");

// play() signatures: the wand's 7-argument form, net=None last, and splats=None last (solo).
const SIG7 = "def play(nfc, leds, buz, accel, i2c, enow, batt=None):\n";
const SIG_NET = "def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):\n";
const SIG_SPLATS = "def play(nfc, leds, buz, accel, i2c, enow, batt=None, splats=None):\n";
const HOST_END = "    while True:\n        ev = net.poll()\n        if ev == (\"end\",):\n            return\n";

let failed = 0;
function t(name, fn) {
  try { fn(); console.log(`ok   ${name}`); }
  catch (e) { failed++; console.log(`FAIL ${name}\n  ${e.message}`); }
}
const probs = code => splatGameProblems(code);
const clean = code => assert.deepEqual(probs(code), []);
const one = (code, re) => {
  const p = probs(code);
  assert.equal(p.length, 1, p.join(" | ") || "no problem reported");
  assert.match(p[0], re);
};
const has = (code, re) => {
  const p = probs(code);
  assert.ok(p.some(s => re.test(s)), `no problem matched ${re}: ${p.join(" | ") || "none"}`);
};
/** The wand send-time gate, as upload.js validateGameCode runs it for role "wand". */
function sendCheck(code) {
  const problems = splatGameProblems(code);
  if (problems.length) return [false, problems.join("\n")];
  const unknown = unknownSplatActionsIn(code);
  if (unknown.length) return [false, `unknown Splat action names: ${unknown.join(", ")}`];
  return [true, null];
}

// --- no Splat declaration -------------------------------------------------

t("ordinary game: no problems", () => clean(SIG7 + "    network = 1\n    # net.poll()\n    print('net')\n"));
t("ordinary game: enow.poll() is fine", () => clean(SIG7 + "    t, d, m = enow.poll()\n"));
t("no declaration: net used without the parameter", () => one(SIG7 + "    ev = net.poll()\n", /uses `net` but play\(\) has no `net=None`/));
t("no declaration: net aliased without the parameter", () => one(SIG7 + "    n = net\n", /uses `net` but play\(\) has no `net=None`/));
t("no declaration: net used with the parameter is refused (net is None)", () =>
  one(SIG_NET + "    ev = net.poll()\n", /declares no Splats .*net is None/));
t("no declaration: splats used is refused (splats is None)", () =>
  one(SIG_SPLATS + "    splats.unit(0).off()\n", /uses `splats` but declares no SPLATS_LOCAL/));

// --- SPLATS_LOCAL: solo wand with its own paired Splats -------------------

t("SPLATS_LOCAL = 1 with splats=None: no problems", () =>
  clean("SPLATS_LOCAL = 1\n" + SIG_SPLATS + "    splats.unit(0).color('turnred')\n"));
t("SPLATS_LOCAL = 2 with splats=None and enow.poll(): no problems", () =>
  clean("SPLATS_LOCAL = 2\n" + SIG_SPLATS + "    t, d, m = enow.poll()\n    splats.poll()\n"));
t("SPLATS_LOCAL = 3 is refused", () => one("SPLATS_LOCAL = 3\n" + SIG_SPLATS, /SPLATS_LOCAL must be 1 or 2; it is 3/));
t("SPLATS_LOCAL = '1' is refused", () => one("SPLATS_LOCAL = '1'\n" + SIG_SPLATS, /SPLATS_LOCAL must be 1 or 2/));
t("SPLATS_LOCAL must not declare SPLATS_MIN", () => has("SPLATS_LOCAL = 1\nSPLATS_MIN = 1\n" + SIG_SPLATS, /must not declare SPLATS_MIN/));
t("SPLATS_LOCAL must not declare SPLATS_MAX", () => has("SPLATS_LOCAL = 1\nSPLATS_MAX = 2\n" + SIG_SPLATS, /must not declare SPLATS_MAX/));
t("SPLATS_LOCAL must not declare SPLAT_HOST", () => has("SPLATS_LOCAL = 1\nSPLAT_HOST = False\n" + SIG_SPLATS, /must not declare SPLAT_HOST/));
t("SPLATS_LOCAL needs splats=None as the last parameter", () => {
  has("SPLATS_LOCAL = 1\n" + SIG7, /needs `splats=None` as play/);
  has("SPLATS_LOCAL = 1\n" + SIG_NET, /needs `splats=None` as play/);
  has("SPLATS_LOCAL = 1\ndef play(nfc, leds, buz, accel, i2c, enow, batt=None, splats):\n    pass\n", /needs `splats=None` as play/);
});
t("SPLATS_LOCAL with net as a ninth parameter is refused", () =>
  has("SPLATS_LOCAL = 1\ndef play(nfc, leds, buz, accel, i2c, enow, batt=None, splats=None, net=None):\n    pass\n", /needs `splats=None` as play/));
t("SPLATS_LOCAL must not use net", () => has("SPLATS_LOCAL = 1\n" + SIG_SPLATS + "    net.poll()\n", /must not use `net`/));
t("SPLATS_LOCAL must not use net.splat", () => has("SPLATS_LOCAL = 1\n" + SIG_SPLATS + "    net.splat(0).off()\n", /must not use `net`/));

// --- SPLAT_HOST: host group game -----------------------------------------

const HOST = "SPLAT_HOST = True\nSPLATS_MIN = 2\nSPLATS_MAX = 4\nPLAYERS_MIN = 1\n";

t("host game: no problems", () =>
  clean(HOST + SIG_NET + "    if net.is_host:\n        net.splat(0).color('turnred')\n" + HOST_END));
t("host game: SPLATS_MIN 1..4 and SPLATS_MAX None are fine", () =>
  clean("SPLAT_HOST = True\nSPLATS_MIN = 1\nSPLATS_MAX = None\n" + SIG_NET + HOST_END));
t("host game: SPLATS_MIN above 4 is refused", () => has(HOST.replace("SPLATS_MIN = 2", "SPLATS_MIN = 5") + SIG_NET + HOST_END, /SPLATS_MIN \(5\) is more than a Splat host holds/));
t("host game: SPLATS_MAX above 4 is refused", () => one(HOST.replace("SPLATS_MAX = 4", "SPLATS_MAX = 5") + SIG_NET + HOST_END, /more than a Splat host holds/));
t("host game: SPLATS_MIN 0 is refused", () => has("SPLAT_HOST = True\nSPLATS_MIN = 0\n" + SIG_NET + HOST_END, /SPLATS_MIN must be a whole number of at least 1/));
t("host game: SPLAT_HOST must be True or False", () => has("SPLAT_HOST = yes\nSPLATS_MIN = 1\n" + SIG_NET + HOST_END, /SPLAT_HOST must be True or False/));
t("host game: needs SPLATS_MIN", () => one("SPLAT_HOST = True\n" + SIG_NET + HOST_END, /needs SPLATS_MIN/));
t("host game: needs net=None", () => has("SPLAT_HOST = True\nSPLATS_MIN = 1\n" + SIG7 + HOST_END, /needs `net=None`/));
t("host game: takes net, not splats", () => has("SPLAT_HOST = True\nSPLATS_MIN = 1\n" + SIG_SPLATS + HOST_END, /takes `net`, not `splats`/));
t("host game: must not call enow.poll()", () => one(HOST + SIG_NET + "    t, d, m = enow.poll()\n" + HOST_END, /enow\.poll/));
t("host game: must return on (\"end\",)", () => one(HOST + SIG_NET + "    ev = net.poll()\n", /must return when net.poll\(\) reports/));
t("host game: a return up to two lines below (\"end\",) is accepted", () =>
  clean(HOST + SIG_NET + "    ev = net.poll()\n    if ev == (\"end\",) or ev == (\"leader_lost\",):\n        led = 0\n        return\n"));
t("host game: net.splat() without an is_host check is refused", () =>
  one(HOST + SIG_NET + "    net.splat(0).off()\n" + HOST_END, /never checks is_host/));
t("host game: PLAYERS_MIN 0 is refused", () => one(HOST.replace("PLAYERS_MIN = 1", "PLAYERS_MIN = 0") + SIG_NET + HOST_END, /at least 1/));
t("host game: PLAYERS_MIN not a number is refused", () => one(HOST.replace("PLAYERS_MIN = 1", "PLAYERS_MIN = x") + SIG_NET + HOST_END, /at least 1/));
t("host game: SPLAT_HOST with SPLATS_LOCAL is refused", () => has("SPLAT_HOST = True\nSPLATS_LOCAL = 1\n" + SIG_SPLATS, /must not declare SPLAT_HOST/));
t("PLAYERS_MIN outside a host game is refused", () => one("SPLATS_MIN = 1\nPLAYERS_MIN = 1\n" + SIG_NET + HOST_END, /only read in a Splat host game/));

// --- SPLATS_MIN without SPLAT_HOST: plain wand lobby, no Splats -----------

t("lobby game with net: no problems", () => clean("SPLATS_MIN = 2\nSPLATS_MAX = 4\n" + SIG_NET + "    net.send(None, {})\n"));
t("lobby game: SPLATS_MAX = None is allowed", () => clean("SPLATS_MIN = 1\nSPLATS_MAX = None\n" + SIG_NET));
t("lobby game without net is refused", () => one("SPLATS_MIN = 2\n" + SIG7, /needs `net=None`/));
t("lobby game: net.splat() is not available", () =>
  one("SPLATS_MIN = 1\n" + SIG_NET + "    net.splat(0).off()\n", /net\.splat\(\) is not available in a plain wand lobby/));
t("lobby game: must not call enow.poll()", () => one("SPLATS_MIN = 1\n" + SIG_NET + "    t, d, m = enow.poll()\n", /enow\.poll/));
t("lobby game: SPLATS_MIN = 0 is refused", () => one("SPLATS_MIN = 0\n" + SIG_NET, /SPLATS_MIN must be a whole number of at least 1/));
t("lobby game: SPLATS_MIN = '2' is refused", () => one("SPLATS_MIN = '2'\n" + SIG_NET, /SPLATS_MIN must be/));
t("lobby game: SPLATS_MAX below SPLATS_MIN is refused", () => one("SPLATS_MIN = 3\nSPLATS_MAX = 2\n" + SIG_NET, /smaller/));
t("lobby game: SPLATS_MAX not a number is refused", () => one("SPLATS_MIN = 2\nSPLATS_MAX = 2.5\n" + SIG_NET, /SPLATS_MAX must be/));
t("lobby game: SPLATS_MAX without SPLATS_MIN is refused", () => one("SPLATS_MAX = 2\n" + SIG_NET, /without SPLATS_MIN/));
t("a comment after a declared value is ignored", () => clean("SPLATS_MIN = 2   # two pads\n" + SIG_NET));

// --- Action names: sendCheck and splats.unit(i) ---------------------------

t("validateGameCode mirror refuses a bad Splat game and a bad action name", () => {
  assert.equal(sendCheck("SPLATS_MIN = 1\n" + SIG7)[0], false);
  const [ok, err] = sendCheck(HOST + SIG_NET + "    if net.is_host:\n        s = net.splat(0)\n        s.color('turnpurpel')\n" + HOST_END);
  assert.equal(ok, false);
  assert.match(err, /turnpurpel/);
});
t("net.splat(i) action names are checked", () => {
  assert.deepEqual(unknownSplatActionsIn("net.splat(0).color('turnpurpel')"), ["turnpurpel"]);
  assert.deepEqual(unknownSplatActionsIn("net.splat(0).sound('mooo')"), ["mooo"]);
});
t("splats.unit(i) color/note/sound names are checked", () => {
  assert.deepEqual(unknownSplatActionsIn("splats.unit(0).color('turnpurpel')"), ["turnpurpel"]);
  assert.deepEqual(unknownSplatActionsIn("splats.unit(1).note('note_z')"), ["note_z"]);
  assert.deepEqual(unknownSplatActionsIn("splats.unit(1).sound('mooo')"), ["mooo"]);
  assert.deepEqual(unknownSplatActionsIn("splats.unit(0).color('turnred', 'middle')"), ["middle"]);
});
t("splats.unit(i).play([...]) names are checked", () => {
  assert.deepEqual(unknownSplatActionsIn("splats.unit(0).play(['turnred', 'mooo', 'note_a'])"), ["mooo"]);
  assert.deepEqual(unknownSplatActionsIn("splats.unit(0).play(('turnpurpel',))"), ["turnpurpel"]);
});
t("known names through splats.unit(i) pass", () => {
  const code = SIG_SPLATS
    + "    splats.unit(0).color('turnred', 'inner')\n"
    + "    splats.unit(1).note('note_a')\n"
    + "    splats.unit(0).sound('cow')\n"
    + "    splats.unit(0).play(['turnblue', 'note_c', 'cat'])\n";
  assert.deepEqual(unknownSplatActionsIn(code), []);
  assert.deepEqual(sendCheck("SPLATS_LOCAL = 1\n" + code), [true, null]);
});

// --- Host games shipped in the experiment ----------------------------------

t("SplatAuthoringRows/wand/games host games pass the send check", () => {
  const dir = resolve(EXPERIMENT, "wand/games");
  const files = readdirSync(dir).filter(f => f.startsWith("host_") && f.endsWith(".py"));
  assert.ok(files.length >= 3, `found ${files.length} host games`);
  for (const f of files) {
    const [ok, err] = sendCheck(readFileSync(resolve(dir, f), "utf8"));
    assert.ok(ok, `${f}: ${err}`);
  }
});

console.log(failed ? `${failed} failed` : "all passed");
process.exit(failed ? 1 : 0);
