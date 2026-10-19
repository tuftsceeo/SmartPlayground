// Run: node --test tests/js/*.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { hexToBytes, bytesToHex, encodePayload, decodePayload, describePayload } from "../../js/radio.js";

test("hex round trip", () => {
  const b = new Uint8Array([0, 1, 0xab, 0xff]);
  assert.equal(bytesToHex(b), "0001abff");
  assert.deepEqual(hexToBytes("0001abff"), b);
  assert.throws(() => hexToBytes("abc"));
  assert.throws(() => hexToBytes("zz"));
});

test("dicts encode as JSON and decode back", () => {
  const p = encodePayload({ type: "goal", team: "blue" });
  assert.deepEqual(decodePayload(p).json, { type: "goal", team: "blue" });
  assert.equal(describePayload(p), '{"type":"goal","team":"blue"}');
});

test("raw text and binary payloads", () => {
  assert.deepEqual(decodePayload(encodePayload("FD_GO")), { text: "FD_GO", json: undefined });
  const bin = new Uint8Array([0xff, 0xfe]);
  assert.equal(decodePayload(bin).text, null);
  assert.equal(describePayload(bin), "0xfffe");
});
