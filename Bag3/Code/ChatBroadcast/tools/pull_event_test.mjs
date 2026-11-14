/**
 * pull_event_test.mjs — text shown for Box/Dial `pull` events. Run from
 * ChatBroadcast/:   node tools/pull_event_test.mjs
 */
import assert from "node:assert/strict";
import { formatPullEvent } from "../js/device/pullEvent.js";

let failed = 0;
function t(name, fn) {
  try { fn(); console.log(`ok   ${name}`); }
  catch (e) { failed++; console.log(`FAIL ${name}\n  ${e.message}`); }
}

const MAC = "AA:BB:CC:DD:EE:FF";

t("ok pull names wand, game and time", () => {
  const r = formatPullEvent({ type: "pull", slug: "tag_game", role: "wand", wand: MAC, ok: true, ms: 840, why: null });
  assert.deepEqual(r, { msg: `Wand ${MAC} got tag_game in 840 ms`, isError: false });
});
t("pretty name replaces slug", () => {
  const r = formatPullEvent({ slug: "tag_game", wand: MAC, ok: true, ms: 5 }, "Tag Game");
  assert.equal(r.msg, `Wand ${MAC} got Tag Game in 5 ms`);
});
t("failed pull is an error and carries why", () => {
  const r = formatPullEvent({ slug: "tag_game", wand: MAC, ok: false, ms: 3000, why: "timeout" });
  assert.deepEqual(r, { msg: `Wand ${MAC} could not get tag_game: timeout`, isError: true });
});
t("null fields degrade", () => {
  assert.equal(formatPullEvent({ ok: false, slug: null, wand: null, ms: null, why: null }).msg,
    "A wand could not get a game");
  assert.equal(formatPullEvent({ ok: true, slug: "x", wand: null, ms: null }).msg, "A wand got x");
});

if (failed) { console.log(`${failed} failed`); process.exit(1); }
