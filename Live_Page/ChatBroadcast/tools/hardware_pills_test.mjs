/**
 * hardware_pills_test.mjs — requirementPills and deviceNeeds rules. Run from ChatBroadcast/:
 *   node tools/hardware_pills_test.mjs
 */
import assert from "node:assert/strict";
import { buildHardwareReqs, requirementPills, deviceNeeds, deviceLine } from "../js/hardware.js";

let failed = 0;
function t(name, fn) {
  try { fn(); console.log(`ok   ${name}`); }
  catch (e) { failed++; console.log(`FAIL ${name}\n  ${e.message}`); }
}
const labels = (r) => requirementPills(r).map((p) => p.label);

t("one wand, no extras: a Wand pill", () => {
  assert.deepEqual(labels(buildHardwareReqs({ code: "", gameName: "Red Flash" })), ["Wand"]);
});
t("two or more wands are counted; a lobby game says Wands", () => {
  assert.deepEqual(labels(buildHardwareReqs({ gameName: "x", minWands: 3 })), ["3 wands"]);
  assert.deepEqual(labels(buildHardwareReqs({ gameName: "x", code: "SPLATS_MIN = 1\n" })), ["Wands"]);
});
t("NFC count leaves out getcode:<slug> and <slug>", () => {
  const code = 'COMMANDS = {"red", "blue"}\n';
  assert.deepEqual(labels(buildHardwareReqs({ code, gameName: "Red Flash" })), ["Wand", "2 NFC tags"]);
});
t("one of a device is named, two or more are counted", () => {
  const r = buildHardwareReqs({ gameName: "x", displays: 1, splats: 2, stations: ["NFC Station"] });
  assert.deepEqual(labels(r), ["Wand", "Icon display", "Station", "2 Splats"]);
});
t("deviceLine joins the same words", () => {
  assert.equal(deviceLine(deviceNeeds({ wands: 2, displays: 1, nfcTags: 3 })), "2 wands · icon display · 3 NFC tags");
  assert.equal(deviceLine(deviceNeeds({ open: true })), "Wands");
});

if (failed) { console.log(`\n${failed} failed`); process.exit(1); }
console.log("\nall passed");
