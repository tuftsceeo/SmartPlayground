/**
 * distribute_test.mjs — DistributeState and labels for the Dial
 * "Distribute code" overlay. Run from ChatBroadcast/:
 *   node tools/distribute_test.mjs
 */
import assert from "node:assert/strict";
import { DistributeState, deviceLabel, signalLevel, deviceNoun, slotsText } from "../js/distribute.js";

let failed = 0;
function t(name, fn) {
  try { fn(); console.log(`ok   ${name}`); }
  catch (e) { failed++; console.log(`FAIL ${name}\n  ${e.message}`); }
}

const A = "AA:BB:CC:DD:00:01", B = "AA:BB:CC:DD:00:02", C = "AA:BB:CC:DD:00:03";

t("labels by kind", () => {
  assert.equal(deviceLabel(A, "wand"), "W-0001");
  assert.equal(deviceLabel(B, "icon_display"), "D-0002");
  assert.equal(deviceLabel(C, null), "?-0003");
});
t("signal thresholds", () => {
  assert.deepEqual([null, -50, -60, -75, -90].map(signalLevel), [-1, 3, 2, 1, 0]);
});
t("scan upserts and selects new rows", () => {
  const s = new DistributeState();
  s.startScan();
  s.upsertReport({ mac: A, kind: "wand", battery: 80, rssi: -50 });
  s.upsertReport({ mac: A.toLowerCase(), kind: "wand", battery: 79, rssi: -52 });
  s.upsertReport({ mac: B, kind: "icon_display", battery: null, rssi: -70 });
  assert.equal(s.rows.length, 2);
  assert.equal(s.rows[0].battery, 79);
  assert.deepEqual(s.selectedMacs(), [A, B]);
  s.endScan();
  assert.equal(s.scanning, false);
});
t("selection, distribute and progress", () => {
  const s = new DistributeState();
  s.startScan();
  for (const m of [A, B, C]) s.upsertReport({ mac: m, kind: "wand" });
  s.toggle(B, false);
  const macs = s.startDistribute();
  assert.deepEqual(macs, [A, C]);
  assert.equal(s.rows[1].status, "");
  s.toggle(A, false);                       // locked while running
  assert.equal(s.rows[0].selected, true);
  s.applyProgress({ mac: A, ok: null, done: 0, total: 2, why: "pushed" });
  assert.equal(s.rows[0].status, "pulling");
  s.applyProgress({ mac: A, ok: true, done: 1, total: 2 });
  s.applyProgress({ mac: C, ok: false, done: 2, total: 2, why: "timeout" });
  assert.deepEqual(s.rows.map((r) => [r.status, r.why]),
    [["done", null], ["", null], ["failed", "timeout"]]);
  s.finish({ done: 2, total: 2, ok: 1 });
  assert.equal(s.running, false);
  assert.equal(s.done, 2);
});
t("abort fails unfinished rows only", () => {
  const s = new DistributeState();
  s.startScan();
  for (const m of [A, B]) s.upsertReport({ mac: m, kind: "wand" });
  s.startDistribute();
  s.applyProgress({ mac: A, ok: true, done: 1, total: 2 });
  s.abort("not_serving");
  assert.deepEqual(s.rows.map((r) => r.status), ["done", "failed"]);
  assert.equal(s.rows[1].why, "not_serving");
});
t("every reported device starts selected", () => {
  const s = new DistributeState();
  s.startScan();
  s.upsertReport({ mac: A, kind: "wand", battery: 5 });
  s.upsertReport({ mac: B, kind: "wand", battery: 80 });
  s.upsertReport({ mac: C, kind: "icon_display", battery: null });
  assert.deepEqual(s.selectedMacs(), [A, B, C]);
});
t("deviceNoun: wands, stations, else devices", () => {
  assert.equal(deviceNoun([]), "devices");
  assert.equal(deviceNoun([{ kind: "wand" }, { kind: "wand" }]), "wands");
  assert.equal(deviceNoun([{ kind: "icon_display" }]), "stations");
  assert.equal(deviceNoun([{ kind: "wand" }, { kind: "icon_display" }]), "devices");
  assert.equal(deviceNoun([{ kind: null }]), "devices");
});
t("allFinished once every sent row is done or failed", () => {
  const s = new DistributeState();
  s.startScan();
  for (const m of [A, B]) s.upsertReport({ mac: m, kind: "wand", battery: 80 });
  assert.equal(s.allFinished(), false);
  s.startDistribute();
  s.applyProgress({ mac: A, ok: true, done: 1, total: 2 });
  assert.equal(s.allFinished(), false);
  s.applyProgress({ mac: B, ok: false, why: "x", done: 2, total: 2 });
  s.finish({ done: 2 });
  assert.equal(s.allFinished(), true);
});

t("slots: role and g kept from status_report", () => {
  const s = new DistributeState();
  s.upsertReport({ mac: A, kind: "wand", role: "splat_host", g: [["hostgame", "h"]] });
  s.upsertReport({ mac: A, kind: "wand", battery: 50 });       // older report shape
  assert.equal(s.rows[0].role, "splat_host");
  assert.deepEqual(s.rows[0].games, [["hostgame", "h"]]);
});
t("slots: replace needed only for full selected devices lacking the game", () => {
  const s = new DistributeState();
  s.upsertReport({ mac: A, kind: "wand", g: [["a", "o"], ["b", "s"], ["c", "h"]] });
  s.upsertReport({ mac: B, kind: "wand", g: [["b", "s"], ["d", "o"], ["e", "o"]] });
  s.upsertReport({ mac: C, kind: "wand", g: [["new", "o"], ["b", "s"], ["c", "h"]] });
  assert.deepEqual(s.fullRows("new").map((r) => r.mac), [A, B]);
  const opts = s.replaceOptions("new");
  assert.equal(opts[0].slug, "b");            // held by both full devices
  assert.equal(opts[0].n, 2);
  assert.deepEqual(opts.map((o) => o.slug), ["b", "a", "c", "d", "e"]);
  s.toggle(A, false); s.toggle(B, false);
  assert.deepEqual(s.replaceOptions("new"), []);
});
t("slots: no g (old firmware) or not full never asks", () => {
  const s = new DistributeState();
  s.upsertReport({ mac: A, kind: "wand" });
  s.upsertReport({ mac: B, kind: "icon_display", g: [["a", "o"]] });
  assert.deepEqual(s.replaceOptions("new"), []);
});
t("slots: card text", () => {
  assert.equal(slotsText(null, "x"), "");
  assert.equal(slotsText([], "x"), "Games 0 of 3");
  assert.equal(slotsText([["a", "h"], ["x", "o"], ["b", "x"]], "x"),
    "Games 3 of 3: a (host game), x ✓, b (won't load)");
});

if (failed) { console.log(`\n${failed} failed`); process.exit(1); }
console.log("\nall passed");
