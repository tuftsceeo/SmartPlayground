/**
 * distribute_test.mjs — DistributeState and labels for the Dial
 * "Distribute code" overlay. Run from ChatBroadcast/:
 *   node tools/distribute_test.mjs
 */
import assert from "node:assert/strict";
import { DistributeState, deviceLabel, signalLevel } from "../js/distribute.js";

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

if (failed) { console.log(`\n${failed} failed`); process.exit(1); }
console.log("\nall passed");
