/**
 * nfc_station_link_test.mjs — catalog index builder and catalog.set reply
 * parsing for the NFC Station link. Run from ChatBroadcast/:
 *   node tools/nfc_station_link_test.mjs
 */

import assert from "node:assert/strict";
import {
  buildCatalogIndex, buildCatalogSetCommand, parseCatalogReply, NfcStationLink,
} from "../js/device/nfcStationLink.js";

let failed = 0;
async function t(name, fn) {
  try { await fn(); console.log(`ok   ${name}`); }
  catch (e) { failed++; console.log(`FAIL ${name}\n  ${e.message}`); }
}

const cooking = {
  name: "Cooking Time",
  code: 'COMMANDS = {"tomato", "milk"}\n',
  requiredTags: [],
};

await t("index keyed by slug with name and baseline + code tags", () => {
  const idx = buildCatalogIndex([cooking]);
  assert.deepEqual(Object.keys(idx), ["cooking_time"]);
  assert.equal(idx.cooking_time.name, "Cooking Time");
  assert.deepEqual(idx.cooking_time.tags,
    ["getcode:cooking_time", "cooking_time", "tomato", "milk"]);
});

await t("declared tags used when code names no COMMANDS", () => {
  const idx = buildCatalogIndex([{ name: "Hop", code: "pass\n", requiredTags: ["frog"] }]);
  assert.ok(idx.hop.tags.includes("frog"));
});

await t("first (newest) entry wins a slug; blanks skipped", () => {
  const idx = buildCatalogIndex([
    { name: "Hop", code: "", requiredTags: ["new"] },
    { name: "hop", code: "", requiredTags: ["old"] },
    null, { name: "" },
  ]);
  assert.deepEqual(Object.keys(idx), ["hop"]);
  assert.ok(idx.hop.tags.includes("new") && !idx.hop.tags.includes("old"));
});

await t("command shape", () => {
  assert.deepEqual(buildCatalogSetCommand([]), { cmd: "catalog.set", index: {} });
});

await t("reply parsing", () => {
  assert.deepEqual(parseCatalogReply({ type: "ok", id: 1, cmd: "catalog.set", groups: 3 }),
    { ok: true, groups: 3 });
  assert.deepEqual(parseCatalogReply({ type: "error", code: "cmd_failed", cmd: "catalog.set",
    id: 1, msg: "ValueError: bad" }), { ok: false, code: "cmd_failed", msg: "ValueError: bad" });
  assert.equal(parseCatalogReply({ type: "ok", cmd: "home" }).ok, false);
});

function fakeAdapter() {
  const a = { onData: null, written: [], clearBacklog() {},
    async writeChunked(text) { a.written.push(JSON.parse(text)); } };
  return a;
}

await t("pushCatalog resolves ok and cmd_failed; forwards card events", async () => {
  const ad = fakeAdapter();
  const link = new NfcStationLink(ad);
  link.start();
  const events = [];
  link.onCardEvent((e) => events.push(e.type));

  let p = link.pushCatalog([cooking]);
  await Promise.resolve();
  const sent = ad.written[0];
  assert.equal(sent.cmd, "catalog.set");
  assert.ok(sent.index.cooking_time);
  ad.onData(JSON.stringify({ type: "ok", id: sent.id, cmd: "catalog.set", groups: 1 }) + "\n");
  assert.deepEqual(await p, { ok: true, groups: 1 });

  p = link.pushCatalog([]);
  await Promise.resolve();
  const id2 = ad.written[1].id;
  ad.onData(JSON.stringify({ type: "error", code: "cmd_failed", cmd: "catalog.set",
    id: id2, msg: "ValueError: x" }) + "\n");
  assert.deepEqual(await p, { ok: false, code: "cmd_failed", msg: "ValueError: x" });

  for (const type of ["card_read", "card_written", "write_failed", "heartbeat"]) {
    ad.onData(JSON.stringify({ type, uid: "01", text: "go" }) + "\n");
  }
  assert.deepEqual(events, ["card_read", "card_written", "write_failed"]);
  link.stop();
});

if (failed) { console.log(`${failed} failed`); process.exit(1); }
console.log("all passed");
