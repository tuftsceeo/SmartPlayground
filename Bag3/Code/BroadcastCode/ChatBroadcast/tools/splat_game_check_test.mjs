/**
 * splat_game_check_test.mjs — send-time checks for wand Splat games
 * (js/splat/splatGameCheck.js, wired into upload.js validateGameCode).
 * Also runs every example in knowledge/party_games.md and the MockWand
 * party games through the full wand check.
 *
 * Usage, from ChatBroadcast/: node tools/splat_game_check_test.mjs
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { splatGameProblems, MAX_SPLATS } from "../js/splat/splatGameCheck.js";
import { validateGameCode } from "../js/upload.js";
import { signatureFor } from "../js/roles.js";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const SIG = "def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):\n";
const SIG7 = "def play(nfc, leds, buz, accel, i2c, enow, batt=None):\n";

let failed = 0;
function t(name, fn) {
  try { fn(); console.log(`ok   ${name}`); }
  catch (e) { failed++; console.log(`FAIL ${name}\n  ${e.message}`); }
}
const probs = code => splatGameProblems(code);
const one = (code, re) => {
  const p = probs(code);
  assert.equal(p.length, 1, p.join(" | "));
  assert.match(p[0], re);
};

t("MAX_SPLATS matches MockWand/lib/pairing.py", () => {
  const src = readFileSync(resolve(ROOT, "../MockWand/lib/pairing.py"), "utf8");
  assert.equal(Number(src.match(/^MAX_SPLATS\s*=\s*(\d+)/m)[1]), MAX_SPLATS);
});

t("wand signature shows net=None and it is optional", () => {
  assert.equal(signatureFor("wand"), "def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None)");
  assert.ok(validateGameCode(SIG7 + "    pass\n", "wand")[0]);
  assert.ok(validateGameCode("def play(nfc, leds, buz, accel, i2c, enow):\n    pass\n", "wand")[0]);
});

t("ordinary game: no problems", () => assert.deepEqual(probs(SIG7 + "    network = 1\n    # net.poll()\n    print('net')\n"), []));
t("SPLATS_LOCAL is refused", () => one("SPLATS_LOCAL = 1\n" + SIG + "    net.splat(0).off()\n", /no solo Splat games/));
t("enow.poll() in a Splat game is refused", () => one("SPLATS_MIN = 1\n" + SIG + "    t, d, m = enow.poll()\n", /enow.poll/));
t("enow.poll() in an ordinary game is fine", () => assert.deepEqual(probs(SIG7 + "    t, d, m = enow.poll()\n"), []));
t("party game: no problems", () => assert.deepEqual(probs("SPLATS_MIN = 2\nSPLATS_MAX = 4\n" + SIG + "    net.send(None, {})\n"), []));
t("SPLATS_MAX = None is allowed", () => assert.deepEqual(probs("SPLATS_MIN = 1\nSPLATS_MAX = None\n" + SIG), []));

t("net used without the parameter", () => one(SIG7 + "    ev = net.poll()\n", /uses `net`/));
t("net aliased without the parameter", () => one(SIG7 + "    n = net\n", /uses `net`/));
t("SPLATS_MIN without net", () => one("SPLATS_MIN = 2\n" + SIG7, /needs `net=None`/));
t("SPLATS_MIN = 0", () => one("SPLATS_MIN = 0\n" + SIG, /SPLATS_MIN must/));
t("SPLATS_MIN = '2'", () => one("SPLATS_MIN = '2'\n" + SIG, /SPLATS_MIN must/));
t("SPLATS_MAX below SPLATS_MIN", () => one("SPLATS_MIN = 3\nSPLATS_MAX = 2\n" + SIG, /smaller/));
t("SPLATS_MAX not a number", () => one("SPLATS_MIN = 2\nSPLATS_MAX = 2.5\n" + SIG, /SPLATS_MAX must/));
t("SPLATS_MAX without SPLATS_MIN", () => one("SPLATS_MAX = 2\n" + SIG, /without SPLATS_MIN/));
t("a comment after the value is ignored", () => assert.deepEqual(probs("SPLATS_MIN = 2   # two pads\n" + SIG), []));

t("validateGameCode refuses a bad Splat game and a bad action name", () => {
  assert.equal(validateGameCode("SPLATS_MIN = 1\n" + SIG7, "wand")[0], false);
  const [ok, err] = validateGameCode("SPLATS_MIN = 1\n" + SIG + "    s = net.splat(0)\n    s.color('turnpurpel')\n", "wand");
  assert.equal(ok, false);
  assert.match(err, /turnpurpel/);
});

t("knowledge/party_games.md examples pass the wand checks", () => {
  const md = readFileSync(resolve(ROOT, "knowledge/party_games.md"), "utf8");
  const games = [...md.matchAll(/```python\n([\s\S]*?)```/g)].map(m => m[1]).filter(c => /^SPLATS_/m.test(c));
  assert.equal(games.length, 2);
  for (const g of games) {
    const [ok, err] = validateGameCode(g, "wand");
    assert.ok(ok, err);
  }
});

t("MockWand party games pass the wand checks", () => {
  for (const f of ["partytest.py", "splattag.py", "relaycolor.py"]) {
    const [ok, err] = validateGameCode(readFileSync(resolve(ROOT, "../MockWand/games", f), "utf8"), "wand");
    assert.ok(ok, `${f}: ${err}`);
  }
});

console.log(failed ? `${failed} failed` : "all passed");
process.exit(failed ? 1 : 0);
