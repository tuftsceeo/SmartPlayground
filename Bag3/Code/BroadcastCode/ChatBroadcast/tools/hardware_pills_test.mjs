/**
 * hardware_pills_test.mjs — requirementPills rules. Run from ChatBroadcast/:
 *   node tools/hardware_pills_test.mjs
 */
import assert from "node:assert/strict";
import { buildHardwareReqs, requirementPills } from "../js/hardware.js";

let failed = 0;
function t(name, fn) {
  try { fn(); console.log(`ok   ${name}`); }
  catch (e) { failed++; console.log(`FAIL ${name}\n  ${e.message}`); }
}
const labels = (r) => requirementPills(r).map((p) => p.label);

t("one wand, no extras: no pills", () => {
  assert.deepEqual(labels(buildHardwareReqs({ code: "", gameName: "Red Flash" })), []);
});
t("wand pill only at 2 or more", () => {
  assert.deepEqual(labels(buildHardwareReqs({ gameName: "x", minWands: 1 })), []);
  assert.deepEqual(labels(buildHardwareReqs({ gameName: "x", minWands: 3 })), ["3 wands"]);
});
t("NFC count leaves out getcode:<slug> and <slug>", () => {
  const code = 'COMMANDS = {"red", "blue"}\n';
  assert.deepEqual(labels(buildHardwareReqs({ code, gameName: "Red Flash" })), ["2 NFC tags"]);
});
t("display and Splat pills at 1 or more", () => {
  const r = buildHardwareReqs({ gameName: "x", displays: 1, splats: 2 });
  assert.deepEqual(labels(r), ["1 icon display", "2 Splats"]);
  assert.deepEqual(labels(buildHardwareReqs({ gameName: "x", displays: 0, splats: 0 })), []);
});

if (failed) { console.log(`\n${failed} failed`); process.exit(1); }
console.log("\nall passed");
